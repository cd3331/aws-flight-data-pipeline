"""
Comprehensive Alerting System for Data Quality Monitoring.

This module handles alert generation, routing, and delivery based on
configured thresholds and business rules.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import boto3
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from config import AlertSeverity, AlertChannel, AlertConfiguration, DataQualityConfiguration

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@dataclass
class Alert:
    """Represents a data quality alert."""
    
    alert_id: str
    title: str
    description: str
    severity: AlertSeverity
    alert_type: str
    timestamp: datetime
    environment: str
    
    # Alert context
    affected_component: str
    metric_name: str
    current_value: float
    threshold_value: float
    
    # Additional metadata
    batch_id: Optional[str] = None
    aircraft_count: Optional[int] = None
    record_count: Optional[int] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize alert with defaults."""
        if self.details is None:
            self.details = {}
        
        if not self.alert_id:
            self.alert_id = f"{self.alert_type}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            'alert_id': self.alert_id,
            'title': self.title,
            'description': self.description,
            'severity': self.severity.value,
            'alert_type': self.alert_type,
            'timestamp': self.timestamp.isoformat(),
            'environment': self.environment,
            'affected_component': self.affected_component,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'batch_id': self.batch_id,
            'aircraft_count': self.aircraft_count,
            'record_count': self.record_count,
            'details': self.details
        }


class AlertSuppressionManager:
    """Manages alert suppression to prevent notification spam."""
    
    def __init__(self, suppression_window_minutes: int = 30):
        self.suppression_window = timedelta(minutes=suppression_window_minutes)
        self.recent_alerts = {}  # alert_key -> timestamp
        self.alert_counts = {}   # alert_key -> count
    
    def should_suppress_alert(self, alert: Alert) -> bool:
        """Determine if alert should be suppressed."""
        alert_key = f"{alert.alert_type}_{alert.affected_component}_{alert.severity.value}"
        current_time = datetime.now(timezone.utc)
        
        # Check if we've seen this alert recently
        if alert_key in self.recent_alerts:
            last_alert_time = self.recent_alerts[alert_key]
            if current_time - last_alert_time < self.suppression_window:
                self.alert_counts[alert_key] = self.alert_counts.get(alert_key, 0) + 1
                return True
        
        # Record this alert
        self.recent_alerts[alert_key] = current_time
        self.alert_counts[alert_key] = 1
        
        # Cleanup old entries
        self._cleanup_old_entries(current_time)
        
        return False
    
    def get_suppressed_count(self, alert: Alert) -> int:
        """Get count of suppressed alerts for this alert type."""
        alert_key = f"{alert.alert_type}_{alert.affected_component}_{alert.severity.value}"
        return self.alert_counts.get(alert_key, 0) - 1  # Subtract 1 for current alert
    
    def _cleanup_old_entries(self, current_time: datetime) -> None:
        """Remove old entries outside suppression window."""
        cutoff_time = current_time - self.suppression_window
        
        keys_to_remove = []
        for alert_key, timestamp in self.recent_alerts.items():
            if timestamp < cutoff_time:
                keys_to_remove.append(alert_key)
        
        for key in keys_to_remove:
            self.recent_alerts.pop(key, None)
            self.alert_counts.pop(key, None)


