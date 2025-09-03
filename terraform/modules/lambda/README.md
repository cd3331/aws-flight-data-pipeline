# Lambda Functions Module

This Terraform module creates a comprehensive Lambda function infrastructure for the flight data pipeline with enterprise-grade features including IAM roles, layers, error handling, monitoring, and event integrations.

## 🚀 Architecture Overview

### Lambda Functions

| Function | Purpose | Memory | Timeout | Concurrency |
|----------|---------|--------|---------|-------------|
| **Ingestion** | Fetch data from OpenSky API | 512MB | 60s | 10 |
| **Processing** | Transform JSON to Parquet | 1024MB | 120s | 5 |
| **Validation** | Data quality checks | 512MB | 60s | 3 |

### Event Flow

```
EventBridge (5min) ──► Ingestion Lambda ──► S3 Raw Data
                                              │
                                              ▼
S3 Event ──────────────► Processing Lambda ──► S3 Processed Data
                                              │
                                              ▼
S3 Event ──────────────► Validation Lambda ──► CloudWatch Metrics
                                              │
                                              ▼
                                            SNS Alerts
```

## 🔧 Features

### Core Components
- ✅ **3 Lambda Functions** with optimized configurations
- ✅ **IAM Roles** with least privilege policies
- ✅ **Lambda Layers** for shared dependencies
- ✅ **CloudWatch Logs** with configurable retention
- ✅ **Dead Letter Queues** for error handling
- ✅ **X-Ray Tracing** for debugging

### Event Integration
- ✅ **EventBridge Rules** for scheduled ingestion
- ✅ **S3 Event Notifications** for processing pipeline
- ✅ **Lambda Permissions** for cross-service access
- ✅ **Retry Logic** with exponential backoff

### Monitoring & Alerting
- ✅ **CloudWatch Alarms** for errors, duration, throttles
- ✅ **SNS Notifications** for critical issues
- ✅ **Custom Dashboards** for operational visibility
- ✅ **Lambda Insights** for enhanced monitoring

### Advanced Features
- ✅ **Versioning & Aliases** for blue/green deployments
- ✅ **Provisioned Concurrency** for consistent performance
- ✅ **Gradual Deployment** with weighted routing
- ✅ **VPC Support** for network isolation

## 📋 Usage

### Basic Configuration

```hcl
module "lambda_functions" {
  source = "./modules/lambda"
  
  # Core configuration
  project_name = "flight-data-pipeline"
  environment  = "prod"
  
  # S3 bucket integration
  raw_data_bucket_name      = module.s3_data_lake.bucket_names.raw_data
  raw_data_bucket_arn       = module.s3_data_lake.bucket_arns.raw_data
  processed_data_bucket_name = module.s3_data_lake.bucket_names.processed_data
  processed_data_bucket_arn  = module.s3_data_lake.bucket_arns.processed_data
  athena_results_bucket_name = module.s3_data_lake.bucket_names.athena_results
  athena_results_bucket_arn  = module.s3_data_lake.bucket_arns.athena_results
  
  # Security
  kms_key_arn = module.s3_data_lake.kms_key.arn
  
  tags = local.common_tags
}
```

### Advanced Configuration

```hcl
module "lambda_functions" {
  source = "./modules/lambda"
  
  # Core configuration
  project_name = "flight-data-pipeline"
  environment  = "prod"
  
  # Lambda configuration
  lambda_config = {
    ingestion = {
      memory_size             = 512
      timeout                 = 60
      reserved_concurrency    = 10
      provisioned_concurrency = 2
      environment_variables = {
        API_RATE_LIMIT = "4000"
        BATCH_SIZE     = "100"
      }
    }
    processing = {
      memory_size             = 1024
      timeout                 = 120
      reserved_concurrency    = 5
      provisioned_concurrency = 0
      environment_variables = {
        COMPRESSION_LEVEL = "9"
        PARALLEL_JOBS     = "4"
      }
    }
    validation = {
      memory_size             = 512
      timeout                 = 60
      reserved_concurrency    = 3
      provisioned_concurrency = 0
      environment_variables = {
        QUALITY_CHECKS = "16"
        STRICT_MODE    = "true"
      }
    }
  }
  
  # Runtime configuration
  lambda_runtime      = "python3.11"
  lambda_architecture = "x86_64"
  log_level          = "INFO"
  log_retention_days = 30
  
  # Event configuration
  enable_scheduled_ingestion    = true
  ingestion_schedule_expression = "rate(5 minutes)"
  
  # Monitoring
  enable_xray_tracing      = true
  enable_cloudwatch_alarms = true
  create_lambda_dashboard  = true
  enable_lambda_insights   = true
  
  # Error handling
  dlq_retention_seconds           = 1209600  # 14 days
  create_error_notification_topic = true
  error_notification_email        = "alerts@company.com"
  
  # Data quality thresholds
  data_quality_config = {
    quality_threshold      = 0.8
    min_completeness_score = 0.7
    max_error_rate        = 0.05
  }
  
  # Advanced features
  enable_lambda_versioning    = true
  enable_provisioned_concurrency = true
  enable_gradual_deployment   = true
  
  tags = local.common_tags
}
```

