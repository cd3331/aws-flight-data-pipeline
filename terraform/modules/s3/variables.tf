# S3 Data Lake Module - Variables
# This file defines all input variables for the S3 data lake module

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
# BUCKET CONFIGURATION
#==============================================================================

variable "bucket_suffix" {
  description = "Random suffix for bucket names to ensure global uniqueness"
  type        = string
  default     = ""
}

variable "enable_versioning" {
  description = "Enable versioning for raw and processed data buckets"
  type        = bool
  default     = true
}

variable "enable_versioning_athena" {
  description = "Enable versioning for Athena results bucket (usually not needed)"
  type        = bool
  default     = false
}

variable "allow_force_destroy" {
  description = "Allow force destroy of buckets (useful for dev environments)"
  type        = bool
  default     = false
}

#==============================================================================
# ENCRYPTION CONFIGURATION
#==============================================================================

variable "create_kms_key" {
  description = "Create a custom KMS key for S3 encryption"
  type        = bool
  default     = false
}

variable "kms_key_id" {
  description = "KMS key ID for S3 encryption (used if create_kms_key is false)"
  type        = string
  default     = "arn:aws:kms:*:*:alias/aws/s3"
}

variable "kms_key_deletion_window" {
  description = "KMS key deletion window in days"
  type        = number
  default     = 10
  validation {
    condition     = var.kms_key_deletion_window >= 7 && var.kms_key_deletion_window <= 30
    error_message = "KMS key deletion window must be between 7 and 30 days."
  }
}

variable "enable_key_rotation" {
  description = "Enable automatic KMS key rotation"
  type        = bool
  default     = true
}

#==============================================================================
# LIFECYCLE POLICIES CONFIGURATION
#==============================================================================

variable "lifecycle_policies" {
  description = "Lifecycle policies for each bucket type"
  type = object({
    raw_data = object({
      ia_transition_days              = number
      glacier_transition_days         = number
      deep_archive_transition_days    = number
      expiration_days                 = number
      noncurrent_version_expiration_days = number
      multipart_upload_days          = number
    })
    processed_data = object({
      ia_transition_days              = number
      glacier_transition_days         = number
      deep_archive_transition_days    = number
      expiration_days                 = number
      noncurrent_version_expiration_days = number
      multipart_upload_days          = number
    })
    athena_results = object({
      ia_transition_days       = number
      expiration_days         = number
      curated_expiration_days = number
      multipart_upload_days   = number
    })
  })
  
  default = {
    # Raw data - aggressive cost optimization (high write, low read)
    raw_data = {
      ia_transition_days              = 30   # Standard-IA minimum 30 days requirement
      glacier_transition_days         = 60   # Glacier after 60 days (increased from 30)
      deep_archive_transition_days    = 90   # Deep Archive after 3 months
      expiration_days                 = 365  # Delete after 1 year
      noncurrent_version_expiration_days = 30 # Delete old versions after 1 month
      multipart_upload_days          = 1    # Quick cleanup of failed uploads
    }
    
    # Processed data - balanced for analytics (frequent reads, medium retention)
    processed_data = {
      ia_transition_days              = 30   # Standard-IA minimum 30 days requirement
      glacier_transition_days         = 90   # Glacier after 3 months
      deep_archive_transition_days    = 365  # Deep Archive after 1 year
      expiration_days                 = 2555 # Delete after 7 years (compliance)
      noncurrent_version_expiration_days = 90 # Keep versions longer for analytics
      multipart_upload_days          = 7    # Standard cleanup
    }
    
    # Athena results - quick cleanup (temporary query results)
    athena_results = {
      ia_transition_days       = 30   # Standard-IA minimum 30 days requirement
      expiration_days         = 60   # Delete query results after 60 days (increased from 30)
      curated_expiration_days = 365  # Keep curated datasets longer
      multipart_upload_days   = 1    # Immediate cleanup
    }
  }
  
  validation {
    condition = alltrue([
      var.lifecycle_policies.raw_data.ia_transition_days > 0,
      var.lifecycle_policies.raw_data.glacier_transition_days > var.lifecycle_policies.raw_data.ia_transition_days,
      var.lifecycle_policies.raw_data.expiration_days > var.lifecycle_policies.raw_data.glacier_transition_days,
      var.lifecycle_policies.processed_data.ia_transition_days > 0,
      var.lifecycle_policies.processed_data.glacier_transition_days > var.lifecycle_policies.processed_data.ia_transition_days,
      var.lifecycle_policies.athena_results.expiration_days > var.lifecycle_policies.athena_results.ia_transition_days
    ])
    error_message = "Lifecycle transition days must be in ascending order and positive."
  }
}

