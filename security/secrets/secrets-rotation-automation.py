#!/usr/bin/env python3
"""
Automated Secrets Rotation Script for Flight Data Pipeline
Handles rotation of API keys, database passwords, and application secrets
"""

import boto3
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import hashlib
import secrets
import string
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecretsRotationManager:
    """Manages automated rotation of secrets across AWS services."""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'production'):
        self.region = region
        self.environment = environment
        self.application_name = 'flightdata-pipeline'
        
        # AWS clients
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        self.ssm_client = boto3.client('ssm', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.sns_client = boto3.client('sns', region_name=region)
        
        # Configuration
        self.parameter_prefix = f'/{self.application_name}/{self.environment}'
        
    def rotate_all_secrets(self) -> Dict[str, Any]:
        """Rotate all applicable secrets."""
        logger.info("Starting automated secrets rotation")
        
        rotation_results = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'results': {},
            'errors': [],
            'summary': {}
        }
        
        # Define secrets to rotate
        secrets_to_rotate = [
            {
                'name': f'{self.application_name}/{self.environment}/api/opensky/credentials',
                'type': 'api_credentials',
                'rotation_interval_days': 30
            },
            {
                'name': f'{self.application_name}/{self.environment}/auth/jwt-secret',
                'type': 'jwt_secret',
                'rotation_interval_days': 90
            },
            {
                'name': f'{self.application_name}/{self.environment}/encryption/application-key',
                'type': 'encryption_key',
                'rotation_interval_days': 180
            },
            {
                'name': f'{self.application_name}/{self.environment}/api/third-party/keys',
                'type': 'api_keys',
                'rotation_interval_days': 60
            }
        ]
        
        for secret_config in secrets_to_rotate:
            try:
                result = self._rotate_secret(secret_config)
                rotation_results['results'][secret_config['name']] = result
                
            except Exception as e:
                error_msg = f"Failed to rotate {secret_config['name']}: {str(e)}"
                logger.error(error_msg)
                rotation_results['errors'].append({
                    'secret_name': secret_config['name'],
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                })
        
        # Generate summary
        rotation_results['summary'] = self._generate_rotation_summary(rotation_results)
        
        # Send notifications
        self._send_rotation_notifications(rotation_results)
        
        return rotation_results
    
    def _rotate_secret(self, secret_config: Dict[str, Any]) -> Dict[str, Any]:
        """Rotate a single secret based on its configuration."""
        secret_name = secret_config['name']
        secret_type = secret_config['type']
        rotation_interval = secret_config['rotation_interval_days']
        
        logger.info(f"Checking rotation status for secret: {secret_name}")
        
        try:
            # Get secret metadata
            secret_info = self.secrets_client.describe_secret(SecretId=secret_name)
            
            # Check if rotation is needed
            if not self._needs_rotation(secret_info, rotation_interval):
                return {
                    'status': 'skipped',
                    'reason': 'Not due for rotation',
                    'last_rotation': secret_info.get('LastRotatedDate'),
                    'next_rotation': self._calculate_next_rotation(secret_info, rotation_interval)
                }
            
            # Perform rotation based on secret type
            if secret_type == 'api_credentials':
                result = self._rotate_api_credentials(secret_name)
            elif secret_type == 'jwt_secret':
                result = self._rotate_jwt_secret(secret_name)
            elif secret_type == 'encryption_key':
                result = self._rotate_encryption_key(secret_name)
            elif secret_type == 'api_keys':
                result = self._rotate_api_keys(secret_name)
            else:
                raise ValueError(f"Unknown secret type: {secret_type}")
            
            logger.info(f"Successfully rotated secret: {secret_name}")
            return result
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {secret_name}")
                return {'status': 'not_found', 'error': 'Secret does not exist'}
            else:
                raise e
    
    def _needs_rotation(self, secret_info: Dict[str, Any], rotation_interval_days: int) -> bool:
        """Check if a secret needs rotation based on last rotation date."""
        last_rotated = secret_info.get('LastRotatedDate')
        
        if not last_rotated:
            # Secret has never been rotated
            created_date = secret_info['CreatedDate']
            days_since_creation = (datetime.now(created_date.tzinfo) - created_date).days
            return days_since_creation >= rotation_interval_days
        
        days_since_rotation = (datetime.now(last_rotated.tzinfo) - last_rotated).days
        return days_since_rotation >= rotation_interval_days
    
    def _calculate_next_rotation(self, secret_info: Dict[str, Any], rotation_interval_days: int) -> datetime:
        """Calculate the next rotation date for a secret."""
        last_rotated = secret_info.get('LastRotatedDate')
        
        if not last_rotated:
            base_date = secret_info['CreatedDate']
        else:
            base_date = last_rotated
        
        return base_date + timedelta(days=rotation_interval_days)
    
    def _rotate_api_credentials(self, secret_name: str) -> Dict[str, Any]:
        """Rotate API credentials (username/password)."""
        logger.info(f"Rotating API credentials for: {secret_name}")
        
        # Get current secret
        current_secret = self.secrets_client.get_secret_value(SecretId=secret_name)
        current_data = json.loads(current_secret['SecretString'])
        
        # Generate new password (keeping same username)
        new_password = self._generate_secure_password(32)
        
        new_data = {
            'username': current_data['username'],
            'password': new_password,
            'endpoint': current_data.get('endpoint', ''),
            'rotated_date': datetime.now().isoformat(),
            'rotation_id': secrets.token_hex(8)
        }
        
        # Update secret with new credentials
        self.secrets_client.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(new_data)
        )
        
        # Test new credentials (if applicable)
        test_result = self._test_api_credentials(new_data)
        
        return {
            'status': 'rotated',
            'rotation_date': datetime.now().isoformat(),
            'test_result': test_result,
            'rotation_id': new_data['rotation_id']
        }
    
    def _rotate_jwt_secret(self, secret_name: str) -> Dict[str, Any]:
        """Rotate JWT signing secret."""
        logger.info(f"Rotating JWT secret for: {secret_name}")
        
        # Generate new JWT secret
        new_jwt_secret = self._generate_secure_key(64)
        
        # Update secret
        self.secrets_client.put_secret_value(
            SecretId=secret_name,
            SecretString=new_jwt_secret
        )
        
        # Notify applications about JWT secret rotation
        self._notify_jwt_rotation(secret_name)
        
        return {
            'status': 'rotated',
            'rotation_date': datetime.now().isoformat(),
            'key_length': len(new_jwt_secret)
        }
    
    def _rotate_encryption_key(self, secret_name: str) -> Dict[str, Any]:
        """Rotate application encryption key."""
        logger.info(f"Rotating encryption key for: {secret_name}")
        
        # Generate new encryption key
        new_key = self._generate_secure_key(64)
        
        # Get current key for gradual migration
        try:
            current_secret = self.secrets_client.get_secret_value(SecretId=secret_name)
            current_key = current_secret['SecretString']
            
            # Create versioned key structure for gradual migration
            key_data = {
                'current_key': new_key,
                'previous_key': current_key,
                'rotation_date': datetime.now().isoformat(),
                'migration_period_days': 30  # Allow 30 days for migration
            }
            
        except ClientError:
            # First time rotation
            key_data = {
                'current_key': new_key,
                'rotation_date': datetime.now().isoformat()
            }
        
        # Update secret
        self.secrets_client.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(key_data)
        )
        
        return {
            'status': 'rotated',
            'rotation_date': datetime.now().isoformat(),
            'migration_period': key_data.get('migration_period_days', 0)
        }
    
    def _rotate_api_keys(self, secret_name: str) -> Dict[str, Any]:
        """Rotate third-party API keys."""
        logger.info(f"Rotating third-party API keys for: {secret_name}")
        
        # Get current secret
        current_secret = self.secrets_client.get_secret_value(SecretId=secret_name)
        current_data = json.loads(current_secret['SecretString'])
        
        # Generate new API keys
        new_data = {}
        rotation_results = {}
        
        for service, current_key in current_data.items():
            if service in ['weather_api_key', 'notification_service_key']:
                # Generate new key
                new_key = self._generate_api_key(32)
                new_data[service] = new_key
                
                # Test new key (placeholder - implement actual testing)
                test_result = self._test_third_party_api_key(service, new_key)
                rotation_results[service] = {
                    'rotated': True,
                    'test_result': test_result
                }
            else:
                # Keep unchanged for non-API keys (like webhooks)
                new_data[service] = current_key
                rotation_results[service] = {'rotated': False, 'reason': 'Manual rotation required'}
        
        new_data['last_rotation'] = datetime.now().isoformat()
        
        # Update secret
        self.secrets_client.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(new_data)
        )
        
        return {
            'status': 'rotated',
            'rotation_date': datetime.now().isoformat(),
            'service_results': rotation_results
        }
    
    def _generate_secure_password(self, length: int) -> str:
        """Generate a secure password."""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(characters) for _ in range(length))
        
        # Ensure password meets complexity requirements
        if not (any(c.islower() for c in password) and 
                any(c.isupper() for c in password) and 
                any(c.isdigit() for c in password) and 
                any(c in "!@#$%^&*" for c in password)):
            # Recursively generate until requirements are met
            return self._generate_secure_password(length)
        
        return password
    
    def _generate_secure_key(self, length: int) -> str:
        """Generate a secure random key."""
        return secrets.token_urlsafe(length)
    
    def _generate_api_key(self, length: int) -> str:
        """Generate a secure API key."""
        return secrets.token_hex(length)
    
    def _test_api_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Test API credentials (placeholder implementation)."""
        # In a real implementation, you would test against the actual API
        logger.info("Testing new API credentials")
        
        # Simulate API test
        time.sleep(1)
        
        return {
            'status': 'success',
            'response_time_ms': 150,
            'test_timestamp': datetime.now().isoformat()
        }
    
    def _test_third_party_api_key(self, service: str, api_key: str) -> Dict[str, Any]:
        """Test third-party API key (placeholder implementation)."""
        # In a real implementation, you would test against the actual service
        logger.info(f"Testing new API key for service: {service}")
        
        # Simulate API test
        time.sleep(1)
        
        return {
            'status': 'success',
            'service': service,
            'test_timestamp': datetime.now().isoformat()
        }
    
    def _notify_jwt_rotation(self, secret_name: str) -> None:
        """Notify applications about JWT secret rotation."""
        try:
            # Get SNS topic for notifications
            topic_arn = self.ssm_client.get_parameter(
                Name=f'{self.parameter_prefix}/alerts/security-topic-arn'
            )['Parameter']['Value']
            
            message = {
                'event': 'jwt_secret_rotated',
                'secret_name': secret_name,
                'timestamp': datetime.now().isoformat(),
                'environment': self.environment,
                'action_required': 'Applications should refresh JWT secret from Secrets Manager'
            }
            
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=f'JWT Secret Rotated - {self.environment.upper()}',
                Message=json.dumps(message, indent=2)
            )
            
        except Exception as e:
            logger.warning(f"Failed to send JWT rotation notification: {e}")
    
    def _generate_rotation_summary(self, rotation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rotation summary statistics."""
        results = rotation_results['results']
        
        total_secrets = len(results)
        rotated_count = sum(1 for r in results.values() if r.get('status') == 'rotated')
        skipped_count = sum(1 for r in results.values() if r.get('status') == 'skipped')
        failed_count = len(rotation_results['errors'])
        
        return {
            'total_secrets': total_secrets,
            'rotated': rotated_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'success_rate': (rotated_count / total_secrets * 100) if total_secrets > 0 else 0
        }
    
    def _send_rotation_notifications(self, rotation_results: Dict[str, Any]) -> None:
        """Send rotation completion notifications."""
        try:
            # Get SNS topic for notifications
            topic_arn = self.ssm_client.get_parameter(
                Name=f'{self.parameter_prefix}/alerts/security-topic-arn'
            )['Parameter']['Value']
            
            summary = rotation_results['summary']
            
            subject = f"Secrets Rotation Complete - {self.environment.upper()}"
            
            message = f"""
Automated Secrets Rotation Summary
Environment: {self.environment.upper()}
Timestamp: {rotation_results['timestamp']}

Results:
- Total Secrets: {summary['total_secrets']}
- Successfully Rotated: {summary['rotated']}
- Skipped (Not Due): {summary['skipped']}
- Failed: {summary['failed']}
- Success Rate: {summary['success_rate']:.1f}%

"""
            
            if rotation_results['errors']:
                message += "\nErrors:\n"
                for error in rotation_results['errors']:
                    message += f"- {error['secret_name']}: {error['error']}\n"
            
            message += f"\nFor detailed results, check CloudWatch logs for function: {self.application_name}-{self.environment}-secrets-rotation"
            
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message
            )
            
            logger.info("Rotation completion notification sent")
            
        except Exception as e:
            logger.warning(f"Failed to send rotation completion notification: {e}")
    
    def check_secret_health(self) -> Dict[str, Any]:
        """Check health status of all secrets."""
        logger.info("Checking secret health status")
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'secrets_status': {},
            'overall_health': 'healthy'
        }
        
        try:
            # List all secrets with our prefix
            paginator = self.secrets_client.get_paginator('list_secrets')
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    secret_name = secret['Name']
                    if secret_name.startswith(f'{self.application_name}/{self.environment}'):
                        health_status = self._check_individual_secret_health(secret)
                        health_report['secrets_status'][secret_name] = health_status
                        
                        if health_status['status'] != 'healthy':
                            health_report['overall_health'] = 'degraded'
        
        except Exception as e:
            logger.error(f"Error checking secret health: {e}")
            health_report['overall_health'] = 'error'
            health_report['error'] = str(e)
        
        return health_report
    
    def _check_individual_secret_health(self, secret: Dict[str, Any]) -> Dict[str, Any]:
        """Check health of an individual secret."""
        secret_name = secret['Name']
        
        try:
            # Check if secret is accessible
            self.secrets_client.get_secret_value(SecretId=secret_name)
            
            # Check rotation status
            last_rotated = secret.get('LastRotatedDate')
            created_date = secret['CreatedDate']
            
            # Calculate age
            if last_rotated:
                age_days = (datetime.now(last_rotated.tzinfo) - last_rotated).days
                reference_date = last_rotated
            else:
                age_days = (datetime.now(created_date.tzinfo) - created_date).days
                reference_date = created_date
            
            # Determine health status
            if age_days > 365:  # Over 1 year
                status = 'critical'
                message = 'Secret is very old and should be rotated immediately'
            elif age_days > 180:  # Over 6 months
                status = 'warning'
                message = 'Secret should be rotated soon'
            elif age_days > 90:   # Over 3 months
                status = 'attention'
                message = 'Secret rotation should be scheduled'
            else:
                status = 'healthy'
                message = 'Secret is current'
            
            return {
                'status': status,
                'message': message,
                'age_days': age_days,
                'last_rotated': last_rotated.isoformat() if last_rotated else None,
                'created_date': created_date.isoformat(),
                'has_automatic_rotation': secret.get('RotationEnabled', False)
            }
            
        except ClientError as e:
            return {
                'status': 'error',
                'message': f'Cannot access secret: {e.response["Error"]["Code"]}',
                'error_code': e.response['Error']['Code']
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }

def lambda_handler(event, context):
    """AWS Lambda handler for scheduled secret rotation."""
    
    # Get environment from Lambda environment variables
    environment = os.environ.get('ENVIRONMENT', 'production')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Initialize rotation manager
    rotation_manager = SecretsRotationManager(region=region, environment=environment)
    
    # Determine action based on event
    action = event.get('action', 'rotate_all')
    
    if action == 'rotate_all':
        results = rotation_manager.rotate_all_secrets()
        return {
            'statusCode': 200,
            'body': json.dumps(results, default=str)
        }
    elif action == 'health_check':
        results = rotation_manager.check_secret_health()
        return {
            'statusCode': 200,
            'body': json.dumps(results, default=str)
        }
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Unknown action: {action}'})
        }

def main():
    """Command-line interface for secrets rotation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Secrets Rotation Manager')
    parser.add_argument('--environment', default='production', help='Environment name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--action', choices=['rotate', 'health_check'], default='rotate', help='Action to perform')
    parser.add_argument('--output', help='Output file for results')
    
    args = parser.parse_args()
    
    # Initialize rotation manager
    rotation_manager = SecretsRotationManager(region=args.region, environment=args.environment)
    
    # Perform action
    if args.action == 'rotate':
        results = rotation_manager.rotate_all_secrets()
    else:  # health_check
        results = rotation_manager.check_secret_health()
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(results, indent=2, default=str))

if __name__ == '__main__':
    main()