## 🔐 Security Configuration

### IAM Least Privilege

The module creates IAM roles with minimal required permissions:

```hcl
# S3 Access - Limited to specific buckets
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject"
  ],
  "Resource": [
    "arn:aws:s3:::raw-data-bucket/*",
    "arn:aws:s3:::processed-data-bucket/*"
  ]
}

# KMS Access - Limited to data lake key
{
  "Effect": "Allow",
  "Action": [
    "kms:Encrypt",
    "kms:Decrypt",
    "kms:GenerateDataKey"
  ],
  "Resource": "arn:aws:kms:region:account:key/key-id"
}
```

### Encryption

- **At Rest**: CloudWatch Logs encrypted with KMS
- **In Transit**: All API calls use HTTPS/TLS
- **DLQ Encryption**: SQS queues encrypted by default
- **Environment Variables**: Sensitive values encrypted

### Network Security

```hcl
# VPC configuration (optional)
vpc_config = {
  subnet_ids = [
    "subnet-12345678",
    "subnet-87654321"
  ]
  security_group_ids = [
    "sg-lambda-flight-data"
  ]
}
```

## 📊 Monitoring & Observability

### CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| **Function Errors** | > 5 errors in 5 minutes | SNS Alert |
| **Duration** | > 80% of timeout | SNS Alert |
| **Throttles** | > 0 throttles | SNS Alert |
| **DLQ Messages** | > 0 messages | SNS Alert |

### Custom Metrics

The module publishes custom metrics for business logic:

```python
# Example custom metrics in Lambda code
cloudwatch.put_metric_data(
    Namespace='FlightDataPipeline',
    MetricData=[
        {
            'MetricName': 'DataQualityScore',
            'Value': quality_score,
            'Unit': 'Percent'
        },
        {
            'MetricName': 'RecordsProcessed',
            'Value': record_count,
            'Unit': 'Count'
        }
    ]
)
```

### X-Ray Tracing

Enable distributed tracing to understand request flows:

```hcl
enable_xray_tracing = true
```

Traces show:
- API calls to OpenSky Network
- S3 operations
- DynamoDB interactions
- Processing duration
- Error locations

### Lambda Insights

Enhanced monitoring with performance metrics:

```hcl
enable_lambda_insights = true
```

Provides:
- Memory utilization
- CPU usage
- Cold start analysis
- Network performance
- Cost optimization insights

## 🚨 Error Handling & Recovery

### Dead Letter Queues

Each Lambda function has a dedicated DLQ:

```hcl
dead_letter_config {
  target_arn = aws_sqs_queue.ingestion_dlq.arn
}
```

**DLQ Configuration:**
- **Retention**: 14 days (configurable)
- **Encryption**: Enabled by default
- **Monitoring**: CloudWatch alarms on message count
- **Processing**: Manual review and replay

### Retry Logic

EventBridge rules include retry configuration:

```hcl
retry_policy {
  maximum_retry_attempts = 3
  maximum_event_age_in_seconds = 3600
}
```

### Circuit Breaker Pattern

Lambda functions implement circuit breaker logic:

```python
# Example circuit breaker implementation
if error_rate > threshold:
    # Stop processing and alert
    send_circuit_breaker_alert()
    return early_exit_response
```

## 🔄 Deployment & Versioning

### Blue/Green Deployments

```hcl
enable_lambda_versioning = true
enable_gradual_deployment = true

# Routes 10% traffic to new version
routing_config {
  additional_version_weights = {
    "$LATEST" = 0.1
  }
}
```

### Provisioned Concurrency

For consistent performance during high traffic:

```hcl
lambda_config = {
  ingestion = {
    provisioned_concurrency = 2  # Keep 2 instances warm
  }
}
```

**Benefits:**
- Eliminates cold starts
- Consistent response times
- Better user experience
- Higher costs (use judiciously)

## 🎯 Performance Optimization

