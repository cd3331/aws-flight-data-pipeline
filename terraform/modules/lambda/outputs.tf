# Lambda Functions Module - Outputs
# This file defines all output values from the Lambda functions module

#==============================================================================
# LAMBDA FUNCTION INFORMATION
#==============================================================================

output "ingestion_function" {
  description = "Ingestion Lambda function details"
  value = {
    function_name     = aws_lambda_function.ingestion.function_name
    function_arn      = aws_lambda_function.ingestion.arn
    qualified_arn     = aws_lambda_function.ingestion.qualified_arn
    invoke_arn        = aws_lambda_function.ingestion.invoke_arn
    version          = aws_lambda_function.ingestion.version
    last_modified    = aws_lambda_function.ingestion.last_modified
    runtime          = aws_lambda_function.ingestion.runtime
    architecture     = aws_lambda_function.ingestion.architectures[0]
    memory_size      = aws_lambda_function.ingestion.memory_size
    timeout          = aws_lambda_function.ingestion.timeout
    handler          = aws_lambda_function.ingestion.handler
    role_arn         = aws_lambda_function.ingestion.role
    kms_key_arn      = aws_lambda_function.ingestion.kms_key_arn
    source_code_hash = aws_lambda_function.ingestion.source_code_hash
    source_code_size = aws_lambda_function.ingestion.source_code_size
    layers           = aws_lambda_function.ingestion.layers
    
    # Configuration details
    reserved_concurrent_executions = aws_lambda_function.ingestion.reserved_concurrent_executions
    dead_letter_config            = aws_lambda_function.ingestion.dead_letter_config
    tracing_config               = aws_lambda_function.ingestion.tracing_config
    vpc_config                   = aws_lambda_function.ingestion.vpc_config
  }
}

output "processing_function" {
  description = "Processing Lambda function details"
  value = {
    function_name     = aws_lambda_function.processing.function_name
    function_arn      = aws_lambda_function.processing.arn
    qualified_arn     = aws_lambda_function.processing.qualified_arn
    invoke_arn        = aws_lambda_function.processing.invoke_arn
    version          = aws_lambda_function.processing.version
    last_modified    = aws_lambda_function.processing.last_modified
    runtime          = aws_lambda_function.processing.runtime
    architecture     = aws_lambda_function.processing.architectures[0]
    memory_size      = aws_lambda_function.processing.memory_size
    timeout          = aws_lambda_function.processing.timeout
    handler          = aws_lambda_function.processing.handler
    role_arn         = aws_lambda_function.processing.role
    kms_key_arn      = aws_lambda_function.processing.kms_key_arn
    source_code_hash = aws_lambda_function.processing.source_code_hash
    source_code_size = aws_lambda_function.processing.source_code_size
    layers           = aws_lambda_function.processing.layers
    
    # Configuration details
    reserved_concurrent_executions = aws_lambda_function.processing.reserved_concurrent_executions
    dead_letter_config            = aws_lambda_function.processing.dead_letter_config
    tracing_config               = aws_lambda_function.processing.tracing_config
    vpc_config                   = aws_lambda_function.processing.vpc_config
  }
}

output "validation_function" {
  description = "Validation Lambda function details"
  value = {
    function_name     = aws_lambda_function.validation.function_name
    function_arn      = aws_lambda_function.validation.arn
    qualified_arn     = aws_lambda_function.validation.qualified_arn
    invoke_arn        = aws_lambda_function.validation.invoke_arn
    version          = aws_lambda_function.validation.version
    last_modified    = aws_lambda_function.validation.last_modified
    runtime          = aws_lambda_function.validation.runtime
    architecture     = aws_lambda_function.validation.architectures[0]
    memory_size      = aws_lambda_function.validation.memory_size
    timeout          = aws_lambda_function.validation.timeout
    handler          = aws_lambda_function.validation.handler
    role_arn         = aws_lambda_function.validation.role
    kms_key_arn      = aws_lambda_function.validation.kms_key_arn
    source_code_hash = aws_lambda_function.validation.source_code_hash
    source_code_size = aws_lambda_function.validation.source_code_size
    layers           = aws_lambda_function.validation.layers
    
    # Configuration details
    reserved_concurrent_executions = aws_lambda_function.validation.reserved_concurrent_executions
    dead_letter_config            = aws_lambda_function.validation.dead_letter_config
    tracing_config               = aws_lambda_function.validation.tracing_config
    vpc_config                   = aws_lambda_function.validation.vpc_config
  }
}

