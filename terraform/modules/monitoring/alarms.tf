# Flight Data Pipeline - CloudWatch Alarms Configuration
# This file contains comprehensive alarm configuration for monitoring pipeline health

#==============================================================================
# PIPELINE HEALTH ALARMS
#==============================================================================

# High Error Rate Alarm (> 5%)
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${local.name_prefix}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.alarm_thresholds.error_rate_threshold
  alarm_description   = "Pipeline errors exceeded ${var.alarm_thresholds.error_rate_threshold} errors"
  alarm_actions       = local.critical_alarms
  ok_actions          = [aws_sns_topic.email_alerts.arn]
  treat_missing_data  = "breaching"
  
  dimensions = {
    FunctionName = var.lambda_function_names.ingestion
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-high-error-rate"
    Severity = "Critical"
    Type     = "Error Rate"
  })
}

# Low Data Quality Alarm (< 0.7)
resource "aws_cloudwatch_metric_alarm" "low_data_quality" {
  alarm_name          = "${local.name_prefix}-low-data-quality"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "DataQualityScore"
  namespace           = "FlightDataPipeline"
  period              = "300"
  statistic           = "Average"
  threshold           = var.alarm_thresholds.data_quality_threshold
  alarm_description   = "Data quality score below ${var.alarm_thresholds.data_quality_threshold}"
  alarm_actions       = local.warning_alarms
  ok_actions          = [aws_sns_topic.email_alerts.arn]
  treat_missing_data  = "breaching"
  
  dimensions = {
    Environment = var.environment
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-low-data-quality"
    Severity = "Warning"
    Type     = "Data Quality"
  })
}

# No Data Ingested Alarm (missing data)
resource "aws_cloudwatch_metric_alarm" "no_data_ingested" {
  alarm_name          = "${local.name_prefix}-no-data-ingested"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = "900"  # 15 minutes
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "No data has been ingested for 30 minutes"
  alarm_actions       = local.critical_alarms
  ok_actions          = [aws_sns_topic.email_alerts.arn]
  treat_missing_data  = "breaching"
  
  dimensions = {
    FunctionName = var.lambda_function_names.ingestion
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-no-data-ingested"
    Severity = "Critical"
    Type     = "Data Availability"
  })
}

# High Processing Latency Alarm (> 60s)
resource "aws_cloudwatch_metric_alarm" "high_processing_latency" {
  alarm_name          = "${local.name_prefix}-high-processing-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.alarm_thresholds.processing_latency_threshold * 1000  # Convert to milliseconds
  alarm_description   = "Processing latency exceeded ${var.alarm_thresholds.processing_latency_threshold}s"
  alarm_actions       = local.warning_alarms
  ok_actions          = [aws_sns_topic.email_alerts.arn]
  
  dimensions = {
    FunctionName = var.lambda_function_names.processing
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-high-processing-latency"
    Severity = "Warning"
    Type     = "Performance"
  })
}

#==============================================================================
# LAMBDA FUNCTION SPECIFIC ALARMS
#==============================================================================

# Ingestion Function Duration Alarm
resource "aws_cloudwatch_metric_alarm" "ingestion_duration" {
  alarm_name          = "${local.name_prefix}-ingestion-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.lambda_timeouts.ingestion * 800  # 80% of timeout in milliseconds
  alarm_description   = "Ingestion function duration approaching timeout"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    FunctionName = var.lambda_function_names.ingestion
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-ingestion-duration"
    Severity = "Warning"
    Function = "ingestion"
  })
}

# Processing Function Memory Utilization
resource "aws_cloudwatch_metric_alarm" "processing_memory" {
  alarm_name          = "${local.name_prefix}-processing-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"  # 85% memory utilization
  alarm_description   = "Processing function memory utilization high"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    FunctionName = var.lambda_function_names.processing
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-processing-memory"
    Severity = "Warning"
    Function = "processing"
  })
}

# Validation Function Throttle Alarm
resource "aws_cloudwatch_metric_alarm" "validation_throttles" {
  alarm_name          = "${local.name_prefix}-validation-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Validation function is being throttled"
  alarm_actions       = local.critical_alarms
  
  dimensions = {
    FunctionName = var.lambda_function_names.validation
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-validation-throttles"
    Severity = "Critical"
    Function = "validation"
  })
}

#==============================================================================
# DEAD LETTER QUEUE ALARMS
#==============================================================================

