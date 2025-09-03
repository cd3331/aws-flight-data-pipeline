# Flight Data Pipeline - S3 Data Lake Configuration
# This file instantiates the S3 data lake module with appropriate configuration

#==============================================================================
# S3 DATA LAKE MODULE INSTANTIATION
#==============================================================================

module "s3_data_lake" {
  source = "./modules/s3"

  # Core configuration
  project_name  = var.project_name
  environment   = var.environment
  bucket_suffix = random_string.suffix.result

  # Versioning configuration
  enable_versioning        = var.s3_config.enable_versioning
  enable_versioning_athena = false # Query results don't need versioning
  allow_force_destroy      = var.development_config.allow_destructive_changes

  # Encryption configuration
  create_kms_key          = var.security_config.create_kms_key
  kms_key_id              = var.s3_config.kms_key_id
  kms_key_deletion_window = 10
  enable_key_rotation     = var.security_config.enable_encryption_at_rest

  # Lifecycle policies optimized for flight data workloads
  lifecycle_policies = {
    # Raw flight data - high ingestion volume, infrequent access after processing
    raw_data = {
      ia_transition_days                 = 30
      glacier_transition_days            = 60
      deep_archive_transition_days       = 90
      expiration_days                    = 180
      noncurrent_version_expiration_days = min(30, var.s3_config.raw_data_expiration_days / 3)
      multipart_upload_days              = var.s3_config.incomplete_multipart_days
    }

    # Processed flight data - frequent analytics access, longer retention
    processed_data = {
      ia_transition_days                 = 30
      glacier_transition_days            = 90
      deep_archive_transition_days       = 180
      expiration_days                    = 365
      noncurrent_version_expiration_days = 90
      multipart_upload_days              = var.s3_config.incomplete_multipart_days
    }

    # Athena query results - temporary data, aggressive cleanup
    athena_results = {
      ia_transition_days      = 30
      expiration_days         = 60  # Quick cleanup of query results
      curated_expiration_days = 365 # Keep curated datasets longer
      multipart_upload_days   = 1   # Immediate cleanup
    }
  }

  # Intelligent Tiering for automatic cost optimization
  enable_intelligent_tiering = var.cost_optimization.enable_intelligent_tiering
  intelligent_tiering_config = {
    archive_access_days      = 90
    deep_archive_access_days = 180
  }

  # Event notifications for Lambda triggers
  enable_event_notifications = var.feature_flags.enable_data_processing

  # Lambda function integration (conditionally set based on feature flags)
  processing_lambda_arn           = var.feature_flags.enable_data_processing ? local.processing_lambda_arn : null
  processing_lambda_function_name = var.feature_flags.enable_data_processing ? local.resource_names.processing_lambda : null
  validation_lambda_arn           = var.feature_flags.enable_data_validation ? local.validation_lambda_arn : null
  validation_lambda_function_name = var.feature_flags.enable_data_validation ? local.resource_names.validation_lambda : null

  # Cross-region replication for disaster recovery (production only)
  enable_cross_region_replication    = var.environment == "prod" && local.create_resources.cross_region_replication
  replication_destination_bucket_arn = var.environment == "prod" ? local.replication_bucket_arn : null
  replication_kms_key_id             = var.environment == "prod" ? local.replication_kms_key_id : null

  # Access logging for audit and compliance
  enable_access_logging     = var.s3_config.enable_access_logging || var.environment == "prod"
  access_log_retention_days = var.environment == "prod" ? 365 : 90

  # S3 inventory for cost optimization
  enable_inventory = var.s3_config.enable_request_metrics || var.environment == "prod"

  # CloudWatch request metrics
  enable_request_metrics        = var.s3_config.enable_request_metrics
  request_metrics_filter_prefix = "year=" # Focus on partitioned data

  # Transfer acceleration for high-volume ingestion
  enable_transfer_acceleration = var.cost_optimization.use_transfer_acceleration && var.environment == "prod"

  # CORS for web-based analytics tools
  enable_cors = var.feature_flags.enable_api_gateway
  cors_configuration = {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD", "PUT", "POST"]
    allowed_origins = local.cors_allowed_origins
    expose_headers  = ["ETag", "x-amz-meta-*"]
    max_age_seconds = 3000
  }

  # Static website hosting for Athena results (development/demo)
  enable_static_website_hosting = var.development_config.enable_local_development
  website_configuration = {
    index_document = "index.html"
    error_document = "404.html"
  }

  # Cost optimization settings
  cost_optimization_settings = {
    enable_requester_pays = var.cost_optimization.enable_requester_pays && var.environment == "prod"
    enable_mfa_delete     = var.environment == "prod" # Must be configured manually
  }

  # Resource tags
  tags = local.storage_tags
}


