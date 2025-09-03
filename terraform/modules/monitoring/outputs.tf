# Flight Data Pipeline - Monitoring Module Outputs
# This file defines all outputs for the monitoring module

#==============================================================================
# CLOUDWATCH DASHBOARD OUTPUTS
#==============================================================================

output "dashboard_urls" {
  description = "URLs for CloudWatch dashboards"
  value = {
    pipeline_monitoring = "https://${local.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${local.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.pipeline_monitoring.dashboard_name}"
    executive_summary   = var.create_executive_dashboard ? "https://${local.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${local.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.executive_summary[0].dashboard_name}" : null
  }
}

output "dashboard_names" {
  description = "Names of created CloudWatch dashboards"
  value = {
    pipeline_monitoring = aws_cloudwatch_dashboard.pipeline_monitoring.dashboard_name
    executive_summary   = var.create_executive_dashboard ? aws_cloudwatch_dashboard.executive_summary[0].dashboard_name : null
  }
}

#==============================================================================
# SNS TOPIC OUTPUTS
#==============================================================================

output "sns_topics" {
  description = "SNS topic information"
  value = {
    email_alerts = {
      arn  = aws_sns_topic.email_alerts.arn
      name = aws_sns_topic.email_alerts.name
    }
    critical_alerts = {
      arn  = aws_sns_topic.critical_alerts.arn
      name = aws_sns_topic.critical_alerts.name
    }
    slack_alerts = var.enable_slack_notifications ? {
      arn  = aws_sns_topic.slack_alerts[0].arn
      name = aws_sns_topic.slack_alerts[0].name
    } : null
    budget_alerts = {
      arn  = aws_sns_topic.budget_alerts.arn
      name = aws_sns_topic.budget_alerts.name
    }
  }
}

output "notification_endpoints" {
  description = "Summary of notification endpoints configured"
  value = {
    email_subscribers        = length(var.alert_email_addresses)
    critical_email_subscribers = length(var.critical_alert_email_addresses)
    sms_subscribers         = var.enable_sms_alerts ? length(var.sms_phone_numbers) : 0
    slack_enabled          = var.enable_slack_notifications
    budget_email_subscribers = length(var.budget_notification_emails)
  }
  sensitive = false
}

#==============================================================================
# DYNAMODB TABLE OUTPUTS
#==============================================================================

output "pipeline_tracking_table" {
  description = "Pipeline tracking DynamoDB table information"
  value = {
    name = aws_dynamodb_table.pipeline_tracking.name
    arn  = aws_dynamodb_table.pipeline_tracking.arn
    
    # Global Secondary Indexes
    global_secondary_indexes = {
      execution_date_index = "ExecutionDateIndex"
      status_index        = "StatusIndex"
    }
    
    # TTL configuration
    ttl_enabled        = true
    ttl_attribute_name = "expires_at"
    
    # Encryption
    encryption_enabled = var.enable_encryption
    kms_key_arn       = var.kms_key_arn
  }
}

#==============================================================================
# CLOUDWATCH ALARM OUTPUTS
#==============================================================================

output "alarm_summary" {
  description = "Summary of CloudWatch alarms created"
  value = {
    # Critical alarms
    critical_alarms = {
      high_error_rate       = aws_cloudwatch_metric_alarm.high_error_rate.alarm_name
      no_data_ingested     = aws_cloudwatch_metric_alarm.no_data_ingested.alarm_name
      validation_throttles = aws_cloudwatch_metric_alarm.validation_throttles.alarm_name
      pipeline_availability = aws_cloudwatch_metric_alarm.pipeline_availability.alarm_name
    }
    
    # Warning alarms
    warning_alarms = {
      low_data_quality         = aws_cloudwatch_metric_alarm.low_data_quality.alarm_name
      high_processing_latency  = aws_cloudwatch_metric_alarm.high_processing_latency.alarm_name
      ingestion_duration      = aws_cloudwatch_metric_alarm.ingestion_duration.alarm_name
      processing_memory       = aws_cloudwatch_metric_alarm.processing_memory.alarm_name
      data_completeness       = aws_cloudwatch_metric_alarm.data_completeness.alarm_name
      data_validity           = aws_cloudwatch_metric_alarm.data_validity.alarm_name
    }
    
    # DLQ alarms
    dlq_alarms = {
      for key, queue_name in var.dlq_names : key => aws_cloudwatch_metric_alarm.dlq_messages[key].alarm_name
      if queue_name != ""
    }
    
    # S3 storage alarms
    s3_storage_alarms = {
      for key, bucket_name in var.s3_bucket_names : key => aws_cloudwatch_metric_alarm.s3_storage_growth[key].alarm_name
    }
    
    # DynamoDB alarms
    dynamodb_alarms = {
      read_throttles  = aws_cloudwatch_metric_alarm.dynamodb_read_throttles.alarm_name
      write_throttles = aws_cloudwatch_metric_alarm.dynamodb_write_throttles.alarm_name
    }
    
    # Anomaly detection
    anomaly_alarms = {}
  }
}

