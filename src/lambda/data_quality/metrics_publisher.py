"""
CloudWatch Metrics Publisher for Data Quality System.

This module handles publishing comprehensive quality metrics to CloudWatch
for monitoring, alerting, and dashboard visualization.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import boto3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from quality_validator import QualityScore, SeverityLevel, QualityDimension

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@dataclass
class MetricPublishConfig:
    """Configuration for CloudWatch metrics publishing."""
    
    namespace: str = "FlightDataPipeline"
    environment_dimension: str = "Environment" 
    pipeline_dimension: str = "PipelineStage"
    
    # Batch publishing configuration
    max_metrics_per_batch: int = 20
    publish_interval_seconds: int = 60
    
    # Custom dimensions
    include_aircraft_type_dimension: bool = True
    include_data_source_dimension: bool = True
    include_geographic_dimension: bool = False
    
    # Metric resolution (1, 5, 10, 30, 60 seconds)
    metric_resolution: int = 60
    
    def __post_init__(self):
        """Validate configuration."""
        if self.max_metrics_per_batch > 20:
            raise ValueError("CloudWatch allows maximum 20 metrics per PutMetricData call")


class DataQualityMetricsPublisher:
    """Publishes data quality metrics to CloudWatch."""
    
    def __init__(self, config: MetricPublishConfig, environment: str = 'dev'):
        """Initialize the metrics publisher."""
        self.config = config
        self.environment = environment
        self.cloudwatch = boto3.client('cloudwatch')
        
        # Metrics buffer for batching
        self.metrics_buffer = []
        self.last_publish_time = datetime.utcnow()
        
        # Aggregation counters for performance
        self.metric_aggregations = {
            'quality_scores': [],
            'completeness_scores': [],
            'validity_scores': [],
            'consistency_scores': [],
            'timeliness_scores': [],
            'quarantine_count': 0,
            'total_records': 0,
            'issues_by_severity': {severity.value: 0 for severity in SeverityLevel},
            'issues_by_type': {},
            'aircraft_processed': set()
        }
        
        logger.info(f"DataQualityMetricsPublisher initialized for environment: {environment}")
    
    def publish_quality_score(self, quality_score: QualityScore, 
                            record_metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Publish quality score metrics to CloudWatch.
        
        Args:
            quality_score: Comprehensive quality assessment
            record_metadata: Additional record metadata for dimensions
        """
        timestamp = datetime.now(timezone.utc)
        base_dimensions = self._get_base_dimensions(record_metadata)
        
        try:
            # 1. Overall Quality Score
            self._add_metric(
                metric_name="OverallQualityScore",
                value=quality_score.overall_score,
                unit="None",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            # 2. Dimensional Quality Scores
            self._add_metric(
                metric_name="CompletenessScore",
                value=quality_score.completeness_score,
                unit="None", 
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            self._add_metric(
                metric_name="ValidityScore",
                value=quality_score.validity_score,
                unit="None",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            self._add_metric(
                metric_name="ConsistencyScore", 
                value=quality_score.consistency_score,
                unit="None",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            self._add_metric(
                metric_name="TimelinessScore",
                value=quality_score.timeliness_score,
                unit="None",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            # 3. Quality Grade Distribution
            self._add_metric(
                metric_name="QualityGradeDistribution",
                value=1,
                unit="Count",
                dimensions=base_dimensions + [
                    {"Name": "QualityGrade", "Value": quality_score.grade}
                ],
                timestamp=timestamp
            )
            
            # 4. Quarantine Status
            if quality_score.should_quarantine:
                self._add_metric(
                    metric_name="QuarantinedRecords",
                    value=1,
                    unit="Count",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            # 5. Issue Metrics
            self._publish_issue_metrics(quality_score.issues_found, base_dimensions, timestamp)
            
            # 6. Update aggregations
            self._update_aggregations(quality_score, record_metadata)
            
            # 7. Publish if buffer is full or time interval reached
            if (len(self.metrics_buffer) >= self.config.max_metrics_per_batch or 
                self._should_publish_now()):
                self.flush_metrics()
                
        except Exception as e:
            logger.error(f"Error publishing quality score metrics: {str(e)}")
            # Don't re-raise to avoid breaking the validation pipeline
    
    def publish_batch_summary(self, batch_size: int, processing_duration_ms: int,
                            batch_metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Publish batch-level summary metrics.
        
        Args:
            batch_size: Number of records in the batch
            processing_duration_ms: Total processing time in milliseconds
            batch_metadata: Additional batch metadata
        """
        timestamp = datetime.now(timezone.utc)
        base_dimensions = self._get_base_dimensions(batch_metadata)
        
        try:
            # Batch processing metrics
            self._add_metric(
                metric_name="BatchSize",
                value=batch_size,
                unit="Count", 
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            self._add_metric(
                metric_name="ProcessingDuration",
                value=processing_duration_ms,
                unit="Milliseconds",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            self._add_metric(
                metric_name="RecordsPerSecond",
                value=batch_size / (processing_duration_ms / 1000) if processing_duration_ms > 0 else 0,
                unit="Count/Second",
                dimensions=base_dimensions,
                timestamp=timestamp
            )
            
            # Quality aggregation metrics
            if self.metric_aggregations['total_records'] > 0:
                avg_quality = sum(self.metric_aggregations['quality_scores']) / len(self.metric_aggregations['quality_scores'])
                
                self._add_metric(
                    metric_name="AverageQualityScore",
                    value=avg_quality,
                    unit="None",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
                
                quarantine_rate = self.metric_aggregations['quarantine_count'] / self.metric_aggregations['total_records']
                self._add_metric(
                    metric_name="QuarantineRate",
                    value=quarantine_rate,
                    unit="Percent",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
                
                # Unique aircraft processed
                self._add_metric(
                    metric_name="UniqueAircraftProcessed",
                    value=len(self.metric_aggregations['aircraft_processed']),
                    unit="Count",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            self.flush_metrics()
            
        except Exception as e:
            logger.error(f"Error publishing batch summary metrics: {str(e)}")
    
    def publish_anomaly_metrics(self, anomaly_type: str, severity: str, 
                              count: int, details: Dict[str, Any] = None) -> None:
        """
        Publish anomaly detection metrics.
        
        Args:
            anomaly_type: Type of anomaly detected
            severity: Severity level of anomalies
            count: Number of anomalies detected
            details: Additional anomaly details
        """
        timestamp = datetime.now(timezone.utc)
        base_dimensions = self._get_base_dimensions(details)
        
        try:
            self._add_metric(
                metric_name="AnomaliesDetected",
                value=count,
                unit="Count",
                dimensions=base_dimensions + [
                    {"Name": "AnomalyType", "Value": anomaly_type},
                    {"Name": "Severity", "Value": severity}
                ],
                timestamp=timestamp
            )
            
            # Specific anomaly metrics
            if anomaly_type == "altitude_anomaly":
                if details and 'altitude_value' in details:
                    self._add_metric(
                        metric_name="AnomalousAltitude",
                        value=details['altitude_value'],
                        unit="None",
                        dimensions=base_dimensions,
                        timestamp=timestamp
                    )
            
            elif anomaly_type == "velocity_anomaly":
                if details and 'velocity_value' in details:
                    self._add_metric(
                        metric_name="AnomalousVelocity",
                        value=details['velocity_value'],
                        unit="None",
                        dimensions=base_dimensions,
                        timestamp=timestamp
                    )
            
            elif anomaly_type == "position_jump":
                if details and 'jump_distance' in details:
                    self._add_metric(
                        metric_name="PositionJumpDistance",
                        value=details['jump_distance'],
                        unit="None",
                        dimensions=base_dimensions,
                        timestamp=timestamp
                    )
            
            if len(self.metrics_buffer) >= self.config.max_metrics_per_batch:
                self.flush_metrics()
                
        except Exception as e:
            logger.error(f"Error publishing anomaly metrics: {str(e)}")
    
    def publish_system_health_metrics(self, health_status: Dict[str, Any]) -> None:
        """
        Publish system health and operational metrics.
        
        Args:
            health_status: System health status dictionary
        """
        timestamp = datetime.now(timezone.utc)
        base_dimensions = self._get_base_dimensions()
        
        try:
            # Data freshness
            if 'data_freshness_seconds' in health_status:
                self._add_metric(
                    metric_name="DataFreshness",
                    value=health_status['data_freshness_seconds'],
                    unit="Seconds",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            # Processing lag
            if 'processing_lag_seconds' in health_status:
                self._add_metric(
                    metric_name="ProcessingLag",
                    value=health_status['processing_lag_seconds'], 
                    unit="Seconds",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            # Error rates
            if 'error_rate' in health_status:
                self._add_metric(
                    metric_name="ErrorRate",
                    value=health_status['error_rate'],
                    unit="Percent",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            # System availability
            if 'availability_percentage' in health_status:
                self._add_metric(
                    metric_name="SystemAvailability",
                    value=health_status['availability_percentage'],
                    unit="Percent",
                    dimensions=base_dimensions,
                    timestamp=timestamp
                )
            
            self.flush_metrics()
            
        except Exception as e:
            logger.error(f"Error publishing system health metrics: {str(e)}")
    
    def flush_metrics(self) -> None:
        """Flush all buffered metrics to CloudWatch."""
        if not self.metrics_buffer:
            return
        
        try:
            # Split metrics into batches if necessary
            for i in range(0, len(self.metrics_buffer), self.config.max_metrics_per_batch):
                batch = self.metrics_buffer[i:i + self.config.max_metrics_per_batch]
                
                response = self.cloudwatch.put_metric_data(
                    Namespace=self.config.namespace,
                    MetricData=batch
                )
                
                logger.debug(f"Published {len(batch)} metrics to CloudWatch")
            
            # Clear buffer and update timestamp
            self.metrics_buffer.clear()
            self.last_publish_time = datetime.utcnow()
            
            # Reset aggregations
            self._reset_aggregations()
            
        except Exception as e:
            logger.error(f"Error flushing metrics to CloudWatch: {str(e)}")
            # Clear buffer to prevent accumulation
            self.metrics_buffer.clear()
    
    def _add_metric(self, metric_name: str, value: float, unit: str,
                   dimensions: List[Dict[str, str]], timestamp: datetime) -> None:
        """Add a metric to the buffer."""
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': timestamp,
            'Dimensions': dimensions
        }
        
        self.metrics_buffer.append(metric_data)
    
    def _get_base_dimensions(self, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Get base dimensions for all metrics."""
        dimensions = [
            {"Name": self.config.environment_dimension, "Value": self.environment},
            {"Name": self.config.pipeline_dimension, "Value": "DataQuality"}
        ]
        
        if metadata:
            # Add aircraft type dimension if available
            if (self.config.include_aircraft_type_dimension and 
                'aircraft_type' in metadata):
                dimensions.append({
                    "Name": "AircraftType", 
                    "Value": metadata['aircraft_type']
                })
            
            # Add data source dimension
            if (self.config.include_data_source_dimension and 
                'data_source' in metadata):
                dimensions.append({
                    "Name": "DataSource",
                    "Value": metadata['data_source']
                })
            
            # Add geographic dimension
            if (self.config.include_geographic_dimension and 
                'region' in metadata):
                dimensions.append({
                    "Name": "GeographicRegion",
                    "Value": metadata['region']
                })
        
        return dimensions
    
    def _publish_issue_metrics(self, issues: List, base_dimensions: List[Dict[str, str]], 
                             timestamp: datetime) -> None:
        """Publish metrics for quality issues."""
        # Count issues by severity
        severity_counts = {}
        dimension_counts = {}
        type_counts = {}
        
        for issue in issues:
            # Count by severity
            severity = issue.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by dimension
            dimension = issue.dimension.value
            dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1
            
            # Count by type
            issue_type = issue.issue_type
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
        
        # Publish severity metrics
        for severity, count in severity_counts.items():
            self._add_metric(
                metric_name="QualityIssuesBySeverity",
                value=count,
                unit="Count",
                dimensions=base_dimensions + [
                    {"Name": "IssueSeverity", "Value": severity}
                ],
                timestamp=timestamp
            )
        
        # Publish dimension metrics
        for dimension, count in dimension_counts.items():
            self._add_metric(
                metric_name="QualityIssuesByDimension",
                value=count,
                unit="Count",
                dimensions=base_dimensions + [
                    {"Name": "QualityDimension", "Value": dimension}
                ],
                timestamp=timestamp
            )
        
        # Publish type metrics (limit to most common types to avoid dimension explosion)
        common_types = ['missing_critical_field', 'invalid_altitude', 'invalid_velocity', 
                       'position_teleportation', 'stale_data']
        
        for issue_type, count in type_counts.items():
            if issue_type in common_types:
                self._add_metric(
                    metric_name="QualityIssuesByType",
                    value=count,
                    unit="Count",
                    dimensions=base_dimensions + [
                        {"Name": "IssueType", "Value": issue_type}
                    ],
                    timestamp=timestamp
                )
    
    def _update_aggregations(self, quality_score, metadata: Optional[Dict[str, Any]]) -> None:
        """Update metric aggregations."""
        self.metric_aggregations['quality_scores'].append(quality_score.overall_score)
        self.metric_aggregations['completeness_scores'].append(quality_score.completeness_score)
        self.metric_aggregations['validity_scores'].append(quality_score.validity_score)
        self.metric_aggregations['consistency_scores'].append(quality_score.consistency_score)
        self.metric_aggregations['timeliness_scores'].append(quality_score.timeliness_score)
        
        if quality_score.should_quarantine:
            self.metric_aggregations['quarantine_count'] += 1
        
        self.metric_aggregations['total_records'] += 1
        
        # Update issue counters
        for issue in quality_score.issues_found:
            severity = issue.severity.value
            issue_type = issue.issue_type
            
            self.metric_aggregations['issues_by_severity'][severity] += 1
            self.metric_aggregations['issues_by_type'][issue_type] = \
                self.metric_aggregations['issues_by_type'].get(issue_type, 0) + 1
        
        # Track aircraft
        if metadata and 'icao24' in metadata:
            self.metric_aggregations['aircraft_processed'].add(metadata['icao24'])
    
    def _should_publish_now(self) -> bool:
        """Determine if metrics should be published now based on time interval."""
        elapsed = (datetime.utcnow() - self.last_publish_time).total_seconds()
        return elapsed >= self.config.publish_interval_seconds
    
    def _reset_aggregations(self) -> None:
        """Reset metric aggregations after publishing."""
        self.metric_aggregations = {
            'quality_scores': [],
            'completeness_scores': [],
            'validity_scores': [],
            'consistency_scores': [],
            'timeliness_scores': [],
            'quarantine_count': 0,
            'total_records': 0,
            'issues_by_severity': {severity.value: 0 for severity in SeverityLevel},
            'issues_by_type': {},
            'aircraft_processed': set()
        }