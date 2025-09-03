# Backend configuration for Production environment
# Usage: terraform init -backend-config=backend.hcl

bucket         = "your-terraform-state-bucket-prod"
key            = "flight-data-pipeline/prod/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-locks-prod"
encrypt        = true

# Additional security for production state
# kms_key_id     = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"