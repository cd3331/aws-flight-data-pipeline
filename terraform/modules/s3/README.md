# S3 Data Lake Module

This Terraform module creates a comprehensive three-tier S3 data lake architecture optimized for the flight data pipeline with advanced cost optimization, security, and monitoring features.

## 🏗️ Architecture Overview

### Three-Tier Data Lake (Medallion Architecture)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   BRONZE LAYER  │    │  SILVER LAYER   │    │   GOLD LAYER    │
│   (Raw Data)    │───▶│ (Processed Data)│───▶│ (Query Results) │
│                 │    │                 │    │                 │
│ • JSON files    │    │ • Parquet files │    │ • Athena results│
│ • High volume   │    │ • Optimized     │    │ • Curated data  │
│ • Short retention│    │ • Analytics     │    │ • Temporary     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Layer Details

| Layer | Purpose | Format | Retention | Access Pattern |
|-------|---------|--------|-----------|----------------|
| **Bronze** | Raw flight data ingestion | JSON | 90 days | Write-heavy, infrequent reads |
| **Silver** | Cleaned & transformed data | Parquet | 7 years | Read-heavy analytics workloads |
| **Gold** | Query results & reports | Mixed | 30 days | Temporary analytical outputs |

## 🚀 Features

### Core Components
- ✅ **Three S3 buckets** with appropriate configurations
- ✅ **KMS encryption** with custom key management
- ✅ **Versioning** for data protection
- ✅ **Lifecycle policies** for cost optimization
- ✅ **Event notifications** for Lambda triggers
- ✅ **Intelligent Tiering** for automatic cost savings

### Security Features
- 🔒 **Encryption at rest** with KMS
- 🔒 **Encryption in transit** with SSL/TLS
- 🔒 **Bucket policies** enforcing security
- 🔒 **Public access blocked** on all buckets
- 🔒 **IAM permissions** with least privilege
- 🔒 **Object lock** for compliance (prod)

### Cost Optimization
- 💰 **Intelligent Tiering** for automatic savings
- 💰 **Lifecycle transitions** (Standard → IA → Glacier → Deep Archive)
- 💰 **Multipart upload cleanup**
- 💰 **Non-current version management**
- 💰 **Inventory reporting** for cost analysis
- 💰 **Requester pays** option (prod)

### Monitoring & Analytics
- 📊 **CloudWatch metrics** and alarms
- 📊 **Access logging** for audit trails
- 📊 **S3 inventory** for cost analysis
- 📊 **Analytics configurations** for usage insights
- 📊 **Request metrics** for performance monitoring

## 📋 Usage

### Basic Usage

```hcl
module "s3_data_lake" {
  source = "./modules/s3"
  
  project_name = "flight-data-pipeline"
  environment  = "prod"
  
  tags = {
    Project     = "FlightDataPipeline"
    Environment = "prod"
    Owner       = "DataTeam"
  }
}
```

### Advanced Configuration

```hcl
module "s3_data_lake" {
  source = "./modules/s3"
  
  # Core configuration
  project_name = "flight-data-pipeline"
  environment  = "prod"
  bucket_suffix = "abc123"
  
  # Encryption
  create_kms_key          = true
  enable_key_rotation     = true
  kms_key_deletion_window = 30
  
  # Versioning
  enable_versioning         = true
  enable_versioning_athena  = false
  
  # Cost optimization
  enable_intelligent_tiering = true
  
  lifecycle_policies = {
    raw_data = {
      ia_transition_days              = 30
      glacier_transition_days         = 30
      deep_archive_transition_days    = 90
      expiration_days                 = 365
      noncurrent_version_expiration_days = 30
      multipart_upload_days          = 1
    }
    processed_data = {
      ia_transition_days              = 14
      glacier_transition_days         = 90
      deep_archive_transition_days    = 365
      expiration_days                 = 2555  # 7 years
      noncurrent_version_expiration_days = 90
      multipart_upload_days          = 7
    }
    athena_results = {
      ia_transition_days       = 3
      expiration_days         = 30
      curated_expiration_days = 365
      multipart_upload_days   = 1
    }
  }
  
  # Event notifications
  enable_event_notifications     = true
  processing_lambda_arn          = module.lambda.processing_function_arn
  processing_lambda_function_name = module.lambda.processing_function_name
  validation_lambda_arn          = module.lambda.validation_function_arn
  validation_lambda_function_name = module.lambda.validation_function_name
  
  # Security and compliance
  enable_access_logging        = true
  access_log_retention_days   = 90
  enable_cross_region_replication = true
  replication_destination_bucket_arn = "arn:aws:s3:::backup-bucket"
  
  # Monitoring
  enable_request_metrics = true
  enable_inventory      = true
  
  tags = local.common_tags
}
```

## 🔧 Configuration Options

### Environment-Specific Defaults

The module automatically adjusts configurations based on the environment:

#### Development (`environment = "dev"`)
- Shorter retention periods (7-30 days)
- Aggressive lifecycle transitions
- Versioning disabled for cost savings
- Minimal monitoring
- No cross-region replication

#### Staging (`environment = "staging"`)  
- Medium retention periods (30-180 days)
- Balanced lifecycle policies
- Full versioning enabled
- Standard monitoring
- Optional replication

#### Production (`environment = "prod"`)
- Extended retention (1-7 years)
- Conservative transitions
- Enhanced security features
- Comprehensive monitoring
- Cross-region replication enabled

### Lifecycle Policy Examples

