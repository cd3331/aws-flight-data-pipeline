# Flight Data Pipeline - Terraform Variables
# This file defines all input variables for the infrastructure

#==============================================================================
# CORE CONFIGURATION
#==============================================================================

variable "project_name" {
  description = "Name of the project - used for resource naming and tagging"
  type        = string
  default     = "flight-data-pipeline"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.aws_region))
    error_message = "AWS region must be a valid region identifier."
  }
}

#==============================================================================
# AUTHENTICATION & ACCESS
#==============================================================================

variable "assume_role_arn" {
  description = "ARN of IAM role to assume for cross-account deployment"
  type        = string
  default     = null
}

variable "assume_role_external_id" {
  description = "External ID for assume role (if required)"
  type        = string
  default     = null
  sensitive   = true
}

#==============================================================================
# ALERTING & NOTIFICATIONS
#==============================================================================

variable "alert_email" {
  description = "Email address for receiving alerts and notifications"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.alert_email))
    error_message = "Alert email must be a valid email address."
  }
}

variable "enable_sns_alerts" {
  description = "Enable SNS alerts for data quality issues"
  type        = bool
  default     = true
}

variable "alert_phone_number" {
  description = "Phone number for SMS alerts (optional, format: +1234567890)"
  type        = string
  default     = null

  validation {
    condition     = var.alert_phone_number == null || can(regex("^\\+[1-9]\\d{1,14}$", var.alert_phone_number))
    error_message = "Phone number must be in E.164 format (e.g., +1234567890)."
  }
}

#==============================================================================
# LAMBDA CONFIGURATION
#==============================================================================

variable "lambda_config" {
  description = "Lambda function configuration settings"
  type = object({
    # Data Ingestion Lambda
    ingestion = object({
      memory_size          = number
      timeout              = number
      reserved_concurrency = number
    })

    # Data Processing Lambda
    processing = object({
      memory_size          = number
      timeout              = number
      reserved_concurrency = number
    })

    # Data Quality Validation Lambda
    validation = object({
      memory_size          = number
      timeout              = number
      reserved_concurrency = number
    })

    # Common settings
    runtime               = string
    architecture          = string
    log_retention_days    = number
    enable_xray_tracing   = bool
    environment_variables = map(string)
  })

  default = {
    ingestion = {
      memory_size          = 512
      timeout              = 300
      reserved_concurrency = 10
    }
    processing = {
      memory_size          = 1024
      timeout              = 900
      reserved_concurrency = 5
    }
    validation = {
      memory_size          = 768
      timeout              = 600
      reserved_concurrency = 3
    }
    runtime               = "python3.11"
    architecture          = "x86_64"
    log_retention_days    = 14
    enable_xray_tracing   = false
    environment_variables = {}
  }

  validation {
    condition = alltrue([
      var.lambda_config.ingestion.memory_size >= 128 && var.lambda_config.ingestion.memory_size <= 10240,
      var.lambda_config.processing.memory_size >= 128 && var.lambda_config.processing.memory_size <= 10240,
      var.lambda_config.validation.memory_size >= 128 && var.lambda_config.validation.memory_size <= 10240,
      var.lambda_config.ingestion.timeout >= 1 && var.lambda_config.ingestion.timeout <= 900,
      var.lambda_config.processing.timeout >= 1 && var.lambda_config.processing.timeout <= 900,
      var.lambda_config.validation.timeout >= 1 && var.lambda_config.validation.timeout <= 900
    ])
    error_message = "Lambda memory must be between 128-10240 MB and timeout between 1-900 seconds."
  }
}

variable "lambda_architecture" {
  description = "Lambda function architecture"
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "Lambda architecture must be either x86_64 or arm64."
  }
}

#==============================================================================
# S3 CONFIGURATION
#==============================================================================

variable "s3_config" {
  description = "S3 bucket configuration settings"
  type = object({
    # Bucket settings
    enable_versioning = bool
    enable_encryption = bool
    kms_key_id        = string

    # Lifecycle management
    enable_lifecycle_rules         = bool
    raw_data_expiration_days       = number
    processed_data_expiration_days = number
    incomplete_multipart_days      = number

    # Access control
    block_public_acls       = bool
    block_public_policy     = bool
    ignore_public_acls      = bool
    restrict_public_buckets = bool

    # Monitoring
    enable_access_logging  = bool
    enable_request_metrics = bool
  })

  default = {
    enable_versioning              = true
    enable_encryption              = true
    kms_key_id                     = "arn:aws:kms:*:*:alias/aws/s3"
    enable_lifecycle_rules         = true
    raw_data_expiration_days       = 90
    processed_data_expiration_days = 365
    incomplete_multipart_days      = 7
    block_public_acls              = true
    block_public_policy            = true
    ignore_public_acls             = true
    restrict_public_buckets        = true
    enable_access_logging          = false
    enable_request_metrics         = false
  }
}

#==============================================================================
# DATABASE CONFIGURATION
#==============================================================================

