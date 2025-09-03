# Flight Data Pipeline - Terraform Infrastructure

This directory contains the complete Terraform configuration for deploying the Flight Data Pipeline on AWS.

## 📁 Directory Structure

```
terraform/
├── main.tf                 # Main configuration with provider and data sources
├── variables.tf            # All input variables with validation
├── locals.tf              # Computed values, naming conventions, and tags
├── versions.tf            # Terraform and provider version constraints
├── terraform.tfvars.example  # Example variable values
├── templates/             # Template files for outputs
│   └── outputs.tpl
├── outputs/              # Generated infrastructure summaries
└── environments/         # Environment-specific configurations
    ├── dev/
    │   ├── backend.hcl
    │   └── terraform.tfvars
    ├── staging/
    │   ├── backend.hcl
    │   └── terraform.tfvars
    └── prod/
        ├── backend.hcl
        └── terraform.tfvars
```

## 🚀 Quick Start

### 1. Prerequisites

- Terraform >= 1.5.0
- AWS CLI configured with appropriate permissions
- S3 bucket for Terraform state storage
- DynamoDB table for state locking

### 2. Setup Terraform Backend

Create the state management resources:

```bash
# Create S3 bucket for state storage
aws s3 mb s3://your-terraform-state-bucket-dev --region us-east-1

# Create DynamoDB table for state locking
aws dynamodb create-table \
    --table-name terraform-state-locks-dev \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### 3. Configure Variables

```bash
# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit variables for your environment
vi terraform.tfvars
```

**Required Variables:**
- `alert_email`: Your email address for notifications
- `project_name`: Customize if needed
- `environment`: Set to dev/staging/prod

### 4. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init -backend-config=environments/dev/backend.hcl

# Plan deployment
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply configuration
terraform apply -var-file="environments/dev/terraform.tfvars"
```

## 🏗️ Infrastructure Components

### Core Components
- **S3 Buckets**: Raw and processed data storage
- **Lambda Functions**: Data ingestion, processing, and validation
- **DynamoDB**: Execution tracking and metadata
- **CloudWatch**: Logging, monitoring, and dashboards
- **SNS**: Alert notifications
- **IAM**: Roles and policies with least privilege

### Optional Components
- **RDS**: PostgreSQL for advanced analytics
- **VPC**: Network isolation (production recommended)
- **API Gateway**: REST API access
- **Kinesis**: Real-time data streaming
- **Glue**: Data catalog and ETL

## 🌍 Multi-Environment Support

### Environment Configurations

| Environment | Purpose | Resource Sizing | Monitoring | Cost Optimization |
|------------|---------|-----------------|------------|------------------|
| **dev** | Development & testing | Minimal (256MB Lambda) | Basic | Aggressive |
| **staging** | Pre-production validation | Medium (512MB Lambda) | Full | Balanced |
| **prod** | Production workloads | Full (1024MB Lambda) | Comprehensive | Intelligent |

### Environment-Specific Features

**Development:**
- Auto-shutdown at 8 PM
- Short data retention (7 days)
- Debug logging enabled
- Reduced monitoring costs

**Staging:**
- Production-like configuration
- Full monitoring enabled
- Medium data retention
- API Gateway testing

**Production:**
- High availability features
- Extended data retention (7 years)
- Enhanced security (VPC, KMS)
- 24/7 monitoring and alerting

## 🔧 Configuration Options

### Lambda Configuration
```hcl
lambda_config = {
  ingestion = {
    memory_size          = 512    # MB
    timeout              = 300    # seconds
    reserved_concurrency = 10     # max concurrent executions
  }
  processing = {
    memory_size          = 1024   # MB for pandas operations
    timeout              = 900    # seconds (15 minutes)
    reserved_concurrency = 5
  }
  validation = {
    memory_size          = 768    # MB for data analysis
    timeout              = 600    # seconds (10 minutes)
    reserved_concurrency = 3
  }
  runtime                = "python3.11"
  architecture          = "x86_64"  # or "arm64" for cost savings
  log_retention_days    = 14
  enable_xray_tracing   = false
}
```

### S3 Configuration
```hcl
s3_config = {
  enable_versioning          = true
  enable_encryption         = true
  raw_data_expiration_days  = 90    # Delete raw data after 90 days
  processed_data_expiration_days = 365  # Keep processed data 1 year
  enable_access_logging     = true  # For audit compliance
}
```

