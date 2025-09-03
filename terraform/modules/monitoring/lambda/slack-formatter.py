"""
Slack notification formatter for AWS CloudWatch alarms and budget alerts.
This Lambda function formats SNS messages and sends them to Slack webhook.
"""

import json
import os
import urllib3
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize HTTP client
http = urllib3.PoolManager()

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Process SNS messages and send formatted alerts to Slack.
    
    Args:
        event: SNS event containing alarm or budget information
        context: Lambda context object
        
    Returns:
        Dict with status information
    """
    try:
        # Get environment variables
        slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        environment = os.environ.get('ENVIRONMENT', 'unknown')
        project_name = os.environ.get('PROJECT_NAME', 'flight-data-pipeline')
        
        if not slack_webhook_url:
            logger.error("SLACK_WEBHOOK_URL environment variable not set")
            return {'statusCode': 400, 'body': 'Webhook URL not configured'}
        
        # Process each SNS record
        messages_sent = 0
        for record in event.get('Records', []):
            if record.get('EventSource') == 'aws:sns':
                message = json.loads(record['Sns']['Message'])
                subject = record['Sns'].get('Subject', 'AWS Alert')
                
                # Format message based on type
                slack_message = format_slack_message(message, subject, environment, project_name)
                
                if slack_message:
                    # Send to Slack
                    response = send_to_slack(slack_webhook_url, slack_message)
                    if response:
                        messages_sent += 1
                        logger.info(f"Successfully sent message to Slack: {subject}")
                    else:
                        logger.error(f"Failed to send message to Slack: {subject}")
        
        return {
            'statusCode': 200,
            'body': f'Successfully processed {messages_sent} messages'
        }
        
    except Exception as e:
        logger.error(f"Error processing SNS message: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

def format_slack_message(message: Dict[str, Any], subject: str, environment: str, project_name: str) -> Optional[Dict[str, Any]]:
    """
    Format different types of AWS alerts for Slack.
    
    Args:
        message: Parsed SNS message
        subject: SNS subject line
        environment: Environment name
        project_name: Project name
        
    Returns:
        Formatted Slack message or None if unsupported
    """
    try:
        # Determine message type and format accordingly
        if 'AlarmName' in message:
            return format_cloudwatch_alarm(message, environment, project_name)
        elif 'budgetName' in message or 'Budget' in subject:
            return format_budget_alert(message, subject, environment, project_name)
        elif 'anomalyScore' in message:
            return format_cost_anomaly(message, environment, project_name)
        else:
            # Generic message format
            return format_generic_message(message, subject, environment, project_name)
            
    except Exception as e:
        logger.error(f"Error formatting message: {str(e)}")
        return None

def format_cloudwatch_alarm(message: Dict[str, Any], environment: str, project_name: str) -> Dict[str, Any]:
    """Format CloudWatch alarm for Slack."""
    
    alarm_name = message.get('AlarmName', 'Unknown Alarm')
    new_state = message.get('NewStateValue', 'UNKNOWN')
    reason = message.get('NewStateReason', 'No reason provided')
    timestamp = message.get('StateChangeTime', datetime.utcnow().isoformat())
    
    # Determine color based on alarm state
    color_map = {
        'ALARM': '#ff0000',      # Red
        'OK': '#00ff00',         # Green
        'INSUFFICIENT_DATA': '#ffaa00'  # Orange
    }
    color = color_map.get(new_state, '#808080')
    
    # Determine urgency level
    is_critical = any(keyword in alarm_name.lower() for keyword in [
        'critical', 'high-error', 'no-data', 'throttle', 'availability'
    ])
    
    urgency = "🚨 CRITICAL" if is_critical else "⚠️ WARNING"
    emoji = "🚨" if new_state == 'ALARM' else "✅" if new_state == 'OK' else "⚠️"
    
    # Format metric information
    metric_info = ""
    if 'Trigger' in message:
        trigger = message['Trigger']
        metric_name = trigger.get('MetricName', '')
        namespace = trigger.get('Namespace', '')
        threshold = trigger.get('Threshold', '')
        comparison = trigger.get('ComparisonOperator', '')
        
        if metric_name:
            metric_info = f"\n*Metric:* {namespace}/{metric_name}\n*Threshold:* {comparison} {threshold}"
    
    return {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {urgency} - {project_name.upper()}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Environment:* {environment.upper()}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*State:* {new_state}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Alarm:* {alarm_name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Time:* {format_timestamp(timestamp)}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Reason:* {reason}{metric_info}"
                        }
                    }
                ]
            }
        ]
    }

def format_budget_alert(message: Dict[str, Any], subject: str, environment: str, project_name: str) -> Dict[str, Any]:
    """Format budget alert for Slack."""
    
    # Extract budget information
    budget_name = message.get('budgetName', 'Unknown Budget')
    account_id = message.get('accountId', 'Unknown')
    
    # Parse budget details from message
    actual_amount = message.get('actualAmount', 0)
    budgeted_amount = message.get('budgetedAmount', 0)
    threshold_type = message.get('thresholdType', 'PERCENTAGE')
    
    # Calculate percentage if not provided
    if budgeted_amount > 0:
        percentage = (actual_amount / budgeted_amount) * 100
    else:
        percentage = 0
    
    # Determine severity
    is_critical = percentage >= 95 or 'CRITICAL' in subject.upper()
    urgency = "🚨 CRITICAL" if is_critical else "⚠️ WARNING"
    color = "#ff0000" if is_critical else "#ffaa00"
    
    return {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"💰 {urgency} - Budget Alert"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Project:* {project_name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Environment:* {environment.upper()}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Budget:* {budget_name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Usage:* {percentage:.1f}%"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Actual:* ${actual_amount:.2f}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Budget:* ${budgeted_amount:.2f}"
                            }
                        ]
                    }
                ]
            }
        ]
    }

def format_cost_anomaly(message: Dict[str, Any], environment: str, project_name: str) -> Dict[str, Any]:
    """Format cost anomaly alert for Slack."""
    
    anomaly_score = message.get('anomalyScore', 0)
    impact = message.get('impact', {})
    max_impact = impact.get('maxImpact', 0)
    total_impact = impact.get('totalImpact', 0)
    
    service = message.get('service', 'Unknown Service')
    
    return {
        "attachments": [
            {
                "color": "#ff6600",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📈 Cost Anomaly Detected - {project_name.upper()}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Environment:* {environment.upper()}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Service:* {service}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Anomaly Score:* {anomaly_score:.2f}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Max Impact:* ${max_impact:.2f}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Total Impact:* ${total_impact:.2f}"
                            }
                        ]
                    }
                ]
            }
        ]
    }

def format_generic_message(message: Dict[str, Any], subject: str, environment: str, project_name: str) -> Dict[str, Any]:
    """Format generic message for Slack."""
    
    return {
        "attachments": [
            {
                "color": "#808080",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"ℹ️ {subject}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Project:* {project_name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Environment:* {environment.upper()}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"```{json.dumps(message, indent=2, default=str)[:2000]}```"
                        }
                    }
                ]
            }
        ]
    }

def send_to_slack(webhook_url: str, message: Dict[str, Any]) -> bool:
    """
    Send formatted message to Slack webhook.
    
    Args:
        webhook_url: Slack webhook URL
        message: Formatted Slack message
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert message to JSON
        payload = json.dumps(message)
        
        # Send to Slack
        response = http.request(
            'POST',
            webhook_url,
            body=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status == 200:
            logger.info("Successfully sent message to Slack")
            return True
        else:
            logger.error(f"Failed to send to Slack. Status: {response.status}, Response: {response.data}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending to Slack: {str(e)}")
        return False

def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return timestamp_str