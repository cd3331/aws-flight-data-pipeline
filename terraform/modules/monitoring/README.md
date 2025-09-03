# Flight Data Pipeline - Monitoring Module

This Terraform module provides comprehensive monitoring, alerting, and cost management for the flight data pipeline with enterprise-grade observability features.

## 🚀 Features Overview

### Monitoring Components
- ✅ **CloudWatch Dashboards** - Pipeline health, performance, cost tracking
- ✅ **25+ CloudWatch Alarms** - Error rates, latency, data quality, resource utilization
- ✅ **SNS Multi-Channel Notifications** - Email, SMS, Slack integration
- ✅ **DynamoDB Pipeline Tracking** - Execution history with TTL cleanup
- ✅ **Budget Monitoring** - Account and service-level cost tracking
- ✅ **Anomaly Detection** - AI-powered cost and performance monitoring
- ✅ **Cost Optimization Alerts** - S3 lifecycle, Lambda cold starts, DynamoDB throttling

## 📊 Dashboard Configuration

### Primary Dashboard Widgets

| Widget | Purpose | Metrics | Update Frequency |
|--------|---------|---------|------------------|
| **Pipeline Health** | Overall system status | Success rates, uptime | 5 minutes |
| **Lambda Performance** | Function duration, invocations | Duration, Memory, Errors | 5 minutes |
| **Data Quality** | Quality scores, completeness | Custom business metrics | 5 minutes |
| **Cost Tracking** | Daily spend by service | Billing metrics | 24 hours |
| **Storage Usage** | S3 bucket sizes, object counts | Storage metrics | 24 hours |

### Executive Summary Dashboard

```hcl
create_executive_dashboard = true
```

Provides high-level KPIs:
- Records processed (24h)
- Data quality score
- Monthly cost (USD)
- Pipeline uptime %

## 🚨 Alarm Configuration

### Critical Alarms (SMS + Email)

| Alarm | Threshold | Evaluation | Action |
|-------|-----------|------------|--------|
| **High Error Rate** | > 5% | 2 periods | Critical alert |
| **No Data Ingested** | < 1 invocation/15min | 2 periods | Critical alert |
| **Pipeline Availability** | < 95% | 3 periods | Critical alert |
| **Lambda Throttles** | > 0 | 1 period | Critical alert |
| **Budget Exceeded** | > $200/month | 1 period | Critical alert |

### Warning Alarms (Email Only)

| Alarm | Threshold | Purpose |
|-------|-----------|---------|
| **Low Data Quality** | < 0.7 score | Data validation issues |
| **High Processing Latency** | > 60s | Performance degradation |
| **Memory Utilization** | > 85% | Resource optimization |
| **Storage Growth** | > 100GB | Cost management |

### Business Logic Monitoring

```hcl
# Custom metrics for business KPIs
alarm_thresholds = {
  error_rate_threshold         = 0.05    # 5%
  data_quality_threshold       = 0.7     # 70%
  processing_latency_threshold = 60      # seconds
  completeness_threshold       = 0.8     # 80%
  validity_threshold          = 0.8      # 80%
  availability_threshold      = 0.95     # 95%
}
```

## 📱 Notification Channels

### Email Notifications

```hcl
# Standard alerts
alert_email_addresses = [
  "team@company.com",
  "devops@company.com"
]

# Critical alerts
critical_alert_email_addresses = [
  "oncall@company.com",
  "manager@company.com"
]

# Budget alerts
budget_notification_emails = [
  "finance@company.com",
  "team-lead@company.com"
]
```

### SMS Alerts (Critical Only)

```hcl
enable_sms_alerts = true
sms_phone_numbers = [
  "+1234567890",  # On-call engineer
  "+1987654321"   # Team lead
]
```

### Slack Integration

```hcl
enable_slack_notifications = true
slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Slack Message Features:**
- Color-coded alerts (Red/Orange/Green)
- Structured formatting with key metrics
- Environment and severity indicators
- Alert type identification (Alarm/Budget/Anomaly)

## 💰 Budget & Cost Monitoring

### Budget Configuration

```hcl
budget_limits = {
  monthly_limit = 200  # USD
}

