# Flight Data Pipeline - Monitoring Module
# This file contains comprehensive monitoring configuration including dashboards, alarms, and notifications

#==============================================================================
# TERRAFORM CONFIGURATION
#==============================================================================

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws.us-east-1]
    }
  }
}

#==============================================================================
# DATA SOURCES
#==============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

#==============================================================================
# LOCALS
#==============================================================================

locals {
  # Common naming
  name_prefix = "${var.project_name}-${var.environment}"
  
  # AWS account and region information
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region     = data.aws_region.current.name
  aws_partition  = data.aws_partition.current.partition
  
  # Notification strategies
  critical_alarms = var.enable_sms_alerts ? [aws_sns_topic.critical_alerts.arn] : [aws_sns_topic.email_alerts.arn]
  warning_alarms  = [aws_sns_topic.email_alerts.arn]
  
  # Dashboard widget configuration
  dashboard_widgets = [
    # Pipeline Health Overview
    {
      type   = "metric"
      x      = 0
      y      = 0
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["FlightDataPipeline", "PipelineHealth", "Environment", var.environment],
          [".", "DataIngestionSuccess", ".", "."],
          [".", "ProcessingSuccess", ".", "."],
          [".", "ValidationSuccess", ".", "."]
        ]
        view    = "timeSeries"
        stacked = false
        region  = local.aws_region
        title   = "Pipeline Health Overview"
        period  = 300
        yAxis = {
          left = {
            min = 0
            max = 100
          }
        }
      }
    },
    
    # Lambda Performance Metrics
    {
      type   = "metric"
      x      = 12
      y      = 0
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_names.ingestion],
          [".", ".", ".", var.lambda_function_names.processing],
          [".", ".", ".", var.lambda_function_names.validation],
          [".", "Invocations", ".", var.lambda_function_names.ingestion],
          [".", ".", ".", var.lambda_function_names.processing],
          [".", ".", ".", var.lambda_function_names.validation]
        ]
        view    = "timeSeries"
        stacked = false
        region  = local.aws_region
        title   = "Lambda Performance"
        period  = 300
      }
    },
    
    # Error Rate Tracking
    {
      type   = "metric"
      x      = 0
      y      = 6
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_names.ingestion],
          [".", ".", ".", var.lambda_function_names.processing],
          [".", ".", ".", var.lambda_function_names.validation],
          [".", "Throttles", ".", var.lambda_function_names.ingestion],
          [".", ".", ".", var.lambda_function_names.processing],
          [".", ".", ".", var.lambda_function_names.validation]
        ]
        view    = "timeSeries"
        stacked = false
        region  = local.aws_region
        title   = "Error Rate & Throttles"
        period  = 300
      }
    },
    
    # Data Quality Scores
    {
      type   = "metric"
      x      = 12
      y      = 6
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["FlightDataPipeline", "DataQualityScore", "Environment", var.environment],
          [".", "CompletenessScore", ".", "."],
          [".", "ValidityScore", ".", "."],
          [".", "ConsistencyScore", ".", "."]
        ]
        view    = "timeSeries"
        stacked = false
        region  = local.aws_region
        title   = "Data Quality Metrics"
        period  = 300
        yAxis = {
          left = {
            min = 0
            max = 1
          }
        }
      }
    },
    
    # Cost Tracking
    {
      type   = "metric"
      x      = 0
      y      = 12
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["AWS/Billing", "EstimatedCharges", "Currency", "USD", "ServiceName", "AmazonS3"],
          [".", ".", ".", ".", ".", "AWSLambda"],
          [".", ".", ".", ".", ".", "AmazonCloudWatch"],
          [".", ".", ".", ".", ".", "AmazonDynamoDB"]
        ]
        view    = "timeSeries"
        stacked = true
        region  = "us-east-1"  # Billing metrics are only in us-east-1
        title   = "Daily Cost by Service"
        period  = 86400  # 24 hours
      }
    },
    
    # S3 Storage Metrics
    {
      type   = "metric"
      x      = 12
      y      = 12
      width  = 12
      height = 6
      
      properties = {
        metrics = [
          ["AWS/S3", "BucketSizeBytes", "BucketName", var.s3_bucket_names.raw_data, "StorageType", "StandardStorage"],
          [".", ".", ".", var.s3_bucket_names.processed_data, ".", "."],
          [".", "NumberOfObjects", ".", var.s3_bucket_names.raw_data, ".", "AllStorageTypes"],
          [".", ".", ".", var.s3_bucket_names.processed_data, ".", "."]
        ]
        view    = "timeSeries"
        stacked = false
        region  = local.aws_region
        title   = "S3 Storage Usage"
        period  = 86400  # 24 hours
      }
    }
  ]
}

