# GitHub Secrets Configuration Template

This document describes the GitHub secrets and environment variables that need to be configured for the Flight Data Pipeline CI/CD workflows.

## 🔐 Repository Secrets

Configure these secrets in your GitHub repository settings (`Settings` > `Secrets and variables` > `Actions`):

### AWS Configuration
```
AWS_ACCESS_KEY_ID
  Description: AWS Access Key ID for deployment
  Value: AKIA******************
  Used in: CI/CD workflows for AWS resource deployment

AWS_SECRET_ACCESS_KEY
  Description: AWS Secret Access Key for deployment
  Value: ****************************************
  Used in: CI/CD workflows for AWS resource deployment

TERRAFORM_STATE_BUCKET
  Description: S3 bucket name for storing Terraform state files
  Value: flightdata-terraform-state-prod
  Used in: Terraform initialization and state management
```

### External Service Credentials
```
OPENSKY_API_USERNAME
  Description: OpenSky Network API username
  Value: your-opensky-username
  Used in: Lambda functions for fetching flight data

OPENSKY_API_PASSWORD
  Description: OpenSky Network API password
  Value: your-opensky-password
  Used in: Lambda functions for fetching flight data
```

### Database Credentials
```
DATABASE_PASSWORD
  Description: Database password (if using RDS)
  Value: secure-database-password
  Used in: Database connections and migrations

DYNAMODB_ENCRYPTION_KEY
  Description: KMS key ID for DynamoDB encryption
  Value: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
  Used in: DynamoDB table encryption configuration
```

### Notification Configuration
```
SLACK_WEBHOOK_URL
  Description: Slack webhook URL for deployment notifications
  Value: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
  Used in: CI/CD workflow notifications

SONAR_TOKEN
  Description: SonarCloud token for code quality analysis
  Value: ****************************************
  Used in: Code quality scanning in CI pipeline
```

### Monitoring and Alerting
```
PAGERDUTY_INTEGRATION_KEY
  Description: PagerDuty integration key for critical alerts
  Value: ********************************
  Used in: Critical alert notifications

DATADOG_API_KEY
  Description: Datadog API key for monitoring (optional)
  Value: ********************************
  Used in: Performance monitoring and metrics
```

## 🌍 Environment-Specific Secrets

Configure these secrets for each environment in GitHub environment settings:

### Development Environment (`dev`)
```
AWS_ACCOUNT_ID_DEV
  Description: AWS Account ID for development environment
  Value: 123456789012

DEV_API_DOMAIN
  Description: Custom domain for development API
  Value: api-dev.flightdata-pipeline.com

DEV_CERTIFICATE_ARN
  Description: SSL certificate ARN for development domain
  Value: arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012
```

### Staging Environment (`staging`)
```
AWS_ACCOUNT_ID_STAGING
  Description: AWS Account ID for staging environment
  Value: 123456789013

STAGING_API_DOMAIN
  Description: Custom domain for staging API
  Value: api-staging.flightdata-pipeline.com

STAGING_CERTIFICATE_ARN
  Description: SSL certificate ARN for staging domain
  Value: arn:aws:acm:us-east-1:123456789013:certificate/12345678-1234-1234-1234-123456789013
```

### Production Environment (`production`)
```
AWS_ACCOUNT_ID_PROD
  Description: AWS Account ID for production environment
  Value: 123456789014

PROD_API_DOMAIN
  Description: Custom domain for production API
  Value: api.flightdata-pipeline.com

PROD_CERTIFICATE_ARN
  Description: SSL certificate ARN for production domain
  Value: arn:aws:acm:us-east-1:123456789014:certificate/12345678-1234-1234-1234-123456789014

PRODUCTION_APPROVAL_TEAM
  Description: GitHub team that can approve production deployments
  Value: @flightdata-pipeline/platform-team
```

## 📋 Environment Variables

These variables are configured directly in the workflow files but can be customized:

### CI Pipeline Variables
```yaml
env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '18'
  TERRAFORM_VERSION: '1.5.7'
  AWS_REGION: 'us-east-1'
```

### Deployment Pipeline Variables
```yaml
env:
  TERRAFORM_VERSION: '1.5.7'
  PYTHON_VERSION: '3.11'
  AWS_REGION: 'us-east-1'
```