# Service-specific budgets
service_budget_limits = {
  lambda_limit   = 50   # USD
  s3_limit      = 100   # USD
  dynamodb_limit = 30   # USD
}

# Alert thresholds
budget_thresholds = {
  warning_threshold  = 80   # 80%
  critical_threshold = 95   # 95%
  forecast_threshold = 100  # 100% (predicted)
}
```

### Cost Anomaly Detection

- **AI-powered detection** of unusual spending patterns
- **$10 minimum impact** threshold for alerts
- **Daily monitoring** with email notifications
- **Service-level analysis** (Lambda, S3, DynamoDB)

### Cost Optimization Alarms

```hcl
# S3 lifecycle optimization
s3_ia_ratio = 0.3  # 30% should be Infrequent Access

# Lambda performance optimization
cold_start_threshold = 10  # per 5 minutes

# DynamoDB capacity optimization
dynamodb_throttle_threshold = 5  # per 5 minutes
```

## 🗄️ Pipeline Execution Tracking

### DynamoDB Table Schema

```hcl
# Partition Key: tracking_id (UUID)
# TTL: expires_at (automatic cleanup)

# Global Secondary Indexes:
# - ExecutionDateIndex: execution_date + tracking_id
# - StatusIndex: status + tracking_id

# Example record structure:
{
  "tracking_id": "uuid-12345",
  "execution_date": "2024-01-15",
  "status": "completed",
  "function_name": "ingestion",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T10:05:00Z",
  "records_processed": 1500,
  "data_quality_score": 0.95,
  "expires_at": 1705276800  # TTL timestamp
}
```

### Query Patterns

```python
# Query by execution date
response = dynamodb.query(
    IndexName='ExecutionDateIndex',
    KeyConditionExpression=Key('execution_date').eq('2024-01-15')
)

# Query by status
response = dynamodb.query(
    IndexName='StatusIndex',
    KeyConditionExpression=Key('status').eq('failed')
)
```

## ⚡ Usage Examples

### Basic Monitoring Setup

```hcl
module "monitoring" {
  source = "./modules/monitoring"
  
  # Core configuration
  project_name = "flight-data-pipeline"
  environment  = "prod"
  
  # Lambda functions to monitor
  lambda_function_names = {
    ingestion  = "flight-data-ingestion"
    processing = "flight-data-processing"  
    validation = "data-quality-validator"
  }
  
  # S3 buckets to monitor
  s3_bucket_names = {
    raw_data       = "flight-data-raw"
    processed_data = "flight-data-processed"
    athena_results = "flight-data-athena"
  }
  
  # Basic notifications
  alert_email_addresses = ["team@company.com"]
  budget_notification_emails = ["finance@company.com"]
  
  # Budget limits
  budget_limits = {
    monthly_limit = 200
  }
  
  tags = local.common_tags
}
```

### Advanced Configuration with All Features

```hcl
module "monitoring" {
  source = "./modules/monitoring"
  
  project_name = "flight-data-pipeline"
  environment  = "prod"
  
  # Lambda monitoring
  lambda_function_names = {
    ingestion  = module.lambda_functions.function_names.ingestion
    processing = module.lambda_functions.function_names.processing
    validation = module.lambda_functions.function_names.validation
  }
  
  lambda_timeouts = {
    ingestion  = 60
    processing = 120
    validation = 60
  }
  
  # S3 monitoring
  s3_bucket_names = {
    raw_data       = module.s3_data_lake.bucket_names.raw_data
    processed_data = module.s3_data_lake.bucket_names.processed_data
    athena_results = module.s3_data_lake.bucket_names.athena_results
  }
  