#==============================================================================
# CLOUDWATCH DASHBOARD
#==============================================================================

resource "aws_cloudwatch_dashboard" "pipeline_monitoring" {
  dashboard_name = "${local.name_prefix}-pipeline-dashboard"

  dashboard_body = jsonencode({
    widgets = local.dashboard_widgets
  })

  depends_on = [
    aws_sns_topic.email_alerts,
    aws_sns_topic.critical_alerts
  ]
}

# Custom dashboard for executive summary
resource "aws_cloudwatch_dashboard" "executive_summary" {
  count = var.create_executive_dashboard ? 1 : 0
  
  dashboard_name = "${local.name_prefix}-executive-summary"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "number"
        x      = 0
        y      = 0
        width  = 6
        height = 6
        
        properties = {
          metrics = [
            ["FlightDataPipeline", "RecordsProcessedDaily", "Environment", var.environment]
          ]
          view   = "singleValue"
          region = local.aws_region
          title  = "Records Processed (24h)"
          period = 86400
        }
      },
      {
        type   = "number"
        x      = 6
        y      = 0
        width  = 6
        height = 6
        
        properties = {
          metrics = [
            ["FlightDataPipeline", "DataQualityScore", "Environment", var.environment]
          ]
          view   = "singleValue"
          region = local.aws_region
          title  = "Data Quality Score"
          period = 3600
        }
      },
      {
        type   = "number"
        x      = 12
        y      = 0
        width  = 6
        height = 6
        
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "USD"]
          ]
          view   = "singleValue"
          region = "us-east-1"
          title  = "Monthly Cost (USD)"
          period = 86400
        }
      },
      {
        type   = "number"
        x      = 18
        y      = 0
        width  = 6
        height = 6
        
        properties = {
          metrics = [
            ["FlightDataPipeline", "PipelineUptime", "Environment", var.environment]
          ]
          view   = "singleValue"
          region = local.aws_region
          title  = "Pipeline Uptime %"
          period = 86400
        }
      }
    ]
  })
}

#==============================================================================
# PIPELINE EXECUTION TRACKING - DYNAMODB TABLE
#==============================================================================

resource "aws_dynamodb_table" "pipeline_tracking" {
  name           = "${local.name_prefix}-pipeline-tracking"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "tracking_id"
  
  # TTL for automatic cleanup
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  attribute {
    name = "tracking_id"
    type = "S"
  }

  attribute {
    name = "execution_date"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # Global Secondary Index for querying by execution date
  global_secondary_index {
    name            = "ExecutionDateIndex"
    hash_key        = "execution_date"
    range_key       = "tracking_id"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "tracking_id"
    projection_type = "ALL"
  }

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  # Server-side encryption
  server_side_encryption {
    enabled = var.enable_encryption
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-pipeline-tracking"
    Purpose     = "Pipeline execution tracking and monitoring"
    Environment = var.environment
  })
}

#==============================================================================
# SNS TOPICS FOR NOTIFICATIONS
#==============================================================================

