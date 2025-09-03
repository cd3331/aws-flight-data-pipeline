# Production Environment Configuration
# This file contains environment-specific variables for the production environment

# Environment identification
environment = "production"
application_name = "flightdata-pipeline"

# AWS Configuration
aws_region = "us-east-1"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Networking Configuration
vpc_cidr = "10.0.0.0/16"
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnet_cidrs = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

# Lambda Configuration
lambda_timeout = 900  # 15 minutes maximum
lambda_memory_size = 2048
lambda_reserved_concurrency = 100
lambda_provisioned_concurrency = 20  # Provisioned concurrency for consistent performance

# DynamoDB Configuration
dynamodb_billing_mode = "PROVISIONED"  # Provisioned for production workloads
dynamodb_read_capacity = 100
dynamodb_write_capacity = 100
dynamodb_enable_point_in_time_recovery = true
dynamodb_backup_retention_days = 90  # 3 months retention

# S3 Configuration
s3_versioning_enabled = true
s3_lifecycle_enabled = true
s3_transition_to_ia_days = 30
s3_transition_to_glacier_days = 90
s3_transition_to_deep_archive_days = 365
s3_expiration_days = 2555  # 7 years retention for compliance

# API Gateway Configuration
api_gateway_stage_name = "prod"
api_gateway_throttle_rate_limit = 2000
api_gateway_throttle_burst_limit = 4000
api_gateway_enable_caching = true
api_gateway_cache_ttl = 600  # 10 minutes cache

# CloudWatch Configuration
log_retention_days = 90  # 3 months retention
enable_detailed_monitoring = true
cloudwatch_alarm_evaluation_periods = 3
cloudwatch_alarm_datapoints_to_alarm = 2

# SNS Configuration
enable_sns_alerts = true
sns_alert_email = "production-alerts@flightdata-pipeline.com"
sns_alert_sms = "+1-555-0123"  # Production SMS alerts

# Security Configuration
enable_waf = true  # Enable WAF for production
enable_cloudtrail = true
enable_config = true  # Enable Config for compliance
kms_key_rotation = true  # Enable key rotation
enable_guardduty = true  # Enable GuardDuty for threat detection
enable_security_hub = true  # Enable Security Hub

# Data Processing Configuration
processing_schedule_enabled = true
processing_schedule_expression = "rate(10 minutes)"  # High frequency for production
batch_size = 1000  # Larger batches for efficiency
max_processing_time_minutes = 45

# External API Configuration
opensky_api_rate_limit = 60  # requests per minute
opensky_api_timeout = 30  # seconds
opensky_api_retry_attempts = 5
opensky_api_circuit_breaker_enabled = true

# Monitoring and Alerting Thresholds (Strict for production)
error_rate_threshold = 1.0   # 1% error rate threshold
latency_threshold_ms = 2000  # 2 seconds latency threshold
cost_alert_threshold = 1000.0  # $1000/month alert
budget_limit = 1500.0  # $1500/month budget limit

# Backup Configuration
backup_schedule = "cron(0 0 * * ? *)"  # Daily at midnight UTC
backup_retention_days = 90
enable_cross_region_backup = true
backup_vault_kms_encryption = true

# Auto Scaling Configuration
dynamodb_enable_autoscaling = true
dynamodb_min_read_capacity = 20
dynamodb_max_read_capacity = 500
dynamodb_min_write_capacity = 20
dynamodb_max_write_capacity = 500
dynamodb_target_utilization = 70

# Load Testing Configuration (for canary deployments)
enable_canary_deployments = true
canary_traffic_percentage = 10
canary_duration_minutes = 30

# Multi-AZ Configuration
enable_multi_az = true
enable_cross_region_replication = true
backup_region = "us-west-2"

# Performance Configuration
enable_x_ray_tracing = true
enable_enhanced_monitoring = true
enable_performance_insights = true

# Disaster Recovery Configuration
enable_disaster_recovery = true
rto_minutes = 240  # 4 hours recovery time objective
rpo_minutes = 60   # 1 hour recovery point objective

# Compliance Configuration
enable_compliance_monitoring = true
compliance_frameworks = ["SOC2", "PCI-DSS", "HIPAA"]
enable_data_encryption_at_rest = true
enable_data_encryption_in_transit = true

# Tags
tags = {
  Environment = "production"
  Project     = "flightdata-pipeline"
  Owner       = "platform-team"
  CostCenter  = "operations"
  Purpose     = "production-workload"
  Backup      = "daily"
  Compliance  = "required"
  Criticality = "high"
  SLA         = "99.9%"
  DataClass   = "confidential"
}

# Feature Flags
enable_experimental_features = false  # No experimental features in production
enable_debug_logging = false
enable_performance_insights = true
enable_enhanced_monitoring = true
enable_cost_optimization = true

# Network Security
enable_vpc_flow_logs = true
enable_network_acls = true
enable_security_groups_logging = true

# Data Retention Policies
log_data_retention_years = 7
metrics_data_retention_years = 2
backup_data_retention_years = 7

# Operational Configuration
maintenance_window = "sun:03:00-sun:04:00"  # Sunday 3-4 AM UTC
patch_schedule = "cron(0 4 ? * SUN *)"  # Sunday 4 AM UTC
health_check_grace_period = 300  # 5 minutes

# Cost Optimization
enable_s3_intelligent_tiering = true
enable_lambda_cost_optimization = true
enable_scheduled_scaling = true
reserved_capacity_percentage = 50  # 50% reserved instances for cost savings