# Lambda Functions Module - Main Configuration
# This module creates Lambda functions for the flight data pipeline with comprehensive
# IAM roles, layers, error handling, and event integrations

#==============================================================================
# DATA SOURCES
#==============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

#==============================================================================
# LAMBDA EXECUTION IAM ROLES
#==============================================================================

# Base Lambda execution role
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-execution-role"
  path = var.iam_path_prefix

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-execution-role"
    Purpose     = "Lambda function execution role"
    SecurityLevel = "Standard"
  })
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# X-Ray tracing policy (if enabled)
resource "aws_iam_role_policy_attachment" "lambda_xray_execution" {
  count = var.enable_xray_tracing ? 1 : 0
  
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# VPC execution policy (if VPC is enabled)
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  count = var.vpc_config != null ? 1 : 0
  
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom IAM policy for S3 access
resource "aws_iam_policy" "lambda_s3_access" {
  name        = "${var.project_name}-${var.environment}-lambda-s3-access"
  path        = var.iam_path_prefix
  description = "IAM policy for Lambda S3 access with least privilege"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 read/write permissions for data buckets
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.raw_data_bucket_arn}/*",
          "${var.processed_data_bucket_arn}/*",
          "${var.athena_results_bucket_arn}/*"
        ]
      },
      # S3 bucket listing permissions
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketNotification"
        ]
        Resource = [
          var.raw_data_bucket_arn,
          var.processed_data_bucket_arn,
          var.athena_results_bucket_arn
        ]
      },
      # KMS permissions for S3 encryption/decryption
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn != null ? [var.kms_key_arn] : ["arn:${data.aws_partition.current.partition}:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:key/*"]
      }
    ]
  })

  tags = var.tags
}

# Attach S3 access policy to Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_s3_access.arn
}

# Custom IAM policy for DynamoDB access
resource "aws_iam_policy" "lambda_dynamodb_access" {
  name        = "${var.project_name}-${var.environment}-lambda-dynamodb-access"
  path        = var.iam_path_prefix
  description = "IAM policy for Lambda DynamoDB access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = var.dynamodb_table_arn != null ? [var.dynamodb_table_arn] : []
      }
    ]
  })

  tags = var.tags
}

# Attach DynamoDB access policy to Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_dynamodb_access" {
  count = var.dynamodb_table_arn != null ? 1 : 0
  
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_dynamodb_access.arn
}

# Custom IAM policy for CloudWatch and SNS
resource "aws_iam_policy" "lambda_cloudwatch_sns_access" {
  name        = "${var.project_name}-${var.environment}-lambda-cloudwatch-sns-access"
  path        = var.iam_path_prefix
  description = "IAM policy for Lambda CloudWatch and SNS access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs (additional permissions beyond basic execution role)
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*"
      },
      # CloudWatch Metrics
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      # SNS publishing for alerts
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = var.sns_topic_arn != null ? [var.sns_topic_arn] : []
      },
      # SQS access for dead letter queues
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.ingestion_dlq.arn,
          aws_sqs_queue.processing_dlq.arn,
          aws_sqs_queue.validation_dlq.arn
        ]
      }
    ]
  })

  tags = var.tags
}

# Attach CloudWatch and SNS access policy
resource "aws_iam_role_policy_attachment" "lambda_cloudwatch_sns_access" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_cloudwatch_sns_access.arn
}

#==============================================================================
# DEAD LETTER QUEUES
#==============================================================================

# Dead Letter Queue for ingestion function
resource "aws_sqs_queue" "ingestion_dlq" {
  name = "${var.project_name}-${var.environment}-ingestion-dlq"
  
  # Message retention
  message_retention_seconds = var.dlq_retention_seconds
  
  # Visibility timeout should be longer than Lambda timeout
  visibility_timeout_seconds = var.lambda_config.ingestion.timeout + 10
  
  # Enable server-side encryption
  kms_master_key_id = var.enable_dlq_encryption ? "alias/aws/sqs" : null
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-ingestion-dlq"
    Purpose = "Dead letter queue for ingestion Lambda function"
  })
}

# Dead Letter Queue for processing function
resource "aws_sqs_queue" "processing_dlq" {
  name = "${var.project_name}-${var.environment}-processing-dlq"
  
  message_retention_seconds  = var.dlq_retention_seconds
  visibility_timeout_seconds = var.lambda_config.processing.timeout + 10
  kms_master_key_id         = var.enable_dlq_encryption ? "alias/aws/sqs" : null
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-processing-dlq"
    Purpose = "Dead letter queue for processing Lambda function"
  })
}

# Dead Letter Queue for validation function
resource "aws_sqs_queue" "validation_dlq" {
  name = "${var.project_name}-${var.environment}-validation-dlq"
  
  message_retention_seconds  = var.dlq_retention_seconds
  visibility_timeout_seconds = var.lambda_config.validation.timeout + 10
  kms_master_key_id         = var.enable_dlq_encryption ? "alias/aws/sqs" : null
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-validation-dlq"
    Purpose = "Dead letter queue for validation Lambda function"
  })
}

#==============================================================================
# LAMBDA LAYER FOR SHARED DEPENDENCIES
#==============================================================================

# Lambda Layer for shared dependencies (pandas, pyarrow, boto3, etc.)
resource "aws_lambda_layer_version" "shared_dependencies" {
  filename                 = var.lambda_layer_zip_path
  layer_name              = "${var.project_name}-${var.environment}-shared-dependencies"
  compatible_runtimes     = [var.lambda_runtime]
  compatible_architectures = [var.lambda_architecture]
  
  description = "Shared dependencies layer for flight data pipeline (pandas, pyarrow, boto3)"
  
  # Only create if zip file exists
  lifecycle {
    ignore_changes = [filename]
  }
}

# Lambda Layer for common utilities
resource "aws_lambda_layer_version" "common_utilities" {
  filename                 = var.common_utilities_zip_path
  layer_name              = "${var.project_name}-${var.environment}-common-utilities"
  compatible_runtimes     = [var.lambda_runtime]
  compatible_architectures = [var.lambda_architecture]
  
  description = "Common utilities layer for flight data pipeline (shared code)"
  
  lifecycle {
    ignore_changes = [filename]
  }
}

#==============================================================================
# CLOUDWATCH LOG GROUPS
#==============================================================================

# CloudWatch Log Group for ingestion function
resource "aws_cloudwatch_log_group" "ingestion_logs" {
  name              = "/aws/lambda/${local.lambda_function_names.ingestion}"
  retention_in_days = var.log_retention_days
  kms_key_id       = var.enable_log_encryption ? var.cloudwatch_kms_key_id : null
  
  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-ingestion-logs"
    LambdaFunction = local.lambda_function_names.ingestion
  })
}

# CloudWatch Log Group for processing function
resource "aws_cloudwatch_log_group" "processing_logs" {
  name              = "/aws/lambda/${local.lambda_function_names.processing}"
  retention_in_days = var.log_retention_days
  kms_key_id       = var.enable_log_encryption ? var.cloudwatch_kms_key_id : null
  
  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-processing-logs"
    LambdaFunction = local.lambda_function_names.processing
  })
}

# CloudWatch Log Group for validation function
resource "aws_cloudwatch_log_group" "validation_logs" {
  name              = "/aws/lambda/${local.lambda_function_names.validation}"
  retention_in_days = var.log_retention_days
  kms_key_id       = var.enable_log_encryption ? var.cloudwatch_kms_key_id : null
  
  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-validation-logs"
    LambdaFunction = local.lambda_function_names.validation
  })
}

#==============================================================================
# LAMBDA FUNCTIONS
#==============================================================================

# Flight Data Ingestion Lambda Function
resource "aws_lambda_function" "ingestion" {
  filename         = var.ingestion_zip_path
  function_name    = local.lambda_function_names.ingestion
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "flight_data_ingestion.lambda_handler"
  source_code_hash = var.ingestion_source_code_hash
  runtime         = var.lambda_runtime
  architectures   = [var.lambda_architecture]
  timeout         = var.lambda_config.ingestion.timeout
  memory_size     = var.lambda_config.ingestion.memory_size
  
  # Layers
  layers = [
    aws_lambda_layer_version.shared_dependencies.arn,
    aws_lambda_layer_version.common_utilities.arn
  ]
  
  # Environment variables
  environment {
    variables = merge(
      var.common_environment_variables,
      var.lambda_config.ingestion.environment_variables,
      {
        RAW_DATA_BUCKET      = var.raw_data_bucket_name
        TRACKING_TABLE       = var.dynamodb_table_name
        ALERT_TOPIC_ARN      = var.sns_topic_arn
        OPENSKY_API_TIMEOUT  = tostring(var.opensky_api_config.request_timeout)
        MAX_RETRIES          = tostring(var.opensky_api_config.max_retries)
        LOG_LEVEL           = var.log_level
        ENVIRONMENT         = var.environment
      }
    )
  }
  
  # Dead letter queue configuration
  dead_letter_config {
    target_arn = aws_sqs_queue.ingestion_dlq.arn
  }
  
  # Reserved concurrency
  reserved_concurrent_executions = var.lambda_config.ingestion.reserved_concurrency
  
  # X-Ray tracing
  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }
  
  # VPC configuration (if provided)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }
  
  # Lifecycle configuration
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
  
  depends_on = [
    aws_cloudwatch_log_group.ingestion_logs,
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_s3_access,
    aws_iam_role_policy_attachment.lambda_cloudwatch_sns_access
  ]
  
  tags = merge(var.tags, {
    Name        = local.lambda_function_names.ingestion
    Purpose     = "Flight data ingestion from OpenSky Network API"
    Runtime     = var.lambda_runtime
    MemorySize  = tostring(var.lambda_config.ingestion.memory_size)
    Timeout     = tostring(var.lambda_config.ingestion.timeout)
  })
}

# Flight Data Processing Lambda Function
resource "aws_lambda_function" "processing" {
  filename         = var.processing_zip_path
  function_name    = local.lambda_function_names.processing
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "flight_data_processor.lambda_handler"
  source_code_hash = var.processing_source_code_hash
  runtime         = var.lambda_runtime
  architectures   = [var.lambda_architecture]
  timeout         = var.lambda_config.processing.timeout
  memory_size     = var.lambda_config.processing.memory_size
  
  # Layers
  layers = [
    aws_lambda_layer_version.shared_dependencies.arn,
    aws_lambda_layer_version.common_utilities.arn
  ]
  
  # Environment variables
  environment {
    variables = merge(
      var.common_environment_variables,
      var.lambda_config.processing.environment_variables,
      {
        RAW_DATA_BUCKET       = var.raw_data_bucket_name
        PROCESSED_DATA_BUCKET = var.processed_data_bucket_name
        QUALITY_THRESHOLD     = tostring(var.data_quality_config.quality_threshold)
        MIN_COMPLETENESS_SCORE = tostring(var.data_quality_config.min_completeness_score)
        LOG_LEVEL            = var.log_level
        ENVIRONMENT          = var.environment
      }
    )
  }
  
  # Dead letter queue configuration
  dead_letter_config {
    target_arn = aws_sqs_queue.processing_dlq.arn
  }
  
  # Reserved concurrency
  reserved_concurrent_executions = var.lambda_config.processing.reserved_concurrency
  
  # X-Ray tracing
  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }
  
  # VPC configuration (if provided)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }
  
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
  
  depends_on = [
    aws_cloudwatch_log_group.processing_logs,
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_s3_access,
    aws_iam_role_policy_attachment.lambda_cloudwatch_sns_access
  ]
  
  tags = merge(var.tags, {
    Name        = local.lambda_function_names.processing
    Purpose     = "Flight data processing and transformation"
    Runtime     = var.lambda_runtime
    MemorySize  = tostring(var.lambda_config.processing.memory_size)
    Timeout     = tostring(var.lambda_config.processing.timeout)
  })
}

# Data Quality Validation Lambda Function
resource "aws_lambda_function" "validation" {
  filename         = var.validation_zip_path
  function_name    = local.lambda_function_names.validation
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "data_quality_validator.lambda_handler"
  source_code_hash = var.validation_source_code_hash
  runtime         = var.lambda_runtime
  architectures   = [var.lambda_architecture]
  timeout         = var.lambda_config.validation.timeout
  memory_size     = var.lambda_config.validation.memory_size
  
  # Layers
  layers = [
    aws_lambda_layer_version.shared_dependencies.arn,
    aws_lambda_layer_version.common_utilities.arn
  ]
  
  # Environment variables
  environment {
    variables = merge(
      var.common_environment_variables,
      var.lambda_config.validation.environment_variables,
      {
        PROCESSED_DATA_BUCKET = var.processed_data_bucket_name
        ALERT_TOPIC_ARN       = var.sns_topic_arn
        QUALITY_THRESHOLD     = tostring(var.data_quality_config.quality_threshold)
        MIN_COMPLETENESS_SCORE = tostring(var.data_quality_config.min_completeness_score)
        MAX_ERROR_RATE        = tostring(var.data_quality_config.max_error_rate)
        LOG_LEVEL            = var.log_level
        ENVIRONMENT          = var.environment
      }
    )
  }
  
  # Dead letter queue configuration
  dead_letter_config {
    target_arn = aws_sqs_queue.validation_dlq.arn
  }
  
  # Reserved concurrency
  reserved_concurrent_executions = var.lambda_config.validation.reserved_concurrency
  
  # X-Ray tracing
  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }
  
  # VPC configuration (if provided)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }
  
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
  
  depends_on = [
    aws_cloudwatch_log_group.validation_logs,
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_s3_access,
    aws_iam_role_policy_attachment.lambda_cloudwatch_sns_access
  ]
  
  tags = merge(var.tags, {
    Name        = local.lambda_function_names.validation
    Purpose     = "Data quality validation and monitoring"
    Runtime     = var.lambda_runtime
    MemorySize  = tostring(var.lambda_config.validation.memory_size)
    Timeout     = tostring(var.lambda_config.validation.timeout)
  })
}

#==============================================================================
# LOCAL VALUES
#==============================================================================

locals {
  # Lambda function names
  lambda_function_names = {
    ingestion  = "${var.project_name}-${var.environment}-flight-ingestion"
    processing = "${var.project_name}-${var.environment}-flight-processing"
    validation = "${var.project_name}-${var.environment}-data-validation"
  }
}