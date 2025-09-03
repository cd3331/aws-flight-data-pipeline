# Flight Data Pipeline - Budget Monitoring and Cost Alarms
# This file contains budget configuration and cost monitoring alarms

#==============================================================================
# AWS BUDGETS
#==============================================================================

# Monthly budget for the entire project
resource "aws_budgets_budget" "monthly_budget" {
  name         = "${local.name_prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.budget_limits.monthly_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = var.budget_thresholds.warning_threshold
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = var.budget_notification_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = var.budget_thresholds.critical_threshold
    threshold_type            = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_notification_emails
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = var.budget_thresholds.forecast_threshold
    threshold_type            = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.budget_notification_emails
  }

  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-monthly-budget"
    Purpose     = "Monthly cost monitoring"
    Environment = var.environment
  })
}

# Service-specific budgets
# resource "aws_budgets_budget" "lambda_budget" {
#   count = var.enable_service_budgets ? 1 : 0
#   
#   name         = "${local.name_prefix}-lambda-budget"
#   budget_type  = "COST"
#   limit_amount = var.service_budget_limits.lambda_limit
#   limit_unit   = "USD"
#   time_unit    = "MONTHLY"
#   
#   cost_filter {
#     name = "Service"
#     values = ["AWS Lambda"]
#   }
# 
#   notification {
#     comparison_operator        = "GREATER_THAN"
#     threshold                 = "80"
#     threshold_type            = "PERCENTAGE"
#     notification_type          = "ACTUAL"
#     subscriber_email_addresses = var.budget_notification_emails
#   }
# }

# resource "aws_budgets_budget" "s3_budget" {
#   count = var.enable_service_budgets ? 1 : 0
#   
#   name         = "${local.name_prefix}-s3-budget"
#   budget_type  = "COST"
#   limit_amount = var.service_budget_limits.s3_limit
#   limit_unit   = "USD"
#   time_unit    = "MONTHLY"
#   
#   cost_filter {
#     name = "Service"
#     values = ["Amazon Simple Storage Service"]
#   }
# 
#   notification {
#     comparison_operator        = "GREATER_THAN"
#     threshold                 = "80"
#     threshold_type            = "PERCENTAGE"
#     notification_type          = "ACTUAL"
#     subscriber_email_addresses = var.budget_notification_emails
#   }
# }

# resource "aws_budgets_budget" "dynamodb_budget" {
#   count = var.enable_service_budgets ? 1 : 0
#   
#   name         = "${local.name_prefix}-dynamodb-budget"
#   budget_type  = "COST"
#   limit_amount = var.service_budget_limits.dynamodb_limit
#   limit_unit   = "USD"
#   time_unit    = "MONTHLY"
#   
#   cost_filter {
#     name = "Service"
#     values = ["Amazon DynamoDB"]
#   }
# 
#   notification {
#     comparison_operator        = "GREATER_THAN"
#     threshold                 = "80"
#     threshold_type            = "PERCENTAGE"
#     notification_type          = "ACTUAL"
#     subscriber_email_addresses = var.budget_notification_emails
#   }
# }

#==============================================================================
# BUDGET SNS TOPIC
#==============================================================================

resource "aws_sns_topic" "budget_alerts" {
  name = "${local.name_prefix}-budget-alerts"
  
  # Server-side encryption
  kms_master_key_id = var.enable_encryption ? var.kms_key_arn : null
  
  tags = merge(var.tags, {
    Name        = "${local.name_prefix}-budget-alerts"
    Purpose     = "Budget and cost alerts"
    Environment = var.environment
  })
}

resource "aws_sns_topic_subscription" "budget_email_alerts" {
  for_each = toset(var.budget_notification_emails)
  
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

#==============================================================================
# CLOUDWATCH BILLING ALARMS
#==============================================================================

# Overall account billing alarm
resource "aws_cloudwatch_metric_alarm" "account_billing" {
  provider = aws.us-east-1  # Billing metrics are only available in us-east-1
  
  alarm_name          = "${local.name_prefix}-account-billing"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24 hours
  statistic           = "Maximum"
  threshold           = var.budget_limits.monthly_limit
  alarm_description   = "Account billing exceeded ${var.budget_limits.monthly_limit} USD"
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    Currency = "USD"
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-account-billing"
    Severity = "Critical"
    Type     = "Cost"
  })
}

# Service-specific billing alarms
resource "aws_cloudwatch_metric_alarm" "lambda_billing" {
  provider = aws.us-east-1
  
  alarm_name          = "${local.name_prefix}-lambda-billing"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = var.service_budget_limits.lambda_limit
  alarm_description   = "Lambda billing exceeded ${var.service_budget_limits.lambda_limit} USD"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  
  dimensions = {
    Currency    = "USD"
    ServiceName = "AWSLambda"
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-lambda-billing"
    Severity = "Warning"
    Service  = "Lambda"
  })
}