variable "dynamodb_config" {
  description = "DynamoDB configuration for execution tracking"
  type = object({
    billing_mode                  = string
    read_capacity_units           = number
    write_capacity_units          = number
    enable_point_in_time_recovery = bool
    enable_server_side_encryption = bool
    ttl_attribute                 = string
    ttl_enabled                   = bool
  })

  default = {
    billing_mode                  = "PAY_PER_REQUEST"
    read_capacity_units           = 0
    write_capacity_units          = 0
    enable_point_in_time_recovery = false
    enable_server_side_encryption = true
    ttl_attribute                 = "ttl"
    ttl_enabled                   = true
  }

  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.dynamodb_config.billing_mode)
    error_message = "DynamoDB billing mode must be either PAY_PER_REQUEST or PROVISIONED."
  }
}

variable "create_rds_instance" {
  description = "Whether to create an RDS instance for advanced analytics"
  type        = bool
  default     = false
}

variable "rds_config" {
  description = "RDS configuration (only used if create_rds_instance is true)"
  type = object({
    engine_version          = string
    instance_class          = string
    allocated_storage       = number
    max_allocated_storage   = number
    backup_retention_period = number
    backup_window           = string
    maintenance_window      = string
    multi_az                = bool
    publicly_accessible     = bool
    deletion_protection     = bool
  })

  default = {
    engine_version          = "15.4"
    instance_class          = "db.t3.micro"
    allocated_storage       = 20
    max_allocated_storage   = 100
    backup_retention_period = 7
    backup_window           = "03:00-04:00"
    maintenance_window      = "sun:04:00-sun:05:00"
    multi_az                = false
    publicly_accessible     = false
    deletion_protection     = false
  }
}

#==============================================================================
# MONITORING & LOGGING
#==============================================================================

variable "monitoring_config" {
  description = "CloudWatch monitoring configuration"
  type = object({
    # Log groups
    log_retention_days  = number
    enable_log_insights = bool

    # Metrics and alarms
    enable_custom_metrics        = bool
    enable_detailed_monitoring   = bool
    enable_synthetic_monitoring  = bool

    # Dashboards
    create_dashboard  = bool
    dashboard_widgets = list(string)

    # Cost monitoring
    enable_cost_monitoring = bool
    cost_threshold_usd     = number
  })

  default = {
    log_retention_days          = 30
    enable_log_insights         = true
    enable_custom_metrics       = true
    enable_detailed_monitoring  = false
    enable_synthetic_monitoring = false
    create_dashboard            = true
    dashboard_widgets           = ["lambda", "s3", "dynamodb", "errors"]
    enable_cost_monitoring      = true
    cost_threshold_usd          = 100
  }
}

#==============================================================================
# SECURITY CONFIGURATION
#==============================================================================

variable "security_config" {
  description = "Security configuration settings"
  type = object({
    # IAM settings
    enable_least_privilege_iam = bool
    iam_path_prefix            = string

    # VPC settings (optional)
    create_vpc           = bool
    vpc_cidr             = string
    enable_nat_gateway   = bool
    enable_vpc_endpoints = bool

    # Encryption
    enable_encryption_at_rest    = bool
    enable_encryption_in_transit = bool
    create_kms_key               = bool
  })

  default = {
    enable_least_privilege_iam   = true
    iam_path_prefix              = "/flight-data-pipeline/"
    create_vpc                   = false
    vpc_cidr                     = "10.0.0.0/16"
    enable_nat_gateway           = false
    enable_vpc_endpoints         = false
    enable_encryption_at_rest    = true
    enable_encryption_in_transit = true
    create_kms_key               = false
  }
}

#==============================================================================
# COST OPTIMIZATION
#==============================================================================

variable "cost_optimization" {
  description = "Cost optimization settings"
  type = object({
    # S3 cost optimization
    enable_intelligent_tiering = bool
    enable_glacier_transitions = bool
    use_transfer_acceleration  = bool
    enable_requester_pays      = bool

    # Lambda cost optimization
    enable_provisioned_concurrency = bool
    use_arm_architecture           = bool

    # CloudWatch cost optimization
    disable_detailed_monitoring = bool
    reduce_log_retention        = bool

    # General settings
    environment_auto_shutdown = bool
    auto_shutdown_schedule    = string
  })

  default = {
    enable_intelligent_tiering     = false
    enable_glacier_transitions     = false
    use_transfer_acceleration      = false
    enable_requester_pays          = false
    enable_provisioned_concurrency = false
    use_arm_architecture           = false
    disable_detailed_monitoring    = true
    reduce_log_retention           = false
    environment_auto_shutdown      = false
    auto_shutdown_schedule         = "cron(0 22 * * ? *)" # 10 PM daily
  }
}

#==============================================================================
# FEATURE FLAGS
#==============================================================================

