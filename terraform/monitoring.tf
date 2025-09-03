# Flight Data Pipeline - Monitoring Infrastructure Configuration
# This file instantiates the monitoring module with comprehensive observability features

#==============================================================================
# MONITORING MODULE INSTANTIATION
#==============================================================================

module "monitoring" {
  source = "./modules/monitoring"

  # Provider configuration
  providers = {
    aws.us-east-1 = aws.us-east-1
  }

  # Core configuration
  project_name = var.project_name
  environment  = var.environment
  tags         = local.monitoring_tags

  # Lambda function integration
  lambda_function_names = {
    ingestion  = module.lambda_functions.function_names.ingestion
    processing = module.lambda_functions.function_names.processing
    validation = module.lambda_functions.function_names.validation
  }

  lambda_timeouts = {
    ingestion  = local.computed_lambda_config.ingestion.timeout
    processing = local.computed_lambda_config.processing.timeout
    validation = local.computed_lambda_config.validation.timeout
  }

  # S3 bucket integration
  s3_bucket_names = {
    raw_data       = module.s3_data_lake.bucket_names.raw_data
    processed_data = module.s3_data_lake.bucket_names.processed_data
    athena_results = module.s3_data_lake.bucket_names.athena_results
  }

  # Dead Letter Queue integration
  dlq_names = {
    ingestion  = module.lambda_functions.dead_letter_queues.ingestion.name
    processing = module.lambda_functions.dead_letter_queues.processing.name
    validation = module.lambda_functions.dead_letter_queues.validation.name
  }

  # Alarm thresholds (environment-specific)
  alarm_thresholds = local.monitoring_thresholds

  # Budget configuration
  budget_limits = {
    monthly_limit = var.budget_config.monthly_limit
  }

  budget_thresholds = {
    warning_threshold  = var.budget_config.warning_threshold
    critical_threshold = var.budget_config.critical_threshold
    forecast_threshold = var.budget_config.forecast_threshold
  }

  service_budget_limits = {
    lambda_limit   = var.budget_config.service_limits.lambda
    s3_limit       = var.budget_config.service_limits.s3
    dynamodb_limit = var.budget_config.service_limits.dynamodb
  }

  enable_service_budgets = var.budget_config.enable_service_budgets

  # Notification configuration
  alert_email_addresses          = var.notification_config.alert_emails
  critical_alert_email_addresses = var.notification_config.critical_alert_emails
  budget_notification_emails     = var.notification_config.budget_emails

  # SMS alerts (production only)
  enable_sms_alerts = var.environment == "prod" && var.notification_config.enable_sms
  sms_phone_numbers = var.notification_config.sms_numbers

  # Slack integration
  enable_slack_notifications = var.notification_config.enable_slack
  slack_webhook_url          = var.notification_config.slack_webhook_url

  # Security configuration
  enable_encryption = var.security_config.enable_encryption_at_rest
  kms_key_arn       = module.s3_data_lake.kms_key != null ? module.s3_data_lake.kms_key.arn : null

  # Executive dashboard (production and staging)
  create_executive_dashboard = var.environment != "dev"

  # Cost optimization thresholds
  cost_optimization_thresholds = local.cost_optimization_settings

  cost_anomaly_thresholds = {
    impact_threshold = var.environment == "prod" ? 25 : 10 # Higher threshold for production
  }
}



#==============================================================================
# ADDITIONAL CLOUDWATCH LOG INSIGHTS QUERIES
#==============================================================================

# Saved queries for common troubleshooting scenarios
resource "aws_cloudwatch_query_definition" "lambda_errors" {
  count = 0

  name = "${local.name_prefix}-lambda-errors"

  query_string = <<-EOT
fields @timestamp, @message, @requestId
| filter @type = "REPORT"
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
EOT

  log_group_names = [
    "/aws/lambda/${module.lambda_functions.function_names.ingestion}",
    "/aws/lambda/${module.lambda_functions.function_names.processing}",
    "/aws/lambda/${module.lambda_functions.function_names.validation}"
  ]
}

resource "aws_cloudwatch_query_definition" "data_quality_issues" {
  count = 0

  name = "${local.name_prefix}-data-quality-issues"

  query_string = <<-EOT
fields @timestamp, @message
| filter @message like /quality_score/
| filter @message like /below threshold/
| stats count() by bin(5m)
| sort @timestamp desc
EOT

  log_group_names = [
    "/aws/lambda/${module.lambda_functions.function_names.validation}"
  ]
}

resource "aws_cloudwatch_query_definition" "processing_performance" {
  count = 0

  name = "${local.name_prefix}-processing-performance"

  query_string = <<-EOT
fields @timestamp, @duration, @billedDuration, @memorySize, @maxMemoryUsed
| filter @type = "REPORT"
| stats avg(@duration), max(@duration), avg(@maxMemoryUsed), max(@maxMemoryUsed) by bin(5m)
| sort @timestamp desc
EOT

  log_group_names = [
    "/aws/lambda/${module.lambda_functions.function_names.processing}"
  ]
}

#==============================================================================
# INTEGRATION WITH EXTERNAL MONITORING TOOLS
#==============================================================================

