# S3 Data Lake Module - Outputs
# This file defines all output values from the S3 module

#==============================================================================
# BUCKET INFORMATION
#==============================================================================

output "raw_data_bucket" {
  description = "Raw data bucket (Bronze layer) information"
  value = {
    id                          = aws_s3_bucket.raw_data.id
    arn                         = aws_s3_bucket.raw_data.arn
    domain_name                 = aws_s3_bucket.raw_data.bucket_domain_name
    regional_domain_name        = aws_s3_bucket.raw_data.bucket_regional_domain_name
    hosted_zone_id             = aws_s3_bucket.raw_data.hosted_zone_id
    region                     = aws_s3_bucket.raw_data.region
    versioning_enabled         = var.enable_versioning
    encryption_enabled         = true
    kms_key_id                = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
    lifecycle_configured       = true
    intelligent_tiering_enabled = var.enable_intelligent_tiering
  }
}

output "processed_data_bucket" {
  description = "Processed data bucket (Silver layer) information"
  value = {
    id                          = aws_s3_bucket.processed_data.id
    arn                         = aws_s3_bucket.processed_data.arn
    domain_name                 = aws_s3_bucket.processed_data.bucket_domain_name
    regional_domain_name        = aws_s3_bucket.processed_data.bucket_regional_domain_name
    hosted_zone_id             = aws_s3_bucket.processed_data.hosted_zone_id
    region                     = aws_s3_bucket.processed_data.region
    versioning_enabled         = var.enable_versioning
    encryption_enabled         = true
    kms_key_id                = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
    lifecycle_configured       = true
    intelligent_tiering_enabled = var.enable_intelligent_tiering
    replication_enabled        = var.enable_cross_region_replication
  }
}

output "athena_results_bucket" {
  description = "Athena results bucket (Gold layer) information"
  value = {
    id                          = aws_s3_bucket.athena_results.id
    arn                         = aws_s3_bucket.athena_results.arn
    domain_name                 = aws_s3_bucket.athena_results.bucket_domain_name
    regional_domain_name        = aws_s3_bucket.athena_results.bucket_regional_domain_name
    hosted_zone_id             = aws_s3_bucket.athena_results.hosted_zone_id
    region                     = aws_s3_bucket.athena_results.region
    versioning_enabled         = var.enable_versioning_athena
    encryption_enabled         = true
    kms_key_id                = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
    lifecycle_configured       = true
    website_hosting_enabled    = var.enable_static_website_hosting
  }
}

#==============================================================================
# BUCKET NAMES (FOR REFERENCE)
#==============================================================================

output "bucket_names" {
  description = "Names of all S3 buckets in the data lake"
  value = {
    raw_data       = aws_s3_bucket.raw_data.id
    processed_data = aws_s3_bucket.processed_data.id
    athena_results = aws_s3_bucket.athena_results.id
    access_logs    = var.enable_access_logging ? aws_s3_bucket.access_logs[0].id : null
  }
}

output "bucket_arns" {
  description = "ARNs of all S3 buckets in the data lake"
  value = {
    raw_data       = aws_s3_bucket.raw_data.arn
    processed_data = aws_s3_bucket.processed_data.arn
    athena_results = aws_s3_bucket.athena_results.arn
    access_logs    = var.enable_access_logging ? aws_s3_bucket.access_logs[0].arn : null
  }
}

#==============================================================================
# KMS ENCRYPTION INFORMATION
#==============================================================================

output "kms_key" {
  description = "KMS key information for S3 encryption"
  value = var.create_kms_key ? {
    id                 = aws_kms_key.s3_data_lake_key[0].id
    arn                = aws_kms_key.s3_data_lake_key[0].arn
    key_id             = aws_kms_key.s3_data_lake_key[0].key_id
    alias_name         = aws_kms_alias.s3_data_lake_key_alias[0].name
    alias_arn          = aws_kms_alias.s3_data_lake_key_alias[0].arn
    key_rotation_enabled = var.enable_key_rotation
  } : null
}

output "encryption_configuration" {
  description = "Encryption configuration details"
  value = {
    kms_key_id    = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
    algorithm     = "aws:kms"
    bucket_key_enabled = true
    key_rotation_enabled = var.create_kms_key ? var.enable_key_rotation : null
  }
}

#==============================================================================
# LIFECYCLE POLICIES INFORMATION
#==============================================================================

output "lifecycle_policies" {
  description = "Applied lifecycle policies for cost optimization"
  value = {
    raw_data = {
      ia_transition_days    = var.lifecycle_policies.raw_data.ia_transition_days
      glacier_transition_days = var.lifecycle_policies.raw_data.glacier_transition_days
      deep_archive_transition_days = var.lifecycle_policies.raw_data.deep_archive_transition_days
      expiration_days      = var.lifecycle_policies.raw_data.expiration_days
      intelligent_tiering  = var.enable_intelligent_tiering
    }
    processed_data = {
      ia_transition_days    = var.lifecycle_policies.processed_data.ia_transition_days
      glacier_transition_days = var.lifecycle_policies.processed_data.glacier_transition_days
      deep_archive_transition_days = var.lifecycle_policies.processed_data.deep_archive_transition_days
      expiration_days      = var.lifecycle_policies.processed_data.expiration_days
      intelligent_tiering  = var.enable_intelligent_tiering
    }
    athena_results = {
      ia_transition_days   = var.lifecycle_policies.athena_results.ia_transition_days
      expiration_days     = var.lifecycle_policies.athena_results.expiration_days
      curated_expiration_days = var.lifecycle_policies.athena_results.curated_expiration_days
    }
  }
}

