# Lambda Functions Module - Variables
# This file defines all input variables for the Lambda functions module

#==============================================================================
# CORE CONFIGURATION
#==============================================================================

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
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

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

#==============================================================================
# IAM CONFIGURATION
#==============================================================================

variable "iam_path_prefix" {
  description = "IAM path prefix for Lambda roles and policies"
  type        = string
  default     = "/flight-data-pipeline/"
}

#==============================================================================
# LAMBDA RUNTIME CONFIGURATION
#==============================================================================

variable "lambda_runtime" {
  description = "Lambda runtime version"
  type        = string
  default     = "python3.11"
  validation {
    condition = contains([
      "python3.8", "python3.9", "python3.10", "python3.11", "python3.12"
    ], var.lambda_runtime)
    error_message = "Lambda runtime must be a supported Python version."
  }
}

variable "lambda_architecture" {
  description = "Lambda architecture (x86_64 or arm64)"
  type        = string
  default     = "x86_64"
  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "Lambda architecture must be either x86_64 or arm64."
  }
}

#==============================================================================
# LAMBDA FUNCTION CONFIGURATIONS
#==============================================================================

variable "lambda_config" {
  description = "Configuration for Lambda functions"
  type = object({
    ingestion = object({
      memory_size             = number
      timeout                 = number
      reserved_concurrency    = number
      provisioned_concurrency = number
      environment_variables   = map(string)
    })
    processing = object({
      memory_size             = number
      timeout                 = number
      reserved_concurrency    = number
      provisioned_concurrency = number
      environment_variables   = map(string)
    })
    validation = object({
      memory_size             = number
      timeout                 = number
      reserved_concurrency    = number
      provisioned_concurrency = number
      environment_variables   = map(string)
    })
  })
  
  default = {
    ingestion = {
      memory_size             = 512
      timeout                 = 60
      reserved_concurrency    = 10
      provisioned_concurrency = 0
      environment_variables   = {}
    }
    processing = {
      memory_size             = 1024
      timeout                 = 120
      reserved_concurrency    = 5
      provisioned_concurrency = 0
      environment_variables   = {}
    }
    validation = {
      memory_size             = 512
      timeout                 = 60
      reserved_concurrency    = 3
      provisioned_concurrency = 0
      environment_variables   = {}
    }
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
    error_message = "Lambda memory must be 128-10240 MB and timeout must be 1-900 seconds."
  }
}

#==============================================================================
# LAMBDA DEPLOYMENT PACKAGES
#==============================================================================

variable "ingestion_zip_path" {
  description = "Path to the ingestion Lambda deployment package"
  type        = string
  default     = "../deployment-packages/ingestion.zip"
}

variable "processing_zip_path" {
  description = "Path to the processing Lambda deployment package"
  type        = string
  default     = "../deployment-packages/processing.zip"
}

variable "validation_zip_path" {
  description = "Path to the validation Lambda deployment package"
  type        = string
  default     = "../deployment-packages/validation.zip"
}

variable "ingestion_source_code_hash" {
  description = "Source code hash for ingestion Lambda (triggers updates)"
  type        = string
  default     = null
}

variable "processing_source_code_hash" {
  description = "Source code hash for processing Lambda (triggers updates)"
  type        = string
  default     = null
}

variable "validation_source_code_hash" {
  description = "Source code hash for validation Lambda (triggers updates)"
  type        = string
  default     = null
}

#==============================================================================
# LAMBDA LAYERS
#==============================================================================

variable "lambda_layer_zip_path" {
  description = "Path to the shared dependencies Lambda layer zip file"
  type        = string
  default     = "../layers/shared-dependencies.zip"
}

variable "common_utilities_zip_path" {
  description = "Path to the common utilities Lambda layer zip file"
  type        = string
  default     = "../layers/common-utilities.zip"
}

#==============================================================================
# S3 BUCKET CONFIGURATION
#==============================================================================

variable "raw_data_bucket_name" {
  description = "Name of the raw data S3 bucket"
  type        = string
}

variable "raw_data_bucket_arn" {
  description = "ARN of the raw data S3 bucket"
  type        = string
}

variable "processed_data_bucket_name" {
  description = "Name of the processed data S3 bucket"
  type        = string
}

variable "processed_data_bucket_arn" {
  description = "ARN of the processed data S3 bucket"
  type        = string
}

variable "athena_results_bucket_name" {
  description = "Name of the Athena results S3 bucket"
  type        = string
}

variable "athena_results_bucket_arn" {
  description = "ARN of the Athena results S3 bucket"
  type        = string
}

#==============================================================================
# ENCRYPTION AND SECURITY
#==============================================================================

variable "kms_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  type        = string
  default     = null
}

variable "enable_log_encryption" {
  description = "Enable encryption for CloudWatch logs"
  type        = bool
  default     = false
}

variable "cloudwatch_kms_key_id" {
  description = "KMS key ID for CloudWatch logs encryption"
  type        = string
  default     = null
}

variable "enable_dlq_encryption" {
  description = "Enable encryption for dead letter queues"
  type        = bool
  default     = true
}

#==============================================================================
# DYNAMODB CONFIGURATION
#==============================================================================

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for execution tracking"
  type        = string
  default     = null
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for execution tracking"
  type        = string
  default     = null
}

#==============================================================================
# SNS CONFIGURATION
#==============================================================================

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  type        = string
  default     = null
}

