# Lambda Functions Module - Event Integrations
# This file contains EventBridge rules, S3 event notifications, and Lambda permissions

#==============================================================================
# EVENTBRIDGE RULES FOR SCHEDULED INGESTION
#==============================================================================

# EventBridge rule for scheduled flight data ingestion (every 5 minutes)
resource "aws_cloudwatch_event_rule" "scheduled_ingestion" {
  name                = "${var.project_name}-${var.environment}-scheduled-ingestion"
  description         = "Trigger flight data ingestion every 5 minutes"
  schedule_expression = var.ingestion_schedule_expression
  state              = var.enable_scheduled_ingestion ? "ENABLED" : "DISABLED"
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-scheduled-ingestion"
    Purpose = "Scheduled flight data ingestion"
  })
}

# EventBridge target for ingestion Lambda function
resource "aws_cloudwatch_event_target" "ingestion_target" {
  rule      = aws_cloudwatch_event_rule.scheduled_ingestion.name
  target_id = "IngestionLambdaTarget"
  arn       = aws_lambda_function.ingestion.arn
  
  # Input transformer to add metadata
  input_transformer {
    input_paths = {
      timestamp = "$.time"
      source    = "$.source"
    }
    input_template = jsonencode({
      "trigger_source" = "eventbridge"
      "trigger_time"   = "<timestamp>"
      "event_source"   = "<source>"
      "batch_id"       = null
      "retry_count"    = 0
    })
  }
  
  # Retry configuration
  retry_policy {
    maximum_retry_attempts = var.eventbridge_retry_config.max_retry_attempts
    maximum_event_age_in_seconds = var.eventbridge_retry_config.max_event_age_seconds
  }
  
  # Dead letter queue for failed events
  dead_letter_config {
    arn = aws_sqs_queue.eventbridge_dlq.arn
  }
}

# Permission for EventBridge to invoke ingestion Lambda
resource "aws_lambda_permission" "allow_eventbridge_ingestion" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduled_ingestion.arn
}

# Dead letter queue for EventBridge failed invocations
resource "aws_sqs_queue" "eventbridge_dlq" {
  name = "${var.project_name}-${var.environment}-eventbridge-dlq"
  
  message_retention_seconds  = var.dlq_retention_seconds
  visibility_timeout_seconds = 60
  kms_master_key_id         = var.enable_dlq_encryption ? "alias/aws/sqs" : null
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-eventbridge-dlq"
    Purpose = "Dead letter queue for EventBridge failed Lambda invocations"
  })
}

#==============================================================================
# S3 EVENT NOTIFICATIONS FOR PROCESSING PIPELINE
#==============================================================================

# Permission for S3 to invoke processing Lambda function
# resource "aws_lambda_permission" "allow_s3_processing" {
#   statement_id  = "AllowExecutionFromS3-${var.raw_data_bucket_name}"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.processing.function_name
#   principal     = "s3.amazonaws.com"
#   source_arn    = var.raw_data_bucket_arn
# }

# Permission for S3 to invoke validation Lambda function
# resource "aws_lambda_permission" "allow_s3_validation" {
#   statement_id  = "AllowExecutionFromS3-${var.processed_data_bucket_name}"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.validation.function_name
#   principal     = "s3.amazonaws.com"
#   source_arn    = var.processed_data_bucket_arn
# }

#==============================================================================
# LAMBDA FUNCTION ALIASES AND VERSIONS
#==============================================================================

# Lambda alias for ingestion function (for blue/green deployments)
resource "aws_lambda_alias" "ingestion_alias" {
  count = var.enable_lambda_versioning ? 1 : 0
  
  name             = var.lambda_alias_name
  description      = "Alias for ingestion Lambda function"
  function_name    = aws_lambda_function.ingestion.function_name
  function_version = "$LATEST"
  
  # Routing configuration for gradual deployments
  dynamic "routing_config" {
    for_each = var.enable_gradual_deployment ? [1] : []
    content {
      additional_version_weights = {
        # Route 10% of traffic to new version during deployment
        "$LATEST" = 0.1
      }
    }
  }
}