#==============================================================================
# EVENT NOTIFICATIONS INFORMATION
#==============================================================================

output "event_notifications" {
  description = "S3 event notification configuration"
  value = {
    enabled = var.enable_event_notifications
    raw_data_triggers = var.enable_event_notifications ? {
      lambda_function_arn = var.processing_lambda_arn
      events = ["s3:ObjectCreated:*"]
      filter_prefix = "year="
      filter_suffix = ".json"
    } : null
    processed_data_triggers = var.enable_event_notifications && var.validation_lambda_arn != null ? {
      lambda_function_arn = var.validation_lambda_arn
      events = ["s3:ObjectCreated:*"]
      filter_prefix = "year="
      filter_suffix = ".parquet"
    } : null
  }
}

#==============================================================================
# REPLICATION INFORMATION
#==============================================================================

output "replication_configuration" {
  description = "Cross-region replication configuration"
  value = var.enable_cross_region_replication ? {
    enabled = true
    source_bucket = aws_s3_bucket.processed_data.id
    destination_bucket_arn = var.replication_destination_bucket_arn
    replication_role_arn = aws_iam_role.s3_replication_role[0].arn
    kms_key_id = var.replication_kms_key_id
  } : null
}

#==============================================================================
# ACCESS LOGGING INFORMATION
#==============================================================================

output "access_logging" {
  description = "S3 access logging configuration"
  value = var.enable_access_logging ? {
    enabled = true
    log_bucket = aws_s3_bucket.access_logs[0].id
    log_bucket_arn = aws_s3_bucket.access_logs[0].arn
    retention_days = var.access_log_retention_days
    raw_data_prefix = "raw-data-access-logs/"
    processed_data_prefix = "processed-data-access-logs/"
  } : null
}

#==============================================================================
# COST OPTIMIZATION INFORMATION
#==============================================================================

output "cost_optimization" {
  description = "Cost optimization features enabled"
  value = {
    intelligent_tiering_enabled = var.enable_intelligent_tiering
    lifecycle_policies_enabled = true
    versioning_optimization = {
      raw_data_versioning = var.enable_versioning
      processed_data_versioning = var.enable_versioning
      athena_results_versioning = var.enable_versioning_athena
    }
    storage_class_optimization = {
      ia_transitions = true
      glacier_transitions = true
      deep_archive_transitions = true
    }
    multipart_upload_cleanup = true
    access_logging_cost = var.enable_access_logging
    inventory_cost = var.enable_inventory
    transfer_acceleration_cost = var.enable_transfer_acceleration
  }
}

#==============================================================================
# SECURITY INFORMATION
#==============================================================================

output "security_configuration" {
  description = "Security configuration applied to buckets"
  value = {
    encryption_at_rest = {
      enabled = true
      kms_managed = var.create_kms_key
      key_rotation = var.create_kms_key ? var.enable_key_rotation : null
    }
    public_access_blocked = {
      raw_data = true
      processed_data = true
      athena_results = true
    }
    ssl_requests_only = true
    versioning_enabled = {
      raw_data = var.enable_versioning
      processed_data = var.enable_versioning
      athena_results = var.enable_versioning_athena
    }
    mfa_delete_enabled = var.cost_optimization_settings.enable_mfa_delete
  }
}

#==============================================================================
# INVENTORY INFORMATION
#==============================================================================

output "inventory_configuration" {
  description = "S3 inventory configuration for cost analysis"
  value = var.enable_inventory ? {
    enabled = true
    raw_data_inventory = {
      name = "raw-data-inventory"
      frequency = "Weekly"
      destination = aws_s3_bucket.athena_results.arn
      prefix = "inventory/raw-data/"
    }
    processed_data_inventory = {
      name = "processed-data-inventory"
      frequency = "Weekly"
      destination = aws_s3_bucket.athena_results.arn
      prefix = "inventory/processed-data/"
    }
  } : null
}

#==============================================================================
# DATA LAKE SUMMARY
#==============================================================================

output "data_lake_summary" {
  description = "Complete data lake architecture summary"
  value = {
    architecture = "Three-tier (Bronze-Silver-Gold)"
    total_buckets = var.enable_access_logging ? 4 : 3
    layers = {
      bronze = {
        name = "Raw Data Layer"
        bucket = aws_s3_bucket.raw_data.id
        purpose = "Flight data ingestion and raw storage"
        retention_days = var.lifecycle_policies.raw_data.expiration_days
        access_pattern = "Write-heavy, infrequent reads"
      }
      silver = {
        name = "Processed Data Layer" 
        bucket = aws_s3_bucket.processed_data.id
        purpose = "Cleaned and transformed flight data"
        retention_days = var.lifecycle_policies.processed_data.expiration_days
        access_pattern = "Read-heavy for analytics"
      }
      gold = {
        name = "Analytics Layer"
        bucket = aws_s3_bucket.athena_results.id
        purpose = "Query results and curated datasets"
        retention_days = var.lifecycle_policies.athena_results.expiration_days
        access_pattern = "Temporary query results"
      }
    }
    features_enabled = {
      encryption = true
      versioning = var.enable_versioning
      lifecycle_policies = true
      event_notifications = var.enable_event_notifications
      intelligent_tiering = var.enable_intelligent_tiering
      cross_region_replication = var.enable_cross_region_replication
      access_logging = var.enable_access_logging
      inventory = var.enable_inventory
    }
    estimated_monthly_cost_factors = {
      storage_classes = ["STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE"]
      request_costs = var.enable_request_metrics
      transfer_costs = var.enable_transfer_acceleration
      kms_costs = var.create_kms_key
      replication_costs = var.enable_cross_region_replication
    }
  }
}