### Memory Sizing

| Function | Memory | Reasoning |
|----------|--------|-----------|
| **Ingestion** | 512MB | Network I/O bound, minimal processing |
| **Processing** | 1024MB | CPU intensive (pandas, pyarrow) |
| **Validation** | 512MB | Balanced compute and memory usage |

### Timeout Configuration

- **Ingestion**: 60s (API calls + S3 upload)
- **Processing**: 120s (Large file processing)
- **Validation**: 60s (Quality checks)

### Reserved Concurrency

Prevents one function from consuming all account concurrency:

- **Ingestion**: 10 (frequent, scheduled)
- **Processing**: 5 (triggered by S3 events)
- **Validation**: 3 (final step, less frequent)

## 📁 File Structure

```
terraform/modules/lambda/
├── main.tf          # Core Lambda functions and IAM
├── events.tf        # EventBridge and S3 integrations
├── variables.tf     # Input variables
├── outputs.tf       # Module outputs
└── README.md        # This documentation
```

## 🔗 Integration Points

### S3 Data Lake

```hcl
# Automatic S3 event notifications
raw_data_bucket → processing_lambda
processed_data_bucket → validation_lambda
```

### DynamoDB

```hcl
# Execution tracking
dynamodb_table_name = "flight-data-execution-tracking"
```

### SNS Alerts

```hcl
# Quality issues and errors
sns_topic_arn = "arn:aws:sns:region:account:alerts"
```

### EventBridge

```hcl
# Scheduled data ingestion
schedule_expression = "rate(5 minutes)"
```

## 🧪 Testing

### Unit Testing

```bash
# Test Lambda functions locally
sam local invoke IngestionFunction --event events/scheduled-event.json
sam local invoke ProcessingFunction --event events/s3-event.json
sam local invoke ValidationFunction --event events/s3-event.json
```

### Integration Testing

```bash
# Deploy to test environment
terraform apply -var-file="test.tfvars"

# Trigger test data flow
aws events put-events --entries file://test-events.json

# Validate results
aws logs filter-log-events --log-group-name "/aws/lambda/ingestion"
```

### Load Testing

```bash
# Generate high volume of S3 events
aws s3 cp test-data/ s3://raw-data-bucket/load-test/ --recursive

# Monitor CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace "AWS/Lambda" \
  --metric-name "Duration" \
  --dimensions Name=FunctionName,Value=processing-function
```

## 📊 Cost Optimization

### Memory vs Duration Trade-off

```bash
# Monitor cost per invocation
Cost = (Duration × Memory × Requests × $0.0000166667) + (Requests × $0.0000002)

# Example calculation for processing function:
# Duration: 30s, Memory: 1024MB, Requests: 10,000/month
# Cost = (30 × 1024 × 10,000 × $0.0000166667) + (10,000 × $0.0000002)
# Cost = $5.12 + $0.002 = $5.122/month
```

### Optimization Strategies

1. **Right-size Memory**: Monitor actual usage
2. **Optimize Code**: Reduce execution time
3. **Use Layers**: Reduce deployment package size
4. **ARM64 Architecture**: 20% cost savings (if compatible)
5. **Provisioned Concurrency**: Only for latency-sensitive functions

## 🚀 Deployment

### Prerequisites

```bash
# Create deployment packages
cd src/lambda
zip -r ../../deployment-packages/ingestion.zip flight_data_ingestion.py
zip -r ../../deployment-packages/processing.zip flight_data_processor.py
zip -r ../../deployment-packages/validation.zip data_quality_validator.py

# Create Lambda layer
cd layers
zip -r ../shared-dependencies.zip python/
```

### Deploy

```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file="production.tfvars"

# Apply configuration
terraform apply -var-file="production.tfvars"
```

### Update Functions

```bash
# Update function code
aws lambda update-function-code \
  --function-name flight-data-ingestion \
  --zip-file fileb://deployment-packages/ingestion.zip

# Update function configuration
aws lambda update-function-configuration \
  --function-name flight-data-ingestion \
  --memory-size 768
```

## 🤝 Best Practices

1. **Idempotency**: Functions should handle duplicate events
2. **Error Handling**: Comprehensive try/catch with logging
3. **Monitoring**: Custom metrics for business logic
4. **Security**: Least privilege IAM policies
5. **Performance**: Regular optimization reviews
6. **Testing**: Automated testing pipeline
7. **Documentation**: Keep runbooks updated

## 📚 Additional Resources

- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
- [Serverless Framework](https://www.serverless.com/)
- [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)