#==============================================================================
# ENVIRONMENT VARIABLES
#==============================================================================

variable "common_environment_variables" {
  description = "Common environment variables for all Lambda functions"
  type        = map(string)
  default     = {}
}

variable "log_level" {
  description = "Log level for Lambda functions"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

#==============================================================================
# CLOUDWATCH LOGGING
#==============================================================================

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

#==============================================================================
# X-RAY TRACING
#==============================================================================

variable "enable_xray_tracing" {
  description = "Enable X-Ray tracing for Lambda functions"
  type        = bool
  default     = false
}

#==============================================================================
# VPC CONFIGURATION
#==============================================================================

variable "vpc_config" {
  description = "VPC configuration for Lambda functions"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

#==============================================================================
# DEAD LETTER QUEUES
#==============================================================================

variable "dlq_retention_seconds" {
  description = "Message retention period for dead letter queues (seconds)"
  type        = number
  default     = 1209600  # 14 days
  validation {
    condition     = var.dlq_retention_seconds >= 60 && var.dlq_retention_seconds <= 1209600
    error_message = "DLQ retention must be between 60 seconds and 14 days."
  }
}

#==============================================================================
# SCHEDULED INGESTION
#==============================================================================

variable "enable_scheduled_ingestion" {
  description = "Enable scheduled ingestion via EventBridge"
  type        = bool
  default     = true
}

variable "ingestion_schedule_expression" {
  description = "Schedule expression for ingestion (cron or rate)"
  type        = string
  default     = "rate(5 minutes)"
  validation {
    condition     = can(regex("^(rate\\([0-9]+ (minute|minutes|hour|hours|day|days)\\)|cron\\(.+\\))$", var.ingestion_schedule_expression))
    error_message = "Schedule expression must be a valid rate() or cron() expression."
  }
}

#==============================================================================
# DATA QUALITY CONFIGURATION
#==============================================================================

variable "data_quality_config" {
  description = "Data quality thresholds and configuration"
  type = object({
    quality_threshold        = number
    min_completeness_score   = number
    max_error_rate          = number
  })
  default = {
    quality_threshold      = 0.8
    min_completeness_score = 0.7
    max_error_rate        = 0.05
  }
  validation {
    condition = alltrue([
      var.data_quality_config.quality_threshold >= 0 && var.data_quality_config.quality_threshold <= 1,
      var.data_quality_config.min_completeness_score >= 0 && var.data_quality_config.min_completeness_score <= 1,
      var.data_quality_config.max_error_rate >= 0 && var.data_quality_config.max_error_rate <= 1
    ])
    error_message = "Data quality thresholds must be between 0 and 1."
  }
}

#==============================================================================
# OPENSKY API CONFIGURATION
#==============================================================================

variable "opensky_api_config" {
  description = "OpenSky Network API configuration"
  type = object({
    request_timeout = number
    max_retries    = number
  })
  default = {
    request_timeout = 30
    max_retries    = 3
  }
}

#==============================================================================
# EVENTBRIDGE CONFIGURATION
#==============================================================================

variable "eventbridge_retry_config" {
  description = "EventBridge retry configuration"
  type = object({
    max_retry_attempts   = number
    max_event_age_seconds = number
  })
  default = {
    max_retry_attempts   = 3
    max_event_age_seconds = 3600  # 1 hour
  }
}

#==============================================================================
# LAMBDA VERSIONING AND ALIASES
#==============================================================================

variable "enable_lambda_versioning" {
  description = "Enable Lambda function versioning and aliases"
  type        = bool
  default     = false
}

variable "lambda_alias_name" {
  description = "Name for Lambda function aliases"
  type        = string
  default     = "LIVE"
}

variable "enable_gradual_deployment" {
  description = "Enable gradual deployment with weighted routing"
  type        = bool
  default     = false
}

variable "enable_provisioned_concurrency" {
  description = "Enable provisioned concurrency for Lambda functions"
  type        = bool
  default     = false
}

#==============================================================================
# MONITORING AND ALARMS
#==============================================================================

variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms for Lambda functions"
  type        = bool
  default     = true
}

variable "error_alarm_threshold" {
  description = "Threshold for Lambda error alarms"
  type        = number
  default     = 5
}

variable "cloudwatch_alarm_actions" {
  description = "List of ARNs for CloudWatch alarm actions"
  type        = list(string)
  default     = []
}

variable "create_lambda_dashboard" {
  description = "Create CloudWatch dashboard for Lambda metrics"
  type        = bool
  default     = true
}

variable "enable_lambda_insights" {
  description = "Enable Lambda Insights for enhanced monitoring"
  type        = bool
  default     = false
}

variable "lambda_insights_layer_arn" {
  description = "ARN of the Lambda Insights layer (region-specific)"
  type        = string
  default     = null
}

#==============================================================================
# ERROR HANDLING AND NOTIFICATIONS
#==============================================================================

variable "create_error_notification_topic" {
  description = "Create SNS topic for Lambda error notifications"
  type        = bool
  default     = true
}

variable "error_notification_email" {
  description = "Email address for Lambda error notifications"
  type        = string
  default     = null
  validation {
    condition = var.error_notification_email == null || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.error_notification_email))
    error_message = "Error notification email must be a valid email address."
  }
}

variable "monitor_lambda_state_changes" {
  description = "Monitor Lambda function state changes with EventBridge"
  type        = bool
  default     = false
}