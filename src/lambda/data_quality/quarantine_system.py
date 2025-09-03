"""
Automated Data Quarantine System for Flight Data Pipeline.

This module provides automated quarantine capabilities for bad data including:
- Automatic quarantine based on quality scores and anomalies
- Segregated storage for quarantined data
- Quarantine metadata tracking
- Recovery and reprocessing workflows
- Quarantine analytics and reporting

Author: Flight Data Pipeline Team
Version: 1.0
"""

import json
import boto3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from quality_validator import QualityScore, QualityIssue, SeverityLevel
from anomaly_detector import Anomaly, AnomalyType

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class QuarantineReason(Enum):
    """Reasons for quarantining data."""
    LOW_QUALITY_SCORE = "low_quality_score"
    CRITICAL_ISSUE = "critical_issue"
    ANOMALY_DETECTED = "anomaly_detected"
    DATA_CORRUPTION = "data_corruption"
    VALIDATION_FAILURE = "validation_failure"
    MANUAL_QUARANTINE = "manual_quarantine"


class QuarantineStatus(Enum):
    """Status of quarantined records."""
    QUARANTINED = "quarantined"
    UNDER_REVIEW = "under_review"
    APPROVED_FOR_RELEASE = "approved_for_release"
    REJECTED = "rejected"
    REPROCESSED = "reprocessed"
    EXPIRED = "expired"


@dataclass
class QuarantineConfig:
    """Configuration for quarantine system."""
    
    # S3 quarantine bucket configuration
    quarantine_bucket: str = "flight-data-quarantine"
    quarantine_prefix: str = "quarantined-data"
    
    # Quality score thresholds
    auto_quarantine_threshold: float = 0.30    # Below this, automatic quarantine
    manual_review_threshold: float = 0.50      # Between this and auto, manual review
    
    # Anomaly thresholds
    critical_anomaly_quarantine: bool = True   # Quarantine on any critical anomaly
    high_anomaly_count_threshold: int = 3      # Quarantine if more than N high/critical anomalies
    
    # Retention and expiration
    quarantine_retention_days: int = 90        # Keep quarantined data for 90 days
    auto_expire_after_days: int = 30          # Auto-expire after 30 days if not reviewed
    
    # DynamoDB table for quarantine metadata
    quarantine_table_name: str = "flight-data-quarantine-tracking"
    
    # Notification settings
    enable_quarantine_notifications: bool = True
    notification_topic_arn: str = None
    
    # Batch processing
    max_quarantine_batch_size: int = 100
    
    # Recovery settings
    enable_auto_recovery: bool = False         # Enable automatic recovery for certain cases
    auto_recovery_score_threshold: float = 0.8 # Auto-recover if reprocessed score above this


@dataclass
class QuarantineRecord:
    """Represents a quarantined data record."""
    
    quarantine_id: str
    original_record_id: str  # icao24 or other identifier
    quarantine_timestamp: float
    quarantine_reason: QuarantineReason
    status: QuarantineStatus
    
    # Quality information
    quality_score: Optional[float] = None
    quality_issues: List[Dict[str, Any]] = None
    anomalies: List[Dict[str, Any]] = None
    
    # Storage locations
    s3_original_location: str = None
    s3_quarantine_location: str = None
    
    # Processing metadata
    processing_batch_id: str = None
    pipeline_version: str = None
    environment: str = None
    
    # Review information
    reviewer: str = None
    review_timestamp: Optional[float] = None
    review_notes: str = None
    
    # Recovery information
    recovery_attempts: int = 0
    last_recovery_attempt: Optional[float] = None
    recovery_successful: bool = False
    
    # Expiration
    expires_at: Optional[float] = None
    
    def __post_init__(self):
        if self.quality_issues is None:
            self.quality_issues = []
        if self.anomalies is None:
            self.anomalies = []


