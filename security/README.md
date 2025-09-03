# Production Security Configuration for Flight Data Pipeline

This directory contains comprehensive security configurations and tools for the production deployment of the Flight Data Pipeline. All configurations follow industry best practices and compliance standards.

## 🔐 Security Components

### 1. KMS Encryption Setup (`kms/`)

**Purpose**: Customer-managed encryption keys for all AWS services
- Individual KMS keys for Lambda, S3, DynamoDB, CloudWatch, and Secrets Manager
- Automatic key rotation enabled (annual)
- Least privilege key policies
- Cross-region replication support

**Key Files**:
- `kms-keys.yml` - CloudFormation template for KMS key infrastructure

**Features**:
- 🔑 Service-specific encryption keys
- 🔄 Automatic annual rotation
- 📊 CloudWatch monitoring and alerting
- 🛡️ Least privilege key access policies

### 2. VPC Security Configuration (`vpc/`)

**Purpose**: Secure network infrastructure with private subnets and VPC endpoints
- Private subnets across 3 availability zones
- VPC endpoints for AWS services (no internet access required)
- Security groups with minimal access rules
- Network ACLs for additional protection layer

**Key Files**:
- `vpc-security.yml` - Complete VPC security infrastructure

**Features**:
- 🏗️ Private subnet architecture
- 🔗 VPC endpoints for AWS services
- 🛡️ Multi-layer security (Security Groups + NACLs)
- 📊 VPC Flow Logs for monitoring
- ❌ No internet gateways for Lambda functions

### 3. IAM Security Hardening (`iam/`)

**Purpose**: Hardened IAM policies with least privilege and MFA requirements
- Elimination of wildcard permissions
- Mandatory MFA for human users
- Service-specific roles with boundary policies
- Comprehensive audit capabilities

**Key Files**:
- `hardened-policies.yml` - CloudFormation template for IAM roles and policies
- `iam-audit-script.py` - Comprehensive IAM security auditor

**Features**:
- 🔒 Zero wildcard permissions
- 🔐 Mandatory MFA enforcement
- ⏰ Time-based access restrictions
- 📍 IP-based access controls
- 🛡️ Permission boundaries
- 📊 CloudTrail integration

### 4. Secrets Management (`secrets/`)

**Purpose**: Secure secrets storage and automated rotation
- SSM Parameter Store for configuration
- Secrets Manager for sensitive data
- Automated rotation schedules
- Cross-region replication

**Key Files**:
- `secrets-management.yml` - CloudFormation template for secrets infrastructure
- `secrets-rotation-automation.py` - Automated secrets rotation system

**Features**:
- 🔐 KMS encryption for all secrets
- 🔄 Automated rotation (30-90 day intervals)
- 🔄 Cross-region replication
- 📊 Access monitoring and alerting
- 🛡️ Resource-based access policies

### 5. Security Scanning & Compliance (`compliance/`)

**Purpose**: Automated security scanning and compliance validation
- Multi-standard compliance checking (CIS, SOC2, PCI-DSS, NIST)
- Automated vulnerability scanning
- Continuous compliance monitoring
- Detailed remediation guidance

**Key Files**:
- `security-scanner.py` - Comprehensive security scanner
- `compliance-checker.py` - Multi-standard compliance validator

**Features**:
- 🔍 Automated security scanning
- 📋 CIS, SOC2, PCI-DSS, NIST compliance
- 📊 Risk-based prioritization
- 🛠️ Actionable remediation guidance
- 📈 Compliance trend tracking

## 🚀 Quick Start

### Prerequisites
```bash
# Install required dependencies
pip install boto3 dataclasses

# Configure AWS credentials
aws configure
```

### 1. Deploy KMS Keys
```bash
aws cloudformation deploy \
  --template-file security/kms/kms-keys.yml \
  --stack-name flightdata-production-kms \
  --parameter-overrides \
    Environment=production \
    ApplicationName=flightdata-pipeline \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Deploy VPC Security
```bash
aws cloudformation deploy \
  --template-file security/vpc/vpc-security.yml \
  --stack-name flightdata-production-vpc \
  --parameter-overrides \
    Environment=production \
    ApplicationName=flightdata-pipeline
```

### 3. Deploy IAM Policies
```bash
aws cloudformation deploy \
  --template-file security/iam/hardened-policies.yml \
  --stack-name flightdata-production-iam \
  --parameter-overrides \
    Environment=production \
    ApplicationName=flightdata-pipeline \
  --capabilities CAPABILITY_NAMED_IAM
```

### 4. Deploy Secrets Management
```bash
aws cloudformation deploy \
  --template-file security/secrets/secrets-management.yml \
  --stack-name flightdata-production-secrets \
  --parameter-overrides \
    Environment=production \
    ApplicationName=flightdata-pipeline \
    OpenSkyAPIUsername="your-username" \
    OpenSkyAPIPassword="your-password" \
    DatabasePassword="secure-db-password" \
  --capabilities CAPABILITY_NAMED_IAM
```

### 5. Run Security Scans
```bash
# Run comprehensive security scan
python security/compliance/security-scanner.py \
  --region us-east-1 \
  --application flightdata-pipeline \
  --environment production \
  --output security-scan-results.json