# Dead Letter Queue Messages Alarm
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  for_each = var.dlq_names
  
  alarm_name          = "${local.name_prefix}-${each.key}-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "Messages in ${each.key} dead letter queue"
  alarm_actions       = local.critical_alarms
  
  dimensions = {
    QueueName = each.value
  }
  
  tags = merge(var.tags, {
    Name      = "${local.name_prefix}-${each.key}-dlq-messages"
    Severity  = "Critical"
    QueueType = "DLQ"
  })
}

#==============================================================================
# S3 BUCKET MONITORING ALARMS
#==============================================================================

# S3 Bucket Size Growth Rate
resource "aws_cloudwatch_metric_alarm" "s3_storage_growth" {
  for_each = var.s3_bucket_names
  
  alarm_name          = "${local.name_prefix}-${each.key}-storage-growth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400"  # Daily
  statistic           = "Average"
  threshold           = var.alarm_thresholds.s3_storage_threshold_gb * 1024 * 1024 * 1024  # Convert GB to bytes
  alarm_description   = "S3 bucket ${each.key} size exceeded threshold"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    BucketName  = each.value
    StorageType = "StandardStorage"
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-${each.key}-storage-growth"
    Severity = "Warning"
    Bucket   = each.key
  })
}

#==============================================================================
# DYNAMODB MONITORING ALARMS
#==============================================================================

# DynamoDB Read Throttle Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_read_throttles" {
  alarm_name          = "${local.name_prefix}-dynamodb-read-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReadThrottles"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "DynamoDB read throttling detected"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    TableName = aws_dynamodb_table.pipeline_tracking.name
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-dynamodb-read-throttles"
    Severity = "Warning"
    Service  = "DynamoDB"
  })
}

# DynamoDB Write Throttle Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_write_throttles" {
  alarm_name          = "${local.name_prefix}-dynamodb-write-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "WriteThrottles"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "DynamoDB write throttling detected"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    TableName = aws_dynamodb_table.pipeline_tracking.name
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-dynamodb-write-throttles"
    Severity = "Warning"
    Service  = "DynamoDB"
  })
}

#==============================================================================
# CUSTOM BUSINESS LOGIC ALARMS
#==============================================================================

# Data Completeness Alarm
resource "aws_cloudwatch_metric_alarm" "data_completeness" {
  alarm_name          = "${local.name_prefix}-data-completeness"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "CompletenessScore"
  namespace           = "FlightDataPipeline"
  period              = "300"
  statistic           = "Average"
  threshold           = var.alarm_thresholds.completeness_threshold
  alarm_description   = "Data completeness score below ${var.alarm_thresholds.completeness_threshold}"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    Environment = var.environment
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-data-completeness"
    Severity = "Warning"
    Type     = "Data Quality"
  })
}

# Data Validity Alarm
resource "aws_cloudwatch_metric_alarm" "data_validity" {
  alarm_name          = "${local.name_prefix}-data-validity"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ValidityScore"
  namespace           = "FlightDataPipeline"
  period              = "300"
  statistic           = "Average"
  threshold           = var.alarm_thresholds.validity_threshold
  alarm_description   = "Data validity score below ${var.alarm_thresholds.validity_threshold}"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    Environment = var.environment
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-data-validity"
    Severity = "Warning"
    Type     = "Data Quality"
  })
}

# Pipeline Availability Alarm
resource "aws_cloudwatch_metric_alarm" "pipeline_availability" {
  alarm_name          = "${local.name_prefix}-pipeline-availability"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "PipelineUptime"
  namespace           = "FlightDataPipeline"
  period              = "300"
  statistic           = "Average"
  threshold           = var.alarm_thresholds.availability_threshold
  alarm_description   = "Pipeline availability below ${var.alarm_thresholds.availability_threshold * 100}%"
  alarm_actions       = local.critical_alarms
  
  dimensions = {
    Environment = var.environment
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-pipeline-availability"
    Severity = "Critical"
    Type     = "Availability"
  })
}

#==============================================================================
# ANOMALY DETECTION
#==============================================================================

# Ingestion rate alarm (simplified without anomaly detection)
resource "aws_cloudwatch_metric_alarm" "ingestion_rate_alarm" {
  alarm_name          = "${local.name_prefix}-ingestion-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Ingestion function not running as expected"
  alarm_actions       = local.warning_alarms
  
  dimensions = {
    FunctionName = var.lambda_function_names.ingestion
  }
  
  tags = merge(var.tags, {
    Name     = "${local.name_prefix}-ingestion-rate"
    Severity = "Warning"
    Type     = "Invocation Monitoring"
  })
}