# Flight Data Pipeline - Lambda Functions Configuration
# This file instantiates the Lambda functions module with appropriate configuration

#==============================================================================
# LAMBDA FUNCTIONS MODULE INSTANTIATION
#==============================================================================

module "lambda_functions" {
  source = "./modules/lambda"

  # Core configuration
  project_name = var.project_name
  environment  = var.environment
  tags         = local.compute_tags

  # IAM configuration
  iam_path_prefix = var.security_config.iam_path_prefix

  # Lambda runtime configuration
  lambda_runtime      = var.lambda_config.runtime
  lambda_architecture = local.optimized_settings.lambda_architecture

  # Lambda function configurations
  lambda_config = {
    ingestion = {
      memory_size             = local.computed_lambda_config.ingestion.memory_size
      timeout                 = local.computed_lambda_config.ingestion.timeout
      reserved_concurrency    = local.computed_lambda_config.ingestion.reserved_concurrency
      provisioned_concurrency = var.cost_optimization.enable_provisioned_concurrency ? var.lambda_config.ingestion.reserved_concurrency : 0
      environment_variables = merge(var.lambda_config.environment_variables, {
        OPENSKY_BASE_URL      = var.opensky_api_config.base_url
        RATE_LIMIT_PER_HOUR   = tostring(var.opensky_api_config.rate_limit_per_hour)
        ENABLE_AUTHENTICATION = tostring(var.opensky_api_config.enable_authentication)
      })
    }
    processing = {
      memory_size             = local.computed_lambda_config.processing.memory_size
      timeout                 = local.computed_lambda_config.processing.timeout
      reserved_concurrency    = local.computed_lambda_config.processing.reserved_concurrency
      provisioned_concurrency = var.cost_optimization.enable_provisioned_concurrency ? var.lambda_config.processing.reserved_concurrency : 0
      environment_variables = merge(var.lambda_config.environment_variables, {
        BATCH_SIZE                  = tostring(var.data_processing_config.batch_size)
        MAX_BATCH_WINDOW_SECONDS    = tostring(var.data_processing_config.max_batch_window_seconds)
        PARALLEL_PROCESSING_ENABLED = tostring(var.data_processing_config.parallel_processing_enabled)
      })
    }
    validation = {
      memory_size             = local.computed_lambda_config.validation.memory_size
      timeout                 = local.computed_lambda_config.validation.timeout
      reserved_concurrency    = local.computed_lambda_config.validation.reserved_concurrency
      provisioned_concurrency = 0 # Validation doesn't need provisioned concurrency
      environment_variables = merge(var.lambda_config.environment_variables, {
        MAX_CONCURRENT_VALIDATIONS = tostring(var.data_processing_config.max_concurrent_executions)
        ENABLE_ANOMALY_DETECTION   = "true"
        VALIDATION_STRICTNESS      = var.environment == "prod" ? "high" : "medium"
      })
    }
  }

  # Deployment packages (these would be built by CI/CD pipeline)
  ingestion_zip_path  = "${path.module}/../deployment-packages/ingestion.zip"
  processing_zip_path = "${path.module}/../deployment-packages/processing.zip"
  validation_zip_path = "${path.module}/../deployment-packages/validation.zip"

  # Source code hashes for deployment detection
  ingestion_source_code_hash  = local.lambda_source_hashes.ingestion
  processing_source_code_hash = local.lambda_source_hashes.processing
  validation_source_code_hash = local.lambda_source_hashes.validation

  # Lambda layers
  lambda_layer_zip_path     = "${path.module}/../layers/shared-dependencies.zip"
  common_utilities_zip_path = "${path.module}/../layers/common-utilities.zip"

  # S3 bucket integration
  raw_data_bucket_name       = module.s3_data_lake.bucket_names.raw_data
  raw_data_bucket_arn        = module.s3_data_lake.bucket_arns.raw_data
  processed_data_bucket_name = module.s3_data_lake.bucket_names.processed_data
  processed_data_bucket_arn  = module.s3_data_lake.bucket_arns.processed_data
  athena_results_bucket_name = module.s3_data_lake.bucket_names.athena_results
  athena_results_bucket_arn  = module.s3_data_lake.bucket_arns.athena_results

