# S3 Data Lake Architecture - Main Configuration
# This module creates a three-tier S3 data lake with Bronze, Silver, and Gold layers

#==============================================================================
# KMS KEYS FOR ENCRYPTION
#==============================================================================

# KMS key for S3 bucket encryption
resource "aws_kms_key" "s3_data_lake_key" {
  count = var.create_kms_key ? 1 : 0
  
  description             = "KMS key for ${var.project_name} S3 data lake encryption"
  deletion_window_in_days = var.kms_key_deletion_window
  enable_key_rotation     = var.enable_key_rotation
  
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "s3-data-lake-key-policy"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 Service"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda Service"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Athena Service"
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
  
  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-s3-kms-key"
    Description = "KMS key for S3 data lake encryption"
  })
}

# KMS key alias for easier reference
resource "aws_kms_alias" "s3_data_lake_key_alias" {
  count = var.create_kms_key ? 1 : 0
  
  name          = "alias/${var.project_name}-${var.environment}-s3-data-lake"
  target_key_id = aws_kms_key.s3_data_lake_key[0].key_id
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

#==============================================================================
# BRONZE LAYER - RAW DATA BUCKET
#==============================================================================

# Raw data bucket (Bronze layer) - for incoming flight data
resource "aws_s3_bucket" "raw_data" {
  bucket        = local.bucket_names.raw_data
  force_destroy = var.allow_force_destroy
  
  tags = merge(var.tags, {
    Name        = local.bucket_names.raw_data
    Layer       = "Bronze"
    DataType    = "Raw"
    Purpose     = "Flight data ingestion and raw storage"
    Retention   = "Short-term"
    AccessPattern = "Write-heavy with occasional reads"
  })
}

# Raw data bucket versioning
resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

# Raw data bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Raw data bucket public access block
resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Raw data bucket lifecycle policy - simplified expiration only
resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  
  rule {
    id     = "raw_data_lifecycle"
    status = "Enabled"
    
    # Apply to all objects
    filter {}
    
    # Delete objects after 90 days
    expiration {
      days = 90
    }
    
    
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  
  # Separate rule for delete markers cleanup
  rule {
    id     = "raw_data_delete_markers"
    status = "Enabled"
    
    filter {}
    
    # Remove delete markers when they become the only version
    expiration {
      expired_object_delete_marker = true
    }
  }
}

# Raw data bucket intelligent tiering
resource "aws_s3_bucket_intelligent_tiering_configuration" "raw_data" {
  count = var.enable_intelligent_tiering ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  name   = "raw-data-intelligent-tiering"
  
  filter {
    prefix = "year="
  }
  
  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_config.archive_access_days
  }
  
  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_config.deep_archive_access_days
  }
}

#==============================================================================
# SILVER LAYER - PROCESSED DATA BUCKET
#==============================================================================

# Processed data bucket (Silver layer) - for cleaned and transformed data
resource "aws_s3_bucket" "processed_data" {
  bucket        = local.bucket_names.processed_data
  force_destroy = var.allow_force_destroy
  
  tags = merge(var.tags, {
    Name        = local.bucket_names.processed_data
    Layer       = "Silver"
    DataType    = "Processed"
    Purpose     = "Cleaned and transformed flight data"
    Retention   = "Medium-term"
    AccessPattern = "Read-heavy for analytics"
  })
}

# Processed data bucket versioning
resource "aws_s3_bucket_versioning" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

# Processed data bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Processed data bucket public access block
resource "aws_s3_bucket_public_access_block" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Processed data bucket lifecycle policy - simplified expiration only
resource "aws_s3_bucket_lifecycle_configuration" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  
  rule {
    id     = "processed_data_lifecycle"
    status = "Enabled"
    
    filter {}
    
    # Delete objects after 365 days
    expiration {
      days = 365
    }
    
    
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Processed data bucket intelligent tiering
resource "aws_s3_bucket_intelligent_tiering_configuration" "processed_data" {
  count = var.enable_intelligent_tiering ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed-data-intelligent-tiering"
  
  # Apply to all objects
  filter {
    prefix = ""
  }
  
  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_config.archive_access_days
  }
  
  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_config.deep_archive_access_days
  }
}

