# Flight Data Pipeline - Local Values and Computed Variables
# This file contains computed values, naming conventions, and resource tags

locals {
  #==============================================================================
  # NAMING CONVENTIONS
  #==============================================================================

  # Base naming convention: {project}-{environment}-{service}-{suffix}
  name_prefix = "${var.project_name}-${var.environment}"

  # Resource naming with consistent patterns
  resource_names = {
    # S3 Buckets (must be globally unique)
    raw_data_bucket         = "${local.name_prefix}-raw-data-${random_string.suffix.result}"
    processed_data_bucket   = "${local.name_prefix}-processed-data-${random_string.suffix.result}"
    lambda_artifacts_bucket = "${local.name_prefix}-lambda-artifacts-${random_string.suffix.result}"

    # Lambda Functions
    ingestion_lambda  = "${local.name_prefix}-flight-ingestion"
    processing_lambda = "${local.name_prefix}-flight-processing"
    validation_lambda = "${local.name_prefix}-data-validation"

    # Lambda Layers
    common_layer = "${local.name_prefix}-common-layer"
    pandas_layer = "${local.name_prefix}-pandas-layer"

    # IAM Roles
    lambda_execution_role = "${local.name_prefix}-lambda-execution-role"
    s3_access_role        = "${local.name_prefix}-s3-access-role"

    # CloudWatch Log Groups
    ingestion_log_group  = "/aws/lambda/${local.name_prefix}-flight-ingestion"
    processing_log_group = "/aws/lambda/${local.name_prefix}-flight-processing"
    validation_log_group = "/aws/lambda/${local.name_prefix}-data-validation"

    # DynamoDB Tables
    execution_tracking_table = "${local.name_prefix}-execution-tracking"
    data_quality_table       = "${local.name_prefix}-data-quality-metrics"

    # SNS Topics
    data_quality_alerts = "${local.name_prefix}-data-quality-alerts"
    system_alerts       = "${local.name_prefix}-system-alerts"

    # SQS Queues
    processing_dlq = "${local.name_prefix}-processing-dlq"
    validation_dlq = "${local.name_prefix}-validation-dlq"

    # CloudWatch Dashboard
    main_dashboard = "${local.name_prefix}-pipeline-dashboard"

    # KMS Keys
    data_encryption_key = "${local.name_prefix}-data-encryption-key"

    # EventBridge Rules
    scheduled_ingestion = "${local.name_prefix}-scheduled-ingestion"

    # VPC Resources (if enabled)
    vpc            = "${local.name_prefix}-vpc"
    private_subnet = "${local.name_prefix}-private-subnet"
    public_subnet  = "${local.name_prefix}-public-subnet"
    nat_gateway    = "${local.name_prefix}-nat-gateway"
  }

  #==============================================================================
  # COMPUTED VALUES
  #==============================================================================

  # AWS Account and Region Information
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region     = data.aws_region.current.name
  aws_partition  = data.aws_partition.current.partition

  # Availability Zones (limited to 2 for cost optimization)
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)

  # Environment-specific configurations
  environment_config = {
    dev = {
      lambda_memory_multiplier   = 0.5
      log_retention_multiplier   = 0.5
      enable_detailed_monitoring = false
      auto_scaling_enabled       = false
      backup_retention_days      = 3
    }
    staging = {
      lambda_memory_multiplier   = 0.75
      log_retention_multiplier   = 1.0
      enable_detailed_monitoring = true
      auto_scaling_enabled       = true
      backup_retention_days      = 7
    }
    prod = {
      lambda_memory_multiplier   = 1.0
      log_retention_multiplier   = 2.0
      enable_detailed_monitoring = true
      auto_scaling_enabled       = true
      backup_retention_days      = 30
    }
  }

  # Current environment configuration
  current_env_config = local.environment_config[var.environment]

  # Computed Lambda configurations with environment-specific adjustments
  computed_lambda_config = {
    ingestion = {
      memory_size          = ceil(var.lambda_config.ingestion.memory_size * local.current_env_config.lambda_memory_multiplier)
      timeout              = var.lambda_config.ingestion.timeout
      reserved_concurrency = var.environment == "prod" ? var.lambda_config.ingestion.reserved_concurrency : null
    }
    processing = {
      memory_size          = ceil(var.lambda_config.processing.memory_size * local.current_env_config.lambda_memory_multiplier)
      timeout              = var.lambda_config.processing.timeout
      reserved_concurrency = var.environment == "prod" ? var.lambda_config.processing.reserved_concurrency : null
    }
    validation = {
      memory_size          = ceil(var.lambda_config.validation.memory_size * local.current_env_config.lambda_memory_multiplier)
      timeout              = var.lambda_config.validation.timeout
      reserved_concurrency = var.environment == "prod" ? var.lambda_config.validation.reserved_concurrency : null
    }
  }

  # Log retention days with environment-specific adjustments
  computed_log_retention = ceil(var.lambda_config.log_retention_days * local.current_env_config.log_retention_multiplier)

  # S3 lifecycle configurations based on environment
  s3_lifecycle_config = {
    raw_data_expiration_days       = var.environment == "dev" ? 30 : var.s3_config.raw_data_expiration_days
    processed_data_expiration_days = var.environment == "dev" ? 90 : var.s3_config.processed_data_expiration_days
  }

  #==============================================================================
  # SECURITY AND ACCESS CONFIGURATIONS
  #==============================================================================

  # Cross-account access configuration
  cross_account_principals = var.assume_role_arn != null ? [
    data.aws_caller_identity.current.arn
  ] : []

  # Lambda function environment variables
  lambda_environment_variables = merge(
    var.lambda_config.environment_variables,
    {
      ENVIRONMENT           = var.environment
      PROJECT_NAME          = var.project_name
      AWS_ACCOUNT_ID        = local.aws_account_id
      RAW_DATA_BUCKET       = local.resource_names.raw_data_bucket
      PROCESSED_DATA_BUCKET = local.resource_names.processed_data_bucket
      TRACKING_TABLE        = local.resource_names.execution_tracking_table
      ALERT_TOPIC_ARN       = "arn:${local.aws_partition}:sns:${local.aws_region}:${local.aws_account_id}:${local.resource_names.data_quality_alerts}"
      QUALITY_THRESHOLD     = tostring(var.data_processing_config.quality_threshold)
      LOG_LEVEL             = var.development_config.enable_debug_logging ? "DEBUG" : "INFO"
    }
  )

  #==============================================================================
  # RESOURCE TAGS
  #==============================================================================

  # Common tags applied to all resources
  common_tags = merge(
    {
      # Core identification tags
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "DataEngineering"

      # Operational tags
      BackupSchedule    = var.environment == "prod" ? "daily" : "weekly"
      MonitoringEnabled = var.monitoring_config.enable_custom_metrics ? "true" : "false"
      CostCenter        = "data-infrastructure"

      # Security tags
      DataClassification = "internal"
      EncryptionRequired = var.security_config.enable_encryption_at_rest ? "true" : "false"

      # Automation tags
      AutoShutdown       = var.cost_optimization.environment_auto_shutdown ? "enabled" : "disabled"
      TerraformWorkspace = terraform.workspace

      # Temporal tags
      CreatedDate  = formatdate("YYYY-MM-DD", timestamp())
      LastModified = formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", timestamp())
    },
    var.additional_tags
  )

  # Specific tag sets for different resource types
  storage_tags = merge(
    local.common_tags,
    {
      ResourceType = "storage"
      BackupPolicy = var.environment == "prod" ? "retain" : "delete"
    }
  )

  compute_tags = merge(
    local.common_tags,
    {
      ResourceType = "compute"
      Monitoring   = var.monitoring_config.enable_detailed_monitoring ? "detailed" : "basic"
    }
  )

  network_tags = merge(
    local.common_tags,
    {
      ResourceType = "network"
      Connectivity = var.security_config.create_vpc ? "isolated" : "default"
    }
  )

  security_tags = merge(
    local.common_tags,
    {
      ResourceType       = "security"
      AccessLevel        = var.security_config.enable_least_privilege_iam ? "restricted" : "standard"
      ComplianceRequired = var.environment == "prod" ? "true" : "false"
    }
  )

  #==============================================================================
  # CONDITIONAL RESOURCE CREATION FLAGS
  #==============================================================================

  # Determine which resources to create based on feature flags and environment
  create_resources = {
    # Core components
    s3_buckets       = true
    lambda_functions = var.feature_flags.enable_data_ingestion || var.feature_flags.enable_data_processing || var.feature_flags.enable_data_validation
    dynamodb_tables  = var.feature_flags.enable_data_ingestion || var.feature_flags.enable_data_processing

    # Optional components
    sns_topics           = var.feature_flags.enable_alerting && var.enable_sns_alerts
    cloudwatch_dashboard = var.feature_flags.enable_monitoring && var.monitoring_config.create_dashboard
    kinesis_streams      = var.feature_flags.enable_kinesis_streaming
    api_gateway          = var.feature_flags.enable_api_gateway
    glue_resources       = var.feature_flags.enable_glue_catalog

    # Environment-specific resources
    rds_instance  = var.create_rds_instance && var.environment != "dev"
    vpc_resources = var.security_config.create_vpc
    nat_gateways  = var.security_config.create_vpc && var.security_config.enable_nat_gateway

    # Development resources
    test_resources = var.development_config.create_test_resources && var.environment == "dev"

    # S3-specific resource flags
    cross_region_replication = var.environment == "prod"
  }

  #==============================================================================
  # COST OPTIMIZATION CALCULATIONS
  #==============================================================================

  # Cost optimization settings based on environment and flags
  optimized_settings = {
    s3_storage_class    = var.cost_optimization.enable_intelligent_tiering ? "INTELLIGENT_TIERING" : "STANDARD"
    lambda_architecture = var.cost_optimization.use_arm_architecture ? "arm64" : var.lambda_config.architecture

    # CloudWatch log retention optimization
    optimized_log_retention = var.cost_optimization.reduce_log_retention ? min(local.computed_log_retention, 7) : local.computed_log_retention

    # Reserved capacity settings for DynamoDB
    dynamodb_billing_mode = var.environment == "prod" && !var.cost_optimization.enable_intelligent_tiering ? "PROVISIONED" : "PAY_PER_REQUEST"
  }

  # Cost optimization settings for various resources
  cost_optimization_settings = {
    # S3 optimization
    enable_s3_intelligent_tiering = var.cost_optimization.enable_intelligent_tiering
    enable_s3_glacier_transitions = var.cost_optimization.enable_glacier_transitions
    use_s3_transfer_acceleration  = var.cost_optimization.use_transfer_acceleration
    enable_s3_requester_pays     = var.cost_optimization.enable_requester_pays
    s3_ia_ratio                  = 0.3

    # Lambda optimization
    use_arm64_architecture           = var.cost_optimization.use_arm_architecture
    enable_lambda_provisioned_concurrency = var.cost_optimization.enable_provisioned_concurrency
    cold_start_threshold            = 10

    # CloudWatch optimization
    disable_detailed_cloudwatch_monitoring = var.cost_optimization.disable_detailed_monitoring
    reduce_cloudwatch_log_retention        = var.cost_optimization.reduce_log_retention

    # DynamoDB optimization
    dynamodb_throttle_threshold = 5

    # Environment-based optimization
    enable_auto_shutdown = var.cost_optimization.environment_auto_shutdown
    shutdown_schedule   = var.cost_optimization.auto_shutdown_schedule

    # Computed settings
    effective_log_retention_days = var.cost_optimization.reduce_log_retention ? 7 : var.monitoring_config.log_retention_days
    effective_lambda_architecture = var.cost_optimization.use_arm_architecture ? "arm64" : var.lambda_config.architecture
  }

  #==============================================================================
  # MONITORING AND ALERTING CONFIGURATIONS
  #==============================================================================

  # CloudWatch metric filters and alarms configuration
  monitoring_thresholds = {
    error_rate_threshold         = var.environment == "prod" ? 0.01 : 0.05
    lambda_error_rate_threshold  = 0.05
    data_quality_threshold       = var.data_processing_config.quality_threshold
    processing_latency_threshold = var.lambda_config.processing.timeout * 800 # 80% of timeout in ms
    completeness_threshold       = var.data_processing_config.min_completeness_score
    validity_threshold           = 0.95
    availability_threshold       = 0.99
    s3_storage_threshold_gb      = var.environment == "prod" ? 1000 : 100
    lambda_duration_threshold_ms = var.lambda_config.processing.timeout * 800 # 80% of timeout
    s3_4xx_error_threshold       = 10
    dynamodb_throttle_threshold  = 5
    data_quality_score_threshold = var.data_processing_config.quality_threshold
    cost_anomaly_threshold_usd   = var.monitoring_config.cost_threshold_usd
  }

  # Alert routing configuration - using SNS topic ARNs instead of email addresses
  alert_routing = {
    critical_alerts = [module.monitoring.sns_topics.critical_alerts.arn]
    warning_alerts  = [module.monitoring.sns_topics.email_alerts.arn]
    info_alerts     = var.environment == "prod" ? [module.monitoring.sns_topics.email_alerts.arn] : []

    # SMS alerts for critical issues in production (handled by the monitoring module)
    sms_alerts = var.alert_phone_number != null && var.environment == "prod" ? [module.monitoring.sns_topics.critical_alerts.arn] : []
  }

  #==============================================================================
  # VALIDATION AND COMPUTED VALIDATIONS
  #==============================================================================

  # Validation flags for configuration consistency
  validation_checks = {
    lambda_memory_valid = alltrue([
      local.computed_lambda_config.ingestion.memory_size >= 128,
      local.computed_lambda_config.processing.memory_size >= 128,
      local.computed_lambda_config.validation.memory_size >= 128
    ])

    s3_config_valid = var.s3_config.enable_encryption || !var.security_config.enable_encryption_at_rest

    environment_consistency = contains(["dev", "staging", "prod"], var.environment)

    cost_optimization_valid = !(var.cost_optimization.use_arm_architecture && var.lambda_config.architecture == "x86_64")
  }

  #==============================================================================
  # LAMBDA-SPECIFIC LOCAL VALUES
  #==============================================================================

  # Lambda source code hashes (would be computed from actual files in real deployment)
  lambda_source_hashes = {
    ingestion  = fileexists("${path.module}/../deployment-packages/ingestion.zip") ? filebase64sha256("${path.module}/../deployment-packages/ingestion.zip") : null
    processing = fileexists("${path.module}/../deployment-packages/processing.zip") ? filebase64sha256("${path.module}/../deployment-packages/processing.zip") : null
    validation = fileexists("${path.module}/../deployment-packages/validation.zip") ? filebase64sha256("${path.module}/../deployment-packages/validation.zip") : null
  }

  # DynamoDB table ARN for execution tracking
  dynamodb_table_arn = var.feature_flags.enable_data_ingestion ? "arn:${local.aws_partition}:dynamodb:${local.aws_region}:${local.aws_account_id}:table/${local.resource_names.execution_tracking_table}" : null

  # SNS topic ARN for data quality alerts
  data_quality_alerts_topic_arn = var.feature_flags.enable_alerting ? "arn:${local.aws_partition}:sns:${local.aws_region}:${local.aws_account_id}:${local.resource_names.data_quality_alerts}" : null

  # Lambda Insights layer ARN (region-specific)
  lambda_insights_layer_arn = "arn:${local.aws_partition}:lambda:${local.aws_region}:580247275435:layer:LambdaInsightsExtension:14"

  # VPC configuration for Lambda functions
  lambda_vpc_config = var.security_config.create_vpc ? {
    subnet_ids         = local.private_subnet_ids
    security_group_ids = [local.lambda_security_group_id]
  } : null

  # Private subnet IDs (would be created by VPC module)
  private_subnet_ids = var.security_config.create_vpc ? [
    "subnet-lambda-private-a", # These would be actual subnet IDs
    "subnet-lambda-private-b"
  ] : []

  # Lambda security group ID
  lambda_security_group_id = var.security_config.create_vpc ? "sg-lambda-flight-data" : null

  # Ingestion schedule based on environment
  ingestion_schedule = var.environment == "dev" ? "rate(10 minutes)" : var.environment == "staging" ? "rate(5 minutes)" : "rate(5 minutes)"

  #==============================================================================
  # S3 DATA LAKE LOCAL VALUES
  #==============================================================================

  # Lambda ARNs (will be populated by Lambda module outputs)
  processing_lambda_arn = "arn:${local.aws_partition}:lambda:${local.aws_region}:${local.aws_account_id}:function:${local.resource_names.processing_lambda}"
  validation_lambda_arn = "arn:${local.aws_partition}:lambda:${local.aws_region}:${local.aws_account_id}:function:${local.resource_names.validation_lambda}"

  # Cross-region replication configuration (production only)
  replication_bucket_arn = var.environment == "prod" ? "arn:aws:s3:::${var.project_name}-${var.environment}-backup-${random_string.suffix.result}" : null
  replication_kms_key_id = var.environment == "prod" ? "arn:aws:kms:*:*:alias/aws/s3" : null

  # CORS allowed origins based on environment
  cors_allowed_origins = var.environment == "prod" ? [
    "https://*.${var.project_name}.com",
    "https://localhost:3000" # For development
  ] : ["*"]                  # Allow all origins in dev/staging

  #==============================================================================
  # MONITORING-SPECIFIC LOCAL VALUES  
  #==============================================================================

  # Monitoring-specific tags
  monitoring_tags = merge(local.common_tags, {
    Component  = "monitoring"
    Purpose    = "observability-and-alerting"
    CostCenter = "engineering"
  })
}