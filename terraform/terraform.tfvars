environment = "dev"
alert_email = "chandra.r.dunn@gmail.com"
project_name = "flight-data-pipeline"
aws_region = "us-east-1"
lambda_architecture = "x86_64"

budget_config = {
  monthly_limit = 50
  warning_threshold = 0.5
  critical_threshold = 0.8
  forecast_threshold = 1.0
  enable_service_budgets = false
  service_limits = {
    lambda = 10
    s3 = 10
    dynamodb = 10
  }
}

notification_config = {
  alert_emails = ["chandra.r.dunn@gmail.com"]
  critical_alert_emails = ["chandra.r.dunn@gmail.com"]
  budget_emails = ["chandra.r.dunn@gmail.com"]
  enable_sms = false
  sms_numbers = []
  enable_slack = false
  slack_webhook_url = ""
}

cost_optimization = {
  use_intelligent_tiering = true
  use_transfer_acceleration = false
  enable_requester_pays = false
  enable_spot_instances = false
  enable_auto_scaling = true
  auto_shutdown_schedule = ""
  disable_detailed_monitoring = true
  enable_glacier_transitions = true
  enable_intelligent_tiering = true
  enable_provisioned_concurrency = false
  environment_auto_shutdown = false
  reduce_log_retention = true
  use_arm_architecture = false
}

monitoring_config = {
  enable_synthetic_monitoring = false
  enable_enhanced_monitoring = false
  log_retention_days = 7
  enable_detailed_monitoring = false
  enable_insights = false
  create_log_insights_queries = false
  cost_threshold_usd = 50
  create_dashboard = true
  dashboard_widgets = []
  enable_cost_monitoring = true
  enable_custom_metrics = false
  enable_log_insights = false
}