class AlertRouter:
    """Routes alerts to appropriate channels based on severity and configuration."""
    
    def __init__(self, alert_config: AlertConfiguration, environment: str):
        self.config = alert_config
        self.environment = environment
        
        # Initialize AWS clients
        self.sns_client = boto3.client('sns')
        self.cloudwatch_client = boto3.client('cloudwatch')
        
        # Initialize alert suppression
        self.suppression_manager = AlertSuppressionManager(
            self.config.suppression_window_minutes
        )
    
    def route_alert(self, alert: Alert) -> bool:
        """Route alert to appropriate channels."""
        try:
            # Check suppression
            if self.suppression_manager.should_suppress_alert(alert):
                suppressed_count = self.suppression_manager.get_suppressed_count(alert)
                logger.info(f"Alert suppressed: {alert.alert_id} (suppressed {suppressed_count} similar alerts)")
                return True
            
            # Get channels for this severity level
            channels = self.config.severity_routing.get(
                alert.severity, 
                self.config.default_channels
            )
            
            success = True
            for channel in channels:
                try:
                    if channel == AlertChannel.SNS:
                        self._send_sns_alert(alert)
                    elif channel == AlertChannel.EMAIL:
                        self._send_email_alert(alert)
                    elif channel == AlertChannel.SLACK:
                        self._send_slack_alert(alert)
                    elif channel == AlertChannel.PAGERDUTY:
                        self._send_pagerduty_alert(alert)
                    elif channel == AlertChannel.CLOUDWATCH_ALARM:
                        self._create_cloudwatch_alarm(alert)
                        
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {str(e)}")
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error routing alert {alert.alert_id}: {str(e)}")
            return False
    
    def _send_sns_alert(self, alert: Alert) -> None:
        """Send alert via SNS."""
        if not self.config.sns_topic_arn:
            logger.warning("SNS topic ARN not configured")
            return
        
        message = self._format_sns_message(alert)
        
        self.sns_client.publish(
            TopicArn=self.config.sns_topic_arn,
            Subject=f"[{alert.severity.value}] {alert.title}",
            Message=message,
            MessageAttributes={
                'environment': {
                    'DataType': 'String',
                    'StringValue': self.environment
                },
                'severity': {
                    'DataType': 'String',
                    'StringValue': alert.severity.value
                },
                'alert_type': {
                    'DataType': 'String',
                    'StringValue': alert.alert_type
                }
            }
        )
        
        logger.info(f"SNS alert sent: {alert.alert_id}")
    
    def _send_email_alert(self, alert: Alert) -> None:
        """Send alert via email (through SNS to configured email addresses)."""
        if not self.config.email_recipients or not self.config.sns_topic_arn:
            logger.warning("Email recipients or SNS topic not configured")
            return
        
        # For simplicity, this uses SNS email subscriptions
        # In production, you might use SES for more control
        self._send_sns_alert(alert)
    
    def _send_slack_alert(self, alert: Alert) -> None:
        """Send alert to Slack webhook."""
        if not self.config.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return
        
        payload = {
            "text": f"🚨 Data Quality Alert: {alert.title}",
            "attachments": [
                {
                    "color": self._get_slack_color(alert.severity),
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value,
                            "short": True
                        },
                        {
                            "title": "Environment",
                            "value": alert.environment,
                            "short": True
                        },
                        {
                            "title": "Component",
                            "value": alert.affected_component,
                            "short": True
                        },
                        {
                            "title": "Metric",
                            "value": f"{alert.metric_name}: {alert.current_value} (threshold: {alert.threshold_value})",
                            "short": False
                        },
                        {
                            "title": "Description",
                            "value": alert.description,
                            "short": False
                        }
                    ],
                    "timestamp": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        response = requests.post(
            self.config.slack_webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        logger.info(f"Slack alert sent: {alert.alert_id}")
    
    def _send_pagerduty_alert(self, alert: Alert) -> None:
        """Send alert to PagerDuty."""
        if not self.config.pagerduty_integration_key:
            logger.warning("PagerDuty integration key not configured")
            return
        
        payload = {
            "routing_key": self.config.pagerduty_integration_key,
            "event_action": "trigger",
            "dedup_key": f"{alert.alert_type}_{alert.affected_component}",
            "payload": {
                "summary": alert.title,
                "severity": alert.severity.value.lower(),
                "source": f"flight-data-pipeline-{self.environment}",
                "component": alert.affected_component,
                "group": "data-quality",
                "class": alert.alert_type,
                "custom_details": {
                    "description": alert.description,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                    "batch_id": alert.batch_id,
                    "details": alert.details
                }
            }
        }
        
        response = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        logger.info(f"PagerDuty alert sent: {alert.alert_id}")
    
    def _create_cloudwatch_alarm(self, alert: Alert) -> None:
        """Create CloudWatch alarm for alert."""
        alarm_name = f"DataQuality-{alert.alert_type}-{alert.affected_component}-{self.environment}"
        
        # Create alarm based on the metric that triggered the alert
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='LessThanThreshold' if 'quality' in alert.metric_name.lower() else 'GreaterThanThreshold',
            EvaluationPeriods=2,
            MetricName=alert.metric_name,
            Namespace='FlightDataPipeline',
            Period=300,
            Statistic='Average',
            Threshold=alert.threshold_value,
            ActionsEnabled=True,
            AlarmActions=[self.config.sns_topic_arn] if self.config.sns_topic_arn else [],
            AlarmDescription=f"Data quality alert: {alert.description}",
            Dimensions=[
                {
                    'Name': 'Environment',
                    'Value': self.environment
                },
                {
                    'Name': 'Component',
                    'Value': alert.affected_component
                }
            ],
            Unit='None'
        )
        
        logger.info(f"CloudWatch alarm created: {alarm_name}")
    
    def _format_sns_message(self, alert: Alert) -> str:
        """Format alert message for SNS."""
        suppressed_count = self.suppression_manager.get_suppressed_count(alert)
        suppressed_note = f" ({suppressed_count} similar alerts suppressed)" if suppressed_count > 0 else ""
        
        return f"""
Flight Data Pipeline - Data Quality Alert{suppressed_note}

Alert ID: {alert.alert_id}
Severity: {alert.severity.value}
Environment: {alert.environment}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Component: {alert.affected_component}
Alert Type: {alert.alert_type}

Metric: {alert.metric_name}
Current Value: {alert.current_value}
Threshold: {alert.threshold_value}

Description:
{alert.description}

{f'Batch ID: {alert.batch_id}' if alert.batch_id else ''}
{f'Records Processed: {alert.record_count}' if alert.record_count else ''}
{f'Aircraft Affected: {alert.aircraft_count}' if alert.aircraft_count else ''}

Additional Details:
{json.dumps(alert.details, indent=2) if alert.details else 'None'}
"""
    
    def _get_slack_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for severity level."""
        colors = {
            AlertSeverity.LOW: "#36a64f",      # Green
            AlertSeverity.MEDIUM: "#ff9500",   # Orange  
            AlertSeverity.HIGH: "#ff0000",     # Red
            AlertSeverity.CRITICAL: "#8b0000"  # Dark Red
        }
        return colors.get(severity, "#cccccc")


class DataQualityAlerting:
    """Main alerting system for data quality monitoring."""
    
    def __init__(self, config: DataQualityConfiguration):
        self.config = config
        self.alert_router = AlertRouter(config.alert_config, config.environment)
        
        # Track metrics for alerting
        self.recent_metrics = {}
        self.baseline_metrics = {}
        
        logger.info("DataQualityAlerting initialized")
    
    def evaluate_quality_metrics(self, batch_results: Dict[str, Any]) -> List[Alert]:
        """Evaluate batch results and generate quality alerts."""
        alerts = []
        
        try:
            # Extract key metrics
            avg_quality_score = batch_results.get('average_quality_score', 1.0)
            quarantine_rate = batch_results.get('quarantine_rate', 0.0)
            anomaly_rate = batch_results.get('anomaly_rate', 0.0)
            error_rate = batch_results.get('error_rate', 0.0)
            processing_duration = batch_results.get('processing_duration_ms', 0)
            
            batch_id = batch_results.get('batch_id')
            record_count = batch_results.get('total_records', 0)
            
            # 1. Quality degradation alert
            if avg_quality_score < self.config.quality_thresholds.poor_threshold:
                severity = AlertSeverity.HIGH if avg_quality_score < self.config.quality_thresholds.auto_quarantine_threshold else AlertSeverity.MEDIUM
                
                alerts.append(Alert(
                    alert_id="",
                    title="Data Quality Degradation Detected",
                    description=f"Average quality score ({avg_quality_score:.3f}) has fallen below acceptable threshold ({self.config.quality_thresholds.poor_threshold})",
                    severity=severity,
                    alert_type="quality_degradation",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="DataValidator",
                    metric_name="AverageQualityScore",
                    current_value=avg_quality_score,
                    threshold_value=self.config.quality_thresholds.poor_threshold,
                    batch_id=batch_id,
                    record_count=record_count
                ))
            
            # 2. High quarantine rate alert
            if quarantine_rate > self.config.alert_config.quarantine_rate_threshold:
                severity = AlertSeverity.CRITICAL if quarantine_rate > 0.30 else AlertSeverity.HIGH
                
                alerts.append(Alert(
                    alert_id="",
                    title="High Quarantine Rate Alert",
                    description=f"Quarantine rate ({quarantine_rate:.1%}) exceeds threshold ({self.config.alert_config.quarantine_rate_threshold:.1%})",
                    severity=severity,
                    alert_type="high_quarantine_rate",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="QuarantineSystem",
                    metric_name="QuarantineRate",
                    current_value=quarantine_rate,
                    threshold_value=self.config.alert_config.quarantine_rate_threshold,
                    batch_id=batch_id,
                    record_count=record_count
                ))
            
            # 3. High anomaly rate alert
            if anomaly_rate > self.config.alert_config.anomaly_rate_threshold:
                severity = AlertSeverity.HIGH if anomaly_rate > 0.10 else AlertSeverity.MEDIUM
                
                alerts.append(Alert(
                    alert_id="",
                    title="High Anomaly Detection Rate",
                    description=f"Anomaly rate ({anomaly_rate:.1%}) exceeds normal threshold ({self.config.alert_config.anomaly_rate_threshold:.1%})",
                    severity=severity,
                    alert_type="high_anomaly_rate",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="AnomalyDetector",
                    metric_name="AnomalyRate",
                    current_value=anomaly_rate,
                    threshold_value=self.config.alert_config.anomaly_rate_threshold,
                    batch_id=batch_id,
                    record_count=record_count
                ))
            
            # 4. Processing delay alert
            processing_delay_minutes = processing_duration / (1000 * 60)  # Convert to minutes
            if processing_delay_minutes > self.config.alert_config.processing_delay_threshold_minutes:
                severity = AlertSeverity.MEDIUM
                
                alerts.append(Alert(
                    alert_id="",
                    title="Processing Delay Alert",
                    description=f"Processing took {processing_delay_minutes:.1f} minutes, exceeding threshold ({self.config.alert_config.processing_delay_threshold_minutes} minutes)",
                    severity=severity,
                    alert_type="processing_delay",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="DataProcessor",
                    metric_name="ProcessingDelayMinutes",
                    current_value=processing_delay_minutes,
                    threshold_value=self.config.alert_config.processing_delay_threshold_minutes,
                    batch_id=batch_id,
                    record_count=record_count
                ))
            
            # 5. Error rate alert
            if error_rate > self.config.alert_config.error_rate_threshold:
                severity = AlertSeverity.CRITICAL if error_rate > 0.10 else AlertSeverity.HIGH
                
                alerts.append(Alert(
                    alert_id="",
                    title="High Error Rate Alert",
                    description=f"Error rate ({error_rate:.1%}) exceeds acceptable threshold ({self.config.alert_config.error_rate_threshold:.1%})",
                    severity=severity,
                    alert_type="high_error_rate",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="DataProcessor",
                    metric_name="ErrorRate",
                    current_value=error_rate,
                    threshold_value=self.config.alert_config.error_rate_threshold,
                    batch_id=batch_id,
                    record_count=record_count
                ))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error evaluating quality metrics for alerting: {str(e)}")
            return []
    
    def send_alerts(self, alerts: List[Alert]) -> bool:
        """Send all generated alerts."""
        if not alerts:
            return True
        
        success = True
        for alert in alerts:
            try:
                result = self.alert_router.route_alert(alert)
                if not result:
                    success = False
                    
            except Exception as e:
                logger.error(f"Error sending alert {alert.alert_id}: {str(e)}")
                success = False
        
        logger.info(f"Sent {len(alerts)} alerts, success: {success}")
        return success
    
    def create_system_health_alert(self, health_status: Dict[str, Any]) -> Optional[Alert]:
        """Create system health alert if thresholds are exceeded."""
        try:
            # Check data freshness
            data_freshness = health_status.get('data_freshness_seconds', 0)
            if data_freshness > self.config.alert_config.processing_delay_threshold_minutes * 60:
                return Alert(
                    alert_id="",
                    title="Data Freshness Alert",
                    description=f"Data is {data_freshness/60:.1f} minutes old, exceeding freshness threshold",
                    severity=AlertSeverity.MEDIUM,
                    alert_type="data_freshness",
                    timestamp=datetime.now(timezone.utc),
                    environment=self.config.environment,
                    affected_component="DataIngestion",
                    metric_name="DataFreshnessMinutes",
                    current_value=data_freshness/60,
                    threshold_value=self.config.alert_config.processing_delay_threshold_minutes,
                    details=health_status
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating system health alert: {str(e)}")
            return None