## 🔧 Setting Up Secrets

### 1. Repository Secrets
Navigate to your repository on GitHub:
1. Go to `Settings` > `Secrets and variables` > `Actions`
2. Click `New repository secret`
3. Add each secret from the list above

### 2. Environment-Specific Secrets
For each environment (dev, staging, production):
1. Go to `Settings` > `Environments`
2. Create environment if it doesn't exist
3. Add environment-specific secrets
4. Configure protection rules (especially for production)

### 3. Environment Protection Rules

#### Development Environment
- No protection rules (automatic deployment)

#### Staging Environment
- Required reviewers: 1 person from development team
- Deployment branches: `main` branch only

#### Production Environment
- Required reviewers: 2 people from platform team
- Deployment branches: `main` branch only
- Wait timer: 5 minutes
- Prevent self-review

## 🛡️ Security Best Practices

### Secret Rotation
```yaml
# Recommended rotation schedule:
AWS_ACCESS_KEY_ID/SECRET: Every 90 days
OPENSKY_API_PASSWORD: Every 180 days
DATABASE_PASSWORD: Every 90 days
SLACK_WEBHOOK_URL: When compromised
SONAR_TOKEN: Every 365 days
```

### Access Control
```yaml
# Principle of least privilege:
- Use separate AWS accounts for each environment
- Create dedicated IAM users/roles for CI/CD
- Limit secret access to specific branches/environments
- Enable secret scanning and dependency alerts
```

### Monitoring
```yaml
# Track secret usage:
- Monitor AWS CloudTrail for API key usage
- Set up alerts for unusual access patterns  
- Regular audit of secret access logs
- Automated detection of secrets in code
```

## 🚀 Deployment Configuration

### Branch Protection Rules
Configure these branch protection rules:

#### `main` branch:
- Require pull request reviews (2 reviewers)
- Require status checks (CI pipeline must pass)
- Require branches to be up to date
- Restrict pushes to admins only
- Include administrators in restrictions

#### `develop` branch:
- Require pull request reviews (1 reviewer)
- Require status checks (CI pipeline must pass)
- Allow force pushes by admins

### Workflow Permissions
Ensure workflows have appropriate permissions:

```yaml
permissions:
  contents: read          # Read repository contents
  actions: read          # Read workflow status
  security-events: write # Upload security scan results
  pull-requests: write   # Comment on PRs
  issues: write         # Create issues for failures
  deployments: write    # Create deployment status
```

## 📞 Emergency Access

### Emergency Deployment
For emergency deployments bypassing normal approval:

1. Use `workflow_dispatch` with `force_deploy: true`
2. Emergency access requires 2FA verification
3. All emergency deployments are logged and audited
4. Post-incident review required within 24 hours

### Secret Recovery
If secrets are compromised:

1. Immediately revoke compromised credentials
2. Update secrets in GitHub
3. Rotate all related credentials
4. Review access logs for unauthorized usage
5. Update incident response documentation

## 🔍 Validation Checklist

Before deploying, verify:

- [ ] All required secrets are configured
- [ ] AWS credentials have appropriate permissions
- [ ] Environment-specific secrets match target environment
- [ ] SSL certificates are valid and not expiring soon
- [ ] Notification channels are working
- [ ] Branch protection rules are properly configured
- [ ] Team members have appropriate access levels

## 📚 Additional Resources

### AWS IAM Policies
The CI/CD user needs the following AWS permissions:
- Lambda: Create, update, invoke functions
- DynamoDB: Create, update, read tables
- S3: Create, read, write buckets
- IAM: Create, update roles (limited scope)
- CloudFormation: Full access to stack resources
- CloudWatch: Create, update alarms and log groups

### Terraform State Management
- State files are stored in S3 with versioning enabled
- DynamoDB table for state locking: `terraform-state-lock`
- Encryption at rest using AWS KMS
- Cross-region replication for disaster recovery

### Monitoring Integration
- CloudWatch alarms for deployment success/failure
- AWS Config rules for compliance monitoring
- CloudTrail logging for all API calls
- VPC Flow Logs for network monitoring

---

**Important**: Never commit secrets directly to the repository. Always use GitHub secrets or environment variables for sensitive information.