# CloudWatch Synthetics for end-to-end monitoring (optional)
resource "aws_synthetics_canary" "pipeline_health_check" {
  count = var.monitoring_config.enable_synthetic_monitoring ? 1 : 0

  name                 = "${local.name_prefix}-pipeline-health"
  artifact_s3_location = "s3://${module.s3_data_lake.bucket_names.athena_results}/canary-artifacts/"
  execution_role_arn   = aws_iam_role.synthetics_role[0].arn
  handler              = "pageLoadBlueprint.handler"
  zip_file             = "synthetics-canary.zip"
  runtime_version      = "syn-nodejs-puppeteer-6.2"

  schedule {
    expression          = "rate(5 minutes)"
    duration_in_seconds = 0
  }

  run_config {
    timeout_in_seconds = 60
    memory_in_mb       = 960
    active_tracing     = true
    environment_variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = local.monitoring_tags
}

# IAM role for Synthetics
resource "aws_iam_role" "synthetics_role" {
  count = var.monitoring_config.enable_synthetic_monitoring ? 1 : 0

  name = "${local.name_prefix}-synthetics-role"

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

  tags = local.monitoring_tags
}

resource "aws_iam_role_policy_attachment" "synthetics_policy" {
  count = var.monitoring_config.enable_synthetic_monitoring ? 1 : 0

  role       = aws_iam_role.synthetics_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchSyntheticsExecutionRolePolicy"
}

#==============================================================================
# CUSTOM METRICS FOR BUSINESS LOGIC
#==============================================================================

# CloudWatch custom metric filters for log-based metrics
resource "aws_cloudwatch_log_metric_filter" "data_quality_score" {
  name           = "${local.name_prefix}-data-quality-score"
  log_group_name = "/aws/lambda/${module.lambda_functions.function_names.validation}"
  pattern        = "[timestamp, request_id, level=\"INFO\", msg=\"Data quality score:\", score]"

  metric_transformation {
    name      = "DataQualityScore"
    namespace = "FlightDataPipeline"
    value     = "$score"

    default_value = 0

    unit = "None"
  }
}

resource "aws_cloudwatch_log_metric_filter" "records_processed" {
  name           = "${local.name_prefix}-records-processed"
  log_group_name = "/aws/lambda/${module.lambda_functions.function_names.processing}"
  pattern        = "[timestamp, request_id, level=\"INFO\", msg=\"Records processed:\", count]"

  metric_transformation {
    name      = "RecordsProcessed"
    namespace = "FlightDataPipeline"
    value     = "$count"

    default_value = 0

    unit = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "api_response_time" {
  name           = "${local.name_prefix}-api-response-time"
  log_group_name = "/aws/lambda/${module.lambda_functions.function_names.ingestion}"
  pattern        = "[timestamp, request_id, level=\"INFO\", msg=\"OpenSky API response time:\", duration, ms]"

  metric_transformation {
    name      = "APIResponseTime"
    namespace = "FlightDataPipeline"
    value     = "$duration"

    default_value = 0

    unit = "Milliseconds"
  }
}

#==============================================================================
# MONITORING MODULE OUTPUTS (RE-EXPORTED)
#==============================================================================

output "monitoring" {
  description = "Monitoring infrastructure configuration and details"
  value = {
    # Dashboard information
    dashboard_urls  = module.monitoring.dashboard_urls
    dashboard_names = module.monitoring.dashboard_names

    # SNS topics
    sns_topics             = module.monitoring.sns_topics
    notification_endpoints = module.monitoring.notification_endpoints

    # DynamoDB tracking table
    pipeline_tracking_table = module.monitoring.pipeline_tracking_table

    # Alarm summary
    alarm_summary = module.monitoring.alarm_summary
    alarm_counts = {
      total_critical = length(module.monitoring.alarm_arns.critical)
      total_warning  = length(module.monitoring.alarm_arns.warning)
    }

    # Budget configuration
    budgets        = module.monitoring.budgets
    billing_alarms = module.monitoring.billing_alarms

    # Cost optimization
    cost_optimization_alarms = module.monitoring.cost_optimization_alarms

    # Slack integration
    slack_integration = module.monitoring.slack_integration

    # Monitoring capabilities summary
    capabilities = {
      dashboards_enabled           = true
      email_alerts_enabled         = length(var.notification_config.alert_emails) > 0
      sms_alerts_enabled           = var.environment == "prod" && var.notification_config.enable_sms
      slack_enabled                = var.notification_config.enable_slack
      budget_monitoring_enabled    = true
      anomaly_detection_enabled    = true
      cost_optimization_enabled    = true
      synthetic_monitoring_enabled = var.monitoring_config.enable_synthetic_monitoring
#       log_insights_queries_enabled = false
    }

    # Environment-specific settings
    environment_config = {
      error_rate_threshold   = local.monitoring_thresholds.error_rate_threshold
      data_quality_threshold = local.monitoring_thresholds.data_quality_threshold
      availability_threshold = local.monitoring_thresholds.availability_threshold
      monthly_budget_limit   = var.budget_config.monthly_limit
    }
  }
  sensitive = false
}