#==============================================================================
# GOLD LAYER - ATHENA RESULTS BUCKET
#==============================================================================

# Athena results bucket - for query results and curated datasets
resource "aws_s3_bucket" "athena_results" {
  bucket        = local.bucket_names.athena_results
  force_destroy = var.allow_force_destroy
  
  tags = merge(var.tags, {
    Name        = local.bucket_names.athena_results
    Layer       = "Gold"
    DataType    = "QueryResults"
    Purpose     = "Athena query results and curated datasets"
    Retention   = "Short-term"
    AccessPattern = "Temporary query results"
  })
}

# Athena results bucket versioning (typically not needed for query results)
resource "aws_s3_bucket_versioning" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  versioning_configuration {
    status = var.enable_versioning_athena ? "Enabled" : "Suspended"
  }
}

# Athena results bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Athena results bucket public access block
resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Athena results bucket lifecycle policy - simplified expiration only
resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  
  # Rule for query results (temporary data)
  rule {
    id     = "athena_query_results_cleanup"
    status = "Enabled"
    
    filter {
      prefix = "query-results/"
    }
    
    expiration {
      days = 30
    }
    
    # Immediate cleanup of incomplete uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
  
  # Rule for curated datasets (longer retention)
  rule {
    id     = "athena_curated_datasets"
    status = "Enabled"
    
    filter {
      prefix = "curated/"
    }
    
    expiration {
      days = 30
    }
    
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  
  # Rule for CloudTrail logs and metadata (if stored here)
  rule {
    id     = "metadata_and_logs"
    status = "Enabled"
    
    filter {
      prefix = "logs/"
    }
    
    expiration {
      days = 365  # Keep logs for compliance
    }
  }
}

#==============================================================================
# S3 EVENT NOTIFICATIONS
#==============================================================================

# Lambda permission for S3 to invoke data processing function
resource "aws_lambda_permission" "s3_invoke_processing" {
  count = var.enable_event_notifications ? 1 : 0
  
  statement_id  = "AllowExecutionFromS3-${aws_s3_bucket.raw_data.id}"
  action        = "lambda:InvokeFunction"
  function_name = var.processing_lambda_function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.raw_data.arn
}

# S3 bucket notification for raw data bucket
resource "aws_s3_bucket_notification" "raw_data_notification" {
  count = var.enable_event_notifications ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  
  lambda_function {
    lambda_function_arn = var.processing_lambda_arn
    events             = ["s3:ObjectCreated:*"]
    filter_prefix      = "year="
    filter_suffix      = ".json"
  }
  
  depends_on = [aws_lambda_permission.s3_invoke_processing]
}

# Lambda permission for S3 to invoke data validation function
resource "aws_lambda_permission" "s3_invoke_validation" {
  count = var.enable_event_notifications && var.validation_lambda_arn != null ? 1 : 0
  
  statement_id  = "AllowExecutionFromS3-${aws_s3_bucket.processed_data.id}"
  action        = "lambda:InvokeFunction"
  function_name = var.validation_lambda_function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.processed_data.arn
}

# S3 bucket notification for processed data bucket
resource "aws_s3_bucket_notification" "processed_data_notification" {
  count = var.enable_event_notifications && var.validation_lambda_arn != null ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  
  lambda_function {
    lambda_function_arn = var.validation_lambda_arn
    events             = ["s3:ObjectCreated:*"]
    filter_prefix      = "year="
    filter_suffix      = ".parquet"
  }
  
  depends_on = [aws_lambda_permission.s3_invoke_validation]
}

#==============================================================================
# CROSS-REGION REPLICATION (OPTIONAL)
#==============================================================================

# IAM role for S3 replication (production environments)
resource "aws_iam_role" "s3_replication_role" {
  count = var.enable_cross_region_replication ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-s3-replication-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

# IAM policy for S3 replication
resource "aws_iam_role_policy" "s3_replication_policy" {
  count = var.enable_cross_region_replication ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-s3-replication-policy"
  role = aws_iam_role.s3_replication_role[0].id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersion",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = "${var.replication_destination_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# S3 bucket replication configuration for processed data (disaster recovery)
resource "aws_s3_bucket_replication_configuration" "processed_data_replication" {
  count = var.enable_cross_region_replication ? 1 : 0
  
  role   = aws_iam_role.s3_replication_role[0].arn
  bucket = aws_s3_bucket.processed_data.id
  
  rule {
    id     = "processed-data-replication"
    status = "Enabled"
    
    filter {}
    
    destination {
      bucket        = var.replication_destination_bucket_arn
      storage_class = "STANDARD_IA"
      
      encryption_configuration {
        replica_kms_key_id = var.replication_kms_key_id
      }
    }
  }
  
  depends_on = [aws_s3_bucket_versioning.processed_data]
}

#==============================================================================
# S3 ACCESS LOGGING (OPTIONAL)
#==============================================================================

# S3 bucket for access logs
resource "aws_s3_bucket" "access_logs" {
  count = var.enable_access_logging ? 1 : 0
  
  bucket        = "${local.bucket_names.raw_data}-access-logs"
  force_destroy = var.allow_force_destroy
  
  tags = merge(var.tags, {
    Name    = "${local.bucket_names.raw_data}-access-logs"
    Purpose = "S3 access logging"
  })
}

# Access logs bucket public access block
resource "aws_s3_bucket_public_access_block" "access_logs" {
  count = var.enable_access_logging ? 1 : 0
  
  bucket = aws_s3_bucket.access_logs[0].id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Access logs bucket lifecycle (cleanup old logs)
resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  count = var.enable_access_logging ? 1 : 0
  
  bucket = aws_s3_bucket.access_logs[0].id
  
  rule {
    id     = "access_logs_cleanup"
    status = "Enabled"
    
    filter {}
    
    expiration {
      days = var.access_log_retention_days
    }
    
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# S3 bucket logging configuration for raw data bucket
resource "aws_s3_bucket_logging" "raw_data_logging" {
  count = var.enable_access_logging ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  
  target_bucket = aws_s3_bucket.access_logs[0].id
  target_prefix = "raw-data-access-logs/"
}

# S3 bucket logging configuration for processed data bucket
resource "aws_s3_bucket_logging" "processed_data_logging" {
  count = var.enable_access_logging ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  
  target_bucket = aws_s3_bucket.access_logs[0].id
  target_prefix = "processed-data-access-logs/"
}

#==============================================================================
# S3 INVENTORY CONFIGURATION (COST OPTIMIZATION)
#==============================================================================

# S3 inventory configuration for cost analysis
resource "aws_s3_bucket_inventory" "raw_data_inventory" {
  count = var.enable_inventory ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  name   = "raw-data-inventory"
  
  included_object_versions = "Current"
  
  schedule {
    frequency = "Weekly"
  }
  
  destination {
    bucket {
      format     = "CSV"
      bucket_arn = aws_s3_bucket.athena_results.arn
      prefix     = "inventory/raw-data/"
    }
  }
  
  optional_fields = [
    "Size",
    "LastModifiedDate",
    "StorageClass",
    "ETag",
    "IsMultipartUploaded",
    "ReplicationStatus",
    "EncryptionStatus"
  ]
}

# S3 inventory for processed data bucket
resource "aws_s3_bucket_inventory" "processed_data_inventory" {
  count = var.enable_inventory ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed-data-inventory"
  
  included_object_versions = "Current"
  
  schedule {
    frequency = "Weekly"
  }
  
  destination {
    bucket {
      format     = "CSV"
      bucket_arn = aws_s3_bucket.athena_results.arn
      prefix     = "inventory/processed-data/"
    }
  }
  
  optional_fields = [
    "Size",
    "LastModifiedDate",
    "StorageClass",
    "ETag",
    "IsMultipartUploaded",
    "ReplicationStatus",
    "EncryptionStatus"
  ]
}