  # Security and encryption
  kms_key_arn           = module.s3_data_lake.kms_key != null ? module.s3_data_lake.kms_key.arn : null
  enable_log_encryption = var.security_config.enable_encryption_at_rest
  cloudwatch_kms_key_id = var.security_config.create_kms_key ? module.s3_data_lake.kms_key.arn : null
  enable_dlq_encryption = var.security_config.enable_encryption_at_rest

  # DynamoDB integration (if execution tracking is enabled)
  dynamodb_table_name = var.feature_flags.enable_data_ingestion ? local.resource_names.execution_tracking_table : null
  dynamodb_table_arn  = var.feature_flags.enable_data_ingestion ? local.dynamodb_table_arn : null

  # SNS integration for alerts
  sns_topic_arn = var.feature_flags.enable_alerting ? local.data_quality_alerts_topic_arn : null

  # Environment variables
  common_environment_variables = local.lambda_environment_variables
  log_level                    = var.development_config.enable_debug_logging ? "DEBUG" : "INFO"

  # CloudWatch logging
  log_retention_days = local.computed_log_retention

  # X-Ray tracing
  enable_xray_tracing = var.lambda_config.enable_xray_tracing

  # VPC configuration (if network isolation is enabled)
  vpc_config = var.security_config.create_vpc ? local.lambda_vpc_config : null

  # Dead letter queue configuration
  dlq_retention_seconds = var.data_processing_config.dead_letter_queue_retention_days * 86400

  # Scheduled ingestion configuration
  enable_scheduled_ingestion    = var.feature_flags.enable_data_ingestion
  ingestion_schedule_expression = local.ingestion_schedule

  # Data quality configuration
  data_quality_config = {
    quality_threshold      = var.data_processing_config.quality_threshold
    min_completeness_score = var.data_processing_config.min_completeness_score
    max_error_rate         = var.data_processing_config.max_error_rate
  }

  # OpenSky API configuration
  opensky_api_config = {
    request_timeout = var.opensky_api_config.request_timeout
    max_retries     = var.opensky_api_config.max_retries
  }

  # EventBridge retry configuration
  eventbridge_retry_config = {
    max_retry_attempts    = var.data_processing_config.max_retry_attempts
    max_event_age_seconds = 3600 # 1 hour
  }

  # Advanced Lambda features
  enable_lambda_versioning       = var.environment == "prod"
  lambda_alias_name              = var.environment == "prod" ? "LIVE" : "LATEST"
  enable_gradual_deployment      = var.environment == "prod"
  enable_provisioned_concurrency = var.cost_optimization.enable_provisioned_concurrency

  # Monitoring and alerting
  enable_cloudwatch_alarms  = var.monitoring_config.enable_custom_metrics
  error_alarm_threshold     = var.environment == "prod" ? 3 : 10
  cloudwatch_alarm_actions  = local.alert_routing.critical_alerts
  create_lambda_dashboard   = var.monitoring_config.create_dashboard
  enable_lambda_insights    = var.environment == "prod" && var.monitoring_config.enable_detailed_monitoring
  lambda_insights_layer_arn = local.lambda_insights_layer_arn

  # Error handling and notifications
  create_error_notification_topic = var.feature_flags.enable_alerting
  error_notification_email        = var.alert_email
  monitor_lambda_state_changes    = var.environment == "prod"
}


#==============================================================================
# LAMBDA FUNCTION OUTPUTS (RE-EXPORTED)
#==============================================================================

# Export key Lambda function information for use by other modules
output "lambda_functions" {
  description = "Lambda function configuration and details"
  value = {
    # Function names and ARNs
    function_names = module.lambda_functions.function_names
    function_arns  = module.lambda_functions.function_arns
    invoke_arns    = module.lambda_functions.function_invoke_arns

    # Execution role
    execution_role_arn  = module.lambda_functions.lambda_execution_role.arn
    execution_role_name = module.lambda_functions.lambda_execution_role.name

    # Layer information
    shared_dependencies_layer_arn = module.lambda_functions.lambda_layers.shared_dependencies.layer_arn
    common_utilities_layer_arn    = module.lambda_functions.lambda_layers.common_utilities.layer_arn

    # Dead letter queues
    dead_letter_queue_arns = {
      ingestion  = module.lambda_functions.dead_letter_queues.ingestion.arn
      processing = module.lambda_functions.dead_letter_queues.processing.arn
      validation = module.lambda_functions.dead_letter_queues.validation.arn
    }

    # CloudWatch log groups
    log_group_names = {
      ingestion  = module.lambda_functions.cloudwatch_log_groups.ingestion.name
      processing = module.lambda_functions.cloudwatch_log_groups.processing.name
      validation = module.lambda_functions.cloudwatch_log_groups.validation.name
    }

    # EventBridge rule
    scheduled_ingestion_rule_arn = module.lambda_functions.eventbridge_rules.scheduled_ingestion.arn

    # Feature status
    xray_tracing_enabled            = var.lambda_config.enable_xray_tracing
    versioning_enabled              = var.environment == "prod"
    provisioned_concurrency_enabled = var.cost_optimization.enable_provisioned_concurrency
    lambda_insights_enabled         = var.environment == "prod" && var.monitoring_config.enable_detailed_monitoring

    # Summary
    total_functions = module.lambda_functions.lambda_summary.total_functions
    runtime         = module.lambda_functions.lambda_summary.runtime
    architecture    = module.lambda_functions.lambda_summary.architecture
  }
  sensitive = false
}

