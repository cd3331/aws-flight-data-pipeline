# Production Environment Configuration
# This file contains environment-specific variable values for production

#==============================================================================
# CORE CONFIGURATION
#==============================================================================

project_name = "flight-data-pipeline"
environment  = "prod"
aws_region   = "us-east-1"

# REQUIRED: Replace with your production alert email
alert_email = "prod-alerts@example.com"
alert_phone_number = "+1234567890"  # REQUIRED: SMS for critical production alerts

#==============================================================================
# PRODUCTION LAMBDA CONFIGURATION - OPTIMIZED FOR PERFORMANCE
#==============================================================================

lambda_config = {
  # Full production resources
  ingestion = {
    memory_size          = 512    # Full memory allocation
    timeout              = 300    # 5 minutes
    reserved_concurrency = 10    # High concurrency for frequent ingestion
  }
  
  processing = {
    memory_size          = 1024   # Maximum memory for large datasets
    timeout              = 900    # 15 minutes for complex processing
    reserved_concurrency = 5     # Balanced concurrency
  }
  
  validation = {
    memory_size          = 768    # Sufficient for comprehensive validation
    timeout              = 600    # 10 minutes
    reserved_concurrency = 3     # Limited but adequate concurrency
  }
  
  runtime                = "python3.11"
  architecture          = "x86_64"  # Proven compatibility in production
  log_retention_days    = 30        # Extended retention for compliance
  enable_xray_tracing   = false     # Disabled for performance in prod
  environment_variables = {
    LOG_LEVEL = "INFO"
    ENABLE_PERFORMANCE_MONITORING = "true"
  }
}

#==============================================================================
# PRODUCTION S3 CONFIGURATION - ENTERPRISE GRADE
#==============================================================================

s3_config = {
  enable_versioning    = true     # REQUIRED for production data protection
  enable_encryption   = true
  kms_key_id         = "arn:aws:kms:*:*:alias/aws/s3"  # Consider custom KMS key for enhanced security
  
  # Production data retention policies
  enable_lifecycle_rules        = true
  raw_data_expiration_days     = 365   # 1 year retention
  processed_data_expiration_days = 2555 # 7 years for compliance
  incomplete_multipart_days    = 7
  
  # Maximum security settings
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  
  # Full monitoring and logging
  enable_access_logging   = true   # REQUIRED for audit compliance
  enable_request_metrics  = true   # REQUIRED for performance monitoring
}

#==============================================================================
# PRODUCTION DATABASE CONFIGURATION
#==============================================================================

dynamodb_config = {
  billing_mode            = "PAY_PER_REQUEST"  # Or "PROVISIONED" for predictable costs
  read_capacity_units    = 0
  write_capacity_units   = 0
  enable_point_in_time_recovery = true   # REQUIRED for production
  enable_server_side_encryption = true
  ttl_attribute          = "ttl"
  ttl_enabled           = true
}

# Optional RDS for production analytics
create_rds_instance = false  # Set to true if advanced analytics are needed

rds_config = {
  engine_version          = "15.4"
  instance_class         = "db.t3.medium"     # Production-sized instance
  allocated_storage      = 100
  max_allocated_storage  = 1000               # Auto-scaling up to 1TB
  backup_retention_period = 30                # 30 days backup retention
  backup_window          = "03:00-04:00"      # Off-peak hours
  maintenance_window     = "sun:04:00-sun:06:00"
  multi_az              = true                # REQUIRED: High availability
  publicly_accessible   = false
  deletion_protection   = true                # REQUIRED: Prevent accidental deletion
}

#==============================================================================
# PRODUCTION MONITORING - COMPREHENSIVE
#==============================================================================

monitoring_config = {
  log_retention_days        = 90     # Extended retention for compliance
  enable_log_insights      = true
  enable_custom_metrics    = true    # Full custom metrics
  enable_detailed_monitoring = true  # Detailed CloudWatch monitoring
  create_dashboard         = true
  dashboard_widgets        = ["lambda", "s3", "dynamodb", "errors", "performance", "costs"]
  enable_cost_monitoring   = true
  cost_threshold_usd       = 500     # Higher threshold for production
}

