# Backend configuration for Staging environment
# Usage: terraform init -backend-config=backend.hcl

bucket         = "your-terraform-state-bucket-staging"
key            = "flight-data-pipeline/staging/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-locks-staging"
encrypt        = true