#==============================================================================
# LAMBDA FUNCTION NAMES AND ARNS (SIMPLIFIED)
#==============================================================================

output "function_names" {
  description = "Lambda function names for easy reference"
  value = {
    ingestion  = aws_lambda_function.ingestion.function_name
    processing = aws_lambda_function.processing.function_name
    validation = aws_lambda_function.validation.function_name
  }
}

output "function_arns" {
  description = "Lambda function ARNs for permissions and integrations"
  value = {
    ingestion  = aws_lambda_function.ingestion.arn
    processing = aws_lambda_function.processing.arn
    validation = aws_lambda_function.validation.arn
  }
}

output "function_invoke_arns" {
  description = "Lambda function invoke ARNs for API Gateway integrations"
  value = {
    ingestion  = aws_lambda_function.ingestion.invoke_arn
    processing = aws_lambda_function.processing.invoke_arn
    validation = aws_lambda_function.validation.invoke_arn
  }
}

#==============================================================================
# IAM ROLE AND POLICIES
#==============================================================================

output "lambda_execution_role" {
  description = "Lambda execution role details"
  value = {
    name = aws_iam_role.lambda_execution_role.name
    arn  = aws_iam_role.lambda_execution_role.arn
    id   = aws_iam_role.lambda_execution_role.id
    path = aws_iam_role.lambda_execution_role.path
    
    # Attached policies
    attached_policies = [
      "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
      aws_iam_policy.lambda_s3_access.arn,
      aws_iam_policy.lambda_cloudwatch_sns_access.arn
    ]
  }
}

output "iam_policies" {
  description = "Custom IAM policies created for Lambda functions"
  value = {
    s3_access = {
      name = aws_iam_policy.lambda_s3_access.name
      arn  = aws_iam_policy.lambda_s3_access.arn
    }
    dynamodb_access = var.dynamodb_table_arn != null ? {
      name = aws_iam_policy.lambda_dynamodb_access.name
      arn  = aws_iam_policy.lambda_dynamodb_access.arn
    } : null
    cloudwatch_sns_access = {
      name = aws_iam_policy.lambda_cloudwatch_sns_access.name
      arn  = aws_iam_policy.lambda_cloudwatch_sns_access.arn
    }
  }
}

#==============================================================================
# LAMBDA LAYERS
#==============================================================================

output "lambda_layers" {
  description = "Lambda layers information"
  value = {
    shared_dependencies = {
      layer_name       = aws_lambda_layer_version.shared_dependencies.layer_name
      layer_arn        = aws_lambda_layer_version.shared_dependencies.arn
      version          = aws_lambda_layer_version.shared_dependencies.version
      created_date     = aws_lambda_layer_version.shared_dependencies.created_date
      source_code_hash = aws_lambda_layer_version.shared_dependencies.source_code_hash
      source_code_size = aws_lambda_layer_version.shared_dependencies.source_code_size
      compatible_runtimes = aws_lambda_layer_version.shared_dependencies.compatible_runtimes
      compatible_architectures = aws_lambda_layer_version.shared_dependencies.compatible_architectures
    }
    common_utilities = {
      layer_name       = aws_lambda_layer_version.common_utilities.layer_name
      layer_arn        = aws_lambda_layer_version.common_utilities.arn
      version          = aws_lambda_layer_version.common_utilities.version
      created_date     = aws_lambda_layer_version.common_utilities.created_date
      source_code_hash = aws_lambda_layer_version.common_utilities.source_code_hash
      source_code_size = aws_lambda_layer_version.common_utilities.source_code_size
      compatible_runtimes = aws_lambda_layer_version.common_utilities.compatible_runtimes
      compatible_architectures = aws_lambda_layer_version.common_utilities.compatible_architectures
    }
  }
}

#==============================================================================
# CLOUDWATCH LOGS
#==============================================================================

output "cloudwatch_log_groups" {
  description = "CloudWatch log groups for Lambda functions"
  value = {
    ingestion = {
      name              = aws_cloudwatch_log_group.ingestion_logs.name
      arn               = aws_cloudwatch_log_group.ingestion_logs.arn
      retention_in_days = aws_cloudwatch_log_group.ingestion_logs.retention_in_days
      kms_key_id        = aws_cloudwatch_log_group.ingestion_logs.kms_key_id
    }
    processing = {
      name              = aws_cloudwatch_log_group.processing_logs.name
      arn               = aws_cloudwatch_log_group.processing_logs.arn
      retention_in_days = aws_cloudwatch_log_group.processing_logs.retention_in_days
      kms_key_id        = aws_cloudwatch_log_group.processing_logs.kms_key_id
    }
    validation = {
      name              = aws_cloudwatch_log_group.validation_logs.name
      arn               = aws_cloudwatch_log_group.validation_logs.arn
      retention_in_days = aws_cloudwatch_log_group.validation_logs.retention_in_days
      kms_key_id        = aws_cloudwatch_log_group.validation_logs.kms_key_id
    }
  }
}