#==============================================================================
# PRODUCTION SECURITY CONFIGURATION - ENHANCED
#==============================================================================

security_config = {
  enable_least_privilege_iam   = true
  iam_path_prefix             = "/flight-data-pipeline-prod/"
  create_vpc                  = true   # RECOMMENDED: Network isolation
  vpc_cidr                   = "10.2.0.0/16"
  enable_nat_gateway         = true    # Required for Lambda internet access
  enable_vpc_endpoints       = true    # Cost-effective alternative to NAT
  enable_encryption_at_rest  = true
  enable_encryption_in_transit = true
  create_kms_key             = true    # Custom KMS key for enhanced security
}

#==============================================================================
# PRODUCTION COST OPTIMIZATION - BALANCED
#==============================================================================

cost_optimization = {
  # Intelligent cost optimization
  enable_intelligent_tiering     = true   # Cost savings for varying access patterns
  enable_glacier_transitions     = true   # Long-term archival cost savings
  enable_provisioned_concurrency = false  # Only if consistent high traffic
  use_arm_architecture          = false   # Stick with proven x86 in production
  disable_detailed_monitoring   = false   # Keep monitoring enabled
  reduce_log_retention          = false   # Maintain full retention
  environment_auto_shutdown     = false   # Never auto-shutdown production
  auto_shutdown_schedule        = ""      # Not applicable
}

#==============================================================================
# PRODUCTION FEATURE FLAGS - ALL FEATURES ENABLED
#==============================================================================

feature_flags = {
  enable_data_ingestion    = true
  enable_data_processing   = true
  enable_data_validation   = true
  enable_monitoring        = true
  enable_alerting         = true
  enable_api_gateway      = true   # Enable API access
  enable_kinesis_streaming = false # Enable if real-time processing needed
  enable_glue_catalog     = true   # Enable for data cataloging
}

#==============================================================================
# PRODUCTION DATA PROCESSING - HIGH QUALITY STANDARDS
#==============================================================================

data_processing_config = {
  batch_size                = 100    # Optimal batch size
  max_batch_window_seconds = 60
  quality_threshold        = 0.85    # High quality threshold
  min_completeness_score   = 0.8     # High completeness requirement
  max_error_rate          = 0.01     # Very low error tolerance (1%)
  max_retry_attempts      = 3
  dead_letter_queue_retention_days = 30  # Extended retention
  parallel_processing_enabled = true
  max_concurrent_executions   = 10
}

#==============================================================================
# PRODUCTION DEVELOPMENT CONFIGURATION
#==============================================================================

development_config = {
  enable_debug_logging      = false  # Production logging only
  create_test_resources     = false  # No test resources in production
  allow_destructive_changes = false  # Strict protection
  enable_local_development  = false
}

#==============================================================================
# PRODUCTION OPENSKY API CONFIGURATION
#==============================================================================

opensky_api_config = {
  base_url              = "https://opensky-network.org/api"
  request_timeout       = 45        # Higher timeout for reliability
  max_retries          = 5          # More retries for production
  rate_limit_per_hour  = 4000
  enable_authentication = false     # Set to true if you have premium access
}

#==============================================================================
# PRODUCTION TAGS - COMPLIANCE AND GOVERNANCE
#==============================================================================

additional_tags = {
  # Compliance and governance
  Environment       = "Production"
  DataClassification = "Internal"
  ComplianceRequired = "true"
  BackupRequired    = "true"
  
  # Operational
  BusinessCriticality = "High"
  SupportLevel       = "24x7"
  ChangeControl      = "Required"
  
  # Financial
  CostCenter        = "DataEngineering"
  BudgetOwner       = "DataTeam"
  ChargebackCode    = "DE-001"
  
  # Security
  SecurityReview    = "Approved"
  DataRetention     = "7Years"
  EncryptionRequired = "true"
}

# Production specific settings
create_output_file = true   # Generate infrastructure documentation
enable_sns_alerts  = true   # REQUIRED: Enable all alert channels