  # DLQ monitoring
  dlq_names = {
    ingestion  = module.lambda_functions.dead_letter_queue_names.ingestion
    processing = module.lambda_functions.dead_letter_queue_names.processing
    validation = module.lambda_functions.dead_letter_queue_names.validation
  }
  
  # Custom alarm thresholds
  alarm_thresholds = {
    error_rate_threshold         = 0.03  # 3% for production
    data_quality_threshold       = 0.8   # Higher standard
    processing_latency_threshold = 45    # Tighter SLA
    availability_threshold       = 0.99  # 99% uptime
    s3_storage_threshold_gb     = 500    # Higher limit
  }
  
  # Multi-channel notifications
  alert_email_addresses = [
    "team@company.com",
    "devops@company.com"
  ]
  
  critical_alert_email_addresses = [
    "oncall@company.com",
    "cto@company.com"
  ]
  
  # SMS for critical issues
  enable_sms_alerts = true
  sms_phone_numbers = [
    "+1555123456",  # On-call
    "+1555987654"   # Backup
  ]
  
  # Slack integration
  enable_slack_notifications = true
  slack_webhook_url = var.slack_webhook_url
  
  # Budget monitoring
  budget_limits = {
    monthly_limit = 500  # Higher production budget
  }
  
  enable_service_budgets = true
  service_budget_limits = {
    lambda_limit   = 100
    s3_limit      = 300
    dynamodb_limit = 50
  }
  
  budget_notification_emails = [
    "finance@company.com",
    "engineering-manager@company.com"
  ]
  
  # Cost optimization
  cost_optimization_thresholds = {
    s3_ia_ratio                 = 0.4   # 40% IA storage target
    cold_start_threshold        = 5     # Stricter cold start monitoring
    dynamodb_throttle_threshold = 2     # Lower throttle tolerance
  }
  
  # Security
  enable_encryption = true
  kms_key_arn      = module.s3_data_lake.kms_key.arn
  
  # Executive reporting
  create_executive_dashboard = true
  
  tags = local.common_tags
}
```

## 🔍 Anomaly Detection

### Ingestion Rate Anomaly

Uses ML-powered detection to identify unusual patterns:
- **Training Period**: 2 weeks historical data
- **Detection Band**: 2 standard deviations
- **Evaluation**: 2 consecutive periods
- **Actions**: Email notification for investigation

### Cost Anomaly Detection

- **Service-level monitoring** for Lambda, S3, DynamoDB
- **Impact threshold**: $10 minimum
- **Daily analysis** with trend detection
- **Root cause analysis** support

## 📈 Custom Metrics Integration

### Lambda Function Metrics

```python
# In your Lambda functions
import boto3

cloudwatch = boto3.client('cloudwatch')

# Publish custom metrics
cloudwatch.put_metric_data(
    Namespace='FlightDataPipeline',
    MetricData=[
        {
            'MetricName': 'DataQualityScore',
            'Value': quality_score,
            'Unit': 'None',
            'Dimensions': [
                {
                    'Name': 'Environment',
                    'Value': os.environ['ENVIRONMENT']
                }
            ]
        },
        {
            'MetricName': 'RecordsProcessed',
            'Value': record_count,
            'Unit': 'Count'
        }
    ]
)
```

### Pipeline Health Tracking

```python
# Track pipeline execution in DynamoDB
def track_execution(tracking_id, function_name, status, metrics=None):
    """Track pipeline execution with TTL for automatic cleanup."""
    
    # Calculate TTL (30 days from now)
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    item = {
        'tracking_id': tracking_id,
        'execution_date': datetime.utcnow().strftime('%Y-%m-%d'),
        'function_name': function_name,
        'status': status,  # 'running', 'completed', 'failed'
        'timestamp': datetime.utcnow().isoformat(),
        'expires_at': ttl,
        'environment': os.environ['ENVIRONMENT']
    }
    
    if metrics:
        item.update(metrics)
    
    dynamodb.put_item(TableName=tracking_table, Item=item)