#### Aggressive Cost Optimization (Raw Data)
```
Day 0:   STANDARD
Day 7:   STANDARD_IA (40% cost reduction)
Day 30:  GLACIER (68% cost reduction)
Day 90:  DEEP_ARCHIVE (77% cost reduction)
Day 365: DELETION
```

#### Analytics Optimized (Processed Data)
```
Day 0:   STANDARD
Day 14:  STANDARD_IA
Day 90:  GLACIER
Day 365: DEEP_ARCHIVE
Day 2555: DELETION (7 years for compliance)
```

#### Quick Cleanup (Query Results)
```
Day 0:  STANDARD
Day 3:  STANDARD_IA
Day 30: DELETION
```

## 💰 Cost Optimization Features

### Intelligent Tiering
Automatically moves objects between access tiers based on usage patterns:
- **Frequent Access**: Standard pricing
- **Infrequent Access**: 40% savings after 30 days
- **Archive Access**: 68% savings after 90 days
- **Deep Archive Access**: 77% savings after 180 days

### Lifecycle Transitions
- **Standard to IA**: 40% storage cost reduction
- **IA to Glacier**: Additional 68% reduction
- **Glacier to Deep Archive**: Up to 77% total reduction

### Cost Monitoring
- S3 Analytics for storage class recommendations
- Inventory reports for detailed cost analysis
- CloudWatch metrics for usage tracking
- Request metrics for optimization insights

## 🔒 Security Best Practices

### Encryption
- **At Rest**: KMS encryption with customer-managed keys
- **In Transit**: SSL/TLS required for all requests
- **Key Rotation**: Automatic annual rotation
- **Bucket Keys**: Enabled for cost optimization

### Access Control
- **Bucket Policies**: Enforce encryption and SSL
- **Public Access**: Completely blocked
- **Service Access**: Least-privilege for AWS services
- **Cross-Account**: Optional with external ID

### Compliance
- **Object Lock**: Governance mode for data retention
- **MFA Delete**: Production environments (manual setup)
- **Access Logging**: Complete audit trail
- **Versioning**: Protection against accidental deletion

## 📊 Monitoring & Alerting

### CloudWatch Metrics
- **Storage Metrics**: Size, object count by storage class
- **Request Metrics**: GET, PUT, DELETE operations
- **Error Metrics**: 4XX and 5XX response codes
- **Data Retrieval**: Glacier/Deep Archive restore costs

### Cost Alerts
Configure CloudWatch alarms for:
- Monthly storage costs exceed threshold
- High request costs (PUT/POST operations)
- Data transfer costs (cross-region)
- Retrieval costs from archive tiers

### Performance Monitoring
- Request latency and throughput
- Error rates by operation type
- Transfer acceleration effectiveness
- Multipart upload success rates

## 🚨 Event Notifications

### Supported Events
- **Object Created**: Triggers data processing pipeline
- **Object Deleted**: Audit and compliance tracking
- **Restore Initiated**: Glacier/Deep Archive retrieval
- **Replication Failed**: Cross-region sync issues

### Integration Points
- **Lambda Functions**: Automatic data processing
- **SNS Topics**: Team notifications
- **SQS Queues**: Decoupled processing
- **EventBridge**: Complex routing logic

## 🔄 Disaster Recovery

### Cross-Region Replication
- **Source**: Processed data bucket (critical data)
- **Destination**: Secondary region bucket
- **Storage Class**: Standard-IA for cost efficiency
- **Encryption**: Replica encrypted with destination KMS key

### Backup Strategy
- **Versioning**: Protection against corruption
- **Cross-Region**: Geographic redundancy
- **Lifecycle**: Automated archive management
- **Point-in-Time**: Version-based recovery

## 📈 Performance Optimization

### Transfer Acceleration
- **CloudFront Edge Locations**: Faster uploads
- **Global Distribution**: Reduced latency
- **Cost Consideration**: Additional transfer charges
- **Use Case**: High-volume ingestion workloads

### Request Optimization
- **Prefix Distribution**: Avoid hot-spotting
- **Multipart Uploads**: Better performance for large files
- **Request Rate**: Gradual ramp-up for new prefixes
- **Batch Operations**: Bulk operations for efficiency

## 🧪 Testing and Validation

### Deployment Testing
```bash
# Validate configuration
terraform validate

# Plan deployment
terraform plan -var-file="testing.tfvars"

# Apply with approval
terraform apply -var-file="testing.tfvars"

# Test bucket access
aws s3 ls s3://your-raw-data-bucket/
```

### Data Pipeline Testing
```bash
# Upload test data
aws s3 cp test-data.json s3://raw-data-bucket/year=2024/month=01/day=01/

# Verify event notification triggered
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/processing"

# Check processed output
aws s3 ls s3://processed-data-bucket/year=2024/month=01/day=01/
```

## 📚 Outputs

### Bucket Information
```hcl
# Access bucket details
bucket_names = module.s3_data_lake.bucket_names
bucket_arns  = module.s3_data_lake.bucket_arns

# Use in other resources
resource "aws_iam_policy" "lambda_s3_access" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = "${module.s3_data_lake.bucket_arns.raw_data}/*"
      }
    ]
  })
}
```

### Security Configuration
```hcl
# KMS key for other services
kms_key_arn = module.s3_data_lake.kms_key.arn

# Use in Lambda environment
environment = {
  RAW_BUCKET_NAME = module.s3_data_lake.bucket_names.raw_data
  KMS_KEY_ID     = module.s3_data_lake.kms_key.key_id
}
```

## 🤝 Contributing

1. Follow Terraform best practices
2. Update documentation for changes
3. Test in development environment
4. Validate cost impact
5. Security review required

## 📄 License

This module is part of the Flight Data Pipeline project.