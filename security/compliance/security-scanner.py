#!/usr/bin/env python3
"""
Comprehensive Security Scanner and Compliance Checker
Performs automated security scanning across AWS resources
"""

import boto3
import json
import logging
import re
import socket
import ssl
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import argparse
import concurrent.futures
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SeverityLevel(Enum):
    """Security finding severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

@dataclass
class SecurityFinding:
    """Represents a security finding."""
    resource_id: str
    resource_type: str
    finding_type: str
    severity: SeverityLevel
    title: str
    description: str
    recommendation: str
    compliance_standards: List[str]
    region: str
    account_id: str
    timestamp: datetime

class SecurityScanner:
    """Comprehensive security scanner for AWS resources."""
    
    def __init__(self, region: str = 'us-east-1', application_name: str = 'flightdata-pipeline', environment: str = 'production'):
        self.region = region
        self.application_name = application_name
        self.environment = environment
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # AWS clients
        self.ec2 = boto3.client('ec2', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.iam = boto3.client('iam')
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.rds = boto3.client('rds', region_name=region)
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.config = boto3.client('config', region_name=region)
        self.guardduty = boto3.client('guardduty', region_name=region)
        self.securityhub = boto3.client('securityhub', region_name=region)
        self.kms = boto3.client('kms', region_name=region)
        self.secrets_manager = boto3.client('secretsmanager', region_name=region)
        
        self.findings: List[SecurityFinding] = []
    
    def scan_all_resources(self) -> Dict[str, Any]:
        """Perform comprehensive security scan."""
        logger.info("Starting comprehensive security scan")
        
        scan_results = {
            'scan_id': f"scan-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'account_id': self.account_id,
            'region': self.region,
            'application': self.application_name,
            'environment': self.environment,
            'findings': [],
            'summary': {},
            'compliance_status': {}
        }
        
        # Run all security checks
        scan_functions = [
            self.scan_vpc_security,
            self.scan_s3_security,
            self.scan_iam_security,
            self.scan_lambda_security,
            self.scan_rds_security,
            self.scan_kms_security,
            self.scan_secrets_security,
            self.scan_cloudtrail_security,
            self.scan_network_security,
            self.check_compliance_standards
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_function = {executor.submit(func): func.__name__ for func in scan_functions}
            
            for future in concurrent.futures.as_completed(future_to_function):
                func_name = future_to_function[future]
                try:
                    future.result()
                    logger.info(f"Completed {func_name}")
                except Exception as e:
                    logger.error(f"Error in {func_name}: {e}")
                    self._add_finding(
                        resource_id="scanner",
                        resource_type="system",
                        finding_type="scan_error",
                        severity=SeverityLevel.MEDIUM,
                        title=f"Scan Function Error: {func_name}",
                        description=f"Error during security scan: {str(e)}",
                        recommendation="Review scanner logs and fix the underlying issue",
                        compliance_standards=[]
                    )
        
        # Convert findings to serializable format
        scan_results['findings'] = [self._finding_to_dict(f) for f in self.findings]
        scan_results['summary'] = self._generate_scan_summary()
        scan_results['compliance_status'] = self._assess_compliance_status()
        
        return scan_results
    
    def scan_vpc_security(self) -> None:
        """Scan VPC security configurations."""
        logger.info("Scanning VPC security")
        
        try:
            # Get VPCs
            vpcs_response = self.ec2.describe_vpcs()
            
            for vpc in vpcs_response['Vpcs']:
                vpc_id = vpc['VpcId']
                
                # Check if VPC has flow logs enabled
                if not self._vpc_has_flow_logs(vpc_id):
                    self._add_finding(
                        resource_id=vpc_id,
                        resource_type="AWS::EC2::VPC",
                        finding_type="vpc_flow_logs_disabled",
                        severity=SeverityLevel.HIGH,
                        title="VPC Flow Logs Not Enabled",
                        description=f"VPC {vpc_id} does not have flow logs enabled for network monitoring",
                        recommendation="Enable VPC Flow Logs to monitor network traffic and detect anomalies",
                        compliance_standards=["CIS", "SOC2", "PCI-DSS"]
                    )
                
                # Check security groups
                self._scan_security_groups(vpc_id)
                
                # Check NACLs
                self._scan_network_acls(vpc_id)
                
                # Check route tables for suspicious routes
                self._scan_route_tables(vpc_id)
        
        except Exception as e:
            logger.error(f"Error scanning VPC security: {e}")
    
    def _vpc_has_flow_logs(self, vpc_id: str) -> bool:
        """Check if VPC has flow logs enabled."""
        try:
            flow_logs = self.ec2.describe_flow_logs(
                Filters=[
                    {'Name': 'resource-id', 'Values': [vpc_id]},
                    {'Name': 'resource-type', 'Values': ['VPC']}
                ]
            )
            return len(flow_logs['FlowLogs']) > 0
        except Exception:
            return False
    
    def _scan_security_groups(self, vpc_id: str) -> None:
        """Scan security groups for misconfigurations."""
        try:
            security_groups = self.ec2.describe_security_groups(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            for sg in security_groups['SecurityGroups']:
                sg_id = sg['GroupId']
                
                # Check for overly permissive inbound rules
                for rule in sg.get('IpPermissions', []):
                    if self._is_overly_permissive_rule(rule, 'inbound'):
                        self._add_finding(
                            resource_id=sg_id,
                            resource_type="AWS::EC2::SecurityGroup",
                            finding_type="overly_permissive_sg_rule",
                            severity=SeverityLevel.HIGH,
                            title="Overly Permissive Security Group Rule",
                            description=f"Security group {sg_id} has overly permissive inbound rules",
                            recommendation="Restrict security group rules to specific IP ranges and ports",
                            compliance_standards=["CIS", "AWS-Foundational"]
                        )
                
                # Check for overly permissive outbound rules
                for rule in sg.get('IpPermissionsEgress', []):
                    if self._is_overly_permissive_rule(rule, 'outbound'):
                        self._add_finding(
                            resource_id=sg_id,
                            resource_type="AWS::EC2::SecurityGroup",
                            finding_type="overly_permissive_sg_egress",
                            severity=SeverityLevel.MEDIUM,
                            title="Overly Permissive Egress Rule",
                            description=f"Security group {sg_id} has overly permissive outbound rules",
                            recommendation="Implement least privilege for outbound traffic",
                            compliance_standards=["CIS"]
                        )
        
        except Exception as e:
            logger.error(f"Error scanning security groups: {e}")
    
    def _is_overly_permissive_rule(self, rule: Dict[str, Any], direction: str) -> bool:
        """Check if a security group rule is overly permissive."""
        # Check for 0.0.0.0/0 access on sensitive ports
        sensitive_ports = [22, 3389, 1433, 3306, 5432, 6379]  # SSH, RDP, SQL Server, MySQL, PostgreSQL, Redis
        
        for ip_range in rule.get('IpRanges', []):
            if ip_range.get('CidrIp') == '0.0.0.0/0':
                # Check if it's on a sensitive port
                from_port = rule.get('FromPort', 0)
                to_port = rule.get('ToPort', 65535)
                
                for port in sensitive_ports:
                    if from_port <= port <= to_port:
                        return True
                
                # Check for full port range access
                if from_port == 0 and to_port == 65535:
                    return True
        
        return False
    
    def _scan_network_acls(self, vpc_id: str) -> None:
        """Scan Network ACLs for security issues."""
        try:
            nacls = self.ec2.describe_network_acls(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            for nacl in nacls['NetworkAcls']:
                nacl_id = nacl['NetworkAclId']
                
                # Check for overly permissive rules
                for entry in nacl.get('Entries', []):
                    if (entry.get('CidrBlock') == '0.0.0.0/0' and 
                        entry.get('RuleAction') == 'allow' and
                        not entry.get('Egress', False)):  # Inbound rule
                        
                        port_range = entry.get('PortRange', {})
                        if (port_range.get('From', 0) <= 22 <= port_range.get('To', 65535) or
                            port_range.get('From', 0) <= 3389 <= port_range.get('To', 65535)):
                            
                            self._add_finding(
                                resource_id=nacl_id,
                                resource_type="AWS::EC2::NetworkAcl",
                                finding_type="permissive_nacl_rule",
                                severity=SeverityLevel.HIGH,
                                title="Permissive Network ACL Rule",
                                description=f"Network ACL {nacl_id} allows unrestricted access to sensitive ports",
                                recommendation="Restrict Network ACL rules to specific IP ranges",
                                compliance_standards=["CIS"]
                            )
        
        except Exception as e:
            logger.error(f"Error scanning Network ACLs: {e}")
    
    def _scan_route_tables(self, vpc_id: str) -> None:
        """Scan route tables for security issues."""
        try:
            route_tables = self.ec2.describe_route_tables(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            for rt in route_tables['RouteTables']:
                rt_id = rt['RouteTableId']
                
                # Check for overly broad routes
                for route in rt.get('Routes', []):
                    if (route.get('DestinationCidrBlock') == '0.0.0.0/0' and
                        route.get('GatewayId', '').startswith('igw-')):
                        
                        # Check if this is attached to private subnets
                        for assoc in rt.get('Associations', []):
                            if assoc.get('SubnetId'):
                                subnet = self.ec2.describe_subnets(SubnetIds=[assoc['SubnetId']])
                                subnet_name = next((tag['Value'] for tag in subnet['Subnets'][0].get('Tags', []) if tag['Key'] == 'Name'), '')
                                
                                if 'private' in subnet_name.lower():
                                    self._add_finding(
                                        resource_id=rt_id,
                                        resource_type="AWS::EC2::RouteTable",
                                        finding_type="private_subnet_internet_route",
                                        severity=SeverityLevel.HIGH,
                                        title="Private Subnet with Internet Route",
                                        description=f"Route table {rt_id} attached to private subnet has internet gateway route",
                                        recommendation="Remove internet gateway routes from private subnets, use NAT gateway instead",
                                        compliance_standards=["CIS", "AWS-Foundational"]
                                    )
        
        except Exception as e:
            logger.error(f"Error scanning route tables: {e}")
    
    def scan_s3_security(self) -> None:
        """Scan S3 bucket security configurations."""
        logger.info("Scanning S3 security")
        
        try:
            buckets_response = self.s3.list_buckets()
            
            for bucket in buckets_response['Buckets']:
                bucket_name = bucket['Name']
                
                # Only scan buckets belonging to our application
                if not bucket_name.startswith(f"{self.application_name}-{self.environment}"):
                    continue
                
                # Check public access block
                self._check_s3_public_access(bucket_name)
                
                # Check bucket encryption
                self._check_s3_encryption(bucket_name)
                
                # Check bucket versioning
                self._check_s3_versioning(bucket_name)
                
                # Check bucket logging
                self._check_s3_logging(bucket_name)
                
                # Check bucket policy
                self._check_s3_bucket_policy(bucket_name)
                
                # Check SSL enforcement
                self._check_s3_ssl_enforcement(bucket_name)
        
        except Exception as e:
            logger.error(f"Error scanning S3 security: {e}")
    
    def _check_s3_public_access(self, bucket_name: str) -> None:
        """Check S3 bucket public access configuration."""
        try:
            public_access_block = self.s3.get_public_access_block(Bucket=bucket_name)
            config = public_access_block['PublicAccessBlockConfiguration']
            
            if not all([
                config.get('BlockPublicAcls', False),
                config.get('IgnorePublicAcls', False),
                config.get('BlockPublicPolicy', False),
                config.get('RestrictPublicBuckets', False)
            ]):
                self._add_finding(
                    resource_id=bucket_name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="s3_public_access_not_blocked",
                    severity=SeverityLevel.HIGH,
                    title="S3 Bucket Public Access Not Fully Blocked",
                    description=f"S3 bucket {bucket_name} does not have all public access blocked",
                    recommendation="Enable all public access block settings for the S3 bucket",
                    compliance_standards=["CIS", "AWS-Foundational", "PCI-DSS"]
                )
        
        except self.s3.exceptions.NoSuchPublicAccessBlockConfiguration:
            self._add_finding(
                resource_id=bucket_name,
                resource_type="AWS::S3::Bucket",
                finding_type="s3_no_public_access_block",
                severity=SeverityLevel.HIGH,
                title="S3 Bucket Missing Public Access Block",
                description=f"S3 bucket {bucket_name} does not have public access block configured",
                recommendation="Configure public access block for the S3 bucket",
                compliance_standards=["CIS", "AWS-Foundational"]
            )
        except Exception as e:
            logger.error(f"Error checking S3 public access for {bucket_name}: {e}")
    
    def _check_s3_encryption(self, bucket_name: str) -> None:
        """Check S3 bucket encryption configuration."""
        try:
            encryption = self.s3.get_bucket_encryption(Bucket=bucket_name)
            rules = encryption['ServerSideEncryptionConfiguration']['Rules']
            
            # Check if using KMS encryption
            kms_encrypted = False
            for rule in rules:
                sse_algorithm = rule['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']
                if sse_algorithm == 'aws:kms':
                    kms_encrypted = True
                    break
            
            if not kms_encrypted:
                self._add_finding(
                    resource_id=bucket_name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="s3_not_using_kms",
                    severity=SeverityLevel.MEDIUM,
                    title="S3 Bucket Not Using KMS Encryption",
                    description=f"S3 bucket {bucket_name} is not using KMS encryption",
                    recommendation="Configure S3 bucket to use KMS encryption with customer managed keys",
                    compliance_standards=["CIS", "SOC2"]
                )
        
        except self.s3.exceptions.NoSuchBucket:
            pass  # Skip if bucket doesn't exist
        except Exception:
            self._add_finding(
                resource_id=bucket_name,
                resource_type="AWS::S3::Bucket",
                finding_type="s3_no_encryption",
                severity=SeverityLevel.HIGH,
                title="S3 Bucket Encryption Not Configured",
                description=f"S3 bucket {bucket_name} does not have server-side encryption configured",
                recommendation="Enable server-side encryption with KMS for the S3 bucket",
                compliance_standards=["CIS", "AWS-Foundational", "PCI-DSS"]
            )
    
    def _check_s3_versioning(self, bucket_name: str) -> None:
        """Check S3 bucket versioning configuration."""
        try:
            versioning = self.s3.get_bucket_versioning(Bucket=bucket_name)
            
            if versioning.get('Status') != 'Enabled':
                self._add_finding(
                    resource_id=bucket_name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="s3_versioning_disabled",
                    severity=SeverityLevel.MEDIUM,
                    title="S3 Bucket Versioning Not Enabled",
                    description=f"S3 bucket {bucket_name} does not have versioning enabled",
                    recommendation="Enable versioning for the S3 bucket to protect against accidental deletion",
                    compliance_standards=["CIS"]
                )
        
        except Exception as e:
            logger.error(f"Error checking S3 versioning for {bucket_name}: {e}")
    
    def _check_s3_logging(self, bucket_name: str) -> None:
        """Check S3 bucket access logging configuration."""
        try:
            logging_config = self.s3.get_bucket_logging(Bucket=bucket_name)
            
            if 'LoggingEnabled' not in logging_config:
                self._add_finding(
                    resource_id=bucket_name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="s3_access_logging_disabled",
                    severity=SeverityLevel.LOW,
                    title="S3 Bucket Access Logging Not Enabled",
                    description=f"S3 bucket {bucket_name} does not have access logging enabled",
                    recommendation="Enable access logging for the S3 bucket for audit purposes",
                    compliance_standards=["CIS"]
                )
        
        except Exception as e:
            logger.error(f"Error checking S3 logging for {bucket_name}: {e}")
    
    def _check_s3_bucket_policy(self, bucket_name: str) -> None:
        """Check S3 bucket policy for security issues."""
        try:
            policy = self.s3.get_bucket_policy(Bucket=bucket_name)
            policy_doc = json.loads(policy['Policy'])
            
            # Check for overly permissive policies
            for statement in policy_doc.get('Statement', []):
                if (statement.get('Effect') == 'Allow' and 
                    statement.get('Principal') == '*'):
                    
                    self._add_finding(
                        resource_id=bucket_name,
                        resource_type="AWS::S3::Bucket",
                        finding_type="s3_overly_permissive_policy",
                        severity=SeverityLevel.HIGH,
                        title="S3 Bucket Policy Allows Public Access",
                        description=f"S3 bucket {bucket_name} has a policy that allows public access",
                        recommendation="Restrict bucket policy to specific principals and actions",
                        compliance_standards=["CIS", "AWS-Foundational"]
                    )
        
        except self.s3.exceptions.NoSuchBucketPolicy:
            pass  # No policy is fine
        except Exception as e:
            logger.error(f"Error checking S3 bucket policy for {bucket_name}: {e}")
    
    def _check_s3_ssl_enforcement(self, bucket_name: str) -> None:
        """Check if S3 bucket enforces SSL/TLS."""
        try:
            policy = self.s3.get_bucket_policy(Bucket=bucket_name)
            policy_doc = json.loads(policy['Policy'])
            
            # Check for SSL enforcement
            ssl_enforced = False
            for statement in policy_doc.get('Statement', []):
                if (statement.get('Effect') == 'Deny' and
                    'aws:SecureTransport' in str(statement.get('Condition', {}))):
                    ssl_enforced = True
                    break
            
            if not ssl_enforced:
                self._add_finding(
                    resource_id=bucket_name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="s3_ssl_not_enforced",
                    severity=SeverityLevel.MEDIUM,
                    title="S3 Bucket Does Not Enforce SSL/TLS",
                    description=f"S3 bucket {bucket_name} does not enforce SSL/TLS for requests",
                    recommendation="Add bucket policy to deny requests that are not made over SSL/TLS",
                    compliance_standards=["CIS", "PCI-DSS"]
                )
        
        except self.s3.exceptions.NoSuchBucketPolicy:
            self._add_finding(
                resource_id=bucket_name,
                resource_type="AWS::S3::Bucket",
                finding_type="s3_ssl_not_enforced",
                severity=SeverityLevel.MEDIUM,
                title="S3 Bucket Does Not Enforce SSL/TLS",
                description=f"S3 bucket {bucket_name} does not have a policy to enforce SSL/TLS",
                recommendation="Add bucket policy to deny requests that are not made over SSL/TLS",
                compliance_standards=["CIS", "PCI-DSS"]
            )
        except Exception as e:
            logger.error(f"Error checking S3 SSL enforcement for {bucket_name}: {e}")
    
    def scan_iam_security(self) -> None:
        """Scan IAM security configurations."""
        logger.info("Scanning IAM security")
        
        try:
            # Check password policy
            self._check_iam_password_policy()
            
            # Check for unused access keys
            self._check_unused_access_keys()
            
            # Check for overprivileged roles
            self._check_overprivileged_roles()
            
            # Check MFA compliance
            self._check_mfa_compliance()
            
            # Check for root access key usage
            self._check_root_access_keys()
        
        except Exception as e:
            logger.error(f"Error scanning IAM security: {e}")
    
    def _check_iam_password_policy(self) -> None:
        """Check IAM password policy compliance."""
        try:
            policy = self.iam.get_account_password_policy()['PasswordPolicy']
            
            issues = []
            
            if policy.get('MinimumPasswordLength', 0) < 14:
                issues.append("Minimum password length should be 14 characters")
            
            if not policy.get('RequireSymbols', False):
                issues.append("Password policy should require symbols")
            
            if not policy.get('RequireNumbers', False):
                issues.append("Password policy should require numbers")
            
            if not policy.get('RequireUppercaseCharacters', False):
                issues.append("Password policy should require uppercase characters")
            
            if not policy.get('RequireLowercaseCharacters', False):
                issues.append("Password policy should require lowercase characters")
            
            if policy.get('MaxPasswordAge', 0) > 90 or policy.get('MaxPasswordAge', 0) == 0:
                issues.append("Password should expire within 90 days")
            
            if issues:
                self._add_finding(
                    resource_id="account-password-policy",
                    resource_type="AWS::IAM::AccountPasswordPolicy",
                    finding_type="weak_password_policy",
                    severity=SeverityLevel.MEDIUM,
                    title="Weak IAM Password Policy",
                    description="Account password policy does not meet security best practices: " + "; ".join(issues),
                    recommendation="Strengthen password policy according to security best practices",
                    compliance_standards=["CIS", "SOC2"]
                )
        
        except self.iam.exceptions.NoSuchEntityException:
            self._add_finding(
                resource_id="account-password-policy",
                resource_type="AWS::IAM::AccountPasswordPolicy",
                finding_type="no_password_policy",
                severity=SeverityLevel.HIGH,
                title="No IAM Password Policy Configured",
                description="Account does not have an IAM password policy configured",
                recommendation="Create and configure an IAM password policy",
                compliance_standards=["CIS", "AWS-Foundational"]
            )
        except Exception as e:
            logger.error(f"Error checking password policy: {e}")
    
    def _check_unused_access_keys(self) -> None:
        """Check for unused access keys."""
        try:
            paginator = self.iam.get_paginator('list_users')
            
            for page in paginator.paginate():
                for user in page['Users']:
                    username = user['UserName']
                    
                    # Get access keys for user
                    keys = self.iam.list_access_keys(UserName=username)
                    
                    for key in keys['AccessKeyMetadata']:
                        key_id = key['AccessKeyId']
                        
                        # Check last used date
                        try:
                            last_used = self.iam.get_access_key_last_used(AccessKeyId=key_id)
                            last_used_date = last_used['AccessKeyLastUsed'].get('LastUsedDate')
                            
                            if last_used_date:
                                days_unused = (datetime.now(last_used_date.tzinfo) - last_used_date).days
                            else:
                                # Key has never been used
                                days_unused = (datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']).days
                            
                            if days_unused > 90:
                                self._add_finding(
                                    resource_id=key_id,
                                    resource_type="AWS::IAM::AccessKey",
                                    finding_type="unused_access_key",
                                    severity=SeverityLevel.MEDIUM,
                                    title="Unused Access Key",
                                    description=f"Access key {key_id} for user {username} has not been used for {days_unused} days",
                                    recommendation="Remove unused access keys to reduce security risk",
                                    compliance_standards=["CIS"]
                                )
                            
                            elif days_unused > 30:
                                key_age = (datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']).days
                                if key_age > 90:
                                    self._add_finding(
                                        resource_id=key_id,
                                        resource_type="AWS::IAM::AccessKey",
                                        finding_type="old_access_key",
                                        severity=SeverityLevel.LOW,
                                        title="Old Access Key",
                                        description=f"Access key {key_id} for user {username} is {key_age} days old",
                                        recommendation="Rotate access keys regularly (every 90 days)",
                                        compliance_standards=["CIS"]
                                    )
                        
                        except Exception as e:
                            logger.error(f"Error checking access key {key_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error checking unused access keys: {e}")
    
    def _check_overprivileged_roles(self) -> None:
        """Check for overprivileged IAM roles."""
        try:
            paginator = self.iam.get_paginator('list_roles')
            
            for page in paginator.paginate():
                for role in page['Roles']:
                    role_name = role['RoleName']
                    
                    # Skip service-linked roles
                    if role['Path'].startswith('/aws-service-role/'):
                        continue
                    
                    # Check attached policies
                    attached_policies = self.iam.list_attached_role_policies(RoleName=role_name)
                    
                    for policy in attached_policies['AttachedPolicies']:
                        if ('Admin' in policy['PolicyName'] or 
                            'FullAccess' in policy['PolicyName']):
                            
                            self._add_finding(
                                resource_id=role['Arn'],
                                resource_type="AWS::IAM::Role",
                                finding_type="overprivileged_role",
                                severity=SeverityLevel.HIGH,
                                title="Overprivileged IAM Role",
                                description=f"Role {role_name} has admin or full access policy attached: {policy['PolicyName']}",
                                recommendation="Implement least privilege principle by using more specific policies",
                                compliance_standards=["CIS", "AWS-Foundational"]
                            )
        
        except Exception as e:
            logger.error(f"Error checking overprivileged roles: {e}")
    
    def _check_mfa_compliance(self) -> None:
        """Check MFA compliance for users."""
        try:
            paginator = self.iam.get_paginator('list_users')
            
            for page in paginator.paginate():
                for user in page['Users']:
                    username = user['UserName']
                    
                    # Check if user has MFA device
                    mfa_devices = self.iam.list_mfa_devices(UserName=username)
                    
                    if len(mfa_devices['MFADevices']) == 0:
                        # Check if user has console access
                        try:
                            login_profile = self.iam.get_login_profile(UserName=username)
                            
                            self._add_finding(
                                resource_id=user['Arn'],
                                resource_type="AWS::IAM::User",
                                finding_type="user_without_mfa",
                                severity=SeverityLevel.HIGH,
                                title="User Without MFA",
                                description=f"User {username} has console access but no MFA device configured",
                                recommendation="Enable MFA for all users with console access",
                                compliance_standards=["CIS", "AWS-Foundational"]
                            )
                        
                        except self.iam.exceptions.NoSuchEntityException:
                            pass  # User doesn't have console access
        
        except Exception as e:
            logger.error(f"Error checking MFA compliance: {e}")
    
    def _check_root_access_keys(self) -> None:
        """Check for root account access keys."""
        try:
            # Get account summary
            summary = self.iam.get_account_summary()['SummaryMap']
            
            if summary.get('AccountAccessKeysPresent', 0) > 0:
                self._add_finding(
                    resource_id=f"arn:aws:iam::{self.account_id}:root",
                    resource_type="AWS::IAM::Root",
                    finding_type="root_access_keys_exist",
                    severity=SeverityLevel.CRITICAL,
                    title="Root Account Has Access Keys",
                    description="Root account has access keys configured",
                    recommendation="Remove root account access keys and use IAM users/roles instead",
                    compliance_standards=["CIS", "AWS-Foundational", "PCI-DSS"]
                )
        
        except Exception as e:
            logger.error(f"Error checking root access keys: {e}")
    
    def scan_lambda_security(self) -> None:
        """Scan Lambda function security configurations."""
        logger.info("Scanning Lambda security")
        
        try:
            paginator = self.lambda_client.get_paginator('list_functions')
            
            for page in paginator.paginate():
                for function in page['Functions']:
                    function_name = function['FunctionName']
                    
                    # Only scan our application's functions
                    if not function_name.startswith(f"{self.application_name}-{self.environment}"):
                        continue
                    
                    function_arn = function['FunctionArn']
                    
                    # Check if function is in VPC
                    if not function.get('VpcConfig', {}).get('VpcId'):
                        self._add_finding(
                            resource_id=function_arn,
                            resource_type="AWS::Lambda::Function",
                            finding_type="lambda_not_in_vpc",
                            severity=SeverityLevel.MEDIUM,
                            title="Lambda Function Not in VPC",
                            description=f"Lambda function {function_name} is not configured to run in a VPC",
                            recommendation="Configure Lambda function to run in a private VPC",
                            compliance_standards=["AWS-Foundational"]
                        )
                    
                    # Check environment variable encryption
                    if function.get('Environment', {}).get('Variables'):
                        kms_key_arn = function.get('KMSKeyArn')
                        if not kms_key_arn:
                            self._add_finding(
                                resource_id=function_arn,
                                resource_type="AWS::Lambda::Function",
                                finding_type="lambda_env_vars_not_encrypted",
                                severity=SeverityLevel.MEDIUM,
                                title="Lambda Environment Variables Not Encrypted",
                                description=f"Lambda function {function_name} has environment variables but they are not encrypted with KMS",
                                recommendation="Encrypt Lambda environment variables using KMS",
                                compliance_standards=["CIS"]
                            )
                    
                    # Check runtime version
                    runtime = function.get('Runtime', '')
                    if self._is_deprecated_runtime(runtime):
                        self._add_finding(
                            resource_id=function_arn,
                            resource_type="AWS::Lambda::Function",
                            finding_type="lambda_deprecated_runtime",
                            severity=SeverityLevel.MEDIUM,
                            title="Lambda Function Using Deprecated Runtime",
                            description=f"Lambda function {function_name} is using deprecated runtime: {runtime}",
                            recommendation="Update to a supported runtime version",
                            compliance_standards=["AWS-Foundational"]
                        )
        
        except Exception as e:
            logger.error(f"Error scanning Lambda security: {e}")
    
    def _is_deprecated_runtime(self, runtime: str) -> bool:
        """Check if Lambda runtime is deprecated."""
        deprecated_runtimes = [
            'python3.6', 'python3.7',
            'nodejs12.x', 'nodejs14.x',
            'dotnetcore3.1',
            'java8',
            'go1.x'
        ]
        return runtime in deprecated_runtimes
    
    def scan_rds_security(self) -> None:
        """Scan RDS security configurations."""
        logger.info("Scanning RDS security")
        
        try:
            paginator = self.rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    instance_id = instance['DBInstanceIdentifier']
                    instance_arn = instance['DBInstanceArn']
                    
                    # Check if instance is publicly accessible
                    if instance.get('PubliclyAccessible', False):
                        self._add_finding(
                            resource_id=instance_arn,
                            resource_type="AWS::RDS::DBInstance",
                            finding_type="rds_publicly_accessible",
                            severity=SeverityLevel.HIGH,
                            title="RDS Instance Publicly Accessible",
                            description=f"RDS instance {instance_id} is configured as publicly accessible",
                            recommendation="Configure RDS instance as not publicly accessible",
                            compliance_standards=["CIS", "AWS-Foundational"]
                        )
                    
                    # Check encryption at rest
                    if not instance.get('StorageEncrypted', False):
                        self._add_finding(
                            resource_id=instance_arn,
                            resource_type="AWS::RDS::DBInstance",
                            finding_type="rds_not_encrypted",
                            severity=SeverityLevel.HIGH,
                            title="RDS Instance Not Encrypted",
                            description=f"RDS instance {instance_id} does not have encryption at rest enabled",
                            recommendation="Enable encryption at rest for RDS instance",
                            compliance_standards=["CIS", "PCI-DSS"]
                        )
                    
                    # Check backup retention
                    backup_retention = instance.get('BackupRetentionPeriod', 0)
                    if backup_retention < 7:
                        self._add_finding(
                            resource_id=instance_arn,
                            resource_type="AWS::RDS::DBInstance",
                            finding_type="rds_insufficient_backup_retention",
                            severity=SeverityLevel.LOW,
                            title="Insufficient RDS Backup Retention",
                            description=f"RDS instance {instance_id} has backup retention of only {backup_retention} days",
                            recommendation="Configure backup retention for at least 7 days",
                            compliance_standards=["CIS"]
                        )
                    
                    # Check minor version upgrade
                    if not instance.get('AutoMinorVersionUpgrade', False):
                        self._add_finding(
                            resource_id=instance_arn,
                            resource_type="AWS::RDS::DBInstance",
                            finding_type="rds_no_auto_minor_version_upgrade",
                            severity=SeverityLevel.LOW,
                            title="RDS Auto Minor Version Upgrade Disabled",
                            description=f"RDS instance {instance_id} does not have auto minor version upgrade enabled",
                            recommendation="Enable auto minor version upgrade for security patches",
                            compliance_standards=["CIS"]
                        )
        
        except Exception as e:
            logger.error(f"Error scanning RDS security: {e}")
    
    def scan_kms_security(self) -> None:
        """Scan KMS key security configurations."""
        logger.info("Scanning KMS security")
        
        try:
            paginator = self.kms.get_paginator('list_keys')
            
            for page in paginator.paginate():
                for key in page['Keys']:
                    key_id = key['KeyId']
                    
                    try:
                        key_metadata = self.kms.describe_key(KeyId=key_id)['KeyMetadata']
                        
                        # Skip AWS managed keys
                        if key_metadata.get('KeyManager') == 'AWS':
                            continue
                        
                        key_arn = key_metadata['Arn']
                        
                        # Check key rotation
                        if not key_metadata.get('KeyRotationEnabled', False):
                            self._add_finding(
                                resource_id=key_arn,
                                resource_type="AWS::KMS::Key",
                                finding_type="kms_rotation_disabled",
                                severity=SeverityLevel.MEDIUM,
                                title="KMS Key Rotation Disabled",
                                description=f"KMS key {key_id} does not have automatic rotation enabled",
                                recommendation="Enable automatic key rotation for KMS keys",
                                compliance_standards=["CIS"]
                            )
                        
                        # Check key age
                        creation_date = key_metadata['CreationDate']
                        key_age_days = (datetime.now(creation_date.tzinfo) - creation_date).days
                        
                        if key_age_days > 365 and not key_metadata.get('KeyRotationEnabled', False):
                            self._add_finding(
                                resource_id=key_arn,
                                resource_type="AWS::KMS::Key",
                                finding_type="kms_key_old_without_rotation",
                                severity=SeverityLevel.MEDIUM,
                                title="Old KMS Key Without Rotation",
                                description=f"KMS key {key_id} is {key_age_days} days old and has no automatic rotation",
                                recommendation="Enable automatic key rotation or manually rotate the key",
                                compliance_standards=["CIS"]
                            )
                    
                    except Exception as e:
                        logger.error(f"Error checking KMS key {key_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning KMS security: {e}")
    
    def scan_secrets_security(self) -> None:
        """Scan Secrets Manager security configurations."""
        logger.info("Scanning Secrets Manager security")
        
        try:
            paginator = self.secrets_manager.get_paginator('list_secrets')
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    secret_name = secret['Name']
                    secret_arn = secret['ARN']
                    
                    # Only scan our application's secrets
                    if not secret_name.startswith(f"{self.application_name}/{self.environment}"):
                        continue
                    
                    # Check automatic rotation
                    if not secret.get('RotationEnabled', False):
                        self._add_finding(
                            resource_id=secret_arn,
                            resource_type="AWS::SecretsManager::Secret",
                            finding_type="secret_rotation_disabled",
                            severity=SeverityLevel.MEDIUM,
                            title="Secret Automatic Rotation Disabled",
                            description=f"Secret {secret_name} does not have automatic rotation enabled",
                            recommendation="Enable automatic rotation for secrets",
                            compliance_standards=["CIS"]
                        )
                    
                    # Check secret age
                    last_rotated = secret.get('LastRotatedDate')
                    if last_rotated:
                        days_since_rotation = (datetime.now(last_rotated.tzinfo) - last_rotated).days
                    else:
                        creation_date = secret['CreatedDate']
                        days_since_rotation = (datetime.now(creation_date.tzinfo) - creation_date).days
                    
                    if days_since_rotation > 90:
                        severity = SeverityLevel.HIGH if days_since_rotation > 365 else SeverityLevel.MEDIUM
                        self._add_finding(
                            resource_id=secret_arn,
                            resource_type="AWS::SecretsManager::Secret",
                            finding_type="secret_not_rotated_recently",
                            severity=severity,
                            title="Secret Not Rotated Recently",
                            description=f"Secret {secret_name} has not been rotated for {days_since_rotation} days",
                            recommendation="Rotate secrets regularly (every 90 days maximum)",
                            compliance_standards=["CIS"]
                        )
        
        except Exception as e:
            logger.error(f"Error scanning Secrets Manager security: {e}")
    
    def scan_cloudtrail_security(self) -> None:
        """Scan CloudTrail security configurations."""
        logger.info("Scanning CloudTrail security")
        
        try:
            trails = self.cloudtrail.describe_trails()['trailList']
            
            if not trails:
                self._add_finding(
                    resource_id=f"arn:aws:cloudtrail:{self.region}:{self.account_id}:trail/*",
                    resource_type="AWS::CloudTrail::Trail",
                    finding_type="no_cloudtrail_configured",
                    severity=SeverityLevel.HIGH,
                    title="No CloudTrail Configured",
                    description="No CloudTrail is configured for the account",
                    recommendation="Configure CloudTrail to log API activities",
                    compliance_standards=["CIS", "AWS-Foundational"]
                )
                return
            
            for trail in trails:
                trail_name = trail['Name']
                trail_arn = trail['TrailARN']
                
                # Check if trail is logging
                status = self.cloudtrail.get_trail_status(Name=trail_name)
                if not status.get('IsLogging', False):
                    self._add_finding(
                        resource_id=trail_arn,
                        resource_type="AWS::CloudTrail::Trail",
                        finding_type="cloudtrail_not_logging",
                        severity=SeverityLevel.HIGH,
                        title="CloudTrail Not Logging",
                        description=f"CloudTrail {trail_name} is not actively logging",
                        recommendation="Enable logging for CloudTrail",
                        compliance_standards=["CIS", "AWS-Foundational"]
                    )
                
                # Check log file validation
                if not trail.get('LogFileValidationEnabled', False):
                    self._add_finding(
                        resource_id=trail_arn,
                        resource_type="AWS::CloudTrail::Trail",
                        finding_type="cloudtrail_log_validation_disabled",
                        severity=SeverityLevel.MEDIUM,
                        title="CloudTrail Log File Validation Disabled",
                        description=f"CloudTrail {trail_name} does not have log file validation enabled",
                        recommendation="Enable log file validation for CloudTrail",
                        compliance_standards=["CIS"]
                    )
                
                # Check encryption
                if not trail.get('KMSKeyId'):
                    self._add_finding(
                        resource_id=trail_arn,
                        resource_type="AWS::CloudTrail::Trail",
                        finding_type="cloudtrail_not_encrypted",
                        severity=SeverityLevel.MEDIUM,
                        title="CloudTrail Logs Not Encrypted",
                        description=f"CloudTrail {trail_name} logs are not encrypted with KMS",
                        recommendation="Configure CloudTrail to encrypt logs with KMS",
                        compliance_standards=["CIS"]
                    )
        
        except Exception as e:
            logger.error(f"Error scanning CloudTrail security: {e}")
    
    def scan_network_security(self) -> None:
        """Scan network security configurations."""
        logger.info("Scanning network security")
        
        # This would include port scanning and SSL/TLS certificate checks
        # For demonstration, we'll add a placeholder
        # In a real implementation, you would scan for:
        # - Open ports on EC2 instances
        # - SSL/TLS certificate validity
        # - Network connectivity issues
        # - DNS configuration
        
        pass
    
    def check_compliance_standards(self) -> None:
        """Check compliance with security standards."""
        logger.info("Checking compliance standards")
        
        # This would implement checks for specific compliance frameworks
        # For demonstration, we'll add placeholder logic
        # In a real implementation, you would check:
        # - CIS Benchmarks
        # - SOC 2 controls
        # - PCI-DSS requirements
        # - AWS Config rules
        # - AWS Security Hub findings
        
        try:
            # Check if Security Hub is enabled
            self.securityhub.get_enabled_standards()
        except:
            self._add_finding(
                resource_id=f"arn:aws:securityhub:{self.region}:{self.account_id}:hub/default",
                resource_type="AWS::SecurityHub::Hub",
                finding_type="security_hub_not_enabled",
                severity=SeverityLevel.MEDIUM,
                title="AWS Security Hub Not Enabled",
                description="AWS Security Hub is not enabled in this region",
                recommendation="Enable AWS Security Hub for centralized security findings management",
                compliance_standards=["AWS-Foundational"]
            )
    
    def _add_finding(self, resource_id: str, resource_type: str, finding_type: str, 
                     severity: SeverityLevel, title: str, description: str, 
                     recommendation: str, compliance_standards: List[str]) -> None:
        """Add a security finding."""
        finding = SecurityFinding(
            resource_id=resource_id,
            resource_type=resource_type,
            finding_type=finding_type,
            severity=severity,
            title=title,
            description=description,
            recommendation=recommendation,
            compliance_standards=compliance_standards,
            region=self.region,
            account_id=self.account_id,
            timestamp=datetime.now()
        )
        self.findings.append(finding)
    
    def _finding_to_dict(self, finding: SecurityFinding) -> Dict[str, Any]:
        """Convert finding to dictionary."""
        return {
            'resource_id': finding.resource_id,
            'resource_type': finding.resource_type,
            'finding_type': finding.finding_type,
            'severity': finding.severity.value,
            'title': finding.title,
            'description': finding.description,
            'recommendation': finding.recommendation,
            'compliance_standards': finding.compliance_standards,
            'region': finding.region,
            'account_id': finding.account_id,
            'timestamp': finding.timestamp.isoformat()
        }
    
    def _generate_scan_summary(self) -> Dict[str, Any]:
        """Generate scan summary statistics."""
        severity_counts = {}
        for severity in SeverityLevel:
            severity_counts[severity.value] = sum(1 for f in self.findings if f.severity == severity)
        
        return {
            'total_findings': len(self.findings),
            'severity_breakdown': severity_counts,
            'resource_types_scanned': len(set(f.resource_type for f in self.findings)),
            'compliance_standards_covered': len(set(std for f in self.findings for std in f.compliance_standards))
        }
    
    def _assess_compliance_status(self) -> Dict[str, Any]:
        """Assess compliance status against standards."""
        compliance_status = {}
        
        # Group findings by compliance standard
        standard_findings = {}
        for finding in self.findings:
            for standard in finding.compliance_standards:
                if standard not in standard_findings:
                    standard_findings[standard] = []
                standard_findings[standard].append(finding)
        
        for standard, findings in standard_findings.items():
            critical_high = sum(1 for f in findings if f.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH])
            total = len(findings)
            
            if critical_high == 0:
                status = "COMPLIANT"
            elif critical_high <= total * 0.1:  # Less than 10% critical/high
                status = "MOSTLY_COMPLIANT"
            else:
                status = "NON_COMPLIANT"
            
            compliance_status[standard] = {
                'status': status,
                'total_findings': total,
                'critical_high_findings': critical_high,
                'compliance_percentage': ((total - critical_high) / total * 100) if total > 0 else 100
            }
        
        return compliance_status
    
    def export_findings(self, output_file: str, format: str = 'json') -> None:
        """Export findings to file."""
        scan_results = {
            'timestamp': datetime.now().isoformat(),
            'findings': [self._finding_to_dict(f) for f in self.findings],
            'summary': self._generate_scan_summary(),
            'compliance_status': self._assess_compliance_status()
        }
        
        if format.lower() == 'json':
            with open(output_file, 'w') as f:
                json.dump(scan_results, f, indent=2, default=str)
        
        logger.info(f"Security scan results exported to {output_file}")

def main():
    """Command-line interface for security scanner."""
    parser = argparse.ArgumentParser(description='Security Scanner and Compliance Checker')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--application', default='flightdata-pipeline', help='Application name')
    parser.add_argument('--environment', default='production', help='Environment')
    parser.add_argument('--output', default='security-scan-results.json', help='Output file')
    parser.add_argument('--format', default='json', choices=['json'], help='Output format')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize scanner
    scanner = SecurityScanner(
        region=args.region,
        application_name=args.application,
        environment=args.environment
    )
    
    # Run scan
    results = scanner.scan_all_resources()
    
    # Print summary
    summary = results['summary']
    print("\n" + "="*60)
    print("SECURITY SCAN SUMMARY")
    print("="*60)
    print(f"Account ID: {results['account_id']}")
    print(f"Region: {results['region']}")
    print(f"Application: {results['application']}")
    print(f"Environment: {results['environment']}")
    print(f"Scan Timestamp: {results['timestamp']}")
    print(f"\nTotal Findings: {summary['total_findings']}")
    print("\nSeverity Breakdown:")
    for severity, count in summary['severity_breakdown'].items():
        print(f"  {severity}: {count}")
    
    print(f"\nResource Types Scanned: {summary['resource_types_scanned']}")
    print(f"Compliance Standards: {summary['compliance_standards_covered']}")
    
    print("\nCompliance Status:")
    for standard, status in results['compliance_status'].items():
        print(f"  {standard}: {status['status']} ({status['compliance_percentage']:.1f}%)")
    
    print("="*60)
    
    # Export results
    scanner.export_findings(args.output, args.format)

if __name__ == '__main__':
    main()