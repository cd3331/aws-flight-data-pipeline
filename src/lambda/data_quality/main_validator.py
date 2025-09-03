"""
Main Data Quality Validation System Lambda Function.

This is the primary Lambda function that orchestrates the complete data quality
validation process including scoring, anomaly detection, metrics publishing,
and quarantine management.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import json
import os
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from quality_validator import (
    DataQualityValidator, QualityConfig, QualityScore, QualityIssue, SeverityLevel
)
from anomaly_detector import AnomalyDetector, AnomalyConfig, Anomaly, AnomalyType
from metrics_publisher import DataQualityMetricsPublisher, MetricPublishConfig
from quarantine_system import (
    DataQuarantineSystem, QuarantineConfig, QuarantineReason, QuarantineStatus
)
from config import DataQualityConfiguration
from alerting import DataQualityAlerting

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


class DataQualityOrchestrator:
    """Main orchestrator for data quality validation pipeline."""
    
    def __init__(self, environment: str = None):
        """Initialize the data quality orchestrator."""
        self.environment = environment or os.environ.get('ENVIRONMENT', 'dev')
        
        # Load centralized configuration
        self.config = DataQualityConfiguration(self.environment)
        
        # Validate configuration
        config_issues = self.config.validate_configuration()
        if config_issues:
            logger.warning(f"Configuration validation issues: {config_issues}")
        
        # Initialize components with centralized config
        self.validator = DataQualityValidator(
            self._convert_to_quality_config(self.config.quality_thresholds), 
            self.environment
        )
        self.anomaly_detector = AnomalyDetector(
            self._convert_to_anomaly_config(self.config.anomaly_thresholds)
        )
        self.metrics_publisher = DataQualityMetricsPublisher(
            self.config.metrics_config, 
            self.environment
        )
        self.quarantine_system = DataQuarantineSystem(
            self._convert_to_quarantine_config(self.config.quarantine_config), 
            self.environment
        )
        self.alerting_system = DataQualityAlerting(self.config)
        
        # S3 client for data operations
        self.s3 = boto3.client('s3')
        
        # Processing statistics
        self.processing_stats = {
            'records_processed': 0,
            'records_quarantined': 0,
            'quality_issues_found': 0,
            'anomalies_detected': 0,
            'average_quality_score': 0.0,
            'processing_start_time': datetime.now(timezone.utc),
            'batch_id': None
        }
        
        logger.info(f"DataQualityOrchestrator initialized for environment: {self.environment}")
    
    def process_records(self, records: List[Dict[str, Any]], 
                       batch_id: str = None,
                       historical_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a batch of records through the complete quality validation pipeline.
        
        Args:
            records: List of flight data records to validate
            batch_id: Batch identifier for tracking
            historical_data: Historical records for statistical analysis
            
        Returns:
            Processing results summary
        """
        start_time = datetime.now(timezone.utc)
        self.processing_stats['batch_id'] = batch_id or f"batch_{int(start_time.timestamp())}"
        
        logger.info(f"Processing batch {self.processing_stats['batch_id']} with {len(records)} records")
        
        try:
            # Results containers
            quality_scores = []
            quarantine_requests = []
            all_anomalies = []
            previous_records = {}  # For consistency checking
            
            # Process each record
            for i, record in enumerate(records):
                try:
                    # Get aircraft ID for tracking
                    icao24 = record.get('icao24', f'unknown_{i}')
                    previous_record = previous_records.get(icao24)
                    
                    # 1. Quality validation
                    quality_score = self.validator.validate_record(record, previous_record)
                    quality_scores.append(quality_score)
                    
                    # 2. Anomaly detection
                    anomalies = self.anomaly_detector.detect_anomalies(record, historical_data)
                    all_anomalies.extend(anomalies)
                    
                    # 3. Evaluate for quarantine
                    should_quarantine, quarantine_reasons = self.quarantine_system.evaluate_for_quarantine(
                        record, quality_score, anomalies, self.processing_stats['batch_id']
                    )
                    
                    if should_quarantine:
                        quarantine_requests.append((record, quality_score, quarantine_reasons, anomalies))
                    
                    # 4. Publish individual record metrics
                    record_metadata = {
                        'icao24': icao24,
                        'data_source': 'opensky_network',
                        'batch_id': self.processing_stats['batch_id']
                    }
                    
                    self.metrics_publisher.publish_quality_score(quality_score, record_metadata)
                    
                    # Publish anomaly metrics
                    if anomalies:
                        for anomaly in anomalies:
                            self.metrics_publisher.publish_anomaly_metrics(
                                anomaly_type=anomaly.anomaly_type.value,
                                severity=anomaly.severity.value,
                                count=1,
                                details=anomaly.metadata
                            )
                    
                    # Update previous records for consistency checking
                    previous_records[icao24] = record
                    
                    # Update processing statistics
                    self.processing_stats['records_processed'] += 1
                    self.processing_stats['quality_issues_found'] += len(quality_score.issues_found)
                    self.processing_stats['anomalies_detected'] += len(anomalies)
                    
                except Exception as e:
                    logger.error(f"Error processing record {i}: {str(e)}")
                    # Continue processing other records
                    continue
            
            # 5. Batch quarantine if needed
            if quarantine_requests:
                quarantine_records = self.quarantine_system.batch_quarantine(
                    quarantine_requests, self.processing_stats['batch_id']
                )
                self.processing_stats['records_quarantined'] = len(quarantine_records)
            
            # 6. Calculate batch-level metrics
            processing_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            if quality_scores:
                avg_quality = sum(score.overall_score for score in quality_scores) / len(quality_scores)
                self.processing_stats['average_quality_score'] = avg_quality
            
            # 7. Publish batch summary metrics
            batch_metadata = {
                'batch_id': self.processing_stats['batch_id'],
                'environment': self.environment,
                'data_source': 'opensky_network'
            }
            
            self.metrics_publisher.publish_batch_summary(
                batch_size=len(records),
                processing_duration_ms=processing_duration_ms,
                batch_metadata=batch_metadata
            )
            
            # 8. Publish system health metrics
            health_status = self._calculate_system_health(quality_scores, all_anomalies)
            self.metrics_publisher.publish_system_health_metrics(health_status)
            
            # 9. Prepare results summary (needed for alerting)
            results = self._prepare_results_summary(quality_scores, all_anomalies, processing_duration_ms)
            
            # 10. Evaluate and send alerts based on batch results
            alerts = self.alerting_system.evaluate_quality_metrics(results)
            if alerts:
                self.alerting_system.send_alerts(alerts)
                logger.info(f"Sent {len(alerts)} data quality alerts")
            
            # Check system health alerts
            health_alert = self.alerting_system.create_system_health_alert(health_status)
            if health_alert:
                self.alerting_system.send_alerts([health_alert])
                logger.info("Sent system health alert")
            
            # 11. Flush all metrics
            self.metrics_publisher.flush_metrics()
            
            logger.info(f"Batch processing completed: {results['summary']}")
            return results
            
        except Exception as e:
            logger.error(f"Error in batch processing: {str(e)}")
            raise
    
    def _convert_to_quality_config(self, thresholds) -> QualityConfig:
        """Convert centralized quality thresholds to QualityConfig."""
        config = QualityConfig()
        
        # Set thresholds from centralized config
        config.excellent_quality_threshold = thresholds.excellent_threshold
        config.good_quality_threshold = thresholds.good_threshold
        config.acceptable_quality_threshold = thresholds.acceptable_threshold
        config.quarantine_threshold = thresholds.auto_quarantine_threshold
        
        return config
    
    def _convert_to_anomaly_config(self, thresholds) -> AnomalyConfig:
        """Convert centralized anomaly thresholds to AnomalyConfig."""
        config = AnomalyConfig()
        
        # Set thresholds from centralized config
        config.max_altitude_feet = thresholds.max_altitude_feet
        config.min_altitude_feet = thresholds.min_altitude_feet
        config.max_velocity_knots = thresholds.max_groundspeed_knots
        config.min_velocity_knots = thresholds.min_groundspeed_knots
        config.z_score_threshold = thresholds.z_score_threshold
        config.teleportation_threshold = thresholds.max_position_jump_km
        config.stuck_time_threshold = thresholds.stuck_time_window_minutes
        
        return config
    
    def _convert_to_quarantine_config(self, quarantine_config) -> QuarantineConfig:
        """Convert centralized quarantine config to QuarantineConfig."""
        config = QuarantineConfig()
        
        # Set configuration from centralized config
        config.quarantine_bucket = quarantine_config.quarantine_bucket
        config.quarantine_table_name = quarantine_config.quarantine_table
        config.auto_quarantine_threshold = self.config.quality_thresholds.auto_quarantine_threshold
        config.notification_topic_arn = self.config.alert_config.sns_topic_arn
        config.enable_quarantine_notifications = True
        
        return config
    
    def _calculate_system_health(self, quality_scores: List[QualityScore], 
                                anomalies: List[Anomaly]) -> Dict[str, Any]:
        """Calculate overall system health metrics."""
        if not quality_scores:
            return {}
        
        avg_quality = sum(score.overall_score for score in quality_scores) / len(quality_scores)
        quarantined_count = sum(1 for score in quality_scores if score.should_quarantine)
        critical_anomalies = sum(1 for anomaly in anomalies if anomaly.severity == SeverityLevel.CRITICAL)
        
        # Calculate health metrics
        quarantine_rate = (quarantined_count / len(quality_scores)) * 100
        critical_anomaly_rate = (critical_anomalies / len(quality_scores)) * 100 if quality_scores else 0
        
        # Overall availability (inverse of quarantine rate)
        availability = max(0, 100 - quarantine_rate)
        
        return {
            'data_freshness_seconds': 60,  # Assuming 1-minute freshness for real-time data
            'processing_lag_seconds': 0,   # No lag in current processing
            'error_rate': quarantine_rate,
            'availability_percentage': availability,
            'average_quality_score': avg_quality,
            'critical_anomaly_rate': critical_anomaly_rate
        }
    
    def _prepare_results_summary(self, quality_scores: List[QualityScore],
                               anomalies: List[Anomaly], processing_duration_ms: int) -> Dict[str, Any]:
        """Prepare comprehensive results summary."""
        if not quality_scores:
            return {
                'summary': 'No records processed',
                'processing_stats': self.processing_stats,
                'processing_duration_ms': processing_duration_ms
            }
        
        # Quality distribution
        grade_distribution = {}
        for score in quality_scores:
            grade = score.grade
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        
        # Issue analysis
        issue_types = {}
        severity_distribution = {}
        for score in quality_scores:
            for issue in score.issues_found:
                issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
                severity = issue.severity.value
                severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
        
        # Anomaly analysis
        anomaly_types = {}
        anomaly_severity = {}
        for anomaly in anomalies:
            atype = anomaly.anomaly_type.value
            anomaly_types[atype] = anomaly_types.get(atype, 0) + 1
            severity = anomaly.severity.value
            anomaly_severity[severity] = anomaly_severity.get(severity, 0) + 1
        
        # Calculate alerting metrics
        quarantine_rate = (self.processing_stats['records_quarantined'] / len(quality_scores)) if quality_scores else 0
        anomaly_rate = (len(anomalies) / len(quality_scores)) if quality_scores else 0
        error_rate = 0  # Could be enhanced to track actual processing errors
        
        return {
            'summary': f"Processed {len(quality_scores)} records, avg quality: {self.processing_stats['average_quality_score']:.3f}, quarantined: {self.processing_stats['records_quarantined']}",
            'processing_stats': self.processing_stats,
            'processing_duration_ms': processing_duration_ms,
            'batch_id': self.processing_stats['batch_id'],
            'total_records': len(quality_scores),
            
            # Alerting metrics
            'average_quality_score': self.processing_stats['average_quality_score'],
            'quarantine_rate': quarantine_rate,
            'anomaly_rate': anomaly_rate,
            'error_rate': error_rate,
            
            'quality_analysis': {
                'average_score': self.processing_stats['average_quality_score'],
                'grade_distribution': grade_distribution,
                'total_issues': self.processing_stats['quality_issues_found'],
                'issue_types': issue_types,
                'severity_distribution': severity_distribution
            },
            'anomaly_analysis': {
                'total_anomalies': len(anomalies),
                'anomaly_types': anomaly_types,
                'severity_distribution': anomaly_severity
            },
            'quarantine_summary': {
                'total_quarantined': self.processing_stats['records_quarantined'],
                'quarantine_rate': quarantine_rate * 100
            }
        }


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda handler for data quality validation.
    
    Expected event format:
    {
        "records": [...],           # Flight data records to validate
        "batch_id": "...",         # Optional batch identifier
        "historical_data": [...]   # Optional historical data for statistical analysis
    }
    """
    try:
        logger.info(f"Data Quality Validation Lambda triggered with {len(event.get('Records', []))} S3 events")
        
        # Initialize orchestrator
        orchestrator = DataQualityOrchestrator()
        
        # Handle S3 event trigger
        if 'Records' in event:
            # Process S3 events (typical trigger)
            records_to_process = []
            batch_id = f"s3_batch_{int(datetime.now(timezone.utc).timestamp())}"
            
            for s3_record in event['Records']:
                if s3_record['eventSource'] == 'aws:s3':
                    bucket = s3_record['s3']['bucket']['name']
                    key = s3_record['s3']['object']['key']
                    
                    # Download and parse S3 object
                    try:
                        response = orchestrator.s3.get_object(Bucket=bucket, Key=key)
                        data = json.loads(response['Body'].read().decode('utf-8'))
                        
                        # Extract flight data records
                        if 'states' in data and data['states']:
                            # OpenSky API format
                            timestamp = data.get('time', datetime.now(timezone.utc).timestamp())
                            for state in data['states']:
                                if len(state) >= 16:  # Valid OpenSky state vector
                                    record = {
                                        'icao24': state[0],
                                        'callsign': state[1],
                                        'origin_country': state[2],
                                        'time_position': state[3],
                                        'last_contact': state[4],
                                        'longitude': state[5],
                                        'latitude': state[6],
                                        'baro_altitude': state[7],
                                        'on_ground': state[8],
                                        'velocity': state[9],
                                        'true_track': state[10],
                                        'vertical_rate': state[11],
                                        'sensors': state[12],
                                        'geo_altitude': state[13],
                                        'squawk': state[14],
                                        'spi': state[15],
                                        'position_source': state[16] if len(state) > 16 else None
                                    }
                                    records_to_process.append(record)
                        else:
                            # Direct record format
                            records_to_process.append(data)
                            
                    except Exception as e:
                        logger.error(f"Failed to process S3 object {bucket}/{key}: {str(e)}")
                        continue
            
            # Process the records
            if records_to_process:
                results = orchestrator.process_records(records_to_process, batch_id)
            else:
                results = {'summary': 'No valid records found in S3 events'}
        
        # Handle direct invocation
        elif 'records' in event:
            records = event['records']
            batch_id = event.get('batch_id')
            historical_data = event.get('historical_data')
            
            results = orchestrator.process_records(records, batch_id, historical_data)
        
        else:
            results = {'error': 'Invalid event format - expected S3 Records or direct records'}
        
        logger.info(f"Lambda execution completed: {results.get('summary', 'Unknown result')}")
        return results
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'summary': 'Lambda execution failed'
        }


# For testing purposes
if __name__ == "__main__":
    # Example usage for testing
    test_records = [
        {
            'icao24': 'abc123',
            'callsign': 'TEST123',
            'origin_country': 'United States',
            'time_position': datetime.now(timezone.utc).timestamp(),
            'last_contact': datetime.now(timezone.utc).timestamp(),
            'longitude': -122.4194,
            'latitude': 37.7749,
            'baro_altitude': 35000,
            'on_ground': False,
            'velocity': 450,
            'true_track': 90,
            'vertical_rate': 0,
            'sensors': [4],
            'geo_altitude': 35100,
            'squawk': '1200',
            'spi': False,
            'position_source': 0
        }
    ]
    
    orchestrator = DataQualityOrchestrator('dev')
    results = orchestrator.process_records(test_records)
    print(json.dumps(results, indent=2))