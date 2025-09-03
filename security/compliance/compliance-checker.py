#!/usr/bin/env python3
"""
Compliance Checker for Security Standards
Validates compliance against CIS, SOC2, PCI-DSS, and AWS Security Best Practices
"""

import boto3
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import argparse
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComplianceStandard(Enum):
    """Compliance standards."""
    CIS = "CIS_AWS_Foundations"
    SOC2 = "SOC2_Type2"
    PCI_DSS = "PCI_DSS_v3.2.1"
    AWS_FOUNDATIONAL = "AWS_Foundational_Security"
    NIST = "NIST_Cybersecurity_Framework"

class ComplianceStatus(Enum):
    """Compliance status levels."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

@dataclass
class ComplianceCheck:
    """Represents a compliance check result."""
    control_id: str
    control_title: str
    standard: ComplianceStandard
    status: ComplianceStatus
    description: str
    evidence: List[str]
    remediation: str
    risk_level: str
    automated: bool
    timestamp: datetime

class ComplianceChecker:
    """Comprehensive compliance checker for multiple security standards."""
    
    def __init__(self, region: str = 'us-east-1', application_name: str = 'flightdata-pipeline', environment: str = 'production'):
        self.region = region
        self.application_name = application_name
        self.environment = environment
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # AWS clients
        self.iam = boto3.client('iam')
        self.ec2 = boto3.client('ec2', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.config = boto3.client('config', region_name=region)
        self.kms = boto3.client('kms', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.rds = boto3.client('rds', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        
        self.checks: List[ComplianceCheck] = []
    
    def run_all_compliance_checks(self) -> Dict[str, Any]:
        """Run all compliance checks across standards."""
        logger.info("Starting comprehensive compliance assessment")
        
        compliance_report = {
            'assessment_id': f"compliance-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'account_id': self.account_id,
            'region': self.region,
            'application': self.application_name,
            'environment': self.environment,
            'standards_assessed': [std.value for std in ComplianceStandard],
            'checks': [],
            'summary': {},
            'recommendations': []
        }
        
        # Run checks for each standard
        self._run_cis_checks()
        self._run_soc2_checks()
        self._run_pci_dss_checks()
        self._run_aws_foundational_checks()
        self._run_nist_checks()
        
        # Convert checks to serializable format
        compliance_report['checks'] = [self._check_to_dict(check) for check in self.checks]
        compliance_report['summary'] = self._generate_compliance_summary()
        compliance_report['recommendations'] = self._generate_remediation_recommendations()
        
        return compliance_report
    
    def _run_cis_checks(self) -> None:
        """Run CIS AWS Foundations Benchmark checks."""
        logger.info("Running CIS AWS Foundations Benchmark checks")
        
        # CIS 1.1 - Maintain current contact details
        self._check_cis_1_1_contact_details()
        
        # CIS 1.2 - Ensure security contact information is provided
        self._check_cis_1_2_security_contact()
        
        # CIS 1.3 - Ensure security questions are registered
        self._check_cis_1_3_security_questions()
        
        # CIS 1.4 - Ensure no root account access key exists
        self._check_cis_1_4_root_access_keys()
        
        # CIS 1.5 - Ensure MFA is enabled for root account
        self._check_cis_1_5_root_mfa()
        
        # CIS 1.6 - Ensure hardware MFA is enabled for root account
        self._check_cis_1_6_root_hardware_mfa()
        
        # CIS 1.7 - Eliminate use of root account for administrative tasks
        self._check_cis_1_7_root_usage()
        
        # CIS 1.8 - Ensure IAM password policy requires minimum length of 14
        self._check_cis_1_8_password_length()
        
        # CIS 1.9 - Ensure IAM password policy prevents password reuse
        self._check_cis_1_9_password_reuse()
        
        # CIS 1.10 - Ensure multi-factor authentication (MFA) is enabled for all IAM users
        self._check_cis_1_10_user_mfa()
        
        # CIS 2.1 - Ensure CloudTrail is enabled in all regions
        self._check_cis_2_1_cloudtrail_all_regions()
        
        # CIS 2.2 - Ensure CloudTrail log file validation is enabled
        self._check_cis_2_2_cloudtrail_validation()
        
        # CIS 2.3 - Ensure the S3 bucket used to store CloudTrail logs is not publicly accessible
        self._check_cis_2_3_cloudtrail_bucket_access()
        
        # CIS 2.4 - Ensure CloudTrail trails are integrated with CloudWatch Logs
        self._check_cis_2_4_cloudtrail_cloudwatch()
        
        # CIS 2.5 - Ensure AWS Config is enabled in all regions
        self._check_cis_2_5_config_enabled()
        
        # CIS 2.6 - Ensure S3 bucket access logging is enabled
        self._check_cis_2_6_s3_access_logging()
        
        # CIS 2.7 - Ensure CloudTrail logs are encrypted at rest using KMS CMKs
        self._check_cis_2_7_cloudtrail_encryption()
        
        # CIS 3.1 - Ensure a log metric filter and alarm exist for unauthorized API calls
        self._check_cis_3_1_unauthorized_api_calls()
        
        # CIS 4.1 - Ensure no security groups allow ingress from 0.0.0.0/0 to port 22
        self._check_cis_4_1_ssh_access()
        
        # CIS 4.2 - Ensure no security groups allow ingress from 0.0.0.0/0 to port 3389
        self._check_cis_4_2_rdp_access()
        
        # CIS 4.3 - Ensure VPC flow logging is enabled in all VPCs
        self._check_cis_4_3_vpc_flow_logging()
    
    def _run_soc2_checks(self) -> None:
        """Run SOC 2 Type II compliance checks."""
        logger.info("Running SOC 2 Type II compliance checks")
        
        # CC6.1 - Logical and physical access controls
        self._check_soc2_cc6_1_access_controls()
        
        # CC6.2 - Authentication and authorization
        self._check_soc2_cc6_2_authentication()
        
        # CC6.3 - System access is removed when no longer required
        self._check_soc2_cc6_3_access_removal()
        
        # CC6.7 - Data transmission and disposal
        self._check_soc2_cc6_7_data_transmission()
        
        # CC6.8 - Configuration management
        self._check_soc2_cc6_8_configuration_management()
        
        # CC7.1 - Detect security events
        self._check_soc2_cc7_1_security_events()
        
        # CC7.2 - Monitor system components
        self._check_soc2_cc7_2_system_monitoring()
        
        # CC8.1 - Authorized changes
        self._check_soc2_cc8_1_change_management()
        
        # A1.2 - Availability monitoring
        self._check_soc2_a1_2_availability_monitoring()
        
        # P6.1 - Privacy data collection
        self._check_soc2_p6_1_data_collection()
    
    def _run_pci_dss_checks(self) -> None:
        """Run PCI DSS compliance checks."""
        logger.info("Running PCI DSS compliance checks")
        
        # PCI DSS 2.1 - Always change vendor-supplied defaults
        self._check_pci_dss_2_1_default_passwords()
        
        # PCI DSS 3.4 - Render cardholder data unreadable
        self._check_pci_dss_3_4_data_encryption()
        
        # PCI DSS 4.1 - Use strong cryptography and security protocols
        self._check_pci_dss_4_1_encryption_protocols()
        
        # PCI DSS 8.1 - Assign unique ID to each person with computer access
        self._check_pci_dss_8_1_unique_ids()
        
        # PCI DSS 8.2 - Implement proper user authentication management
        self._check_pci_dss_8_2_authentication_management()
        
        # PCI DSS 10.1 - Implement audit trails
        self._check_pci_dss_10_1_audit_trails()
        
        # PCI DSS 10.2 - Automated audit trails for all users
        self._check_pci_dss_10_2_automated_audit()
        
        # PCI DSS 11.4 - Use intrusion-detection and/or intrusion-prevention techniques
        self._check_pci_dss_11_4_intrusion_detection()
    
    def _run_aws_foundational_checks(self) -> None:
        """Run AWS Foundational Security Standard checks."""
        logger.info("Running AWS Foundational Security Standard checks")
        
        # [EC2.1] EBS snapshots should not be public
        self._check_aws_ec2_1_ebs_snapshots_public()
        
        # [EC2.2] VPC default security groups should prohibit inbound and outbound traffic
        self._check_aws_ec2_2_default_sg_traffic()
        
        # [IAM.1] IAM policies should not allow full "*" administrative privileges
        self._check_aws_iam_1_full_privileges()
        
        # [IAM.2] IAM users should not have IAM policies attached
        self._check_aws_iam_2_user_policies()
        
        # [IAM.3] IAM users' access keys should be rotated every 90 days or less
        self._check_aws_iam_3_access_key_rotation()
        
        # [S3.1] S3 Block Public Access setting should be enabled
        self._check_aws_s3_1_block_public_access()
        
        # [S3.2] S3 buckets should restrict public read access
        self._check_aws_s3_2_public_read_access()
        
        # [S3.3] S3 buckets should restrict public write access
        self._check_aws_s3_3_public_write_access()
        
        # [S3.4] S3 buckets should have server-side encryption enabled
        self._check_aws_s3_4_server_side_encryption()
    
    def _run_nist_checks(self) -> None:
        """Run NIST Cybersecurity Framework checks."""
        logger.info("Running NIST Cybersecurity Framework checks")
        
        # ID.AM-2 - Software platforms and applications are inventoried
        self._check_nist_id_am_2_inventory()
        
        # PR.AC-1 - Identities and credentials are issued, managed, and revoked
        self._check_nist_pr_ac_1_identity_management()
        
        # PR.AC-4 - Access permissions and authorizations are managed
        self._check_nist_pr_ac_4_access_permissions()
        
        # PR.DS-1 - Data-at-rest is protected
        self._check_nist_pr_ds_1_data_at_rest()
        
        # PR.DS-2 - Data-in-transit is protected
        self._check_nist_pr_ds_2_data_in_transit()
        
        # DE.AE-3 - Event data are collected and correlated
        self._check_nist_de_ae_3_event_data()
        
        # DE.CM-1 - Networks and network services are monitored
        self._check_nist_de_cm_1_network_monitoring()
        
        # RS.RP-1 - Response plan is executed during or after an incident
        self._check_nist_rs_rp_1_response_plan()
    
    # CIS Check Implementations
    
    def _check_cis_1_4_root_access_keys(self) -> None:
        """CIS 1.4 - Ensure no root account access key exists."""
        try:
            summary = self.iam.get_account_summary()['SummaryMap']
            root_access_keys = summary.get('AccountAccessKeysPresent', 0)
            
            status = ComplianceStatus.COMPLIANT if root_access_keys == 0 else ComplianceStatus.NON_COMPLIANT
            evidence = [f"Root access keys present: {root_access_keys}"]
            
            self._add_check(
                control_id="CIS-1.4",
                control_title="Ensure no root account access key exists",
                standard=ComplianceStandard.CIS,
                status=status,
                description="Root account should not have access keys to prevent unauthorized usage",
                evidence=evidence,
                remediation="Remove any existing root account access keys via AWS Console",
                risk_level="Critical",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("CIS-1.4", ComplianceStandard.CIS, str(e))
    
    def _check_cis_1_8_password_length(self) -> None:
        """CIS 1.8 - Ensure IAM password policy requires minimum length of 14."""
        try:
            try:
                policy = self.iam.get_account_password_policy()['PasswordPolicy']
                min_length = policy.get('MinimumPasswordLength', 0)
                
                status = ComplianceStatus.COMPLIANT if min_length >= 14 else ComplianceStatus.NON_COMPLIANT
                evidence = [f"Minimum password length: {min_length}"]
                
            except self.iam.exceptions.NoSuchEntityException:
                status = ComplianceStatus.NON_COMPLIANT
                evidence = ["No password policy configured"]
            
            self._add_check(
                control_id="CIS-1.8",
                control_title="Ensure IAM password policy requires minimum length of 14",
                standard=ComplianceStandard.CIS,
                status=status,
                description="Password policy should require minimum 14 character length",
                evidence=evidence,
                remediation="Set IAM password policy minimum length to 14 characters",
                risk_level="Medium",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("CIS-1.8", ComplianceStandard.CIS, str(e))
    
    def _check_cis_2_1_cloudtrail_all_regions(self) -> None:
        """CIS 2.1 - Ensure CloudTrail is enabled in all regions."""
        try:
            trails = self.cloudtrail.describe_trails()['trailList']
            multi_region_trails = [t for t in trails if t.get('IsMultiRegionTrail', False)]
            
            status = ComplianceStatus.COMPLIANT if multi_region_trails else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Total trails: {len(trails)}",
                f"Multi-region trails: {len(multi_region_trails)}"
            ]
            
            self._add_check(
                control_id="CIS-2.1",
                control_title="Ensure CloudTrail is enabled in all regions",
                standard=ComplianceStandard.CIS,
                status=status,
                description="CloudTrail should be enabled in all AWS regions for comprehensive logging",
                evidence=evidence,
                remediation="Configure CloudTrail with multi-region logging enabled",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("CIS-2.1", ComplianceStandard.CIS, str(e))
    
    def _check_cis_4_1_ssh_access(self) -> None:
        """CIS 4.1 - Ensure no security groups allow ingress from 0.0.0.0/0 to port 22."""
        try:
            security_groups = self.ec2.describe_security_groups()['SecurityGroups']
            violations = []
            
            for sg in security_groups:
                for rule in sg.get('IpPermissions', []):
                    # Check for SSH access from anywhere
                    if (rule.get('FromPort') == 22 and rule.get('ToPort') == 22):
                        for ip_range in rule.get('IpRanges', []):
                            if ip_range.get('CidrIp') == '0.0.0.0/0':
                                violations.append(sg['GroupId'])
                                break
            
            status = ComplianceStatus.COMPLIANT if not violations else ComplianceStatus.NON_COMPLIANT
            evidence = [f"Security groups with SSH access from 0.0.0.0/0: {len(violations)}"]
            if violations:
                evidence.append(f"Violating security groups: {', '.join(violations[:5])}")
            
            self._add_check(
                control_id="CIS-4.1",
                control_title="Ensure no security groups allow ingress from 0.0.0.0/0 to port 22",
                standard=ComplianceStandard.CIS,
                status=status,
                description="SSH access should not be allowed from the entire internet",
                evidence=evidence,
                remediation="Restrict SSH access to specific IP ranges or use bastion hosts",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("CIS-4.1", ComplianceStandard.CIS, str(e))
    
    # SOC 2 Check Implementations
    
    def _check_soc2_cc6_1_access_controls(self) -> None:
        """SOC 2 CC6.1 - Logical and physical access controls."""
        try:
            # Check IAM users have appropriate access controls
            users = self.iam.list_users()['Users']
            users_without_mfa = []
            
            for user in users:
                mfa_devices = self.iam.list_mfa_devices(UserName=user['UserName'])['MFADevices']
                if not mfa_devices:
                    # Check if user has console access
                    try:
                        self.iam.get_login_profile(UserName=user['UserName'])
                        users_without_mfa.append(user['UserName'])
                    except self.iam.exceptions.NoSuchEntityException:
                        pass  # User doesn't have console access
            
            status = ComplianceStatus.COMPLIANT if not users_without_mfa else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Total IAM users: {len(users)}",
                f"Users without MFA (with console access): {len(users_without_mfa)}"
            ]
            
            self._add_check(
                control_id="SOC2-CC6.1",
                control_title="Logical and physical access controls are implemented",
                standard=ComplianceStandard.SOC2,
                status=status,
                description="Access controls should be implemented to restrict logical access",
                evidence=evidence,
                remediation="Implement MFA for all users with console access",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("SOC2-CC6.1", ComplianceStandard.SOC2, str(e))
    
    def _check_soc2_cc7_1_security_events(self) -> None:
        """SOC 2 CC7.1 - System is designed to detect security events."""
        try:
            trails = self.cloudtrail.describe_trails()['trailList']
            active_trails = []
            
            for trail in trails:
                status = self.cloudtrail.get_trail_status(Name=trail['Name'])
                if status.get('IsLogging', False):
                    active_trails.append(trail['Name'])
            
            # Check if GuardDuty is enabled (this would require additional logic)
            # For now, we'll check CloudTrail as a basic security event detection
            
            status = ComplianceStatus.COMPLIANT if active_trails else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Total CloudTrail trails: {len(trails)}",
                f"Active logging trails: {len(active_trails)}"
            ]
            
            self._add_check(
                control_id="SOC2-CC7.1",
                control_title="System is designed to detect security events",
                standard=ComplianceStandard.SOC2,
                status=status,
                description="System should have mechanisms to detect security events",
                evidence=evidence,
                remediation="Enable CloudTrail logging and consider GuardDuty for threat detection",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("SOC2-CC7.1", ComplianceStandard.SOC2, str(e))
    
    # PCI DSS Check Implementations
    
    def _check_pci_dss_3_4_data_encryption(self) -> None:
        """PCI DSS 3.4 - Render cardholder data unreadable."""
        try:
            # Check S3 bucket encryption
            buckets = self.s3.list_buckets()['Buckets']
            unencrypted_buckets = []
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                # Only check application buckets
                if bucket_name.startswith(f"{self.application_name}-{self.environment}"):
                    try:
                        self.s3.get_bucket_encryption(Bucket=bucket_name)
                    except:
                        unencrypted_buckets.append(bucket_name)
            
            status = ComplianceStatus.COMPLIANT if not unencrypted_buckets else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Application S3 buckets: {len([b for b in buckets if b['Name'].startswith(f'{self.application_name}-{self.environment}')])}", 
                f"Unencrypted buckets: {len(unencrypted_buckets)}"
            ]
            
            self._add_check(
                control_id="PCI-DSS-3.4",
                control_title="Render cardholder data unreadable",
                standard=ComplianceStandard.PCI_DSS,
                status=status,
                description="Cardholder data must be rendered unreadable through encryption",
                evidence=evidence,
                remediation="Enable encryption for all S3 buckets storing sensitive data",
                risk_level="Critical",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("PCI-DSS-3.4", ComplianceStandard.PCI_DSS, str(e))
    
    def _check_pci_dss_10_1_audit_trails(self) -> None:
        """PCI DSS 10.1 - Implement audit trails."""
        try:
            trails = self.cloudtrail.describe_trails()['trailList']
            trails_with_validation = [t for t in trails if t.get('LogFileValidationEnabled', False)]
            
            status = ComplianceStatus.COMPLIANT if trails_with_validation else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"CloudTrail trails: {len(trails)}",
                f"Trails with log file validation: {len(trails_with_validation)}"
            ]
            
            self._add_check(
                control_id="PCI-DSS-10.1",
                control_title="Implement audit trails",
                standard=ComplianceStandard.PCI_DSS,
                status=status,
                description="Audit trails must be implemented to track access to network resources and cardholder data",
                evidence=evidence,
                remediation="Enable CloudTrail with log file validation for comprehensive audit trails",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("PCI-DSS-10.1", ComplianceStandard.PCI_DSS, str(e))
    
    # AWS Foundational Security Standard Implementations
    
    def _check_aws_s3_1_block_public_access(self) -> None:
        """AWS S3.1 - S3 Block Public Access setting should be enabled."""
        try:
            buckets = self.s3.list_buckets()['Buckets']
            non_compliant_buckets = []
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                # Only check application buckets
                if bucket_name.startswith(f"{self.application_name}-{self.environment}"):
                    try:
                        public_access_block = self.s3.get_public_access_block(Bucket=bucket_name)
                        config = public_access_block['PublicAccessBlockConfiguration']
                        
                        if not all([
                            config.get('BlockPublicAcls', False),
                            config.get('IgnorePublicAcls', False),
                            config.get('BlockPublicPolicy', False),
                            config.get('RestrictPublicBuckets', False)
                        ]):
                            non_compliant_buckets.append(bucket_name)
                    except:
                        non_compliant_buckets.append(bucket_name)
            
            status = ComplianceStatus.COMPLIANT if not non_compliant_buckets else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Application S3 buckets: {len([b for b in buckets if b['Name'].startswith(f'{self.application_name}-{self.environment}')])}", 
                f"Non-compliant buckets: {len(non_compliant_buckets)}"
            ]
            
            self._add_check(
                control_id="AWS-S3.1",
                control_title="S3 Block Public Access setting should be enabled",
                standard=ComplianceStandard.AWS_FOUNDATIONAL,
                status=status,
                description="S3 buckets should have block public access settings enabled",
                evidence=evidence,
                remediation="Enable all block public access settings for S3 buckets",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("AWS-S3.1", ComplianceStandard.AWS_FOUNDATIONAL, str(e))
    
    def _check_aws_iam_3_access_key_rotation(self) -> None:
        """AWS IAM.3 - IAM users' access keys should be rotated every 90 days or less."""
        try:
            users = self.iam.list_users()['Users']
            old_keys = []
            
            for user in users:
                keys = self.iam.list_access_keys(UserName=user['UserName'])['AccessKeyMetadata']
                for key in keys:
                    age_days = (datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']).days
                    if age_days > 90:
                        old_keys.append({
                            'user': user['UserName'],
                            'key_id': key['AccessKeyId'],
                            'age_days': age_days
                        })
            
            status = ComplianceStatus.COMPLIANT if not old_keys else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"Total users: {len(users)}",
                f"Keys older than 90 days: {len(old_keys)}"
            ]
            
            self._add_check(
                control_id="AWS-IAM.3",
                control_title="IAM users' access keys should be rotated every 90 days or less",
                standard=ComplianceStandard.AWS_FOUNDATIONAL,
                status=status,
                description="Access keys should be rotated regularly to reduce security risk",
                evidence=evidence,
                remediation="Implement access key rotation policy and rotate old keys",
                risk_level="Medium",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("AWS-IAM.3", ComplianceStandard.AWS_FOUNDATIONAL, str(e))
    
    # NIST Cybersecurity Framework Implementations
    
    def _check_nist_pr_ds_1_data_at_rest(self) -> None:
        """NIST PR.DS-1 - Data-at-rest is protected."""
        try:
            # Check S3 encryption
            buckets = self.s3.list_buckets()['Buckets']
            encrypted_buckets = 0
            total_app_buckets = 0
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                if bucket_name.startswith(f"{self.application_name}-{self.environment}"):
                    total_app_buckets += 1
                    try:
                        self.s3.get_bucket_encryption(Bucket=bucket_name)
                        encrypted_buckets += 1
                    except:
                        pass
            
            # Check RDS encryption
            rds_instances = self.rds.describe_db_instances()['DBInstances']
            encrypted_rds = sum(1 for db in rds_instances if db.get('StorageEncrypted', False))
            
            s3_compliant = encrypted_buckets == total_app_buckets if total_app_buckets > 0 else True
            rds_compliant = encrypted_rds == len(rds_instances) if rds_instances else True
            
            status = ComplianceStatus.COMPLIANT if s3_compliant and rds_compliant else ComplianceStatus.NON_COMPLIANT
            evidence = [
                f"S3 buckets encrypted: {encrypted_buckets}/{total_app_buckets}",
                f"RDS instances encrypted: {encrypted_rds}/{len(rds_instances)}"
            ]
            
            self._add_check(
                control_id="NIST-PR.DS-1",
                control_title="Data-at-rest is protected",
                standard=ComplianceStandard.NIST,
                status=status,
                description="Data at rest should be protected through encryption",
                evidence=evidence,
                remediation="Enable encryption for all data storage services (S3, RDS, EBS)",
                risk_level="High",
                automated=True
            )
            
        except Exception as e:
            self._add_check_error("NIST-PR.DS-1", ComplianceStandard.NIST, str(e))
    
    # Helper methods for checks that require manual verification
    
    def _check_cis_1_1_contact_details(self) -> None:
        """CIS 1.1 - Manual check for contact details."""
        self._add_check(
            control_id="CIS-1.1",
            control_title="Maintain current contact details",
            standard=ComplianceStandard.CIS,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description="Account contact details should be current and accurate",
            evidence=["Manual verification required"],
            remediation="Verify and update account contact details in AWS Console",
            risk_level="Low",
            automated=False
        )
    
    def _check_cis_1_2_security_contact(self) -> None:
        """CIS 1.2 - Manual check for security contact."""
        self._add_check(
            control_id="CIS-1.2",
            control_title="Ensure security contact information is provided",
            standard=ComplianceStandard.CIS,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description="Security contact information should be provided to AWS",
            evidence=["Manual verification required"],
            remediation="Configure security contact information in AWS Console",
            risk_level="Low",
            automated=False
        )
    
    def _check_cis_1_3_security_questions(self) -> None:
        """CIS 1.3 - Manual check for security questions."""
        self._add_check(
            control_id="CIS-1.3",
            control_title="Ensure security questions are registered",
            standard=ComplianceStandard.CIS,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description="Security questions should be registered for account recovery",
            evidence=["Manual verification required"],
            remediation="Configure security questions in AWS Console",
            risk_level="Medium",
            automated=False
        )
    
    def _check_cis_1_5_root_mfa(self) -> None:
        """CIS 1.5 - Manual check for root MFA."""
        self._add_check(
            control_id="CIS-1.5",
            control_title="Ensure MFA is enabled for root account",
            standard=ComplianceStandard.CIS,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description="Multi-factor authentication should be enabled for root account",
            evidence=["Manual verification required"],
            remediation="Enable MFA for root account via AWS Console",
            risk_level="Critical",
            automated=False
        )
    
    def _check_cis_1_6_root_hardware_mfa(self) -> None:
        """CIS 1.6 - Manual check for root hardware MFA."""
        self._add_check(
            control_id="CIS-1.6",
            control_title="Ensure hardware MFA is enabled for root account",
            standard=ComplianceStandard.CIS,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description="Hardware MFA device should be used for root account",
            evidence=["Manual verification required"],
            remediation="Configure hardware MFA device for root account",
            risk_level="Critical",
            automated=False
        )
    
    def _check_cis_1_7_root_usage(self) -> None:
        """CIS 1.7 - Check root account usage."""
        try:
            # This would require CloudTrail log analysis
            # For now, marking as insufficient data
            self._add_check(
                control_id="CIS-1.7",
                control_title="Eliminate use of root account for administrative tasks",
                standard=ComplianceStandard.CIS,
                status=ComplianceStatus.INSUFFICIENT_DATA,
                description="Root account should not be used for day-to-day administrative tasks",
                evidence=["CloudTrail log analysis required"],
                remediation="Use IAM users/roles for administrative tasks, avoid root account usage",
                risk_level="High",
                automated=False
            )
        except Exception as e:
            self._add_check_error("CIS-1.7", ComplianceStandard.CIS, str(e))
    
    def _add_check_for_remaining_controls(self):
        """Add placeholder checks for remaining controls."""
        remaining_checks = [
            ("CIS-1.9", "password reuse prevention"),
            ("CIS-1.10", "user MFA compliance"),
            ("CIS-2.2", "CloudTrail log validation"),
            ("CIS-2.3", "CloudTrail bucket access"),
            ("CIS-2.4", "CloudTrail CloudWatch integration"),
            ("CIS-2.5", "Config service enabled"),
            ("CIS-2.6", "S3 access logging"),
            ("CIS-2.7", "CloudTrail encryption"),
            ("CIS-3.1", "unauthorized API calls monitoring"),
            ("CIS-4.2", "RDP access restriction"),
            ("CIS-4.3", "VPC flow logging"),
        ]
        
        for control_id, description in remaining_checks:
            if not any(check.control_id == control_id for check in self.checks):
                self._add_check(
                    control_id=control_id,
                    control_title=f"Check for {description}",
                    standard=ComplianceStandard.CIS,
                    status=ComplianceStatus.INSUFFICIENT_DATA,
                    description=f"Automated check for {description} not yet implemented",
                    evidence=["Implementation pending"],
                    remediation="Implement automated check for this control",
                    risk_level="Medium",
                    automated=False
                )
    
    def _add_check(self, control_id: str, control_title: str, standard: ComplianceStandard, 
                   status: ComplianceStatus, description: str, evidence: List[str], 
                   remediation: str, risk_level: str, automated: bool) -> None:
        """Add a compliance check result."""
        check = ComplianceCheck(
            control_id=control_id,
            control_title=control_title,
            standard=standard,
            status=status,
            description=description,
            evidence=evidence,
            remediation=remediation,
            risk_level=risk_level,
            automated=automated,
            timestamp=datetime.now()
        )
        self.checks.append(check)
    
    def _add_check_error(self, control_id: str, standard: ComplianceStandard, error: str) -> None:
        """Add an error result for a compliance check."""
        self._add_check(
            control_id=control_id,
            control_title=f"Error in {control_id}",
            standard=standard,
            status=ComplianceStatus.INSUFFICIENT_DATA,
            description=f"Error occurred during compliance check: {error}",
            evidence=[f"Error: {error}"],
            remediation="Review and fix the compliance check implementation",
            risk_level="Unknown",
            automated=True
        )
    
    def _check_to_dict(self, check: ComplianceCheck) -> Dict[str, Any]:
        """Convert compliance check to dictionary."""
        return {
            'control_id': check.control_id,
            'control_title': check.control_title,
            'standard': check.standard.value,
            'status': check.status.value,
            'description': check.description,
            'evidence': check.evidence,
            'remediation': check.remediation,
            'risk_level': check.risk_level,
            'automated': check.automated,
            'timestamp': check.timestamp.isoformat()
        }
    
    def _generate_compliance_summary(self) -> Dict[str, Any]:
        """Generate compliance summary across all standards."""
        summary = {
            'total_checks': len(self.checks),
            'by_standard': {},
            'by_status': {},
            'by_risk_level': {},
            'automation_coverage': 0
        }
        
        # Group by standard
        for standard in ComplianceStandard:
            standard_checks = [c for c in self.checks if c.standard == standard]
            
            status_counts = {}
            for status in ComplianceStatus:
                status_counts[status.value] = sum(1 for c in standard_checks if c.status == status)
            
            summary['by_standard'][standard.value] = {
                'total_checks': len(standard_checks),
                'status_breakdown': status_counts,
                'compliance_percentage': (status_counts.get('COMPLIANT', 0) / len(standard_checks) * 100) if standard_checks else 0
            }
        
        # Group by status
        for status in ComplianceStatus:
            summary['by_status'][status.value] = sum(1 for c in self.checks if c.status == status)
        
        # Group by risk level
        risk_levels = set(c.risk_level for c in self.checks)
        for risk in risk_levels:
            summary['by_risk_level'][risk] = sum(1 for c in self.checks if c.risk_level == risk)
        
        # Automation coverage
        automated_checks = sum(1 for c in self.checks if c.automated)
        summary['automation_coverage'] = (automated_checks / len(self.checks) * 100) if self.checks else 0
        
        return summary
    
    def _generate_remediation_recommendations(self) -> List[Dict[str, Any]]:
        """Generate prioritized remediation recommendations."""
        # Get non-compliant checks
        non_compliant = [c for c in self.checks if c.status == ComplianceStatus.NON_COMPLIANT]
        
        # Sort by risk level priority
        risk_priority = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        non_compliant.sort(key=lambda x: risk_priority.get(x.risk_level, 4))
        
        recommendations = []
        for check in non_compliant[:10]:  # Top 10 priorities
            recommendations.append({
                'control_id': check.control_id,
                'control_title': check.control_title,
                'standard': check.standard.value,
                'risk_level': check.risk_level,
                'remediation': check.remediation,
                'priority_score': risk_priority.get(check.risk_level, 4)
            })
        
        return recommendations
    
    def export_compliance_report(self, output_file: str) -> None:
        """Export compliance report to file."""
        report = self.run_all_compliance_checks()
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Compliance report exported to {output_file}")

def main():
    """Command-line interface for compliance checker."""
    parser = argparse.ArgumentParser(description='Compliance Checker for Security Standards')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--application', default='flightdata-pipeline', help='Application name')
    parser.add_argument('--environment', default='production', help='Environment')
    parser.add_argument('--output', default='compliance-report.json', help='Output file')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize compliance checker
    checker = ComplianceChecker(
        region=args.region,
        application_name=args.application,
        environment=args.environment
    )
    
    # Run compliance assessment
    results = checker.run_all_compliance_checks()
    
    # Print summary
    summary = results['summary']
    print("\n" + "="*70)
    print("COMPLIANCE ASSESSMENT SUMMARY")
    print("="*70)
    print(f"Account ID: {results['account_id']}")
    print(f"Region: {results['region']}")
    print(f"Application: {results['application']}")
    print(f"Environment: {results['environment']}")
    print(f"Assessment Timestamp: {results['timestamp']}")
    print(f"\nTotal Compliance Checks: {summary['total_checks']}")
    print(f"Automation Coverage: {summary['automation_coverage']:.1f}%")
    
    print(f"\nOverall Status Breakdown:")
    for status, count in summary['by_status'].items():
        print(f"  {status}: {count}")
    
    print(f"\nCompliance by Standard:")
    for standard, data in summary['by_standard'].items():
        print(f"  {standard}: {data['compliance_percentage']:.1f}% ({data['status_breakdown']['COMPLIANT']}/{data['total_checks']})")
    
    print(f"\nTop Priority Remediations:")
    for i, rec in enumerate(results['recommendations'][:5], 1):
        print(f"  {i}. [{rec['risk_level']}] {rec['control_id']}: {rec['control_title']}")
    
    print("="*70)
    
    # Export report
    checker.export_compliance_report(args.output)

if __name__ == '__main__':
    main()