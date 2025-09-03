# Staging Environment Configuration
# This file contains environment-specific variables for the staging environment

# Environment identification
environment = "staging"
application_name = "flightdata-pipeline"

# AWS Configuration
aws_region = "us-east-1"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Networking Configuration
vpc_cidr = "10.2.0.0/16"
private_subnet_cidrs = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
public_subnet_cidrs = ["10.2.101.0/24", "10.2.102.0/24", "10.2.103.0/24"]

# Lambda Configuration
lambda_timeout = 600
lambda_memory_size = 1024
lambda_reserved_concurrency = 50
lambda_provisioned_concurrency = 5  # Some provisioned concurrency for staging

# DynamoDB Configuration
dynamodb_billing_mode = "PROVISIONED"  # Provisioned for more predictable performance
dynamodb_read_capacity = 25
dynamodb_write_capacity = 25
dynamodb_enable_point_in_time_recovery = true
dynamodb_backup_retention_days = 30

# S3 Configuration
s3_versioning_enabled = true
s3_lifecycle_enabled = true
s3_transition_to_ia_days = 30
s3_transition_to_glacier_days = 90
s3_expiration_days = 730  # 2 years retention

# API Gateway Configuration
api_gateway_stage_name = "staging"
api_gateway_throttle_rate_limit = 500
api_gateway_throttle_burst_limit = 1000
api_gateway_enable_caching = true
api_gateway_cache_ttl = 300

# CloudWatch Configuration
log_retention_days = 30
enable_detailed_monitoring = true
cloudwatch_alarm_evaluation_periods = 2
cloudwatch_alarm_datapoints_to_alarm = 2

# SNS Configuration
enable_sns_alerts = true
sns_alert_email = "staging-alerts@flightdata-pipeline.com"

# Security Configuration
enable_waf = true  # Enable WAF for staging
enable_cloudtrail = true
enable_config = true  # Enable Config for compliance testing
kms_key_rotation = true  # Enable key rotation for staging

# Data Processing Configuration
processing_schedule_enabled = true
processing_schedule_expression = "rate(15 minutes)"  # Similar to production frequency
batch_size = 500
max_processing_time_minutes = 30

# External API Configuration
opensky_api_rate_limit = 30  # requests per minute
opensky_api_timeout = 30  # seconds
opensky_api_retry_attempts = 3

# Monitoring and Alerting Thresholds
error_rate_threshold = 5.0   # Lower threshold for staging
latency_threshold_ms = 3000  # Lower threshold for staging
cost_alert_threshold = 200.0 # $200/month alert

# Backup Configuration
backup_schedule = "cron(0 1 * * ? *)"  # Daily at 1 AM UTC
backup_retention_days = 30
enable_cross_region_backup = true  # Enable cross-region backup

# Auto Scaling Configuration
dynamodb_enable_autoscaling = true
dynamodb_min_read_capacity = 5
dynamodb_max_read_capacity = 100
dynamodb_min_write_capacity = 5
dynamodb_max_write_capacity = 100
dynamodb_target_utilization = 70

# Tags
tags = {
  Environment = "staging"
  Project     = "flightdata-pipeline"
  Owner       = "qa-team"
  CostCenter  = "engineering"
  Purpose     = "pre-production-testing"
  Backup      = "daily"
  Compliance  = "required"
}

# Feature Flags
enable_experimental_features = false  # Disable experimental features in staging
enable_debug_logging = false
enable_performance_insights = true
enable_enhanced_monitoring = true