variable "feature_flags" {
  description = "Feature flags for enabling/disabling components"
  type = object({
    enable_data_ingestion    = bool
    enable_data_processing   = bool
    enable_data_validation   = bool
    enable_monitoring        = bool
    enable_alerting          = bool
    enable_api_gateway       = bool
    enable_kinesis_streaming = bool
    enable_glue_catalog      = bool
  })

  default = {
    enable_data_ingestion    = true
    enable_data_processing   = true
    enable_data_validation   = true
    enable_monitoring        = true
    enable_alerting          = true
    enable_api_gateway       = false
    enable_kinesis_streaming = false
    enable_glue_catalog      = false
  }
}

#==============================================================================
# DATA PROCESSING CONFIGURATION
#==============================================================================

variable "data_processing_config" {
  description = "Data processing pipeline configuration"
  type = object({
    # Batch processing settings
    batch_size               = number
    max_batch_window_seconds = number

    # Data quality thresholds
    quality_threshold      = number
    min_completeness_score = number
    max_error_rate         = number

    # Retry and error handling
    max_retry_attempts               = number
    dead_letter_queue_retention_days = number

    # Performance settings
    parallel_processing_enabled = bool
    max_concurrent_executions   = number
  })

  default = {
    batch_size                       = 100
    max_batch_window_seconds         = 60
    quality_threshold                = 0.8
    min_completeness_score           = 0.7
    max_error_rate                   = 0.05
    max_retry_attempts               = 3
    dead_letter_queue_retention_days = 14
    parallel_processing_enabled      = true
    max_concurrent_executions        = 10
  }

  validation {
    condition = alltrue([
      var.data_processing_config.quality_threshold >= 0 && var.data_processing_config.quality_threshold <= 1,
      var.data_processing_config.min_completeness_score >= 0 && var.data_processing_config.min_completeness_score <= 1,
      var.data_processing_config.max_error_rate >= 0 && var.data_processing_config.max_error_rate <= 1
    ])
    error_message = "Quality thresholds must be between 0 and 1."
  }
}

#==============================================================================
# DEVELOPMENT & TESTING
#==============================================================================

variable "development_config" {
  description = "Development and testing configuration"
  type = object({
    enable_debug_logging      = bool
    create_test_resources     = bool
    allow_destructive_changes = bool
    enable_local_development  = bool
  })

  default = {
    enable_debug_logging      = false
    create_test_resources     = false
    allow_destructive_changes = false
    enable_local_development  = false
  }
}

#==============================================================================
# BUDGET CONFIGURATION
#==============================================================================

variable "budget_config" {
  description = "Budget configuration for cost monitoring and alerts"
  type = object({
    monthly_limit        = number
    warning_threshold    = number
    critical_threshold   = number
    forecast_threshold   = number
    enable_service_budgets = bool
    service_limits = object({
      lambda   = number
      s3       = number
      dynamodb = number
    })
  })

  default = {
    monthly_limit          = 100
    warning_threshold      = 0.8
    critical_threshold     = 0.9
    forecast_threshold     = 1.0
    enable_service_budgets = true
    service_limits = {
      lambda   = 50
      s3       = 30
      dynamodb = 20
    }
  }

  validation {
    condition = alltrue([
      var.budget_config.monthly_limit > 0,
      var.budget_config.warning_threshold > 0 && var.budget_config.warning_threshold < 1,
      var.budget_config.critical_threshold > var.budget_config.warning_threshold && var.budget_config.critical_threshold < 1,
      var.budget_config.forecast_threshold >= 1
    ])
    error_message = "Budget thresholds must be valid percentages and monthly limit must be positive."
  }
}

#==============================================================================
# NOTIFICATION CONFIGURATION
#==============================================================================

variable "notification_config" {
  description = "Notification configuration for alerts and monitoring"
  type = object({
    alert_emails         = list(string)
    critical_alert_emails = list(string)
    budget_emails        = list(string)
    enable_sms          = bool
    sms_numbers         = list(string)
    enable_slack        = bool
    slack_webhook_url   = string
  })

  default = {
    alert_emails          = []
    critical_alert_emails = []
    budget_emails         = []
    enable_sms           = false
    sms_numbers          = []
    enable_slack         = false
    slack_webhook_url    = ""
  }

  validation {
    condition = alltrue([
      for email in var.notification_config.alert_emails : 
      can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All alert emails must be valid email addresses."
  }
}

#==============================================================================
# ADDITIONAL CONFIGURATION
#==============================================================================

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "create_output_file" {
  description = "Whether to create a local output file with infrastructure details"
  type        = bool
  default     = false
}

variable "opensky_api_config" {
  description = "OpenSky Network API configuration"
  type = object({
    base_url              = string
    request_timeout       = number
    max_retries           = number
    rate_limit_per_hour   = number
    enable_authentication = bool
  })

  default = {
    base_url              = "https://opensky-network.org/api"
    request_timeout       = 30
    max_retries           = 3
    rate_limit_per_hour   = 4000
    enable_authentication = false
  }
}