class DataQuarantineSystem:
    """Automated quarantine system for flight data."""
    
    def __init__(self, config: QuarantineConfig, environment: str = 'dev'):
        """Initialize the quarantine system."""
        self.config = config
        self.environment = environment
        
        # AWS clients
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.sns = boto3.client('sns') if config.notification_topic_arn else None
        
        # DynamoDB table
        self.quarantine_table = self.dynamodb.Table(config.quarantine_table_name)
        
        # Metrics tracking
        self.quarantine_metrics = {
            'total_quarantined': 0,
            'quarantine_reasons': {},
            'auto_quarantined': 0,
            'manual_review_required': 0,
            'recovered_count': 0
        }
        
        logger.info(f"DataQuarantineSystem initialized for environment: {environment}")
    
    def evaluate_for_quarantine(self, record: Dict[str, Any], 
                              quality_score: QualityScore,
                              anomalies: List[Anomaly] = None,
                              batch_id: str = None) -> Tuple[bool, List[QuarantineReason]]:
        """
        Evaluate if a record should be quarantined.
        
        Args:
            record: Original data record
            quality_score: Quality assessment results
            anomalies: List of detected anomalies
            batch_id: Processing batch identifier
            
        Returns:
            Tuple of (should_quarantine, reasons)
        """
        should_quarantine = False
        reasons = []
        anomalies = anomalies or []
        
        try:
            # 1. Check quality score threshold
            if quality_score.overall_score < self.config.auto_quarantine_threshold:
                should_quarantine = True
                reasons.append(QuarantineReason.LOW_QUALITY_SCORE)
                logger.debug(f"Record quarantined due to low quality score: {quality_score.overall_score}")
            
            # 2. Check for critical issues
            critical_issues = [issue for issue in quality_score.issues_found 
                             if issue.severity == SeverityLevel.CRITICAL]
            if critical_issues:
                should_quarantine = True
                reasons.append(QuarantineReason.CRITICAL_ISSUE)
                logger.debug(f"Record quarantined due to {len(critical_issues)} critical issues")
            
            # 3. Check anomalies
            if anomalies:
                # Critical anomalies
                critical_anomalies = [a for a in anomalies if a.severity == SeverityLevel.CRITICAL]
                if critical_anomalies and self.config.critical_anomaly_quarantine:
                    should_quarantine = True
                    reasons.append(QuarantineReason.ANOMALY_DETECTED)
                    logger.debug(f"Record quarantined due to {len(critical_anomalies)} critical anomalies")
                
                # High anomaly count
                high_severity_anomalies = [a for a in anomalies 
                                         if a.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
                if len(high_severity_anomalies) >= self.config.high_anomaly_count_threshold:
                    should_quarantine = True
                    reasons.append(QuarantineReason.ANOMALY_DETECTED)
                    logger.debug(f"Record quarantined due to high anomaly count: {len(high_severity_anomalies)}")
                
                # Data corruption anomalies
                corruption_anomalies = [a for a in anomalies 
                                      if a.anomaly_type == AnomalyType.DATA_CORRUPTION]
                if corruption_anomalies:
                    should_quarantine = True
                    reasons.append(QuarantineReason.DATA_CORRUPTION)
                    logger.debug(f"Record quarantined due to data corruption: {len(corruption_anomalies)}")
            
            # 4. Force quarantine if quality score indicates
            if quality_score.should_quarantine and not should_quarantine:
                should_quarantine = True
                reasons.append(QuarantineReason.VALIDATION_FAILURE)
            
            # Update metrics
            if should_quarantine:
                self.quarantine_metrics['total_quarantined'] += 1
                self.quarantine_metrics['auto_quarantined'] += 1
                for reason in reasons:
                    reason_key = reason.value
                    self.quarantine_metrics['quarantine_reasons'][reason_key] = \
                        self.quarantine_metrics['quarantine_reasons'].get(reason_key, 0) + 1
            
            return should_quarantine, reasons
            
        except Exception as e:
            logger.error(f"Error evaluating quarantine criteria: {str(e)}")
            # If we can't evaluate properly, err on the side of caution
            return True, [QuarantineReason.VALIDATION_FAILURE]
    
    def quarantine_record(self, record: Dict[str, Any],
                         quality_score: QualityScore,
                         reasons: List[QuarantineReason],
                         anomalies: List[Anomaly] = None,
                         batch_id: str = None,
                         original_s3_location: str = None) -> QuarantineRecord:
        """
        Quarantine a data record.
        
        Args:
            record: Original data record
            quality_score: Quality assessment
            reasons: Reasons for quarantine
            anomalies: Detected anomalies
            batch_id: Processing batch ID
            original_s3_location: Original S3 location
            
        Returns:
            QuarantineRecord: Created quarantine record
        """
        anomalies = anomalies or []
        
        try:
            # Generate quarantine ID
            quarantine_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).timestamp()
            
            # Create quarantine record
            quarantine_record = QuarantineRecord(
                quarantine_id=quarantine_id,
                original_record_id=record.get('icao24', str(uuid.uuid4())),
                quarantine_timestamp=timestamp,
                quarantine_reason=reasons[0] if reasons else QuarantineReason.VALIDATION_FAILURE,
                status=QuarantineStatus.QUARANTINED,
                quality_score=quality_score.overall_score,
                quality_issues=[issue.__dict__ for issue in quality_score.issues_found],
                anomalies=[asdict(anomaly) for anomaly in anomalies],
                s3_original_location=original_s3_location,
                processing_batch_id=batch_id,
                environment=self.environment,
                expires_at=timestamp + (self.config.quarantine_retention_days * 24 * 3600)
            )
            
            # Store original record in quarantine S3 location
            s3_quarantine_location = self._store_quarantine_data(
                quarantine_id, record, quality_score, anomalies, timestamp
            )
            quarantine_record.s3_quarantine_location = s3_quarantine_location
            
            # Store quarantine metadata in DynamoDB
            self._store_quarantine_metadata(quarantine_record, reasons)
            
            # Send notification if enabled
            if self.config.enable_quarantine_notifications:
                self._send_quarantine_notification(quarantine_record, reasons)
            
            logger.info(f"Record quarantined: {quarantine_id}, reasons: {[r.value for r in reasons]}")
            return quarantine_record
            
        except Exception as e:
            logger.error(f"Error quarantining record: {str(e)}")
            raise
    
    def batch_quarantine(self, quarantine_requests: List[Tuple[Dict[str, Any], QualityScore, 
                                                            List[QuarantineReason], List[Anomaly]]],
                        batch_id: str = None) -> List[QuarantineRecord]:
        """
        Quarantine multiple records in batch for efficiency.
        
        Args:
            quarantine_requests: List of (record, quality_score, reasons, anomalies) tuples
            batch_id: Processing batch ID
            
        Returns:
            List of created quarantine records
        """
        quarantine_records = []
        
        try:
            # Process in batches to avoid overwhelming services
            for i in range(0, len(quarantine_requests), self.config.max_quarantine_batch_size):
                batch = quarantine_requests[i:i + self.config.max_quarantine_batch_size]
                
                for record, quality_score, reasons, anomalies in batch:
                    try:
                        quarantine_record = self.quarantine_record(
                            record, quality_score, reasons, anomalies, batch_id
                        )
                        quarantine_records.append(quarantine_record)
                    except Exception as e:
                        logger.error(f"Failed to quarantine individual record: {str(e)}")
                        continue
            
            logger.info(f"Batch quarantine completed: {len(quarantine_records)} records quarantined")
            return quarantine_records
            
        except Exception as e:
            logger.error(f"Error in batch quarantine: {str(e)}")
            return quarantine_records
    
    def review_quarantine_record(self, quarantine_id: str, 
                                reviewer: str,
                                action: QuarantineStatus,
                                notes: str = None) -> bool:
        """
        Review and update quarantine record status.
        
        Args:
            quarantine_id: Quarantine record ID
            reviewer: Reviewer identifier
            action: Action to take (APPROVED_FOR_RELEASE, REJECTED, etc.)
            notes: Review notes
            
        Returns:
            Success status
        """
        try:
            timestamp = datetime.now(timezone.utc).timestamp()
            
            # Update quarantine record in DynamoDB
            response = self.quarantine_table.update_item(
                Key={'quarantine_id': quarantine_id},
                UpdateExpression='SET #status = :status, reviewer = :reviewer, review_timestamp = :timestamp, review_notes = :notes',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': action.value,
                    ':reviewer': reviewer,
                    ':timestamp': timestamp,
                    ':notes': notes or ''
                },
                ReturnValues='UPDATED_NEW'
            )
            
            logger.info(f"Quarantine record {quarantine_id} reviewed by {reviewer}: {action.value}")
            
            # If approved for release, trigger recovery process
            if action == QuarantineStatus.APPROVED_FOR_RELEASE:
                self._trigger_recovery(quarantine_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error reviewing quarantine record {quarantine_id}: {str(e)}")
            return False
    
    def get_quarantine_statistics(self, start_date: datetime = None, 
                                end_date: datetime = None) -> Dict[str, Any]:
        """
        Get quarantine statistics for reporting.
        
        Args:
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Statistics dictionary
        """
        try:
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            start_timestamp = start_date.timestamp()
            end_timestamp = end_date.timestamp()
            
            # Query quarantine table for records in date range
            response = self.quarantine_table.scan(
                FilterExpression='quarantine_timestamp BETWEEN :start_ts AND :end_ts',
                ExpressionAttributeValues={
                    ':start_ts': start_timestamp,
                    ':end_ts': end_timestamp
                }
            )
            
            records = response['Items']
            
            # Calculate statistics
            stats = {
                'total_quarantined': len(records),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'by_reason': {},
                'by_status': {},
                'quality_score_distribution': {
                    'excellent': 0,  # >= 0.9
                    'good': 0,       # 0.8-0.89
                    'fair': 0,       # 0.7-0.79
                    'poor': 0,       # 0.5-0.69
                    'critical': 0    # < 0.5
                },
                'average_quality_score': 0.0,
                'recovery_rate': 0.0,
                'auto_expired': 0,
                'pending_review': 0
            }
            
            total_quality_score = 0
            quality_scores = []
            recovered_count = 0
            
            for record in records:
                # Count by reason
                reason = record.get('quarantine_reason', 'unknown')
                stats['by_reason'][reason] = stats['by_reason'].get(reason, 0) + 1
                
                # Count by status
                status = record.get('status', 'unknown')
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # Quality score distribution
                quality_score = record.get('quality_score', 0)
                if quality_score:
                    quality_scores.append(quality_score)
                    total_quality_score += quality_score
                    
                    if quality_score >= 0.9:
                        stats['quality_score_distribution']['excellent'] += 1
                    elif quality_score >= 0.8:
                        stats['quality_score_distribution']['good'] += 1
                    elif quality_score >= 0.7:
                        stats['quality_score_distribution']['fair'] += 1
                    elif quality_score >= 0.5:
                        stats['quality_score_distribution']['poor'] += 1
                    else:
                        stats['quality_score_distribution']['critical'] += 1
                
                # Recovery tracking
                if status == QuarantineStatus.REPROCESSED.value:
                    recovered_count += 1
                elif status == QuarantineStatus.EXPIRED.value:
                    stats['auto_expired'] += 1
                elif status == QuarantineStatus.QUARANTINED.value:
                    stats['pending_review'] += 1
            
            # Calculate derived statistics
            if quality_scores:
                stats['average_quality_score'] = total_quality_score / len(quality_scores)
            
            if len(records) > 0:
                stats['recovery_rate'] = (recovered_count / len(records)) * 100
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting quarantine statistics: {str(e)}")
            return {}
    
    def cleanup_expired_records(self) -> int:
        """
        Clean up expired quarantine records.
        
        Returns:
            Number of records cleaned up
        """
        try:
            current_time = datetime.now(timezone.utc).timestamp()
            cleaned_count = 0
            
            # Scan for expired records
            response = self.quarantine_table.scan(
                FilterExpression='expires_at < :current_time AND #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':current_time': current_time,
                    ':status': QuarantineStatus.QUARANTINED.value
                }
            )
            
            for record in response['Items']:
                quarantine_id = record['quarantine_id']
                
                try:
                    # Update status to expired
                    self.quarantine_table.update_item(
                        Key={'quarantine_id': quarantine_id},
                        UpdateExpression='SET #status = :status',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': QuarantineStatus.EXPIRED.value
                        }
                    )
                    
                    # Optionally delete S3 data (based on retention policy)
                    s3_location = record.get('s3_quarantine_location')
                    if s3_location:
                        self._cleanup_s3_data(s3_location)
                    
                    cleaned_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup quarantine record {quarantine_id}: {str(e)}")
                    continue
            
            logger.info(f"Cleaned up {cleaned_count} expired quarantine records")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error in cleanup process: {str(e)}")
            return 0
    
    def _store_quarantine_data(self, quarantine_id: str, record: Dict[str, Any],
                              quality_score: QualityScore, anomalies: List[Anomaly],
                              timestamp: float) -> str:
        """Store quarantined data in S3."""
        try:
            # Create quarantine data package
            quarantine_data = {
                'quarantine_id': quarantine_id,
                'timestamp': timestamp,
                'original_record': record,
                'quality_assessment': quality_score.to_dict(),
                'anomalies': [asdict(anomaly) for anomaly in anomalies],
                'metadata': {
                    'quarantined_at': datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                    'environment': self.environment,
                    'pipeline_version': '1.0'
                }
            }
            
            # Generate S3 key
            date_str = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y/%m/%d')
            s3_key = f"{self.config.quarantine_prefix}/{date_str}/{quarantine_id}.json"
            
            # Store in S3
            self.s3.put_object(
                Bucket=self.config.quarantine_bucket,
                Key=s3_key,
                Body=json.dumps(quarantine_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'quarantine-id': quarantine_id,
                    'quality-score': str(quality_score.overall_score),
                    'environment': self.environment
                }
            )
            
            s3_location = f"s3://{self.config.quarantine_bucket}/{s3_key}"
            logger.debug(f"Quarantine data stored at: {s3_location}")
            return s3_location
            
        except Exception as e:
            logger.error(f"Failed to store quarantine data: {str(e)}")
            raise
    
    def _store_quarantine_metadata(self, quarantine_record: QuarantineRecord,
                                  reasons: List[QuarantineReason]) -> None:
        """Store quarantine metadata in DynamoDB."""
        try:
            item = asdict(quarantine_record)
            item['reasons'] = [reason.value for reason in reasons]
            
            # Convert enum values to strings for DynamoDB
            item['quarantine_reason'] = item['quarantine_reason'].value
            item['status'] = item['status'].value
            
            self.quarantine_table.put_item(Item=item)
            
        except Exception as e:
            logger.error(f"Failed to store quarantine metadata: {str(e)}")
            raise
    
    def _send_quarantine_notification(self, quarantine_record: QuarantineRecord,
                                    reasons: List[QuarantineReason]) -> None:
        """Send notification about quarantined record."""
        if not self.sns or not self.config.notification_topic_arn:
            return
        
        try:
            message = {
                'event_type': 'data_quarantined',
                'quarantine_id': quarantine_record.quarantine_id,
                'record_id': quarantine_record.original_record_id,
                'environment': self.environment,
                'timestamp': quarantine_record.quarantine_timestamp,
                'reasons': [reason.value for reason in reasons],
                'quality_score': quarantine_record.quality_score,
                'issue_count': len(quarantine_record.quality_issues),
                'anomaly_count': len(quarantine_record.anomalies)
            }
            
            self.sns.publish(
                TopicArn=self.config.notification_topic_arn,
                Message=json.dumps(message),
                Subject=f"Data Quarantine Alert - {self.environment}"
            )
            
        except Exception as e:
            logger.error(f"Failed to send quarantine notification: {str(e)}")
    
    def _trigger_recovery(self, quarantine_id: str) -> None:
        """Trigger recovery process for approved record."""
        try:
            # This would trigger a recovery Lambda or workflow
            # For now, just update the status
            self.quarantine_table.update_item(
                Key={'quarantine_id': quarantine_id},
                UpdateExpression='SET recovery_attempts = recovery_attempts + :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            
            logger.info(f"Recovery triggered for quarantine record: {quarantine_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger recovery for {quarantine_id}: {str(e)}")
    
    def _cleanup_s3_data(self, s3_location: str) -> None:
        """Clean up S3 quarantine data."""
        try:
            # Parse S3 location
            if s3_location.startswith('s3://'):
                s3_location = s3_location[5:]
            
            bucket, key = s3_location.split('/', 1)
            
            self.s3.delete_object(Bucket=bucket, Key=key)
            logger.debug(f"Cleaned up S3 quarantine data: {s3_location}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup S3 data at {s3_location}: {str(e)}")