output "alarm_arns" {
  description = "ARNs of all CloudWatch alarms"
  value = {
    critical = [
      aws_cloudwatch_metric_alarm.high_error_rate.arn,
      aws_cloudwatch_metric_alarm.no_data_ingested.arn,
      aws_cloudwatch_metric_alarm.validation_throttles.arn,
      aws_cloudwatch_metric_alarm.pipeline_availability.arn
    ]
    warning = [
      aws_cloudwatch_metric_alarm.low_data_quality.arn,
      aws_cloudwatch_metric_alarm.high_processing_latency.arn,
      aws_cloudwatch_metric_alarm.ingestion_duration.arn,
      aws_cloudwatch_metric_alarm.processing_memory.arn,
      aws_cloudwatch_metric_alarm.data_completeness.arn,
      aws_cloudwatch_metric_alarm.data_validity.arn
    ]
  }
}

#==============================================================================
# BUDGET OUTPUTS
#==============================================================================

output "budgets" {
  description = "Budget information"
  value = {
    monthly_budget = {
      name   = aws_budgets_budget.monthly_budget.name
      limit  = var.budget_limits.monthly_limit
      unit   = "USD"
    }
    
    service_budgets = null
    
    # Cost anomaly detection
    cost_anomaly_detector = {
#       name = aws_ce_anomaly_detector.project_cost_anomaly.name
#       arn  = aws_ce_anomaly_detector.project_cost_anomaly.arn
    }
  }
}

output "billing_alarms" {
  description = "Billing alarm information"
  value = {
    account_billing = aws_cloudwatch_metric_alarm.account_billing.alarm_name
    service_alarms = {}
  }
}

#==============================================================================
# COST OPTIMIZATION OUTPUTS
#==============================================================================

output "cost_optimization_alarms" {
  description = "Cost optimization alarm information"
  value = {
    s3_storage_optimization = {
      for key, bucket_name in var.s3_bucket_names : key => aws_cloudwatch_metric_alarm.s3_storage_optimization[key].alarm_name
    }
    lambda_cold_starts     = aws_cloudwatch_metric_alarm.lambda_cold_starts.alarm_name
    dynamodb_throttling    = aws_cloudwatch_metric_alarm.dynamodb_throttling_cost.alarm_name
  }
}

#==============================================================================
# LAMBDA FUNCTION OUTPUTS (IF SLACK ENABLED)
#==============================================================================

output "slack_integration" {
  description = "Slack integration information"
  value = var.enable_slack_notifications ? {
    lambda_function = {
      name = aws_lambda_function.slack_formatter[0].function_name
      arn  = aws_lambda_function.slack_formatter[0].arn
    }
    sns_topic = {
      name = aws_sns_topic.slack_alerts[0].name
      arn  = aws_sns_topic.slack_alerts[0].arn
    }
    webhook_configured = var.slack_webhook_url != null
  } : null
}

#==============================================================================
# MONITORING SUMMARY
#==============================================================================

output "monitoring_summary" {
  description = "Overall monitoring configuration summary"
  value = {
    # Dashboard count
    dashboards_created = var.create_executive_dashboard ? 2 : 1
    
    # Alarm counts
    total_alarms = (
      4 +  # Critical alarms
      6 +  # Warning alarms
      length([for k, v in var.dlq_names : k if v != ""]) +  # DLQ alarms
      length(var.s3_bucket_names) +  # S3 storage alarms
      2 +  # DynamoDB alarms
      1 +  # Anomaly detection
      4 +  # Billing alarms
      length(var.s3_bucket_names) +  # Storage optimization
      3    # Cost optimization
    )
    
    # SNS topics
    sns_topics_created = var.enable_slack_notifications ? 4 : 3
    
    # Budget configuration
    budgets_configured = var.enable_service_budgets ? 4 : 1
    
    # Cost monitoring
    cost_anomaly_detection_enabled = true
    
    # Notification channels
    notification_channels = {
      email = length(var.alert_email_addresses) > 0
      sms   = var.enable_sms_alerts
      slack = var.enable_slack_notifications
    }
    
    # Thresholds configured
    thresholds = {
      error_rate_percent       = var.alarm_thresholds.error_rate_threshold * 100
      data_quality_score       = var.alarm_thresholds.data_quality_threshold
      processing_latency_seconds = var.alarm_thresholds.processing_latency_threshold
      monthly_budget_usd       = var.budget_limits.monthly_limit
    }
  }
  sensitive = false
}