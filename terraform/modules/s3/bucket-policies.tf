# S3 Data Lake Module - Bucket Policies and Security
# This file contains additional security configurations including bucket policies,
# request metrics, CORS, and advanced security settings

#==============================================================================
# BUCKET POLICIES FOR ENHANCED SECURITY
#==============================================================================

# Raw data bucket policy - enforce encryption and secure transport
resource "aws_s3_bucket_policy" "raw_data_policy" {
  bucket = aws_s3_bucket.raw_data.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "raw-data-bucket-policy"
    Statement = [
      # Deny unencrypted uploads
      {
        Sid       = "DenyUnencryptedUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.raw_data.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      # Deny uploads with wrong KMS key
      {
        Sid       = "DenyWrongEncryptionKey"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.raw_data.arn}/*"
        Condition = {
          StringNotLikeIfExists = {
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.create_kms_key ? aws_kms_key.s3_data_lake_key[0].arn : var.kms_key_id
          }
        }
      },
      # Deny non-SSL requests
      {
        Sid       = "DenyNonSSLRequests"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      # Allow Lambda service access for processing
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.raw_data.arn}/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Processed data bucket policy - optimized for analytics access
resource "aws_s3_bucket_policy" "processed_data_policy" {
  bucket = aws_s3_bucket.processed_data.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "processed-data-bucket-policy"
    Statement = [
      # Deny unencrypted uploads
      {
        Sid       = "DenyUnencryptedUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.processed_data.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      # Deny non-SSL requests
      {
        Sid       = "DenyNonSSLRequests"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      # Allow Athena service access
      {
        Sid    = "AllowAthenaAccess"
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      # Allow Glue service access for cataloging
      {
        Sid    = "AllowGlueAccess"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Athena results bucket policy - allow Athena service access
resource "aws_s3_bucket_policy" "athena_results_policy" {
  bucket = aws_s3_bucket.athena_results.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "athena-results-bucket-policy"
    Statement = [
      # Deny non-SSL requests
      {
        Sid       = "DenyNonSSLRequests"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      # Allow Athena service full access for query results
      {
        Sid    = "AllowAthenaFullAccess"
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

#==============================================================================
# CLOUDWATCH REQUEST METRICS
#==============================================================================

# Request metrics for raw data bucket
resource "aws_s3_bucket_metric" "raw_data_metrics" {
  count = var.enable_request_metrics ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  name   = "raw-data-metrics"
  
  filter {
    prefix = var.request_metrics_filter_prefix
  }
}

# Request metrics for processed data bucket
resource "aws_s3_bucket_metric" "processed_data_metrics" {
  count = var.enable_request_metrics ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed-data-metrics"
  
  # Monitor all objects for analytics workloads
  filter {
    prefix = ""
  }
}

# Request metrics for Athena results bucket
resource "aws_s3_bucket_metric" "athena_results_metrics" {
  count = var.enable_request_metrics ? 1 : 0
  
  bucket = aws_s3_bucket.athena_results.id
  name   = "athena-results-metrics"
  
  filter {
    prefix = "query-results/"
  }
}

#==============================================================================
# TRANSFER ACCELERATION
#==============================================================================

# Transfer acceleration for raw data bucket (high upload volume)
resource "aws_s3_bucket_accelerate_configuration" "raw_data_acceleration" {
  count = var.enable_transfer_acceleration ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  status = "Enabled"
}

#==============================================================================
# CORS CONFIGURATION
#==============================================================================

# CORS configuration for processed data bucket (if web access needed)
resource "aws_s3_bucket_cors_configuration" "processed_data_cors" {
  count = var.enable_cors ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  
  cors_rule {
    allowed_headers = var.cors_configuration.allowed_headers
    allowed_methods = var.cors_configuration.allowed_methods
    allowed_origins = var.cors_configuration.allowed_origins
    expose_headers  = var.cors_configuration.expose_headers
    max_age_seconds = var.cors_configuration.max_age_seconds
  }
}

# CORS configuration for Athena results bucket (for web-based query tools)
resource "aws_s3_bucket_cors_configuration" "athena_results_cors" {
  count = var.enable_cors ? 1 : 0
  
  bucket = aws_s3_bucket.athena_results.id
  
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.cors_configuration.allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

#==============================================================================
# WEBSITE CONFIGURATION (OPTIONAL)
#==============================================================================

# Website configuration for Athena results bucket (if static hosting needed)
resource "aws_s3_bucket_website_configuration" "athena_results_website" {
  count = var.enable_static_website_hosting ? 1 : 0
  
  bucket = aws_s3_bucket.athena_results.id
  
  index_document {
    suffix = var.website_configuration.index_document
  }
  
  error_document {
    key = var.website_configuration.error_document
  }
  
  routing_rule {
    condition {
      key_prefix_equals = "query-results/"
    }
    redirect {
      replace_key_prefix_with = "results/"
    }
  }
}

#==============================================================================
# REQUESTER PAYS (COST OPTIMIZATION)
#==============================================================================

# Requester pays configuration for processed data bucket
resource "aws_s3_bucket_request_payment_configuration" "processed_data_requester_pays" {
  count = var.cost_optimization_settings.enable_requester_pays ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  payer  = "Requester"
}

#==============================================================================
# OBJECT LOCK CONFIGURATION (COMPLIANCE)
#==============================================================================

# Object lock configuration for processed data bucket (production compliance)
resource "aws_s3_bucket_object_lock_configuration" "processed_data_object_lock" {
  count = var.environment == "prod" && var.enable_versioning ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = 30  # 30-day retention for compliance
    }
  }
  
  depends_on = [aws_s3_bucket_versioning.processed_data]
}

#==============================================================================
# ANALYTICS CONFIGURATION
#==============================================================================

# Analytics configuration for processed data bucket
resource "aws_s3_bucket_analytics_configuration" "processed_data_analytics" {
  count = var.environment != "dev" ? 1 : 0
  
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed-data-analytics"
  
  filter {
    prefix = "year="
  }
  
  storage_class_analysis {
    data_export {
      output_schema_version = "V_1"
      
      destination {
        s3_bucket_destination {
          bucket_arn = aws_s3_bucket.athena_results.arn
          prefix     = "analytics/processed-data/"
          format     = "CSV"
        }
      }
    }
  }
}

# Analytics configuration for raw data bucket
resource "aws_s3_bucket_analytics_configuration" "raw_data_analytics" {
  count = var.environment == "prod" ? 1 : 0
  
  bucket = aws_s3_bucket.raw_data.id
  name   = "raw-data-analytics"
  
  filter {
    prefix = "year="
  }
  
  storage_class_analysis {
    data_export {
      output_schema_version = "V_1"
      
      destination {
        s3_bucket_destination {
          bucket_arn = aws_s3_bucket.athena_results.arn
          prefix     = "analytics/raw-data/"
          format     = "CSV"
        }
      }
    }
  }
}

#==============================================================================
# MFA DELETE CONFIGURATION
#==============================================================================

# Note: MFA Delete must be configured using the AWS CLI or SDK by the root account
# This configuration is documented here for reference but cannot be managed via Terraform

# To enable MFA Delete on versioned buckets (production only):
# aws s3api put-bucket-versioning \
#   --bucket ${bucket-name} \
#   --versioning-configuration Status=Enabled,MFADelete=Enabled \
#   --mfa "serial-number token-code"

#==============================================================================
# ADDITIONAL SECURITY CONFIGURATIONS
#==============================================================================

# Bucket ownership controls (ACL disabled for security)
resource "aws_s3_bucket_ownership_controls" "raw_data_ownership" {
  bucket = aws_s3_bucket.raw_data.id
  
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_ownership_controls" "processed_data_ownership" {
  bucket = aws_s3_bucket.processed_data.id
  
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_ownership_controls" "athena_results_ownership" {
  bucket = aws_s3_bucket.athena_results.id
  
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

#==============================================================================
# NOTIFICATION CONFIGURATION EXTENSIONS
#==============================================================================

# SNS topic for S3 event notifications (optional)
resource "aws_sns_topic" "s3_events" {
  count = var.enable_event_notifications && var.environment == "prod" ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-s3-events"
  
  tags = var.tags
}

# SNS topic policy for S3 notifications
resource "aws_sns_topic_policy" "s3_events_policy" {
  count = var.enable_event_notifications && var.environment == "prod" ? 1 : 0
  
  arn = aws_sns_topic.s3_events[0].arn
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = "SNS:Publish"
        Resource = aws_sns_topic.s3_events[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}