# Lambda alias for processing function
resource "aws_lambda_alias" "processing_alias" {
  count = var.enable_lambda_versioning ? 1 : 0
  
  name             = var.lambda_alias_name
  description      = "Alias for processing Lambda function"
  function_name    = aws_lambda_function.processing.function_name
  function_version = "$LATEST"
}

# Lambda alias for validation function
resource "aws_lambda_alias" "validation_alias" {
  count = var.enable_lambda_versioning ? 1 : 0
  
  name             = var.lambda_alias_name
  description      = "Alias for validation Lambda function"
  function_name    = aws_lambda_function.validation.function_name
  function_version = "$LATEST"
}

#==============================================================================
# LAMBDA PROVISIONED CONCURRENCY (OPTIONAL)
#==============================================================================

# Provisioned concurrency for ingestion function (if enabled)
resource "aws_lambda_provisioned_concurrency_config" "ingestion_provisioned" {
  count = var.enable_provisioned_concurrency && var.lambda_config.ingestion.provisioned_concurrency > 0 ? 1 : 0
  
  function_name                     = aws_lambda_function.ingestion.function_name
  provisioned_concurrent_executions = var.lambda_config.ingestion.provisioned_concurrency
  qualifier                         = var.enable_lambda_versioning ? aws_lambda_alias.ingestion_alias[0].name : "$LATEST"
}

# Provisioned concurrency for processing function (if enabled)
resource "aws_lambda_provisioned_concurrency_config" "processing_provisioned" {
  count = var.enable_provisioned_concurrency && var.lambda_config.processing.provisioned_concurrency > 0 ? 1 : 0
  
  function_name                     = aws_lambda_function.processing.function_name
  provisioned_concurrent_executions = var.lambda_config.processing.provisioned_concurrency
  qualifier                         = var.enable_lambda_versioning ? aws_lambda_alias.processing_alias[0].name : "$LATEST"
}

#==============================================================================
# CLOUDWATCH ALARMS FOR LAMBDA MONITORING
#==============================================================================

# CloudWatch alarm for ingestion function errors
resource "aws_cloudwatch_metric_alarm" "ingestion_error_alarm" {
  count = var.enable_cloudwatch_alarms ? 1 : 0
  
  alarm_name          = "${local.lambda_function_names.ingestion}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  alarm_description   = "This metric monitors errors in the ingestion Lambda function"
  alarm_actions       = var.cloudwatch_alarm_actions
  
  dimensions = {
    FunctionName = aws_lambda_function.ingestion.function_name
  }
  
  tags = var.tags
}

# CloudWatch alarm for processing function duration
resource "aws_cloudwatch_metric_alarm" "processing_duration_alarm" {
  count = var.enable_cloudwatch_alarms ? 1 : 0
  
  alarm_name          = "${local.lambda_function_names.processing}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.lambda_config.processing.timeout * 1000 * 0.8  # 80% of timeout in milliseconds
  alarm_description   = "This metric monitors duration of the processing Lambda function"
  alarm_actions       = var.cloudwatch_alarm_actions
  
  dimensions = {
    FunctionName = aws_lambda_function.processing.function_name
  }
  
  tags = var.tags
}

# CloudWatch alarm for validation function throttles
resource "aws_cloudwatch_metric_alarm" "validation_throttle_alarm" {
  count = var.enable_cloudwatch_alarms ? 1 : 0
  
  alarm_name          = "${local.lambda_function_names.validation}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors throttles in the validation Lambda function"
  alarm_actions       = var.cloudwatch_alarm_actions
  
  dimensions = {
    FunctionName = aws_lambda_function.validation.function_name
  }
  
  tags = var.tags
}

# CloudWatch alarm for dead letter queue messages
resource "aws_cloudwatch_metric_alarm" "dlq_message_alarm" {
  count = var.enable_cloudwatch_alarms ? 1 : 0
  
  alarm_name          = "${var.project_name}-${var.environment}-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "This metric monitors messages in dead letter queues"
  alarm_actions       = var.cloudwatch_alarm_actions
  
  dimensions = {
    QueueName = aws_sqs_queue.ingestion_dlq.name
  }
  
  tags = var.tags
}

