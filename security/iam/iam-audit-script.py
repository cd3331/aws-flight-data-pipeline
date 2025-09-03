#!/usr/bin/env python3
"""
IAM Policy Audit Script for Flight Data Pipeline
Identifies security vulnerabilities and policy violations
"""

import boto3
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IAMAuditor:
    """Comprehensive IAM security auditor."""
    
    def __init__(self, region: str = 'us-east-1'):
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        self.region = region
        
    def audit_all_policies(self) -> Dict[str, Any]:
        """Perform comprehensive IAM audit."""
        logger.info("Starting comprehensive IAM audit")
        
        audit_results = {
            'timestamp': datetime.now().isoformat(),
            'account_id': self._get_account_id(),
            'wildcard_violations': self._check_wildcard_permissions(),
            'overprivileged_roles': self._check_overprivileged_roles(),
            'inactive_users': self._check_inactive_users(),
            'mfa_violations': self._check_mfa_requirements(),
            'password_policy': self._check_password_policy(),
            'access_key_rotation': self._check_access_key_rotation(),
            'unused_roles': self._check_unused_roles(),
            'cross_account_roles': self._check_cross_account_roles(),
            'service_linked_roles': self._audit_service_linked_roles(),
            'policy_versions': self._check_policy_versions(),
            'assume_role_policies': self._audit_assume_role_policies(),
            'summary': {}
        }
        
        # Generate summary
        audit_results['summary'] = self._generate_summary(audit_results)
        
        return audit_results
    
    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        try:
            return self.sts.get_caller_identity()['Account']
        except Exception as e:
            logger.error(f"Failed to get account ID: {e}")
            return 'unknown'
    
    def _check_wildcard_permissions(self) -> List[Dict[str, Any]]:
        """Check for dangerous wildcard permissions."""
        logger.info("Checking for wildcard permissions")
        violations = []
        
        try:
            # Check managed policies
            paginator = self.iam.get_paginator('list_policies')
            for page in paginator.paginate(Scope='Local'):
                for policy in page['Policies']:
                    violations.extend(self._analyze_policy_wildcards(policy))
            
            # Check inline policies for roles
            roles_paginator = self.iam.get_paginator('list_roles')
            for page in roles_paginator.paginate():
                for role in page['Roles']:
                    violations.extend(self._analyze_role_inline_policies(role))
        
        except Exception as e:
            logger.error(f"Error checking wildcard permissions: {e}")
        
        return violations
    
    def _analyze_policy_wildcards(self, policy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze a single policy for wildcard violations."""
        violations = []
        
        try:
            policy_version = self.iam.get_policy_version(
                PolicyArn=policy['Arn'],
                VersionId=policy['DefaultVersionId']
            )
            
            policy_doc = policy_version['PolicyVersion']['Document']
            violations.extend(self._scan_policy_document(policy_doc, policy['Arn'], 'managed'))
            
        except Exception as e:
            logger.error(f"Error analyzing policy {policy.get('Arn', 'unknown')}: {e}")
        
        return violations
    
    def _analyze_role_inline_policies(self, role: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze inline policies for a role."""
        violations = []
        
        try:
            inline_policies = self.iam.list_role_policies(RoleName=role['RoleName'])
            
            for policy_name in inline_policies['PolicyNames']:
                policy = self.iam.get_role_policy(
                    RoleName=role['RoleName'],
                    PolicyName=policy_name
                )
                
                violations.extend(self._scan_policy_document(
                    policy['PolicyDocument'],
                    f"{role['Arn']}/{policy_name}",
                    'inline'
                ))
                
        except Exception as e:
            logger.error(f"Error analyzing inline policies for role {role.get('RoleName', 'unknown')}: {e}")
        
        return violations
    
    def _scan_policy_document(self, policy_doc: Dict[str, Any], policy_identifier: str, policy_type: str) -> List[Dict[str, Any]]:
        """Scan policy document for security issues."""
        violations = []
        
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        for i, statement in enumerate(statements):
            # Check for wildcard resources with sensitive actions
            if statement.get('Effect') == 'Allow':
                resources = statement.get('Resource', [])
                actions = statement.get('Action', [])
                
                if not isinstance(resources, list):
                    resources = [resources]
                if not isinstance(actions, list):
                    actions = [actions]
                
                # Check for dangerous wildcards
                if '*' in resources:
                    dangerous_actions = self._get_dangerous_actions(actions)
                    if dangerous_actions:
                        violations.append({
                            'policy_identifier': policy_identifier,
                            'policy_type': policy_type,
                            'statement_index': i,
                            'severity': 'HIGH',
                            'issue': 'Wildcard resource with dangerous actions',
                            'dangerous_actions': dangerous_actions,
                            'recommendation': 'Replace wildcard with specific resource ARNs'
                        })
                
                # Check for admin-level wildcards
                if '*' in actions and '*' in resources:
                    violations.append({
                        'policy_identifier': policy_identifier,
                        'policy_type': policy_type,
                        'statement_index': i,
                        'severity': 'CRITICAL',
                        'issue': 'Full admin access with wildcard action and resource',
                        'recommendation': 'Implement least privilege with specific actions and resources'
                    })
        
        return violations
    
    def _get_dangerous_actions(self, actions: List[str]) -> List[str]:
        """Identify dangerous actions that shouldn't use wildcard resources."""
        dangerous_patterns = [
            r'iam:.*',
            r'sts:AssumeRole',
            r'kms:(Delete|Disable|Put|Create|Update).*',
            r'ec2:(Create|Delete|Modify|Replace).*',
            r'cloudtrail:(Stop|Delete|Update).*',
            r's3:(Delete|Put).*Policy',
            r'rds:(Delete|Modify).*',
            r'lambda:(Delete|Update)FunctionConfiguration'
        ]
        
        dangerous_actions = []
        for action in actions:
            for pattern in dangerous_patterns:
                if re.match(pattern, action):
                    dangerous_actions.append(action)
        
        return dangerous_actions
    
    def _check_overprivileged_roles(self) -> List[Dict[str, Any]]:
        """Check for overprivileged roles."""
        logger.info("Checking for overprivileged roles")
        overprivileged = []
        
        try:
            paginator = self.iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page['Roles']:
                    privileges = self._analyze_role_privileges(role)
                    if privileges['risk_score'] >= 8:  # High risk threshold
                        overprivileged.append({
                            'role_name': role['RoleName'],
                            'role_arn': role['Arn'],
                            'risk_score': privileges['risk_score'],
                            'risk_factors': privileges['risk_factors'],
                            'last_used': role.get('RoleLastUsed', {}).get('LastUsedDate'),
                            'recommendation': self._get_privilege_recommendation(privileges)
                        })
        
        except Exception as e:
            logger.error(f"Error checking overprivileged roles: {e}")
        
        return overprivileged
    
    def _analyze_role_privileges(self, role: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze role privileges and calculate risk score."""
        risk_score = 0
        risk_factors = []
        
        try:
            # Check attached managed policies
            attached_policies = self.iam.list_attached_role_policies(RoleName=role['RoleName'])
            for policy in attached_policies['AttachedPolicies']:
                if 'Admin' in policy['PolicyName'] or 'FullAccess' in policy['PolicyName']:
                    risk_score += 5
                    risk_factors.append(f"Attached admin policy: {policy['PolicyName']}")
                elif 'PowerUser' in policy['PolicyName']:
                    risk_score += 3
                    risk_factors.append(f"Attached power user policy: {policy['PolicyName']}")
            
            # Check inline policies
            inline_policies = self.iam.list_role_policies(RoleName=role['RoleName'])
            if len(inline_policies['PolicyNames']) > 5:
                risk_score += 2
                risk_factors.append(f"Many inline policies: {len(inline_policies['PolicyNames'])}")
            
            # Check assume role policy
            assume_role_doc = role['AssumeRolePolicyDocument']
            if self._has_broad_assume_policy(assume_role_doc):
                risk_score += 3
                risk_factors.append("Broad assume role policy")
        
        except Exception as e:
            logger.error(f"Error analyzing role privileges for {role.get('RoleName', 'unknown')}: {e}")
        
        return {
            'risk_score': risk_score,
            'risk_factors': risk_factors
        }
    
    def _has_broad_assume_policy(self, assume_role_doc: Dict[str, Any]) -> bool:
        """Check if assume role policy is too broad."""
        statements = assume_role_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                principal = statement.get('Principal', {})
                if isinstance(principal, str) and principal == '*':
                    return True
                if isinstance(principal, dict):
                    aws_principal = principal.get('AWS')
                    if aws_principal == '*':
                        return True
        
        return False
    
    def _check_inactive_users(self) -> List[Dict[str, Any]]:
        """Check for inactive IAM users."""
        logger.info("Checking for inactive users")
        inactive_users = []
        cutoff_date = datetime.now() - timedelta(days=90)
        
        try:
            paginator = self.iam.get_paginator('list_users')
            for page in paginator.paginate():
                for user in page['Users']:
                    last_activity = self._get_user_last_activity(user['UserName'])
                    if last_activity and last_activity < cutoff_date:
                        inactive_users.append({
                            'username': user['UserName'],
                            'user_arn': user['Arn'],
                            'last_activity': last_activity.isoformat(),
                            'days_inactive': (datetime.now() - last_activity).days,
                            'has_access_keys': self._user_has_access_keys(user['UserName']),
                            'has_mfa': self._user_has_mfa(user['UserName']),
                            'recommendation': 'Consider disabling or removing inactive user'
                        })
        
        except Exception as e:
            logger.error(f"Error checking inactive users: {e}")
        
        return inactive_users
    
    def _get_user_last_activity(self, username: str) -> Optional[datetime]:
        """Get user's last activity date."""
        try:
            user = self.iam.get_user(UserName=username)
            return user['User'].get('PasswordLastUsed')
        except Exception:
            return None
    
    def _user_has_access_keys(self, username: str) -> bool:
        """Check if user has access keys."""
        try:
            keys = self.iam.list_access_keys(UserName=username)
            return len(keys['AccessKeyMetadata']) > 0
        except Exception:
            return False
    
    def _user_has_mfa(self, username: str) -> bool:
        """Check if user has MFA enabled."""
        try:
            mfa_devices = self.iam.list_mfa_devices(UserName=username)
            return len(mfa_devices['MFADevices']) > 0
        except Exception:
            return False
    
    def _check_mfa_requirements(self) -> Dict[str, Any]:
        """Check MFA compliance."""
        logger.info("Checking MFA requirements")
        mfa_report = {
            'users_without_mfa': [],
            'roles_without_mfa_requirement': [],
            'compliance_percentage': 0
        }
        
        try:
            # Check users
            paginator = self.iam.get_paginator('list_users')
            total_users = 0
            users_with_mfa = 0
            
            for page in paginator.paginate():
                for user in page['Users']:
                    total_users += 1
                    if self._user_has_mfa(user['UserName']):
                        users_with_mfa += 1
                    else:
                        mfa_report['users_without_mfa'].append({
                            'username': user['UserName'],
                            'user_arn': user['Arn'],
                            'last_login': user.get('PasswordLastUsed'),
                            'has_access_keys': self._user_has_access_keys(user['UserName'])
                        })
            
            if total_users > 0:
                mfa_report['compliance_percentage'] = (users_with_mfa / total_users) * 100
            
            # Check roles for MFA requirements in assume role policies
            roles_paginator = self.iam.get_paginator('list_roles')
            for page in roles_paginator.paginate():
                for role in page['Roles']:
                    if not self._role_requires_mfa(role):
                        mfa_report['roles_without_mfa_requirement'].append({
                            'role_name': role['RoleName'],
                            'role_arn': role['Arn'],
                            'service_role': self._is_service_role(role),
                            'recommendation': 'Add MFA requirement to assume role policy for human users'
                        })
        
        except Exception as e:
            logger.error(f"Error checking MFA requirements: {e}")
        
        return mfa_report
    
    def _role_requires_mfa(self, role: Dict[str, Any]) -> bool:
        """Check if role requires MFA for assumption."""
        assume_role_doc = role['AssumeRolePolicyDocument']
        statements = assume_role_doc.get('Statement', [])
        
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                condition = statement.get('Condition', {})
                # Check for MFA condition
                bool_condition = condition.get('Bool', {})
                if bool_condition.get('aws:MultiFactorAuthPresent') == 'true':
                    return True
        
        return False
    
    def _is_service_role(self, role: Dict[str, Any]) -> bool:
        """Check if role is assumed by AWS services."""
        assume_role_doc = role['AssumeRolePolicyDocument']
        statements = assume_role_doc.get('Statement', [])
        
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                principal = statement.get('Principal', {})
                if isinstance(principal, dict) and 'Service' in principal:
                    return True
        
        return False
    
    def _check_password_policy(self) -> Dict[str, Any]:
        """Check account password policy compliance."""
        logger.info("Checking password policy")
        
        try:
            policy = self.iam.get_account_password_policy()['PasswordPolicy']
            
            compliance = {
                'exists': True,
                'minimum_length': policy.get('MinimumPasswordLength', 0),
                'require_symbols': policy.get('RequireSymbols', False),
                'require_numbers': policy.get('RequireNumbers', False),
                'require_uppercase': policy.get('RequireUppercaseCharacters', False),
                'require_lowercase': policy.get('RequireLowercaseCharacters', False),
                'max_age': policy.get('MaxPasswordAge', 0),
                'password_reuse_prevention': policy.get('PasswordReusePrevention', 0),
                'hard_expiry': policy.get('HardExpiry', False),
                'recommendations': []
            }
            
            # Check against best practices
            if compliance['minimum_length'] < 14:
                compliance['recommendations'].append('Increase minimum password length to 14 characters')
            
            if not all([
                compliance['require_symbols'],
                compliance['require_numbers'],
                compliance['require_uppercase'],
                compliance['require_lowercase']
            ]):
                compliance['recommendations'].append('Require all character types (symbols, numbers, upper/lowercase)')
            
            if compliance['max_age'] == 0 or compliance['max_age'] > 90:
                compliance['recommendations'].append('Set password expiration to 90 days or less')
            
            if compliance['password_reuse_prevention'] < 5:
                compliance['recommendations'].append('Prevent reuse of last 5 passwords')
            
        except self.iam.exceptions.NoSuchEntityException:
            compliance = {
                'exists': False,
                'recommendations': ['Create and configure account password policy']
            }
        except Exception as e:
            logger.error(f"Error checking password policy: {e}")
            compliance = {'error': str(e)}
        
        return compliance
    
    def _check_access_key_rotation(self) -> List[Dict[str, Any]]:
        """Check for old access keys that need rotation."""
        logger.info("Checking access key rotation")
        old_keys = []
        cutoff_date = datetime.now() - timedelta(days=90)
        
        try:
            paginator = self.iam.get_paginator('list_users')
            for page in paginator.paginate():
                for user in page['Users']:
                    keys = self.iam.list_access_keys(UserName=user['UserName'])
                    for key in keys['AccessKeyMetadata']:
                        if key['CreateDate'].replace(tzinfo=None) < cutoff_date:
                            last_used = self._get_access_key_last_used(key['AccessKeyId'])
                            old_keys.append({
                                'username': user['UserName'],
                                'access_key_id': key['AccessKeyId'],
                                'age_days': (datetime.now() - key['CreateDate'].replace(tzinfo=None)).days,
                                'status': key['Status'],
                                'last_used': last_used.isoformat() if last_used else 'Never',
                                'recommendation': 'Rotate access key'
                            })
        
        except Exception as e:
            logger.error(f"Error checking access key rotation: {e}")
        
        return old_keys
    
    def _get_access_key_last_used(self, access_key_id: str) -> Optional[datetime]:
        """Get last used date for access key."""
        try:
            response = self.iam.get_access_key_last_used(AccessKeyId=access_key_id)
            return response['AccessKeyLastUsed'].get('LastUsedDate')
        except Exception:
            return None
    
    def _check_unused_roles(self) -> List[Dict[str, Any]]:
        """Check for unused roles."""
        logger.info("Checking for unused roles")
        unused_roles = []
        cutoff_date = datetime.now() - timedelta(days=60)
        
        try:
            paginator = self.iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page['Roles']:
                    last_used = role.get('RoleLastUsed', {}).get('LastUsedDate')
                    
                    if last_used:
                        if last_used.replace(tzinfo=None) < cutoff_date:
                            unused_roles.append({
                                'role_name': role['RoleName'],
                                'role_arn': role['Arn'],
                                'last_used': last_used.isoformat(),
                                'days_unused': (datetime.now() - last_used.replace(tzinfo=None)).days,
                                'service_role': self._is_service_role(role),
                                'recommendation': 'Consider removing if truly unused'
                            })
                    else:
                        # Role has never been used
                        creation_date = role['CreateDate'].replace(tzinfo=None)
                        if creation_date < cutoff_date:
                            unused_roles.append({
                                'role_name': role['RoleName'],
                                'role_arn': role['Arn'],
                                'last_used': 'Never',
                                'days_since_creation': (datetime.now() - creation_date).days,
                                'service_role': self._is_service_role(role),
                                'recommendation': 'Consider removing if not needed'
                            })
        
        except Exception as e:
            logger.error(f"Error checking unused roles: {e}")
        
        return unused_roles
    
    def _check_cross_account_roles(self) -> List[Dict[str, Any]]:
        """Check cross-account role assumptions."""
        logger.info("Checking cross-account roles")
        cross_account_roles = []
        current_account = self._get_account_id()
        
        try:
            paginator = self.iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page['Roles']:
                    assume_role_doc = role['AssumeRolePolicyDocument']
                    statements = assume_role_doc.get('Statement', [])
                    
                    if not isinstance(statements, list):
                        statements = [statements]
                    
                    for statement in statements:
                        if statement.get('Effect') == 'Allow':
                            principal = statement.get('Principal', {})
                            
                            if isinstance(principal, dict) and 'AWS' in principal:
                                aws_principals = principal['AWS']
                                if isinstance(aws_principals, str):
                                    aws_principals = [aws_principals]
                                
                                for aws_principal in aws_principals:
                                    if ':' in aws_principal and current_account not in aws_principal:
                                        external_id = statement.get('Condition', {}).get('StringEquals', {}).get('sts:ExternalId')
                                        
                                        cross_account_roles.append({
                                            'role_name': role['RoleName'],
                                            'role_arn': role['Arn'],
                                            'external_principal': aws_principal,
                                            'has_external_id': bool(external_id),
                                            'has_mfa_requirement': self._role_requires_mfa(role),
                                            'recommendation': 'Verify external account access is still needed and properly secured'
                                        })
        
        except Exception as e:
            logger.error(f"Error checking cross-account roles: {e}")
        
        return cross_account_roles
    
    def _audit_service_linked_roles(self) -> List[Dict[str, Any]]:
        """Audit service-linked roles."""
        logger.info("Auditing service-linked roles")
        service_roles = []
        
        try:
            paginator = self.iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page['Roles']:
                    if '/aws-service-role/' in role['Path']:
                        service_roles.append({
                            'role_name': role['RoleName'],
                            'role_arn': role['Arn'],
                            'service_name': role['Path'].split('/')[2] if len(role['Path'].split('/')) > 2 else 'unknown',
                            'creation_date': role['CreateDate'].isoformat(),
                            'last_used': role.get('RoleLastUsed', {}).get('LastUsedDate'),
                            'status': 'Active' if role.get('RoleLastUsed', {}).get('LastUsedDate') else 'Inactive'
                        })
        
        except Exception as e:
            logger.error(f"Error auditing service-linked roles: {e}")
        
        return service_roles
    
    def _check_policy_versions(self) -> List[Dict[str, Any]]:
        """Check for policies with multiple versions."""
        logger.info("Checking policy versions")
        policies_with_versions = []
        
        try:
            paginator = self.iam.get_paginator('list_policies')
            for page in paginator.paginate(Scope='Local'):
                for policy in page['Policies']:
                    versions = self.iam.list_policy_versions(PolicyArn=policy['Arn'])
                    if len(versions['Versions']) > 1:
                        policies_with_versions.append({
                            'policy_name': policy['PolicyName'],
                            'policy_arn': policy['Arn'],
                            'version_count': len(versions['Versions']),
                            'default_version': policy['DefaultVersionId'],
                            'recommendation': 'Clean up old policy versions if not needed'
                        })
        
        except Exception as e:
            logger.error(f"Error checking policy versions: {e}")
        
        return policies_with_versions
    
    def _audit_assume_role_policies(self) -> List[Dict[str, Any]]:
        """Audit assume role policies for security issues."""
        logger.info("Auditing assume role policies")
        policy_issues = []
        
        try:
            paginator = self.iam.get_paginator('list_roles')
            for page in paginator.paginate():
                for role in page['Roles']:
                    issues = self._analyze_assume_role_policy(role)
                    if issues:
                        policy_issues.append({
                            'role_name': role['RoleName'],
                            'role_arn': role['Arn'],
                            'issues': issues
                        })
        
        except Exception as e:
            logger.error(f"Error auditing assume role policies: {e}")
        
        return policy_issues
    
    def _analyze_assume_role_policy(self, role: Dict[str, Any]) -> List[Dict[str, str]]:
        """Analyze assume role policy for security issues."""
        issues = []
        assume_role_doc = role['AssumeRolePolicyDocument']
        statements = assume_role_doc.get('Statement', [])
        
        if not isinstance(statements, list):
            statements = [statements]
        
        for i, statement in enumerate(statements):
            if statement.get('Effect') == 'Allow':
                principal = statement.get('Principal', {})
                condition = statement.get('Condition', {})
                
                # Check for overly broad principals
                if principal == '*':
                    issues.append({
                        'severity': 'CRITICAL',
                        'issue': 'Wildcard principal allows anyone to assume role',
                        'statement_index': i
                    })
                
                # Check for missing conditions on cross-account access
                if isinstance(principal, dict) and 'AWS' in principal:
                    aws_principals = principal['AWS']
                    if isinstance(aws_principals, str):
                        aws_principals = [aws_principals]
                    
                    current_account = self._get_account_id()
                    for aws_principal in aws_principals:
                        if ':' in aws_principal and current_account not in aws_principal:
                            if not condition:
                                issues.append({
                                    'severity': 'HIGH',
                                    'issue': 'Cross-account access without conditions',
                                    'statement_index': i,
                                    'external_principal': aws_principal
                                })
        
        return issues
    
    def _get_privilege_recommendation(self, privileges: Dict[str, Any]) -> str:
        """Get recommendation for reducing privileges."""
        if privileges['risk_score'] >= 8:
            return "Review and implement least privilege principles. Consider breaking down into smaller, more specific roles."
        elif privileges['risk_score'] >= 5:
            return "Consider reducing attached policies and implementing more granular permissions."
        else:
            return "Privileges appear reasonable, but regular review is recommended."
    
    def _generate_summary(self, audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate audit summary."""
        return {
            'total_wildcard_violations': len(audit_results.get('wildcard_violations', [])),
            'critical_violations': len([v for v in audit_results.get('wildcard_violations', []) if v.get('severity') == 'CRITICAL']),
            'overprivileged_roles_count': len(audit_results.get('overprivileged_roles', [])),
            'inactive_users_count': len(audit_results.get('inactive_users', [])),
            'mfa_compliance_percentage': audit_results.get('mfa_violations', {}).get('compliance_percentage', 0),
            'old_access_keys_count': len(audit_results.get('access_key_rotation', [])),
            'unused_roles_count': len(audit_results.get('unused_roles', [])),
            'cross_account_roles_count': len(audit_results.get('cross_account_roles', [])),
            'recommendations_count': sum([
                len(audit_results.get('wildcard_violations', [])),
                len(audit_results.get('overprivileged_roles', [])),
                len(audit_results.get('inactive_users', [])),
                len(audit_results.get('mfa_violations', {}).get('users_without_mfa', [])),
                len(audit_results.get('access_key_rotation', [])),
                len(audit_results.get('unused_roles', []))
            ])
        }
    
    def export_report(self, audit_results: Dict[str, Any], output_file: str) -> None:
        """Export audit report to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(audit_results, f, indent=2, default=str)
        logger.info(f"Audit report exported to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='IAM Security Auditor')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--output', default='iam-audit-report.json', help='Output file')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    auditor = IAMAuditor(region=args.region)
    audit_results = auditor.audit_all_policies()
    
    # Print summary
    summary = audit_results['summary']
    print("\n" + "="*50)
    print("IAM SECURITY AUDIT SUMMARY")
    print("="*50)
    print(f"Account ID: {audit_results['account_id']}")
    print(f"Timestamp: {audit_results['timestamp']}")
    print(f"Critical Violations: {summary['critical_violations']}")
    print(f"Total Violations: {summary['total_wildcard_violations']}")
    print(f"Overprivileged Roles: {summary['overprivileged_roles_count']}")
    print(f"Inactive Users: {summary['inactive_users_count']}")
    print(f"MFA Compliance: {summary['mfa_compliance_percentage']:.1f}%")
    print(f"Old Access Keys: {summary['old_access_keys_count']}")
    print(f"Unused Roles: {summary['unused_roles_count']}")
    print(f"Cross-Account Roles: {summary['cross_account_roles_count']}")
    print(f"Total Recommendations: {summary['recommendations_count']}")
    print("="*50)
    
    # Export report
    auditor.export_report(audit_results, args.output)

if __name__ == '__main__':
    main()