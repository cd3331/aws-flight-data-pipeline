# Staging Environment Configuration
# This file contains environment-specific variable values for staging (pre-production)

#==============================================================================
# CORE CONFIGURATION
#==============================================================================

project_name = "flight-data-pipeline"
environment  = "staging"
aws_region   = "us-east-1"

# Replace with your staging alerts email
alert_email = "staging-alerts@example.com"
alert_phone_number = "+1234567890"  # Optional: SMS for critical alerts

#==============================================================================
# STAGING LAMBDA CONFIGURATION - PRODUCTION-LIKE
#==============================================================================

lambda_config = {
  # Production-like settings for realistic testing
  ingestion = {
    memory_size          = 384    # 75% of production
    timeout              = 240    # 4 minutes
    reserved_concurrency = 5     # Moderate concurrency
  }
  
  processing = {
    memory_size          = 768    # 75% of production
    timeout              = 720    # 12 minutes
    reserved_concurrency = 3     # Moderate concurrency
  }
  
  validation = {
    memory_size          = 512    # 75% of production
    timeout              = 450    # 7.5 minutes
    reserved_concurrency = 2     # Limited concurrency
  }
  
  runtime                = "python3.11"
  architecture          = "x86_64"
  log_retention_days    = 14     # Medium retention
  enable_xray_tracing   = true   # Enable for testing
  environment_variables = {
    LOG_LEVEL = "INFO"
  }
}

#==============================================================================
# STAGING S3 CONFIGURATION
#==============================================================================

s3_config = {
  enable_versioning    = true    # Enable for testing data recovery
  enable_encryption   = true
  kms_key_id         = "arn:aws:kms:*:*:alias/aws/s3"
  
  # Moderate retention periods
  enable_lifecycle_rules        = true
  raw_data_expiration_days     = 30    # 1 month
  processed_data_expiration_days = 120  # 4 months
  incomplete_multipart_days    = 3
  
  # Security settings (always enabled)
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  
  # Enable monitoring for staging validation
  enable_access_logging   = true
  enable_request_metrics  = true
}

#==============================================================================
# STAGING DATABASE CONFIGURATION
#==============================================================================

dynamodb_config = {
  billing_mode            = "PAY_PER_REQUEST"
  read_capacity_units    = 0
  write_capacity_units   = 0
  enable_point_in_time_recovery = true   # Enable for data protection
  enable_server_side_encryption = true
  ttl_attribute          = "ttl"
  ttl_enabled           = true
}

# Optional RDS for staging testing
create_rds_instance = false

rds_config = {
  engine_version          = "15.4"
  instance_class         = "db.t3.small"   # Slightly larger than dev
  allocated_storage      = 20
  max_allocated_storage  = 50
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  multi_az              = false           # Single AZ for staging
  publicly_accessible   = false
  deletion_protection   = true            # Protect staging data
}

#==============================================================================
# STAGING MONITORING - PRODUCTION-LIKE
#==============================================================================

monitoring_config = {
  log_retention_days        = 14    # 2 weeks
  enable_log_insights      = true
  enable_custom_metrics    = true   # Full monitoring
  enable_detailed_monitoring = true  # Enable for performance testing
  create_dashboard         = true
  dashboard_widgets        = ["lambda", "s3", "dynamodb", "errors", "performance"]
  enable_cost_monitoring   = true
  cost_threshold_usd       = 75     # Medium threshold
}

#==============================================================================
# STAGING SECURITY CONFIGURATION
#==============================================================================

security_config = {
  enable_least_privilege_iam   = true
  iam_path_prefix             = "/flight-data-pipeline-staging/"
  create_vpc                  = false  # Use default VPC
  vpc_cidr                   = "10.1.0.0/16"
  enable_nat_gateway         = false
  enable_vpc_endpoints       = false
  enable_encryption_at_rest  = true
  enable_encryption_in_transit = true
  create_kms_key             = false  # Use AWS managed keys
}

#==============================================================================
# STAGING COST OPTIMIZATION - BALANCED
#==============================================================================

cost_optimization = {
  # Balanced cost optimization
  enable_intelligent_tiering     = false
  enable_glacier_transitions     = false
  enable_provisioned_concurrency = false
  use_arm_architecture          = false
  disable_detailed_monitoring   = false  # Keep monitoring enabled
  reduce_log_retention          = false
  environment_auto_shutdown     = false  # No auto-shutdown in staging
  auto_shutdown_schedule        = "cron(0 22 * * ? *)"
}

#==============================================================================
# STAGING FEATURE FLAGS - FULL TESTING
#==============================================================================

feature_flags = {
  enable_data_ingestion    = true
  enable_data_processing   = true
  enable_data_validation   = true
  enable_monitoring        = true
  enable_alerting         = true   # Full alerting for testing
  enable_api_gateway      = true   # Test API features
  enable_kinesis_streaming = false # Optional advanced features
  enable_glue_catalog     = false
}

#==============================================================================
# STAGING DATA PROCESSING - PRODUCTION-LIKE
#==============================================================================

data_processing_config = {
  batch_size                = 75     # Moderate batch size
  max_batch_window_seconds = 45
  quality_threshold        = 0.8     # Production threshold
  min_completeness_score   = 0.7
  max_error_rate          = 0.05     # Production-like error rate
  max_retry_attempts      = 3
  dead_letter_queue_retention_days = 7
  parallel_processing_enabled = true
  max_concurrent_executions   = 5
}

#==============================================================================
# STAGING DEVELOPMENT CONFIGURATION
#==============================================================================

development_config = {
  enable_debug_logging      = false  # Production-like logging
  create_test_resources     = true   # Additional test resources
  allow_destructive_changes = false  # Protect staging environment
  enable_local_development  = false
}

#==============================================================================
# STAGING-SPECIFIC SETTINGS
#==============================================================================

opensky_api_config = {
  base_url              = "https://opensky-network.org/api"
  request_timeout       = 30
  max_retries          = 3
  rate_limit_per_hour  = 4000
  enable_authentication = false
}

#==============================================================================
# ADDITIONAL STAGING TAGS
#==============================================================================

additional_tags = {
  Purpose           = "Staging"
  TestingEnvironment = "Pre-Production"
  DataRetention     = "Medium"
  MonitoringLevel   = "Full"
  BackupStrategy    = "Standard"
}

# Staging specific settings
create_output_file = true   # Generate infrastructure summary
enable_sns_alerts  = true   # Enable alerts for testing notification flow