#==============================================================================
# LAMBDA INSIGHTS (OPTIONAL)
#==============================================================================

# Lambda Insights extension for enhanced monitoring
resource "aws_lambda_layer_version" "lambda_insights" {
  count = var.enable_lambda_insights ? 1 : 0
  
  layer_name = "${var.project_name}-${var.environment}-lambda-insights"
  
  # Lambda Insights layer ARN varies by region
  # This would typically be provided as a variable
  filename = var.lambda_insights_layer_arn
  
  compatible_runtimes     = [var.lambda_runtime]
  compatible_architectures = [var.lambda_architecture]
  
  description = "Lambda Insights monitoring layer"
}

# IAM policy for Lambda Insights
resource "aws_iam_policy" "lambda_insights_policy" {
  count = var.enable_lambda_insights ? 1 : 0
  
  name        = "${var.project_name}-${var.environment}-lambda-insights-policy"
  path        = var.iam_path_prefix
  description = "IAM policy for Lambda Insights"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda-insights:*"
      }
    ]
  })

  tags = var.tags
}

# Attach Lambda Insights policy
resource "aws_iam_role_policy_attachment" "lambda_insights_policy" {
  count = var.enable_lambda_insights ? 1 : 0
  
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_insights_policy[0].arn
}

#==============================================================================
# CUSTOM METRICS AND DASHBOARDS
#==============================================================================

# Custom CloudWatch dashboard for Lambda functions
resource "aws_cloudwatch_dashboard" "lambda_dashboard" {
  count = var.create_lambda_dashboard ? 1 : 0
  
  dashboard_name = "${var.project_name}-${var.environment}-lambda-dashboard"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.ingestion.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.processing.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.validation.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Lambda Function Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfVisibleMessages", "QueueName", aws_sqs_queue.ingestion_dlq.name],
            [".", ".", ".", aws_sqs_queue.processing_dlq.name],
            [".", ".", ".", aws_sqs_queue.validation_dlq.name],
            [".", ".", ".", aws_sqs_queue.eventbridge_dlq.name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Dead Letter Queue Messages"
          period  = 300
        }
      }
    ]
  })
}

#==============================================================================
# ERROR RECOVERY AND RETRY CONFIGURATIONS
#==============================================================================

# SNS topic for Lambda error notifications
resource "aws_sns_topic" "lambda_errors" {
  count = var.create_error_notification_topic ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-lambda-errors"
  
  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-lambda-errors"
    Purpose = "Lambda function error notifications"
  })
}

# SNS topic subscription for Lambda errors
resource "aws_sns_topic_subscription" "lambda_error_email" {
  count = var.create_error_notification_topic && var.error_notification_email != null ? 1 : 0
  
  topic_arn = aws_sns_topic.lambda_errors[0].arn
  protocol  = "email"
  endpoint  = var.error_notification_email
}

# EventBridge rule for Lambda function state changes
resource "aws_cloudwatch_event_rule" "lambda_state_change" {
  count = var.monitor_lambda_state_changes ? 1 : 0
  
  name        = "${var.project_name}-${var.environment}-lambda-state-change"
  description = "Capture Lambda function state changes"
  
  event_pattern = jsonencode({
    source        = ["aws.lambda"]
    detail-type   = ["Lambda Function Invocation Result - Failure"]
    detail = {
      functionName = [
        aws_lambda_function.ingestion.function_name,
        aws_lambda_function.processing.function_name,
        aws_lambda_function.validation.function_name
      ]
    }
  })
  
  tags = var.tags
}

# EventBridge target for Lambda state changes
resource "aws_cloudwatch_event_target" "lambda_state_change_target" {
  count = var.monitor_lambda_state_changes && var.create_error_notification_topic ? 1 : 0
  
  rule      = aws_cloudwatch_event_rule.lambda_state_change[0].name
  target_id = "LambdaErrorSNSTarget"
  arn       = aws_sns_topic.lambda_errors[0].arn
}