```

## 🔧 Maintenance & Operations

### Alarm Tuning

1. **Monitor Alarm History**
   ```bash
   aws cloudwatch describe-alarm-history --alarm-name flight-data-prod-high-error-rate
   ```

2. **Adjust Thresholds Based on Baseline**
   ```hcl
   # Gradually tighten thresholds as system stabilizes
   alarm_thresholds = {
     error_rate_threshold = 0.02  # Reduce from 5% to 2%
   }
   ```

### Cost Optimization Reviews

- **Weekly**: Review budget alerts and usage patterns
- **Monthly**: Analyze cost anomalies and optimization opportunities
- **Quarterly**: Reassess budget limits and service allocations

### Dashboard Customization

```hcl
# Add custom widgets to existing dashboard
dashboard_body = jsonencode({
  widgets = concat(
    local.standard_widgets,
    [
      {
        type = "metric"
        properties = {
          metrics = [
            ["CustomNamespace", "BusinessMetric", "Dimension", "Value"]
          ]
          title = "Custom Business Metric"
        }
      }
    ]
  )
})
```

## 🔒 Security Considerations

### Encryption
- **SNS Topics**: KMS encryption for sensitive alerts
- **DynamoDB**: Server-side encryption with customer-managed keys
- **Lambda Environment Variables**: Encrypted sensitive configuration

### Access Control
```hcl
# IAM policy for monitoring access
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "cloudwatch:GetDashboard"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${var.aws_region}"
        }
      }
    }
  ]
}
```

### Sensitive Data Handling
- **Phone numbers**: Validated E.164 format
- **Email addresses**: Validated format
- **Slack webhooks**: Secure HTTPS endpoints only
- **Budget information**: No sensitive financial data in logs

## 📚 Integration Points

### Lambda Functions
- Automatic function discovery via module outputs
- Performance monitoring with duration/memory tracking
- Error rate calculation and anomaly detection

### S3 Data Lake
- Storage growth monitoring and cost optimization
- Lifecycle policy effectiveness tracking
- Access pattern analysis for tier optimization

### DynamoDB
- Throttling detection and capacity optimization
- TTL cleanup verification
- Query performance monitoring

## 🚀 Deployment

### Prerequisites
```bash
# Ensure required providers
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      configuration_aliases = [aws.us-east-1]
    }
  }
}
```

### Deploy Monitoring
```bash
# Plan monitoring infrastructure
terraform plan -target=module.monitoring

# Apply monitoring configuration
terraform apply -target=module.monitoring

# Verify dashboards
aws cloudwatch list-dashboards --dashboard-name-prefix flight-data

# Test notifications
aws sns publish --topic-arn <topic-arn> --message "Test message"
```

## 💡 Best Practices

1. **Start Simple**: Begin with basic email alerts, add SMS/Slack gradually
2. **Tune Thresholds**: Monitor false positives and adjust thresholds accordingly
3. **Regular Reviews**: Weekly alarm reviews, monthly cost optimization
4. **Document Runbooks**: Link CloudWatch alarms to operational procedures
5. **Test Notifications**: Regular testing of all notification channels
6. **Monitor the Monitors**: Set up alarms for missing metrics or failed notifications

## 🆘 Troubleshooting

### Common Issues

**High False Positive Rate**
```hcl
# Increase evaluation periods or adjust thresholds
evaluation_periods = 3  # Instead of 2
threshold = 0.08        # Instead of 0.05
```

**Missing Custom Metrics**
```python
# Verify metric publishing in Lambda
logger.info(f"Publishing metric: {metric_name} = {value}")
```

**Slack Integration Not Working**
```bash
# Test webhook URL manually
curl -X POST -H 'Content-type: application/json' \
--data '{"text":"Test message"}' \
YOUR_WEBHOOK_URL
```

**Budget Alerts Not Triggering**
```bash
# Check budget configuration
aws budgets describe-budgets --account-id <account-id>
```

This monitoring module provides comprehensive observability for your flight data pipeline with enterprise-grade alerting, cost management, and performance tracking capabilities.