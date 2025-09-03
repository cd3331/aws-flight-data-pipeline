# Terraform and provider version constraints
# This file should be the first to be read for version requirements

terraform {
  # Terraform version constraint
  required_version = ">= 1.5.0, < 2.0.0"

  # Required providers with version constraints
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      configuration_aliases = [aws.us-east-1]
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }

    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }

    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}