#==============================================================================
# CLOUDWATCH ALARMS FOR LAMBDA INTEGRATION
#==============================================================================

# CloudWatch alarm for overall Lambda pipeline health
resource "aws_cloudwatch_metric_alarm" "lambda_pipeline_health" {
  count = var.monitoring_config.enable_custom_metrics ? 1 : 0

  alarm_name          = "${local.name_prefix}-lambda-pipeline-health"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = local.monitoring_thresholds.lambda_error_rate_threshold * 10
  alarm_description   = "Overall Lambda pipeline health check - high error rate detected"
  alarm_actions       = local.alert_routing.critical_alerts

  # Composite alarm across all functions would require more complex setup
  # This is a simplified version monitoring one key function
  dimensions = {
    FunctionName = module.lambda_functions.function_names.processing
  }

  tags = local.common_tags
}

# CloudWatch alarm for data pipeline processing lag
resource "aws_cloudwatch_metric_alarm" "data_processing_lag" {
  count = var.monitoring_config.enable_custom_metrics ? 1 : 0

  alarm_name          = "${local.name_prefix}-data-processing-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = local.monitoring_thresholds.lambda_duration_threshold_ms
  alarm_description   = "Data processing Lambda functions taking too long"
  alarm_actions       = local.alert_routing.warning_alerts

  dimensions = {
    FunctionName = module.lambda_functions.function_names.processing
  }

  tags = local.common_tags
}

#==============================================================================
# IAM POLICIES FOR LAMBDA INTEGRATION WITH OTHER SERVICES
#==============================================================================

# Additional IAM policy for Lambda to access EventBridge
resource "aws_iam_policy" "lambda_eventbridge_access" {
  count = var.feature_flags.enable_data_ingestion ? 1 : 0

  name        = "${local.name_prefix}-lambda-eventbridge-access"
  path        = var.security_config.iam_path_prefix
  description = "IAM policy for Lambda functions to interact with EventBridge"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents",
          "events:DescribeRule",
          "events:ListTargetsByRule"
        ]
        Resource = [
          "arn:${local.aws_partition}:events:${local.aws_region}:${local.aws_account_id}:rule/${local.name_prefix}-*",
          "arn:${local.aws_partition}:events:${local.aws_region}:${local.aws_account_id}:event-bus/default"
        ]
      }
    ]
  })

  tags = local.security_tags
}

# Attach EventBridge access policy to Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_eventbridge_access" {
  count = var.feature_flags.enable_data_ingestion ? 1 : 0

  role       = module.lambda_functions.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_eventbridge_access[0].arn
}

#==============================================================================
# LAMBDA PERMISSIONS FOR CROSS-SERVICE ACCESS
#==============================================================================

# Lambda permission for CloudWatch Events to invoke functions (redundant but explicit)
resource "aws_lambda_permission" "allow_cloudwatch_events" {
  statement_id  = "AllowExecutionFromCloudWatchEvents"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_functions.function_names.ingestion
  principal     = "events.amazonaws.com"
  source_arn    = module.lambda_functions.eventbridge_rules.scheduled_ingestion.arn
}

# Output the Lambda execution role ARN for use by other modules
output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role for use by other services"
  value       = module.lambda_functions.lambda_execution_role.arn
}

output "lambda_function_arns_map" {
  description = "Map of Lambda function ARNs for integration purposes"
  value = {
    for name, arn in module.lambda_functions.function_arns : name => arn
  }
}