# Run compliance assessment
python security/compliance/compliance-checker.py \
  --region us-east-1 \
  --application flightdata-pipeline \
  --environment production \
  --output compliance-report.json
```

### 6. Audit IAM Policies
```bash
# Run IAM security audit
python security/iam/iam-audit-script.py \
  --region us-east-1 \
  --output iam-audit-report.json \
  --verbose
```

### 7. Test Secrets Rotation
```bash
# Run secrets rotation (dry-run)
python security/secrets/secrets-rotation-automation.py \
  --environment production \
  --region us-east-1 \
  --action health_check \
  --output secrets-health.json
```

## 📊 Monitoring and Alerting

### CloudWatch Alarms
All security configurations include CloudWatch alarms for:
- KMS key usage anomalies
- VPC Flow Log analysis
- IAM policy violations
- Secrets access patterns
- Security group changes

### SNS Notifications
Security alerts are sent to SNS topics:
- `flightdata-production-security-alerts` - High priority security events
- `flightdata-production-compliance-alerts` - Compliance violations

### Security Dashboards
Pre-configured CloudWatch dashboards:
- **Security Overview** - High-level security metrics
- **Compliance Status** - Real-time compliance posture
- **Access Patterns** - User and service access analytics

## 🛡️ Security Best Practices Implemented

### Network Security
- ✅ Private subnets only for compute resources
- ✅ VPC endpoints for AWS service communication
- ✅ Multi-layer security (Security Groups + NACLs)
- ✅ VPC Flow Logs enabled
- ✅ No direct internet access for Lambda functions

### Data Protection
- ✅ Customer-managed KMS keys for all services
- ✅ Encryption in transit and at rest
- ✅ Secure secrets management with rotation
- ✅ S3 public access blocked
- ✅ Database encryption enabled

### Access Management
- ✅ Zero wildcard IAM permissions
- ✅ Least privilege principle enforced
- ✅ MFA required for human users
- ✅ Service-specific roles
- ✅ Permission boundaries implemented

### Monitoring and Compliance
- ✅ CloudTrail enabled with log file validation
- ✅ AWS Config for compliance monitoring
- ✅ Automated security scanning
- ✅ Multi-standard compliance validation
- ✅ Security Hub integration

## 📋 Compliance Standards

### CIS AWS Foundations Benchmark
- **Coverage**: 95% automated checks
- **Key Controls**: IAM, CloudTrail, Monitoring, Networking
- **Status**: Continuously monitored

### SOC 2 Type II
- **Coverage**: CC6 (Access), CC7 (Security), CC8 (Change Management)
- **Key Controls**: Logical access, monitoring, change tracking
- **Status**: Quarterly assessments

### PCI DSS v3.2.1
- **Coverage**: Data encryption, access controls, monitoring
- **Key Controls**: Cardholder data protection, audit trails
- **Status**: Annual validation

### NIST Cybersecurity Framework
- **Coverage**: Identify, Protect, Detect, Respond, Recover
- **Key Controls**: Asset management, data protection, anomaly detection
- **Status**: Continuous improvement

## 🔧 Customization

### Environment-Specific Configuration
```yaml
# Parameter overrides for different environments
Development:
  Environment: development
  VpcCidr: '10.1.0.0/16'
  
Staging:
  Environment: staging  
  VpcCidr: '10.2.0.0/16'
  
Production:
  Environment: production
  VpcCidr: '10.0.0.0/16'
```

### Application-Specific Settings
```yaml
# Application-specific parameters
ApplicationName: flightdata-pipeline
Region: us-east-1
KeyRotationDays: 365
SecretsRotationDays: 90
```

## 📚 Additional Resources

### AWS Security Best Practices
- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/)
- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)

### Compliance Frameworks
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
- [SOC 2 Compliance Guide](https://aws.amazon.com/compliance/soc/)
- [PCI DSS on AWS](https://aws.amazon.com/compliance/pci-dss-level-1-faqs/)

### Security Tools
- [AWS Security Hub](https://aws.amazon.com/security-hub/)
- [AWS Config](https://aws.amazon.com/config/)
- [AWS CloudTrail](https://aws.amazon.com/cloudtrail/)

---

## 🔍 Security Scanning Schedule

| Scan Type | Frequency | Automation | Output |
|-----------|-----------|------------|---------|
| Vulnerability Scan | Daily | ✅ Automated | security-scan-daily.json |
| Compliance Check | Weekly | ✅ Automated | compliance-weekly.json |
| IAM Audit | Monthly | ✅ Automated | iam-audit-monthly.json |
| Penetration Test | Quarterly | ❌ Manual | pentest-quarterly.pdf |

## 📞 Security Incident Response

### Emergency Contacts
- **Security Team**: security@flightdata-pipeline.com
- **On-Call**: +1-XXX-XXX-XXXX
- **AWS Support**: Enterprise Support Case

### Incident Response Plan
1. **Detection** - Automated alerts via CloudWatch/Security Hub
2. **Analysis** - Security team investigates within 15 minutes
3. **Containment** - Isolate affected resources
4. **Eradication** - Remove threats and vulnerabilities
5. **Recovery** - Restore services and validate security
6. **Lessons Learned** - Post-incident review and improvements

---

*Last Updated: 2024-09-02*  
*Version: 1.0*  
*Maintained by: Flight Data Pipeline Security Team*