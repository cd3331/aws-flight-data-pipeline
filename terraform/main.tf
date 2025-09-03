# Flight Data Pipeline - Main Terraform Configuration
# This file contains the core AWS provider configuration and data sources

# Configure Terraform backend for state management
terraform {
  # backend "s3" {
  #   # Backend configuration is provided via backend config files
  #   # or environment variables for each environment
  #   # 
  #   # Example backend configuration:
  #   # bucket         = "your-terraform-state-bucket"
  #   # key            = "flight-data-pipeline/terraform.tfstate"
  #   # region         = "us-east-1"
  #   # dynamodb_table = "terraform-state-locks"
  #   # encrypt        = true
  #   # 
  #   # Use: terraform init -backend-config=backend-dev.hcl
  # }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  # Use assume role if cross-account deployment is needed
  dynamic "assume_role" {
    for_each = var.assume_role_arn != null ? [1] : []
    content {
      role_arn     = var.assume_role_arn
      session_name = "TerraformFlightDataPipeline"
      external_id  = var.assume_role_external_id
    }
  }

  # Common tags applied to all resources
  default_tags {
    tags = local.common_tags
  }
}

# AWS Provider for us-east-1 (required for billing metrics)
provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"

  # Use assume role if cross-account deployment is needed
  dynamic "assume_role" {
    for_each = var.assume_role_arn != null ? [1] : []
    content {
      role_arn     = var.assume_role_arn
      session_name = "TerraformFlightDataPipeline"
      external_id  = var.assume_role_external_id
    }
  }

  # Common tags applied to all resources
  default_tags {
    tags = local.common_tags
  }
}

# Data source to get current AWS account information
data "aws_caller_identity" "current" {}

# Data source to get current AWS region
data "aws_region" "current" {}

# Data source to get available availability zones
data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "zone-type"
    values = ["availability-zone"]
  }
}

# Data source to get AWS partition (aws, aws-gov, aws-cn)
data "aws_partition" "current" {}

# Data source for EC2 instance types available in the region
data "aws_ec2_instance_types" "available" {
  filter {
    name   = "instance-type"
    values = ["t3.micro", "t3.small", "t3.medium"]
  }
}

# Random string for unique resource naming
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

# Random password for database if needed
resource "random_password" "db_password" {
  count   = var.create_rds_instance ? 1 : 0
  length  = 16
  special = true
}

# Local file for storing outputs (optional)
resource "local_file" "terraform_outputs" {
  count = var.create_output_file ? 1 : 0

  content = templatefile("${path.module}/templates/outputs.tpl", {
    aws_account_id = data.aws_caller_identity.current.account_id
    aws_region     = data.aws_region.current.name
    environment    = var.environment
    project_name   = var.project_name
    timestamp      = timestamp()
  })

  filename        = "${path.module}/outputs/${var.environment}-infrastructure.txt"
  file_permission = "0644"

  depends_on = [
    data.aws_caller_identity.current,
    data.aws_region.current
  ]
}