### Data Quality Thresholds
```hcl
data_processing_config = {
  quality_threshold        = 0.8   # Overall quality score (80%)
  min_completeness_score   = 0.7   # Minimum field completeness (70%)
  max_error_rate          = 0.05   # Maximum error rate (5%)
  batch_size              = 100    # Records per processing batch
}
```

## 🔒 Security Best Practices

### IAM Security
- Least privilege access policies
- Separate roles for each Lambda function
- Cross-service permissions limited to required resources
- IAM path prefixes for organization

### Data Security
- Encryption at rest (S3, DynamoDB)
- Encryption in transit (HTTPS, TLS)
- VPC isolation (optional)
- KMS key management (custom keys for production)

### Network Security
```hcl
security_config = {
  create_vpc               = true   # Network isolation
  enable_vpc_endpoints     = true   # Avoid NAT gateway costs
  block_public_acls       = true    # S3 security
  restrict_public_buckets = true
}
```

## 💰 Cost Optimization

### Development Optimizations
- ARM64 architecture (20% cost savings)
- Reduced Lambda memory allocations
- Short log retention periods
- Auto-shutdown scheduling
- Disabled detailed monitoring

### Production Optimizations
- S3 Intelligent Tiering
- Lifecycle policies for data archival
- Reserved capacity for predictable workloads
- CloudWatch cost monitoring with alerts

### Cost Monitoring
```hcl
monitoring_config = {
  enable_cost_monitoring  = true
  cost_threshold_usd     = 100    # Alert at $100/month
}
```

## 📊 Monitoring & Alerting

### CloudWatch Dashboards
Automatically created dashboards include:
- Lambda performance metrics
- S3 request metrics and errors
- DynamoDB read/write capacity
- Data quality scores
- Cost tracking

### Alert Configuration
```hcl
# Email alerts
alert_email = "team@company.com"

# SMS alerts (production critical alerts)
alert_phone_number = "+1234567890"

# Alert thresholds
monitoring_thresholds = {
  lambda_error_rate_threshold   = 0.01  # 1% error rate
  data_quality_score_threshold = 0.8   # 80% quality minimum
}
```

## 🔄 Deployment Workflows

### Development Deployment
```bash
cd terraform
terraform workspace select dev
terraform init -backend-config=environments/dev/backend.hcl
terraform plan -var-file="environments/dev/terraform.tfvars"
terraform apply -var-file="environments/dev/terraform.tfvars" -auto-approve
```

### Production Deployment
```bash
cd terraform
terraform workspace select prod
terraform init -backend-config=environments/prod/backend.hcl
terraform plan -var-file="environments/prod/terraform.tfvars"
# Manual approval required for production
terraform apply -var-file="environments/prod/terraform.tfvars"
```

### State Management Commands
```bash
# List all resources
terraform state list

# Show resource details
terraform state show aws_s3_bucket.raw_data

# Import existing resource
terraform import aws_s3_bucket.existing_bucket bucket-name

# Refresh state from AWS
terraform refresh
```

## 🐛 Troubleshooting

### Common Issues

**Backend Configuration Error:**
```bash
# Error: Backend configuration changed
terraform init -reconfigure -backend-config=environments/dev/backend.hcl
```

**State Lock Issues:**
```bash
# Force unlock (use carefully)
terraform force-unlock LOCK_ID
```

**Variable Validation Errors:**
- Check `terraform.tfvars` values against validation rules
- Ensure email addresses are valid format
- Verify AWS region names
- Check memory/timeout ranges for Lambda functions

### Debugging
```bash
# Enable debug logging
export TF_LOG=DEBUG
terraform plan

# Validate configuration
terraform validate

# Format configuration
terraform fmt -recursive
```

## 📝 Best Practices

### State Management
1. Use remote state storage (S3)
2. Enable state locking (DynamoDB)
3. Use workspaces for environments
4. Regular state backups

### Variable Management
1. Never commit `terraform.tfvars` to version control
2. Use environment-specific variable files
3. Implement variable validation
4. Document all variables

### Security
1. Enable encryption for all data stores
2. Use least privilege IAM policies
3. Regular security reviews
4. Implement network isolation for production

### Monitoring
1. Enable CloudWatch logging for all resources
2. Set up cost monitoring and alerting
3. Create environment-specific dashboards
4. Regular resource utilization reviews

## 📚 Additional Resources

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [CloudWatch Monitoring Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/)

## 🤝 Contributing

1. Follow Terraform style guidelines
2. Validate all configurations before committing
3. Update documentation for any changes
4. Test in development environment first
5. Use descriptive commit messages