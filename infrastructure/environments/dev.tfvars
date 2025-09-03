# Development Environment Configuration
# This file contains environment-specific variables for the development environment

# Environment identification
environment = "dev"
application_name = "flightdata-pipeline"

# AWS Configuration
aws_region = "us-east-1"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Networking Configuration
vpc_cidr = "10.1.0.0/16"
private_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
public_subnet_cidrs = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]

# Lambda Configuration
lambda_timeout = 300
lambda_memory_size = 512
lambda_reserved_concurrency = 10
lambda_provisioned_concurrency = 0  # No provisioned concurrency for dev

# DynamoDB Configuration
dynamodb_billing_mode = "PAY_PER_REQUEST"  # On-demand for cost savings in dev
dynamodb_read_capacity = 5
dynamodb_write_capacity = 5
dynamodb_enable_point_in_time_recovery = true
dynamodb_backup_retention_days = 7

# S3 Configuration
s3_versioning_enabled = true
s3_lifecycle_enabled = true
s3_transition_to_ia_days = 30
s3_transition_to_glacier_days = 90
s3_expiration_days = 365

# API Gateway Configuration
api_gateway_stage_name = "dev"
api_gateway_throttle_rate_limit = 100
api_gateway_throttle_burst_limit = 200
api_gateway_enable_caching = false
api_gateway_cache_ttl = 300

# CloudWatch Configuration
log_retention_days = 7
enable_detailed_monitoring = false
cloudwatch_alarm_evaluation_periods = 2
cloudwatch_alarm_datapoints_to_alarm = 2

# SNS Configuration
enable_sns_alerts = true
sns_alert_email = "dev-alerts@flightdata-pipeline.com"

# Security Configuration
enable_waf = false  # Disable WAF for dev to reduce costs
enable_cloudtrail = true
enable_config = false  # Disable Config for dev to reduce costs
kms_key_rotation = false  # Disable key rotation for dev

# Data Processing Configuration
processing_schedule_enabled = true
processing_schedule_expression = "rate(30 minutes)"  # More frequent for dev testing
batch_size = 100
max_processing_time_minutes = 15

# External API Configuration
opensky_api_rate_limit = 10  # requests per minute
opensky_api_timeout = 30  # seconds
opensky_api_retry_attempts = 3

# Monitoring and Alerting Thresholds
error_rate_threshold = 10.0  # Higher threshold for dev
latency_threshold_ms = 5000   # Higher threshold for dev
cost_alert_threshold = 50.0   # Lower threshold for dev ($50/month)

# Backup Configuration
backup_schedule = "cron(0 2 * * ? *)"  # Daily at 2 AM UTC
backup_retention_days = 7
enable_cross_region_backup = false  # Disable for dev to reduce costs

# Tags
tags = {
  Environment = "dev"
  Project     = "flightdata-pipeline"
  Owner       = "development-team"
  CostCenter  = "engineering"
  Purpose     = "development-testing"
  Backup      = "daily"
}

# Feature Flags
enable_experimental_features = true
enable_debug_logging = true
enable_performance_insights = false
enable_enhanced_monitoring = false