#==============================================================================
# DEAD LETTER QUEUES
#==============================================================================

output "dead_letter_queues" {
  description = "Dead letter queues for Lambda functions"
  value = {
    ingestion = {
      name = aws_sqs_queue.ingestion_dlq.name
      arn  = aws_sqs_queue.ingestion_dlq.arn
      url  = aws_sqs_queue.ingestion_dlq.id
    }
    processing = {
      name = aws_sqs_queue.processing_dlq.name
      arn  = aws_sqs_queue.processing_dlq.arn
      url  = aws_sqs_queue.processing_dlq.id
    }
    validation = {
      name = aws_sqs_queue.validation_dlq.name
      arn  = aws_sqs_queue.validation_dlq.arn
      url  = aws_sqs_queue.validation_dlq.id
    }
    eventbridge = {
      name = aws_sqs_queue.eventbridge_dlq.name
      arn  = aws_sqs_queue.eventbridge_dlq.arn
      url  = aws_sqs_queue.eventbridge_dlq.id
    }
  }
}

#==============================================================================
# EVENTBRIDGE CONFIGURATION
#==============================================================================

output "eventbridge_rules" {
  description = "EventBridge rules for scheduled events"
  value = {
    scheduled_ingestion = {
      name                = aws_cloudwatch_event_rule.scheduled_ingestion.name
      arn                 = aws_cloudwatch_event_rule.scheduled_ingestion.arn
      schedule_expression = aws_cloudwatch_event_rule.scheduled_ingestion.schedule_expression
      state               = aws_cloudwatch_event_rule.scheduled_ingestion.state
    }
    lambda_state_change = var.monitor_lambda_state_changes ? {
      name = aws_cloudwatch_event_rule.lambda_state_change[0].name
      arn  = aws_cloudwatch_event_rule.lambda_state_change[0].arn
    } : null
  }
}

#==============================================================================
# LAMBDA ALIASES (IF VERSIONING IS ENABLED)
#==============================================================================

output "lambda_aliases" {
  description = "Lambda function aliases (if versioning is enabled)"
  value = var.enable_lambda_versioning ? {
    ingestion = {
      name             = aws_lambda_alias.ingestion_alias[0].name
      arn              = aws_lambda_alias.ingestion_alias[0].arn
      function_version = aws_lambda_alias.ingestion_alias[0].function_version
      invoke_arn       = aws_lambda_alias.ingestion_alias[0].invoke_arn
    }
    processing = {
      name             = aws_lambda_alias.processing_alias[0].name
      arn              = aws_lambda_alias.processing_alias[0].arn
      function_version = aws_lambda_alias.processing_alias[0].function_version
      invoke_arn       = aws_lambda_alias.processing_alias[0].invoke_arn
    }
    validation = {
      name             = aws_lambda_alias.validation_alias[0].name
      arn              = aws_lambda_alias.validation_alias[0].arn
      function_version = aws_lambda_alias.validation_alias[0].function_version
      invoke_arn       = aws_lambda_alias.validation_alias[0].invoke_arn
    }
  } : null
}

#==============================================================================
# PROVISIONED CONCURRENCY (IF ENABLED)
#==============================================================================

output "provisioned_concurrency" {
  description = "Provisioned concurrency configurations (if enabled)"
  value = var.enable_provisioned_concurrency ? {
    ingestion = var.lambda_config.ingestion.provisioned_concurrency > 0 ? {
      provisioned_concurrent_executions = aws_lambda_provisioned_concurrency_config.ingestion_provisioned[0].provisioned_concurrent_executions
    } : null
    processing = var.lambda_config.processing.provisioned_concurrency > 0 ? {
      provisioned_concurrent_executions = aws_lambda_provisioned_concurrency_config.processing_provisioned[0].provisioned_concurrent_executions
    } : null
  } : null
}

#==============================================================================
# CLOUDWATCH ALARMS
#==============================================================================