#==============================================================================
# INTELLIGENT TIERING CONFIGURATION
#==============================================================================

variable "enable_intelligent_tiering" {
  description = "Enable S3 Intelligent Tiering for automatic cost optimization"
  type        = bool
  default     = false
}

variable "intelligent_tiering_config" {
  description = "Configuration for S3 Intelligent Tiering"
  type = object({
    archive_access_days      = number
    deep_archive_access_days = number
  })
  default = {
    archive_access_days      = 90   # Move to Archive Access after 90 days
    deep_archive_access_days = 180  # Move to Deep Archive Access after 180 days
  }
  validation {
    condition     = var.intelligent_tiering_config.deep_archive_access_days > var.intelligent_tiering_config.archive_access_days
    error_message = "Deep archive access days must be greater than archive access days."
  }
}

#==============================================================================
# EVENT NOTIFICATIONS CONFIGURATION
#==============================================================================

variable "enable_event_notifications" {
  description = "Enable S3 event notifications for Lambda triggers"
  type        = bool
  default     = true
}

variable "processing_lambda_arn" {
  description = "ARN of the Lambda function to trigger for raw data processing"
  type        = string
  default     = null
}

variable "processing_lambda_function_name" {
  description = "Name of the Lambda function for processing (used for permissions)"
  type        = string
  default     = null
}

variable "validation_lambda_arn" {
  description = "ARN of the Lambda function to trigger for data validation"
  type        = string
  default     = null
}

variable "validation_lambda_function_name" {
  description = "Name of the Lambda function for validation (used for permissions)"
  type        = string
  default     = null
}

#==============================================================================
# CROSS-REGION REPLICATION CONFIGURATION
#==============================================================================

variable "enable_cross_region_replication" {
  description = "Enable cross-region replication for disaster recovery"
  type        = bool
  default     = false
}

variable "replication_destination_bucket_arn" {
  description = "ARN of the destination bucket for cross-region replication"
  type        = string
  default     = null
}

variable "replication_kms_key_id" {
  description = "KMS key ID for replication encryption"
  type        = string
  default     = null
}

#==============================================================================
# ACCESS LOGGING CONFIGURATION
#==============================================================================

variable "enable_access_logging" {
  description = "Enable S3 access logging for audit purposes"
  type        = bool
  default     = false
}

variable "access_log_retention_days" {
  description = "Number of days to retain access logs"
  type        = number
  default     = 90
  validation {
    condition     = var.access_log_retention_days > 0 && var.access_log_retention_days <= 2555
    error_message = "Access log retention days must be between 1 and 2555."
  }
}

#==============================================================================
# S3 INVENTORY CONFIGURATION
#==============================================================================

variable "enable_inventory" {
  description = "Enable S3 inventory for cost optimization and management"
  type        = bool
  default     = false
}

#==============================================================================
# REQUEST METRICS CONFIGURATION
#==============================================================================

variable "enable_request_metrics" {
  description = "Enable CloudWatch request metrics for S3 buckets"
  type        = bool
  default     = false
}

variable "request_metrics_filter_prefix" {
  description = "Prefix filter for request metrics (empty for all objects)"
  type        = string
  default     = ""
}

#==============================================================================
# TRANSFER ACCELERATION CONFIGURATION
#==============================================================================

variable "enable_transfer_acceleration" {
  description = "Enable S3 Transfer Acceleration for faster uploads"
  type        = bool
  default     = false
}

#==============================================================================
# CORS CONFIGURATION
#==============================================================================

variable "enable_cors" {
  description = "Enable CORS configuration for web access"
  type        = bool
  default     = false
}

variable "cors_configuration" {
  description = "CORS configuration for S3 buckets"
  type = object({
    allowed_headers = list(string)
    allowed_methods = list(string)
    allowed_origins = list(string)
    expose_headers  = list(string)
    max_age_seconds = number
  })
  default = {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

#==============================================================================
# WEBSITE CONFIGURATION
#==============================================================================

variable "enable_static_website_hosting" {
  description = "Enable static website hosting for Athena results bucket"
  type        = bool
  default     = false
}

variable "website_configuration" {
  description = "Static website hosting configuration"
  type = object({
    index_document = string
    error_document = string
  })
  default = {
    index_document = "index.html"
    error_document = "error.html"
  }
}

#==============================================================================
# COST OPTIMIZATION SETTINGS
#==============================================================================

variable "cost_optimization_settings" {
  description = "Additional cost optimization settings"
  type = object({
    enable_requester_pays = bool
    enable_mfa_delete    = bool
  })
  default = {
    enable_requester_pays = false  # Make requestor pay for requests and data transfer
    enable_mfa_delete    = false   # Require MFA for object deletion (production)
  }
}