"""
Comprehensive Configuration System for Data Quality Validation Pipeline.

This module provides centralized configuration management for all components
of the data quality system, including thresholds, alerting logic, and
runtime parameters.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger()


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM" 
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertChannel(Enum):
    """Alert delivery channels."""
    SNS = "SNS"
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    PAGERDUTY = "PAGERDUTY"
    CLOUDWATCH_ALARM = "CLOUDWATCH_ALARM"


@dataclass
class QualityThresholds:
    """Quality scoring thresholds configuration."""
    
    # Overall quality score thresholds
    excellent_threshold: float = 0.95    # A grade
    good_threshold: float = 0.85         # B grade
    acceptable_threshold: float = 0.75   # C grade
    poor_threshold: float = 0.65         # D grade
    # Below poor_threshold = F grade (0.65 and below)
    
    # Dimensional thresholds
    completeness_critical_threshold: float = 0.60  # Critical missing data
    validity_critical_threshold: float = 0.70      # Critical invalid data
    consistency_critical_threshold: float = 0.65   # Critical inconsistencies
    timeliness_critical_threshold: float = 0.80    # Critical staleness
    
    # Quarantine thresholds
    auto_quarantine_threshold: float = 0.50        # Automatic quarantine
    manual_review_threshold: float = 0.65          # Requires manual review
    
    # Batch-level thresholds
    batch_failure_rate_threshold: float = 0.20     # 20% of batch failing
    batch_quarantine_rate_threshold: float = 0.15  # 15% quarantined
    
    def __post_init__(self):
        """Validate threshold consistency."""
        if not (self.excellent_threshold >= self.good_threshold >= 
                self.acceptable_threshold >= self.poor_threshold >= 
                self.auto_quarantine_threshold):
            raise ValueError("Quality thresholds must be in descending order")


@dataclass
class AnomalyThresholds:
    """Anomaly detection thresholds configuration."""
    
    # Physical limits
    min_altitude_feet: float = -1000.0
    max_altitude_feet: float = 60000.0
    min_groundspeed_knots: float = 0.0
    max_groundspeed_knots: float = 800.0
    min_latitude: float = -90.0
    max_latitude: float = 90.0
    min_longitude: float = -180.0
    max_longitude: float = 180.0
    
    # Statistical anomaly detection
    z_score_threshold: float = 3.0          # Standard deviations
    iqr_multiplier: float = 1.5             # IQR outlier detection
    percentile_threshold: float = 0.05      # 95th/5th percentile
    
    # Position jump detection
    max_position_jump_km: float = 100.0     # Max realistic position change
    max_altitude_change_feet: float = 10000.0  # Max altitude change per minute
    max_speed_change_knots: float = 100.0   # Max speed change per minute
    
    # Stuck aircraft detection
    stuck_position_threshold_km: float = 0.1    # Position variance threshold
    stuck_altitude_threshold_feet: float = 50.0 # Altitude variance threshold
    stuck_speed_threshold_knots: float = 5.0    # Speed variance threshold
    stuck_time_window_minutes: int = 10         # Time window for stuck detection
    
    # Temporal anomalies
    max_data_age_minutes: int = 30          # Maximum acceptable data age
    future_data_tolerance_minutes: int = 5  # Tolerance for future timestamps
    
    # Geographic boundaries (can be extended for specific regions)
    geographic_boundaries: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "continental_us": {
            "min_lat": 24.0, "max_lat": 49.0,
            "min_lon": -125.0, "max_lon": -66.0
        },
        "europe": {
            "min_lat": 35.0, "max_lat": 71.0,
            "min_lon": -10.0, "max_lon": 40.0
        }
    })


@dataclass
class MetricsConfiguration:
    """CloudWatch metrics publishing configuration."""
    
    namespace: str = "FlightDataPipeline"
    environment_dimension: str = "Environment"
    pipeline_dimension: str = "PipelineStage"
    
    # Publishing configuration
    max_metrics_per_batch: int = 20
    publish_interval_seconds: int = 60
    metric_resolution: int = 60  # seconds
    
    # Dimension configuration
    include_aircraft_type_dimension: bool = True
    include_data_source_dimension: bool = True
    include_geographic_dimension: bool = False
    
    # Retention and aggregation
    detailed_metrics_retention_days: int = 7
    summary_metrics_retention_days: int = 90


@dataclass
class QuarantineConfiguration:
    """Quarantine system configuration."""
    
    # S3 configuration
    quarantine_bucket: str = "flight-data-quarantine"
    quarantine_prefix: str = "quarantined-data"
    
    # DynamoDB configuration
    quarantine_table: str = "flight-data-quarantine-metadata"
    
    # Retention and cleanup
    quarantine_retention_days: int = 30
    auto_cleanup_enabled: bool = True
    cleanup_batch_size: int = 100
    
    # Review workflow
    auto_review_enabled: bool = True
    manual_review_required_score: float = 0.40
    review_sla_hours: int = 24
    
    # Performance limits
    max_quarantine_size_mb: int = 1024  # 1GB per quarantine entry
    max_batch_quarantine_count: int = 1000


@dataclass
class AlertConfiguration:
    """Alerting system configuration."""
    
    # Alert thresholds
    quality_degradation_threshold: float = 0.10    # 10% drop in quality
    anomaly_rate_threshold: float = 0.05           # 5% anomaly rate
    quarantine_rate_threshold: float = 0.15        # 15% quarantine rate
    processing_delay_threshold_minutes: int = 15   # Processing delay
    error_rate_threshold: float = 0.02             # 2% error rate
    
    # Alert channels and routing
    default_channels: List[AlertChannel] = field(default_factory=lambda: [
        AlertChannel.SNS, AlertChannel.CLOUDWATCH_ALARM
    ])
    
    severity_routing: Dict[AlertSeverity, List[AlertChannel]] = field(default_factory=lambda: {
        AlertSeverity.LOW: [AlertChannel.CLOUDWATCH_ALARM],
        AlertSeverity.MEDIUM: [AlertChannel.SNS, AlertChannel.CLOUDWATCH_ALARM],
        AlertSeverity.HIGH: [AlertChannel.SNS, AlertChannel.EMAIL, AlertChannel.CLOUDWATCH_ALARM],
        AlertSeverity.CRITICAL: [AlertChannel.SNS, AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.CLOUDWATCH_ALARM]
    })
    
    # Alert suppression and escalation
    suppression_window_minutes: int = 30
    escalation_delay_minutes: int = 60
    max_alerts_per_hour: int = 10
    
    # SNS topic configuration
    sns_topic_arn: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    slack_webhook_url: Optional[str] = None
    pagerduty_integration_key: Optional[str] = None


@dataclass
class ProcessingConfiguration:
    """Processing pipeline configuration."""
    
    # Batch processing
    max_batch_size: int = 1000
    batch_timeout_seconds: int = 300
    max_concurrent_batches: int = 10
    
    # Memory and performance
    max_memory_usage_mb: int = 2048
    processing_timeout_seconds: int = 900
    
    # Historical data
    historical_data_window_hours: int = 24
    max_historical_records: int = 10000
    
    # Error handling
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 5
    exponential_backoff: bool = True


class DataQualityConfiguration:
    """Central configuration manager for the data quality system."""
    
    def __init__(self, environment: str = None, config_source: str = "environment"):
        """
        Initialize configuration from specified source.
        
        Args:
            environment: Deployment environment (dev, staging, prod)
            config_source: Configuration source ('environment', 'file', 'parameter_store')
        """
        self.environment = environment or os.environ.get('ENVIRONMENT', 'dev')
        self.config_source = config_source
        
        # Load all configuration components
        self.quality_thresholds = self._load_quality_thresholds()
        self.anomaly_thresholds = self._load_anomaly_thresholds()
        self.metrics_config = self._load_metrics_configuration()
        self.quarantine_config = self._load_quarantine_configuration()
        self.alert_config = self._load_alert_configuration()
        self.processing_config = self._load_processing_configuration()
        
        logger.info(f"DataQualityConfiguration loaded for environment: {self.environment}")
    
    def _load_quality_thresholds(self) -> QualityThresholds:
        """Load quality threshold configuration."""
        config = QualityThresholds()
        
        if self.config_source == "environment":
            config.excellent_threshold = float(os.environ.get('QUALITY_EXCELLENT_THRESHOLD', config.excellent_threshold))
            config.good_threshold = float(os.environ.get('QUALITY_GOOD_THRESHOLD', config.good_threshold))
            config.acceptable_threshold = float(os.environ.get('QUALITY_ACCEPTABLE_THRESHOLD', config.acceptable_threshold))
            config.poor_threshold = float(os.environ.get('QUALITY_POOR_THRESHOLD', config.poor_threshold))
            config.auto_quarantine_threshold = float(os.environ.get('QUALITY_QUARANTINE_THRESHOLD', config.auto_quarantine_threshold))
            config.manual_review_threshold = float(os.environ.get('QUALITY_REVIEW_THRESHOLD', config.manual_review_threshold))
            config.batch_failure_rate_threshold = float(os.environ.get('BATCH_FAILURE_RATE_THRESHOLD', config.batch_failure_rate_threshold))
            config.batch_quarantine_rate_threshold = float(os.environ.get('BATCH_QUARANTINE_RATE_THRESHOLD', config.batch_quarantine_rate_threshold))
        
        return config
    
    def _load_anomaly_thresholds(self) -> AnomalyThresholds:
        """Load anomaly detection threshold configuration."""
        config = AnomalyThresholds()
        
        if self.config_source == "environment":
            config.min_altitude_feet = float(os.environ.get('ANOMALY_MIN_ALTITUDE', config.min_altitude_feet))
            config.max_altitude_feet = float(os.environ.get('ANOMALY_MAX_ALTITUDE', config.max_altitude_feet))
            config.min_groundspeed_knots = float(os.environ.get('ANOMALY_MIN_SPEED', config.min_groundspeed_knots))
            config.max_groundspeed_knots = float(os.environ.get('ANOMALY_MAX_SPEED', config.max_groundspeed_knots))
            config.z_score_threshold = float(os.environ.get('ANOMALY_Z_SCORE_THRESHOLD', config.z_score_threshold))
            config.max_position_jump_km = float(os.environ.get('ANOMALY_MAX_POSITION_JUMP', config.max_position_jump_km))
            config.stuck_time_window_minutes = int(os.environ.get('ANOMALY_STUCK_TIME_WINDOW', config.stuck_time_window_minutes))
            config.max_data_age_minutes = int(os.environ.get('ANOMALY_MAX_DATA_AGE', config.max_data_age_minutes))
            
            # Load geographic boundaries if provided as JSON
            boundaries_json = os.environ.get('ANOMALY_GEOGRAPHIC_BOUNDARIES')
            if boundaries_json:
                try:
                    config.geographic_boundaries = json.loads(boundaries_json)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON for geographic boundaries, using defaults")
        
        return config
    
    def _load_metrics_configuration(self) -> MetricsConfiguration:
        """Load CloudWatch metrics configuration."""
        config = MetricsConfiguration()
        
        if self.config_source == "environment":
            config.namespace = os.environ.get('METRICS_NAMESPACE', config.namespace)
            config.environment_dimension = os.environ.get('METRICS_ENVIRONMENT_DIMENSION', config.environment_dimension)
            config.max_metrics_per_batch = int(os.environ.get('METRICS_MAX_BATCH_SIZE', config.max_metrics_per_batch))
            config.publish_interval_seconds = int(os.environ.get('METRICS_PUBLISH_INTERVAL', config.publish_interval_seconds))
            config.include_aircraft_type_dimension = os.environ.get('METRICS_INCLUDE_AIRCRAFT_TYPE', 'true').lower() == 'true'
            config.include_data_source_dimension = os.environ.get('METRICS_INCLUDE_DATA_SOURCE', 'true').lower() == 'true'
            config.include_geographic_dimension = os.environ.get('METRICS_INCLUDE_GEOGRAPHIC', 'false').lower() == 'true'
        
        return config
    
    def _load_quarantine_configuration(self) -> QuarantineConfiguration:
        """Load quarantine system configuration."""
        config = QuarantineConfiguration()
        
        if self.config_source == "environment":
            config.quarantine_bucket = os.environ.get('QUARANTINE_BUCKET', config.quarantine_bucket)
            config.quarantine_prefix = os.environ.get('QUARANTINE_PREFIX', config.quarantine_prefix)
            config.quarantine_table = os.environ.get('QUARANTINE_TABLE', config.quarantine_table)
            config.quarantine_retention_days = int(os.environ.get('QUARANTINE_RETENTION_DAYS', config.quarantine_retention_days))
            config.auto_cleanup_enabled = os.environ.get('QUARANTINE_AUTO_CLEANUP', 'true').lower() == 'true'
            config.auto_review_enabled = os.environ.get('QUARANTINE_AUTO_REVIEW', 'true').lower() == 'true'
            config.manual_review_required_score = float(os.environ.get('QUARANTINE_MANUAL_REVIEW_SCORE', config.manual_review_required_score))
            config.max_quarantine_size_mb = int(os.environ.get('QUARANTINE_MAX_SIZE_MB', config.max_quarantine_size_mb))
        
        return config
    
    def _load_alert_configuration(self) -> AlertConfiguration:
        """Load alerting configuration."""
        config = AlertConfiguration()
        
        if self.config_source == "environment":
            config.quality_degradation_threshold = float(os.environ.get('ALERT_QUALITY_DEGRADATION_THRESHOLD', config.quality_degradation_threshold))
            config.anomaly_rate_threshold = float(os.environ.get('ALERT_ANOMALY_RATE_THRESHOLD', config.anomaly_rate_threshold))
            config.quarantine_rate_threshold = float(os.environ.get('ALERT_QUARANTINE_RATE_THRESHOLD', config.quarantine_rate_threshold))
            config.processing_delay_threshold_minutes = int(os.environ.get('ALERT_PROCESSING_DELAY_THRESHOLD', config.processing_delay_threshold_minutes))
            config.error_rate_threshold = float(os.environ.get('ALERT_ERROR_RATE_THRESHOLD', config.error_rate_threshold))
            config.sns_topic_arn = os.environ.get('ALERT_SNS_TOPIC_ARN')
            config.slack_webhook_url = os.environ.get('ALERT_SLACK_WEBHOOK_URL')
            config.pagerduty_integration_key = os.environ.get('ALERT_PAGERDUTY_INTEGRATION_KEY')
            
            # Parse email recipients
            email_recipients = os.environ.get('ALERT_EMAIL_RECIPIENTS', '')
            if email_recipients:
                config.email_recipients = [email.strip() for email in email_recipients.split(',')]
        
        return config
    
    def _load_processing_configuration(self) -> ProcessingConfiguration:
        """Load processing pipeline configuration."""
        config = ProcessingConfiguration()
        
        if self.config_source == "environment":
            config.max_batch_size = int(os.environ.get('PROCESSING_MAX_BATCH_SIZE', config.max_batch_size))
            config.batch_timeout_seconds = int(os.environ.get('PROCESSING_BATCH_TIMEOUT', config.batch_timeout_seconds))
            config.max_concurrent_batches = int(os.environ.get('PROCESSING_MAX_CONCURRENT_BATCHES', config.max_concurrent_batches))
            config.max_memory_usage_mb = int(os.environ.get('PROCESSING_MAX_MEMORY_MB', config.max_memory_usage_mb))
            config.processing_timeout_seconds = int(os.environ.get('PROCESSING_TIMEOUT', config.processing_timeout_seconds))
            config.historical_data_window_hours = int(os.environ.get('PROCESSING_HISTORICAL_WINDOW_HOURS', config.historical_data_window_hours))
            config.max_historical_records = int(os.environ.get('PROCESSING_MAX_HISTORICAL_RECORDS', config.max_historical_records))
            config.max_retry_attempts = int(os.environ.get('PROCESSING_MAX_RETRIES', config.max_retry_attempts))
        
        return config
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration overrides."""
        if self.environment == 'prod':
            return {
                'alert_config': {
                    'max_alerts_per_hour': 5,
                    'escalation_delay_minutes': 30
                },
                'quality_thresholds': {
                    'auto_quarantine_threshold': 0.60  # Stricter in prod
                },
                'processing_config': {
                    'max_retry_attempts': 5
                }
            }
        elif self.environment == 'staging':
            return {
                'alert_config': {
                    'max_alerts_per_hour': 20
                },
                'processing_config': {
                    'max_batch_size': 500
                }
            }
        else:  # dev
            return {
                'alert_config': {
                    'max_alerts_per_hour': 50,
                    'suppression_window_minutes': 5
                },
                'quality_thresholds': {
                    'auto_quarantine_threshold': 0.40  # More lenient in dev
                }
            }
    
    def validate_configuration(self) -> List[str]:
        """Validate the complete configuration and return any issues."""
        issues = []
        
        # Validate quality thresholds
        try:
            self.quality_thresholds.__post_init__()
        except ValueError as e:
            issues.append(f"Quality thresholds validation failed: {str(e)}")
        
        # Validate metric batch size
        if self.metrics_config.max_metrics_per_batch > 20:
            issues.append("CloudWatch metrics batch size cannot exceed 20")
        
        # Validate alert configuration
        if self.alert_config.sns_topic_arn and not self.alert_config.sns_topic_arn.startswith('arn:aws:sns:'):
            issues.append("Invalid SNS topic ARN format")
        
        # Validate processing limits
        if self.processing_config.max_batch_size > 10000:
            issues.append("Batch size too large, may cause memory issues")
        
        return issues
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            'environment': self.environment,
            'quality_thresholds': self.quality_thresholds.__dict__,
            'anomaly_thresholds': self.anomaly_thresholds.__dict__,
            'metrics_config': self.metrics_config.__dict__,
            'quarantine_config': self.quarantine_config.__dict__,
            'alert_config': {k: v for k, v in self.alert_config.__dict__.items() 
                           if not k.endswith('_key') and not k.endswith('_url')},  # Exclude sensitive data
            'processing_config': self.processing_config.__dict__
        }