#==============================================================================
# S3 DATA LAKE OUTPUTS (RE-EXPORTED)
#==============================================================================

# Export key S3 data lake information for use by other modules
output "s3_data_lake" {
  description = "S3 data lake configuration and bucket information"
  value = {
    # Bucket names and ARNs
    raw_data_bucket_name       = module.s3_data_lake.bucket_names.raw_data
    processed_data_bucket_name = module.s3_data_lake.bucket_names.processed_data
    athena_results_bucket_name = module.s3_data_lake.bucket_names.athena_results

    raw_data_bucket_arn       = module.s3_data_lake.bucket_arns.raw_data
    processed_data_bucket_arn = module.s3_data_lake.bucket_arns.processed_data
    athena_results_bucket_arn = module.s3_data_lake.bucket_arns.athena_results

    # Security configuration
    kms_key_arn = module.s3_data_lake.kms_key != null ? module.s3_data_lake.kms_key.arn : null
    kms_key_id  = module.s3_data_lake.kms_key != null ? module.s3_data_lake.kms_key.key_id : null

    # Feature status
    versioning_enabled          = var.s3_config.enable_versioning
    intelligent_tiering_enabled = var.cost_optimization.enable_intelligent_tiering
    cross_region_replication    = var.environment == "prod"
    access_logging_enabled      = var.s3_config.enable_access_logging || var.environment == "prod"

    # Data lake summary
    architecture  = "Three-tier (Bronze-Silver-Gold)"
    total_buckets = module.s3_data_lake.data_lake_summary.total_buckets
  }
  sensitive = false
}

#==============================================================================
# CLOUDWATCH ALARMS FOR S3 DATA LAKE
#==============================================================================

# CloudWatch alarm for high storage costs
resource "aws_cloudwatch_metric_alarm" "s3_high_storage_cost" {
  count = var.monitoring_config.enable_cost_monitoring ? 1 : 0

  alarm_name          = "${local.name_prefix}-s3-high-storage-cost"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400" # Daily
  statistic           = "Average"
  threshold           = var.monitoring_config.cost_threshold_usd * 1000000000 # Convert to bytes (rough estimate)
  alarm_description   = "S3 storage cost is approaching threshold"
  alarm_actions       = local.alert_routing.warning_alerts

  dimensions = {
    BucketName  = module.s3_data_lake.bucket_names.raw_data
    StorageType = "StandardStorage"
  }

  tags = local.common_tags
}

# CloudWatch alarm for high request errors
resource "aws_cloudwatch_metric_alarm" "s3_high_error_rate" {
  count = var.monitoring_config.enable_custom_metrics ? 1 : 0

  alarm_name          = "${local.name_prefix}-s3-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4xxErrors"
  namespace           = "AWS/S3"
  period              = "300" # 5 minutes
  statistic           = "Sum"
  threshold           = local.monitoring_thresholds.s3_4xx_error_threshold
  alarm_description   = "High S3 4xx error rate detected"
  alarm_actions       = local.alert_routing.critical_alerts

  dimensions = {
    BucketName = module.s3_data_lake.bucket_names.raw_data
  }

  tags = local.common_tags
}

#==============================================================================
# IAM POLICIES FOR S3 DATA LAKE ACCESS
#==============================================================================

# IAM policy for Lambda functions to access S3 data lake
resource "aws_iam_policy" "s3_data_lake_lambda_access" {
  name        = "${local.name_prefix}-s3-data-lake-lambda-access"
  path        = var.security_config.iam_path_prefix
  description = "IAM policy for Lambda functions to access S3 data lake"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Raw data bucket access (read/write for ingestion)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:DeleteObject"
        ]
        Resource = "${module.s3_data_lake.bucket_arns.raw_data}/*"
      },
      # Processed data bucket access (read/write for processing)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:DeleteObject"
        ]
        Resource = "${module.s3_data_lake.bucket_arns.processed_data}/*"
      },
      # Athena results bucket access (read/write for validation)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${module.s3_data_lake.bucket_arns.athena_results}/*"
      },
      # Bucket listing permissions
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning"
        ]
        Resource = [
          module.s3_data_lake.bucket_arns.raw_data,
          module.s3_data_lake.bucket_arns.processed_data,
          module.s3_data_lake.bucket_arns.athena_results
        ]
      },
      # KMS permissions for encryption/decryption
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = module.s3_data_lake.kms_key != null ? module.s3_data_lake.kms_key.arn : var.s3_config.kms_key_id
      }
    ]
  })

  tags = local.security_tags
}

# Output the IAM policy ARN for use by Lambda modules
output "s3_lambda_access_policy_arn" {
  description = "ARN of the IAM policy for Lambda S3 data lake access"
  value       = aws_iam_policy.s3_data_lake_lambda_access.arn
}