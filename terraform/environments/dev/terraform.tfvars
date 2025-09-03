# Development Environment Configuration
# This file contains environment-specific variable values for development

#==============================================================================
# CORE CONFIGURATION
#==============================================================================

project_name = "flight-data-pipeline"
environment  = "dev"
aws_region   = "us-east-1"

# Replace with your email address
alert_email = "dev-team@example.com"

#==============================================================================
# DEVELOPMENT-OPTIMIZED LAMBDA CONFIGURATION
#==============================================================================

lambda_config = {
  # Reduced memory and concurrency for cost optimization
  ingestion = {
    memory_size          = 256    # Reduced for dev
    timeout              = 180    # 3 minutes
    reserved_concurrency = 2     # Low concurrency
  }
  
  processing = {
    memory_size          = 512    # Reduced for dev
    timeout              = 600    # 10 minutes
    reserved_concurrency = 1     # Sequential processing
  }
  
  validation = {
    memory_size          = 384    # Reduced for dev
    timeout              = 300    # 5 minutes
    reserved_concurrency = 1     # Single concurrent execution
  }
  
  runtime                = "python3.11"
  architecture          = "x86_64"
  log_retention_days    = 7      # Short retention for dev
  enable_xray_tracing   = true   # Enable debugging
  environment_variables = {
    LOG_LEVEL = "DEBUG"
  }
}

#==============================================================================
# DEVELOPMENT S3 CONFIGURATION
#==============================================================================

s3_config = {
  enable_versioning    = false   # Disabled for cost savings
  enable_encryption   = true
  kms_key_id         = "arn:aws:kms:*:*:alias/aws/s3"
  
  # Short retention periods for development
  enable_lifecycle_rules        = true
  raw_data_expiration_days     = 7     # Delete after 1 week
  processed_data_expiration_days = 30   # Delete after 1 month
  incomplete_multipart_days    = 1     # Clean up quickly
  
  # Security settings (always enabled)
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  
  # Monitoring disabled for cost savings
  enable_access_logging   = false
  enable_request_metrics  = false
}

#==============================================================================
# DEVELOPMENT DATABASE CONFIGURATION
#==============================================================================

dynamodb_config = {
  billing_mode            = "PAY_PER_REQUEST"
  read_capacity_units    = 0
  write_capacity_units   = 0
  enable_point_in_time_recovery = false
  enable_server_side_encryption = true
  ttl_attribute          = "ttl"
  ttl_enabled           = true
}

# No RDS in development
create_rds_instance = false

#==============================================================================
# DEVELOPMENT MONITORING
#==============================================================================

monitoring_config = {
  log_retention_days        = 7     # Short retention
  enable_log_insights      = true
  enable_custom_metrics    = false  # Disabled for cost savings
  enable_detailed_monitoring = false
  create_dashboard         = true   # Useful for development
  dashboard_widgets        = ["lambda", "errors"]  # Minimal widgets
  enable_cost_monitoring   = true
  cost_threshold_usd       = 25     # Lower threshold for dev
}

#==============================================================================
# DEVELOPMENT SECURITY CONFIGURATION
#==============================================================================

security_config = {
  enable_least_privilege_iam   = true
  iam_path_prefix             = "/flight-data-pipeline-dev/"
  create_vpc                  = false  # Use default VPC
  vpc_cidr                   = "10.0.0.0/16"
  enable_nat_gateway         = false
  enable_vpc_endpoints       = false
  enable_encryption_at_rest  = true
  enable_encryption_in_transit = true
  create_kms_key             = false
}

#==============================================================================
# DEVELOPMENT COST OPTIMIZATION
#==============================================================================

cost_optimization = {
  # Aggressive cost optimization for development
  enable_intelligent_tiering     = false
  enable_glacier_transitions     = false
  enable_provisioned_concurrency = false
  use_arm_architecture          = false  # Keep x86 for compatibility
  disable_detailed_monitoring   = true
  reduce_log_retention          = true
  environment_auto_shutdown     = true   # Enable auto-shutdown
  auto_shutdown_schedule        = "cron(0 20 * * ? *)"  # 8 PM shutdown
}

#==============================================================================
# DEVELOPMENT FEATURE FLAGS
#==============================================================================

feature_flags = {
  enable_data_ingestion    = true
  enable_data_processing   = true
  enable_data_validation   = true
  enable_monitoring        = true
  enable_alerting         = false  # Reduced alerting in dev
  enable_api_gateway      = false
  enable_kinesis_streaming = false
  enable_glue_catalog     = false
}

#==============================================================================
# DEVELOPMENT DATA PROCESSING
#==============================================================================

data_processing_config = {
  batch_size                = 50    # Smaller batches
  max_batch_window_seconds = 30
  quality_threshold        = 0.7    # Lower threshold for testing
  min_completeness_score   = 0.6
  max_error_rate          = 0.1     # Allow more errors in dev
  max_retry_attempts      = 2
  dead_letter_queue_retention_days = 3
  parallel_processing_enabled = false  # Sequential for easier debugging
  max_concurrent_executions   = 2
}

#==============================================================================
# DEVELOPMENT SPECIFIC SETTINGS
#==============================================================================

development_config = {
  enable_debug_logging      = true
  create_test_resources     = true   # Create additional test resources
  allow_destructive_changes = true   # Allow resource deletion
  enable_local_development  = true
}

#==============================================================================
# ADDITIONAL DEVELOPMENT TAGS
#==============================================================================

additional_tags = {
  Purpose        = "Development"
  AutoDelete     = "true"
  DeveloperTeam  = "DataEngineering"
  TestingEnabled = "true"
}

# Development specific settings
create_output_file = true   # Generate infrastructure summary
enable_sns_alerts  = false  # Disable email alerts in dev