resource "aws_cloudwatch_metric_alarm" "s3_billing" {
  provider = aws.us-east-1
  
  alarm_name          = "${local.name_prefix}-s3-billing"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = var.service_budget_limits.s3_limit
  alarm_description   = "S3 billing exceeded ${var.service_budget_limits.s3_limit} USD"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  
  dimensions = {
    Currency    = "USD"
    ServiceName = "AmazonS3"
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-s3-billing"
    Severity = "Warning"
    Service  = "S3"
  })
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_billing" {
  provider = aws.us-east-1
  
  alarm_name          = "${local.name_prefix}-dynamodb-billing"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = var.service_budget_limits.dynamodb_limit
  alarm_description   = "DynamoDB billing exceeded ${var.service_budget_limits.dynamodb_limit} USD"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  
  dimensions = {
    Currency    = "USD"
    ServiceName = "AmazonDynamoDB"
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-dynamodb-billing"
    Severity = "Warning"
    Service  = "DynamoDB"
  })
}

#==============================================================================
# COST OPTIMIZATION MONITORING
#==============================================================================

# S3 storage class distribution
resource "aws_cloudwatch_metric_alarm" "s3_storage_optimization" {
  for_each = var.s3_bucket_names
  
  alarm_name          = "${local.name_prefix}-${each.key}-storage-optimization"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  threshold           = var.cost_optimization_thresholds.s3_ia_ratio
  alarm_description   = "S3 bucket ${each.key} may benefit from lifecycle optimization"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  treat_missing_data  = "notBreaching"
  
  metric_query {
    id          = "ia_storage"
    return_data = false
    
    metric {
      metric_name = "BucketSizeBytes"
      namespace   = "AWS/S3"
      period      = 86400
      stat        = "Average"
      
      dimensions = {
        BucketName  = each.value
        StorageType = "StandardIAStorage"
      }
    }
  }
  
  metric_query {
    id          = "standard_storage"
    return_data = false
    
    metric {
      metric_name = "BucketSizeBytes"
      namespace   = "AWS/S3"
      period      = 86400
      stat        = "Average"
      
      dimensions = {
        BucketName  = each.value
        StorageType = "StandardStorage"
      }
    }
  }
  
  metric_query {
    id          = "optimization_ratio"
    expression  = "ia_storage/(standard_storage+ia_storage)"
    label       = "IA Storage Ratio"
    return_data = true
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-${each.key}-storage-optimization"
    Severity = "Info"
    Type     = "Cost Optimization"
  })
}

# Lambda cold start monitoring (cost impact)
resource "aws_cloudwatch_metric_alarm" "lambda_cold_starts" {
  alarm_name          = "${local.name_prefix}-lambda-cold-starts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ColdStarts"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.cost_optimization_thresholds.cold_start_threshold
  alarm_description   = "High Lambda cold starts may indicate need for provisioned concurrency"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  
  dimensions = {
    FunctionName = var.lambda_function_names.ingestion
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-lambda-cold-starts"
    Severity = "Info"
    Type     = "Cost Optimization"
  })
}

# DynamoDB throttling cost impact
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttling_cost" {
  alarm_name          = "${local.name_prefix}-dynamodb-throttling-cost"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = var.cost_optimization_thresholds.dynamodb_throttle_threshold
  alarm_description   = "DynamoDB throttling may indicate need for capacity adjustment"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
  
  metric_query {
    id          = "read_throttles"
    return_data = false
    
    metric {
      metric_name = "ReadThrottles"
      namespace   = "AWS/DynamoDB"
      period      = 300
      stat        = "Sum"
      
      dimensions = {
        TableName = aws_dynamodb_table.pipeline_tracking.name
      }
    }
  }
  
  metric_query {
    id          = "write_throttles"
    return_data = false
    
    metric {
      metric_name = "WriteThrottles"
      namespace   = "AWS/DynamoDB"
      period      = 300
      stat        = "Sum"
      
      dimensions = {
        TableName = aws_dynamodb_table.pipeline_tracking.name
      }
    }
  }
  
  metric_query {
    id          = "total_throttles"
    expression  = "read_throttles + write_throttles"
    label       = "Total Throttles"
    return_data = true
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-dynamodb-throttling-cost"
    Severity = "Info"
    Type     = "Cost Optimization"
  })
}

#==============================================================================
# COST ANOMALY DETECTION
#==============================================================================

# Cost anomaly detection removed - not supported in all regions
# Alternative monitoring via CloudWatch billing alerts in main budget resources above