output "cloudwatch_alarms" {
  description = "CloudWatch alarms for Lambda monitoring (if enabled)"
  value = var.enable_cloudwatch_alarms ? {
    ingestion_errors = {
      name      = aws_cloudwatch_metric_alarm.ingestion_error_alarm[0].alarm_name
      arn       = aws_cloudwatch_metric_alarm.ingestion_error_alarm[0].arn
      threshold = aws_cloudwatch_metric_alarm.ingestion_error_alarm[0].threshold
    }
    processing_duration = {
      name      = aws_cloudwatch_metric_alarm.processing_duration_alarm[0].alarm_name
      arn       = aws_cloudwatch_metric_alarm.processing_duration_alarm[0].arn
      threshold = aws_cloudwatch_metric_alarm.processing_duration_alarm[0].threshold
    }
    validation_throttles = {
      name      = aws_cloudwatch_metric_alarm.validation_throttle_alarm[0].alarm_name
      arn       = aws_cloudwatch_metric_alarm.validation_throttle_alarm[0].arn
      threshold = aws_cloudwatch_metric_alarm.validation_throttle_alarm[0].threshold
    }
    dlq_messages = {
      name      = aws_cloudwatch_metric_alarm.dlq_message_alarm[0].alarm_name
      arn       = aws_cloudwatch_metric_alarm.dlq_message_alarm[0].arn
      threshold = aws_cloudwatch_metric_alarm.dlq_message_alarm[0].threshold
    }
  } : null
}

#==============================================================================
# ERROR NOTIFICATIONS
#==============================================================================

output "error_notification_topic" {
  description = "SNS topic for Lambda error notifications (if enabled)"
  value = var.create_error_notification_topic ? {
    name = aws_sns_topic.lambda_errors[0].name
    arn  = aws_sns_topic.lambda_errors[0].arn
    
    # Subscription details (if email is configured)
    email_subscription = var.error_notification_email != null ? {
      protocol = "email"
      endpoint = var.error_notification_email
    } : null
  } : null
}

#==============================================================================
# DASHBOARD
#==============================================================================

output "cloudwatch_dashboard" {
  description = "CloudWatch dashboard for Lambda monitoring (if enabled)"
  value = var.create_lambda_dashboard ? {
    dashboard_name = aws_cloudwatch_dashboard.lambda_dashboard[0].dashboard_name
    dashboard_arn  = aws_cloudwatch_dashboard.lambda_dashboard[0].dashboard_arn
  } : null
}

#==============================================================================
# LAMBDA INSIGHTS
#==============================================================================

output "lambda_insights" {
  description = "Lambda Insights configuration (if enabled)"
  value = var.enable_lambda_insights ? {
    layer_arn     = aws_lambda_layer_version.lambda_insights[0].arn
    layer_version = aws_lambda_layer_version.lambda_insights[0].version
    policy_arn    = aws_iam_policy.lambda_insights_policy[0].arn
  } : null
}

#==============================================================================
# SUMMARY INFORMATION
#==============================================================================

output "lambda_summary" {
  description = "Summary of all Lambda functions and their configurations"
  value = {
    # Basic information
    total_functions = 3
    runtime         = var.lambda_runtime
    architecture    = var.lambda_architecture
    
    # Function configurations
    functions = {
      ingestion = {
        memory_mb = var.lambda_config.ingestion.memory_size
        timeout_s = var.lambda_config.ingestion.timeout
        reserved_concurrency = var.lambda_config.ingestion.reserved_concurrency
      }
      processing = {
        memory_mb = var.lambda_config.processing.memory_size
        timeout_s = var.lambda_config.processing.timeout
        reserved_concurrency = var.lambda_config.processing.reserved_concurrency
      }
      validation = {
        memory_mb = var.lambda_config.validation.memory_size
        timeout_s = var.lambda_config.validation.timeout
        reserved_concurrency = var.lambda_config.validation.reserved_concurrency
      }
    }
    
    # Features enabled
    features = {
      xray_tracing           = var.enable_xray_tracing
      versioning            = var.enable_lambda_versioning
      provisioned_concurrency = var.enable_provisioned_concurrency
      lambda_insights       = var.enable_lambda_insights
      cloudwatch_alarms     = var.enable_cloudwatch_alarms
      error_notifications   = var.create_error_notification_topic
      scheduled_ingestion   = var.enable_scheduled_ingestion
      vpc_enabled           = var.vpc_config != null
    }
    
    # Integration points
    integrations = {
      s3_buckets = [
        var.raw_data_bucket_name,
        var.processed_data_bucket_name,
        var.athena_results_bucket_name
      ]
      dynamodb_table = var.dynamodb_table_name
      sns_topic     = var.sns_topic_arn
      eventbridge_scheduled = var.enable_scheduled_ingestion
    }
  }
}