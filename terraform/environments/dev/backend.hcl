# Backend configuration for Development environment
# Usage: terraform init -backend-config=backend.hcl

bucket         = "your-terraform-state-bucket-dev"
key            = "flight-data-pipeline/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-locks-dev"
encrypt        = true

# Optional: Use workspaces for multiple developers
# workspace_key_prefix = "dev-workspaces"