# Email alerts topic
resource "aws_sns_topic" "email_alerts" {
  name = "${local.name_prefix}-email-alerts"
  
  # Server-side encryption
  kms_master_key_id = var.enable_encryption ? var.kms_key_arn : null
  
  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-email-alerts"
    Purpose     = "Email notifications for pipeline alerts"
    Environment = var.environment
  })
}

# Critical alerts topic (for SMS)
resource "aws_sns_topic" "critical_alerts" {
  name = "${local.name_prefix}-critical-alerts"
  
  # Server-side encryption
  kms_master_key_id = var.enable_encryption ? var.kms_key_arn : null
  
  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-critical-alerts"
    Purpose     = "Critical SMS and email notifications"
    Environment = var.environment
  })
}

# Slack webhook topic
resource "aws_sns_topic" "slack_alerts" {
  count = var.enable_slack_notifications ? 1 : 0
  
  name = "${local.name_prefix}-slack-alerts"
  
  # Server-side encryption
  kms_master_key_id = var.enable_encryption ? var.kms_key_arn : null
  
  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-slack-alerts"
    Purpose     = "Slack webhook notifications"
    Environment = var.environment
  })
}

#==============================================================================
# SNS SUBSCRIPTIONS
#==============================================================================

# Email subscriptions for standard alerts
resource "aws_sns_topic_subscription" "email_alerts" {
  for_each = toset(var.alert_email_addresses)
  
  topic_arn = aws_sns_topic.email_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# Email subscriptions for critical alerts
resource "aws_sns_topic_subscription" "critical_email_alerts" {
  for_each = toset(var.critical_alert_email_addresses)
  
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# SMS subscriptions for critical alerts
resource "aws_sns_topic_subscription" "sms_alerts" {
  for_each = var.enable_sms_alerts ? toset(var.sms_phone_numbers) : []
  
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "sms"
  endpoint  = each.value
}

# Slack webhook subscription
resource "aws_sns_topic_subscription" "slack_webhook" {
  count = var.enable_slack_notifications && var.slack_webhook_url != null ? 1 : 0
  
  topic_arn = aws_sns_topic.slack_alerts[0].arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
}

#==============================================================================
# LAMBDA FUNCTION FOR SLACK NOTIFICATIONS
#==============================================================================

# Lambda function to format Slack messages
resource "aws_lambda_function" "slack_formatter" {
  count = var.enable_slack_notifications ? 1 : 0
  
  filename         = "${path.module}/lambda/slack-formatter.zip"
  function_name    = "${local.name_prefix}-slack-formatter"
  role            = aws_iam_role.slack_lambda_role[0].arn
  handler         = "index.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  
  environment {
    variables = {
      SLACK_WEBHOOK_URL = var.slack_webhook_url
      ENVIRONMENT      = var.environment
      PROJECT_NAME     = var.project_name
    }
  }
  
  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-slack-formatter"
    Purpose     = "Format and send Slack notifications"
    Environment = var.environment
  })
}

# IAM role for Slack Lambda function
resource "aws_iam_role" "slack_lambda_role" {
  count = var.enable_slack_notifications ? 1 : 0
  
  name = "${local.name_prefix}-slack-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

# IAM policy for Slack Lambda function
resource "aws_iam_role_policy_attachment" "slack_lambda_basic" {
  count = var.enable_slack_notifications ? 1 : 0
  
  role       = aws_iam_role.slack_lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permission for SNS to invoke Slack Lambda
resource "aws_lambda_permission" "allow_sns_slack" {
  count = var.enable_slack_notifications ? 1 : 0
  
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_formatter[0].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.slack_alerts[0].arn
}

# SNS subscription to trigger Slack Lambda
resource "aws_sns_topic_subscription" "slack_lambda_trigger" {
  count = var.enable_slack_notifications ? 1 : 0
  
  topic_arn = aws_sns_topic.slack_alerts[0].arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.slack_formatter[0].arn
}