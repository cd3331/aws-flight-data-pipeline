# S3 Data Lake Module - Local Values
# This file contains computed values and local configurations for the S3 module

locals {
  #==============================================================================
  # BUCKET NAMING
  #==============================================================================
  
  # Generate consistent bucket names with global uniqueness
  bucket_names = {
    raw_data       = "${var.project_name}-${var.environment}-raw-data${var.bucket_suffix != "" ? "-${var.bucket_suffix}" : ""}"
    processed_data = "${var.project_name}-${var.environment}-processed-data${var.bucket_suffix != "" ? "-${var.bucket_suffix}" : ""}"
    athena_results = "${var.project_name}-${var.environment}-athena-results${var.bucket_suffix != "" ? "-${var.bucket_suffix}" : ""}"
  }
  
  #==============================================================================
  # ENVIRONMENT-SPECIFIC CONFIGURATIONS
  #==============================================================================
  
  # Environment-based lifecycle optimization
  environment_configs = {
    dev = {
      # Development - aggressive cost optimization
      raw_data_retention_days       = 30    # Shorter retention
      processed_data_retention_days = 90
      athena_results_retention_days = 7
      enable_versioning            = false  # Reduce costs in dev
      enable_cross_region_replication = false
      enable_detailed_monitoring   = false
      intelligent_tiering_enabled  = false
      multipart_threshold_mb       = 64     # Smaller threshold
    }
    staging = {
      # Staging - balanced approach
      raw_data_retention_days       = 90
      processed_data_retention_days = 180
      athena_results_retention_days = 30
      enable_versioning            = true
      enable_cross_region_replication = false
      enable_detailed_monitoring   = true
      intelligent_tiering_enabled  = var.enable_intelligent_tiering
      multipart_threshold_mb       = 128
    }
    prod = {
      # Production - optimized for compliance and performance
      raw_data_retention_days       = 365   # 1 year
      processed_data_retention_days = 2555  # 7 years for compliance
      athena_results_retention_days = 90
      enable_versioning            = true
      enable_cross_region_replication = var.enable_cross_region_replication
      enable_detailed_monitoring   = true
      intelligent_tiering_enabled  = var.enable_intelligent_tiering
      multipart_threshold_mb       = 256
    }
  }
  
  # Current environment configuration
  current_config = local.environment_configs[var.environment]
  
  #==============================================================================
  # STORAGE CLASS TRANSITION OPTIMIZATION
  #==============================================================================
  
  # Optimized lifecycle policies based on data access patterns
  optimized_lifecycle_policies = {
    # Raw data - write-heavy, infrequent reads after processing
    raw_data = {
      ia_transition_days    = var.environment == "dev" ? 3 : var.lifecycle_policies.raw_data.ia_transition_days
      glacier_transition_days = var.environment == "dev" ? 7 : var.lifecycle_policies.raw_data.glacier_transition_days
      deep_archive_transition_days = var.environment == "dev" ? 14 : var.lifecycle_policies.raw_data.deep_archive_transition_days
      expiration_days      = local.current_config.raw_data_retention_days
    }
    
    # Processed data - read-heavy for analytics, longer retention
    processed_data = {
      ia_transition_days    = var.lifecycle_policies.processed_data.ia_transition_days
      glacier_transition_days = var.lifecycle_policies.processed_data.glacier_transition_days
      deep_archive_transition_days = var.lifecycle_policies.processed_data.deep_archive_transition_days
      expiration_days      = local.current_config.processed_data_retention_days
    }
    
    # Athena results - temporary data, quick cleanup
    athena_results = {
      ia_transition_days   = var.lifecycle_policies.athena_results.ia_transition_days
      expiration_days     = local.current_config.athena_results_retention_days
      curated_expiration_days = var.lifecycle_policies.athena_results.curated_expiration_days
    }
  }
  
  #==============================================================================
  # ACCESS PATTERN OPTIMIZATION
  #==============================================================================
  
  # Define access patterns for intelligent tiering configuration
  access_patterns = {
    raw_data = {
      # High write volume, low read volume after processing
      access_frequency = "low"
      tiering_enabled  = var.enable_intelligent_tiering && var.environment == "prod"
      archive_threshold_days = 30
      deep_archive_threshold_days = 90
    }
    
    processed_data = {
      # Medium to high read volume for analytics
      access_frequency = "medium"
      tiering_enabled  = var.enable_intelligent_tiering
      archive_threshold_days = 90
      deep_archive_threshold_days = 180
    }
    
    athena_results = {
      # Low read volume, temporary storage
      access_frequency = "low"
      tiering_enabled  = false  # Not beneficial for short-lived data
      archive_threshold_days = 0
      deep_archive_threshold_days = 0
    }
  }
  
  #==============================================================================
  # SECURITY CONFIGURATIONS
  #==============================================================================
  
  # Bucket policy statements for enhanced security
  bucket_policy_statements = {
    # Deny unencrypted uploads
    deny_unencrypted_uploads = {
      effect = "Deny"
      principals = ["*"]
      actions = ["s3:PutObject"]
      condition = {
        test = "StringNotEquals"
        variable = "s3:x-amz-server-side-encryption"
        values = ["aws:kms"]
      }
    }
    
    # Deny uploads without proper encryption context
    deny_wrong_encryption_key = {
      effect = "Deny"
      principals = ["*"]
      actions = ["s3:PutObject"]
      condition = {
        test = "StringNotLikeIfExists"
        variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
        values = [var.create_kms_key ? "arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:key/*" : var.kms_key_id]
      }
    }
    
    # Deny non-SSL requests
    deny_non_ssl = {
      effect = "Deny"
      principals = ["*"]
      actions = ["s3:*"]
      condition = {
        test = "Bool"
        variable = "aws:SecureTransport"
        values = ["false"]
      }
    }
  }
  
  #==============================================================================
  # MONITORING AND ALERTING CONFIGURATIONS
  #==============================================================================
  
  # CloudWatch metrics configuration
  cloudwatch_metrics = {
    raw_data = {
      enable_request_metrics = var.enable_request_metrics || local.current_config.enable_detailed_monitoring
      enable_replication_metrics = var.enable_cross_region_replication
      metrics_filter_prefix = "year="  # Focus on partitioned data
    }
    
    processed_data = {
      enable_request_metrics = var.enable_request_metrics || local.current_config.enable_detailed_monitoring
      enable_replication_metrics = var.enable_cross_region_replication
      metrics_filter_prefix = ""  # Monitor all objects
    }
    
    athena_results = {
      enable_request_metrics = var.enable_request_metrics && var.environment == "prod"
      enable_replication_metrics = false
      metrics_filter_prefix = "query-results/"
    }
  }
  
  #==============================================================================
  # COST OPTIMIZATION CALCULATIONS
  #==============================================================================
  
  # Cost optimization settings based on environment and usage patterns
  cost_optimization = {
    # Storage class optimization
    use_intelligent_tiering = var.enable_intelligent_tiering && local.current_config.intelligent_tiering_enabled
    use_reduced_redundancy  = var.environment == "dev"  # Only for non-critical dev data
    
    # Request optimization
    enable_transfer_acceleration = var.enable_transfer_acceleration && var.environment == "prod"
    multipart_threshold_bytes   = local.current_config.multipart_threshold_mb * 1024 * 1024
    
    # Lifecycle optimization
    aggressive_lifecycle = var.environment == "dev"
    compliance_lifecycle = var.environment == "prod"
    
    # Monitoring optimization
    enable_inventory        = var.enable_inventory || (var.environment == "prod")
    enable_analytics       = var.environment != "dev"
    enable_request_payment = var.cost_optimization_settings.enable_requester_pays && var.environment == "prod"
  }
  
  #==============================================================================
  # NOTIFICATION CONFIGURATIONS
  #==============================================================================
  
  # Event notification configurations for each bucket
  notification_events = {
    raw_data = {
      object_created = [
        "s3:ObjectCreated:Put",
        "s3:ObjectCreated:Post",
        "s3:ObjectCreated:CompleteMultipartUpload"
      ]
      object_removed = var.environment == "prod" ? ["s3:ObjectRemoved:Delete"] : []
      filter_prefixes = ["year="]  # Only notify for partitioned data
      filter_suffixes = [".json"]  # Only JSON files
    }
    
    processed_data = {
      object_created = [
        "s3:ObjectCreated:Put",
        "s3:ObjectCreated:Post",
        "s3:ObjectCreated:CompleteMultipartUpload"
      ]
      object_removed = var.environment == "prod" ? ["s3:ObjectRemoved:Delete"] : []
      filter_prefixes = ["year="]
      filter_suffixes = [".parquet"]  # Only Parquet files
    }
    
    athena_results = {
      object_created = []  # Usually no notifications needed
      object_removed = []
      filter_prefixes = []
      filter_suffixes = []
    }
  }
  
  #==============================================================================
  # COMPLIANCE AND GOVERNANCE
  #==============================================================================
  
  # Compliance settings based on environment
  compliance_settings = {
    object_lock_enabled = var.environment == "prod"  # Enable for production compliance
    mfa_delete_enabled  = var.cost_optimization_settings.enable_mfa_delete && var.environment == "prod"
    
    # Retention policies for compliance
    legal_hold_enabled = var.environment == "prod"
    retention_mode = var.environment == "prod" ? "COMPLIANCE" : "GOVERNANCE"
    
    # Audit settings
    cloudtrail_enabled = var.environment == "prod"
    access_logging_enabled = var.enable_access_logging || var.environment == "prod"
    
    # Data classification
    data_classification = {
      raw_data       = "Internal"
      processed_data = "Internal"
      athena_results = "Internal"
    }
  }
  
  #==============================================================================
  # PERFORMANCE OPTIMIZATION
  #==============================================================================
  
  # Performance settings based on workload patterns
  performance_settings = {
    # Request rate optimization
    request_rate_optimization = {
      raw_data = {
        # High write rate optimization
        prefix_randomization = true
        multipart_enabled   = true
        transfer_acceleration = var.enable_transfer_acceleration
      }
      processed_data = {
        # Balanced read/write optimization
        prefix_randomization = false  # Analytics workloads prefer predictable prefixes
        multipart_enabled   = true
        transfer_acceleration = false
      }
      athena_results = {
        # Low volume, temporary data
        prefix_randomization = false
        multipart_enabled   = false
        transfer_acceleration = false
      }
    }
    
    # Caching and CDN settings (if web access needed)
    cdn_enabled = var.enable_static_website_hosting
    cache_control_max_age = var.enable_static_website_hosting ? 3600 : 0
  }
  
  #==============================================================================
  # VALIDATION FLAGS
  #==============================================================================
  
  # Runtime validation checks
  validation_checks = {
    bucket_names_valid = alltrue([
      length(local.bucket_names.raw_data) >= 3,
      length(local.bucket_names.raw_data) <= 63,
      length(local.bucket_names.processed_data) >= 3,
      length(local.bucket_names.processed_data) <= 63,
      length(local.bucket_names.athena_results) >= 3,
      length(local.bucket_names.athena_results) <= 63
    ])
    
    lifecycle_policies_valid = alltrue([
      local.optimized_lifecycle_policies.raw_data.ia_transition_days > 0,
      local.optimized_lifecycle_policies.processed_data.glacier_transition_days > local.optimized_lifecycle_policies.processed_data.ia_transition_days,
      local.optimized_lifecycle_policies.athena_results.expiration_days > 0
    ])
    
    encryption_valid = var.create_kms_key || var.kms_key_id != ""
  }
}