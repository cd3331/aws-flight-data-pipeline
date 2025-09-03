# Flight Data Pipeline - Monitoring Module Variables
# This file defines all input variables for the monitoring module

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
# LAMBDA FUNCTION CONFIGURATION
#==============================================================================

variable "lambda_function_names" {
  description = "Names of the Lambda functions to monitor"
  type = object({
    ingestion  = string
    processing = string
    validation = string
  })
}

variable "lambda_timeouts" {
  description = "Timeout values for Lambda functions (in seconds)"
  type = object({
    ingestion  = number
    processing = number
    validation = number
  })
  default = {
    ingestion  = 60
    processing = 120
    validation = 60
  }
}

#==============================================================================
# S3 BUCKET CONFIGURATION
#==============================================================================

variable "s3_bucket_names" {
  description = "Names of S3 buckets to monitor"
  type = object({
    raw_data        = string
    processed_data  = string
    athena_results  = string
  })
}

#==============================================================================
# DEAD LETTER QUEUE CONFIGURATION
#==============================================================================

variable "dlq_names" {
  description = "Names of Dead Letter Queues to monitor"
  type = map(string)
  default = {
    ingestion  = ""
    processing = ""
    validation = ""
  }
}

#==============================================================================
# ALARM THRESHOLDS
#==============================================================================

variable "alarm_thresholds" {
  description = "Threshold values for CloudWatch alarms"
  type = object({
    error_rate_threshold           = number  # Percentage (0.05 = 5%)
    data_quality_threshold         = number  # Score (0.7)
    processing_latency_threshold   = number  # Seconds (60)
    completeness_threshold         = number  # Score (0.8)
    validity_threshold            = number  # Score (0.8)
    availability_threshold        = number  # Percentage (0.95 = 95%)
    s3_storage_threshold_gb       = number  # GB (100)
  })
  default = {
    error_rate_threshold           = 0.05  # 5%
    data_quality_threshold         = 0.7
    processing_latency_threshold   = 60
    completeness_threshold         = 0.8
    validity_threshold            = 0.8
    availability_threshold        = 0.95  # 95%
    s3_storage_threshold_gb       = 100
  }
  
  validation {
    condition = alltrue([
      var.alarm_thresholds.error_rate_threshold >= 0 && var.alarm_thresholds.error_rate_threshold <= 1,
      var.alarm_thresholds.data_quality_threshold >= 0 && var.alarm_thresholds.data_quality_threshold <= 1,
      var.alarm_thresholds.processing_latency_threshold > 0,
      var.alarm_thresholds.completeness_threshold >= 0 && var.alarm_thresholds.completeness_threshold <= 1,
      var.alarm_thresholds.validity_threshold >= 0 && var.alarm_thresholds.validity_threshold <= 1,
      var.alarm_thresholds.availability_threshold >= 0 && var.alarm_thresholds.availability_threshold <= 1,
      var.alarm_thresholds.s3_storage_threshold_gb > 0
    ])
    error_message = "Alarm thresholds must be within valid ranges."
  }
}

#==============================================================================
# BUDGET CONFIGURATION
#==============================================================================

variable "budget_limits" {
  description = "Budget limit configurations"
  type = object({
    monthly_limit = number  # USD
  })
  default = {
    monthly_limit = 200
  }
  
  validation {
    condition     = var.budget_limits.monthly_limit > 0
    error_message = "Monthly budget limit must be greater than 0."
  }
}

variable "budget_thresholds" {
  description = "Budget alert thresholds (percentages)"
  type = object({
    warning_threshold  = number  # 80%
    critical_threshold = number  # 95%
    forecast_threshold = number  # 100%
  })
  default = {
    warning_threshold  = 80
    critical_threshold = 95
    forecast_threshold = 100
  }
  
  validation {
    condition = alltrue([
      var.budget_thresholds.warning_threshold > 0 && var.budget_thresholds.warning_threshold <= 100,
      var.budget_thresholds.critical_threshold > 0 && var.budget_thresholds.critical_threshold <= 100,
      var.budget_thresholds.forecast_threshold > 0 && var.budget_thresholds.forecast_threshold <= 100,
      var.budget_thresholds.warning_threshold < var.budget_thresholds.critical_threshold
    ])
    error_message = "Budget thresholds must be valid percentages and in ascending order."
  }
}

variable "service_budget_limits" {
  description = "Service-specific budget limits"
  type = object({
    lambda_limit   = number
    s3_limit      = number
    dynamodb_limit = number
  })
  default = {
    lambda_limit   = 50
    s3_limit      = 100
    dynamodb_limit = 30
  }
}

variable "enable_service_budgets" {
  description = "Enable service-specific budget tracking"
  type        = bool
  default     = true
}

variable "budget_notification_emails" {
  description = "Email addresses for budget notifications"
  type        = list(string)
  validation {
    condition = alltrue([
      for email in var.budget_notification_emails : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All budget notification emails must be valid email addresses."
  }
}

#==============================================================================
# NOTIFICATION CONFIGURATION
#==============================================================================

variable "alert_email_addresses" {
  description = "Email addresses for general alert notifications"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for email in var.alert_email_addresses : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All alert email addresses must be valid email addresses."
  }
}

variable "critical_alert_email_addresses" {
  description = "Email addresses for critical alert notifications"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for email in var.critical_alert_email_addresses : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All critical alert email addresses must be valid email addresses."
  }
}

variable "enable_sms_alerts" {
  description = "Enable SMS notifications for critical alerts"
  type        = bool
  default     = false
}

variable "sms_phone_numbers" {
  description = "Phone numbers for SMS alerts (E.164 format)"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for phone in var.sms_phone_numbers : can(regex("^\\+[1-9]\\d{1,14}$", phone))
    ])
    error_message = "All phone numbers must be in E.164 format (e.g., +1234567890)."
  }
}

variable "enable_slack_notifications" {
  description = "Enable Slack webhook notifications"
  type        = bool
  default     = false
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = null
#   validation {
#     condition = var.slack_webhook_url == null || can(regex("^https://hooks\\.slack\\.com/services/", var.slack_webhook_url))
#     error_message = "Slack webhook URL must be a valid Slack webhook URL."
#   }
}
#==============================================================================
# DASHBOARD CONFIGURATION
#==============================================================================

variable "create_executive_dashboard" {
  description = "Create executive summary dashboard"
  type        = bool
  default     = true
}

#==============================================================================
# ENCRYPTION CONFIGURATION
#==============================================================================

variable "enable_encryption" {
  description = "Enable encryption for SNS topics and DynamoDB"
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encryption"
  type        = string
  default     = null
}

#==============================================================================
# COST OPTIMIZATION THRESHOLDS
#==============================================================================

variable "cost_optimization_thresholds" {
  description = "Thresholds for cost optimization alerts"
  type = object({
    s3_ia_ratio                  = number  # Minimum IA storage ratio (0.3 = 30%)
    cold_start_threshold         = number  # Maximum cold starts per period
    dynamodb_throttle_threshold  = number  # Maximum throttles per period
  })
  default = {
    s3_ia_ratio                 = 0.3   # 30% of storage should be IA
    cold_start_threshold        = 10    # 10 cold starts per 5 minutes
    dynamodb_throttle_threshold = 5     # 5 throttles per 5 minutes
  }
}

variable "cost_anomaly_thresholds" {
  description = "Cost anomaly detection thresholds"
  type = object({
    impact_threshold = number  # Minimum cost impact for anomaly alert (USD)
  })
  default = {
    impact_threshold = 10  # $10 impact threshold
  }
}