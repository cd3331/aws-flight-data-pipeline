"""
Pipeline test utilities for integration testing.

Provides test harness, resource management, and monitoring utilities
for comprehensive pipeline testing.
"""
import boto3
import json
import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import Mock, MagicMock
import pandas as pd
import io
import psutil
import os
from contextlib import contextmanager
from dataclasses import dataclass
from moto import mock_aws


@dataclass
class ResourceUsage:
    """Track resource usage metrics."""
    cpu_percent: float
    memory_mb: float
    timestamp: float


class PipelineTestHarness:
    """Complete test harness for pipeline integration testing."""
    
    def __init__(self):
        """Initialize test harness with AWS service mocks."""
        self.s3_client = None
        self.dynamodb = None
        self.lambda_client = None
        self.sns_client = None
        self.sqs_client = None
        
        # Test infrastructure
        self.raw_bucket = f"test-raw-data-{uuid.uuid4().hex[:8]}"
        self.processed_bucket = f"test-processed-data-{uuid.uuid4().hex[:8]}"
        self.tracking_table = f"test-processing-tracking-{uuid.uuid4().hex[:8]}"
        self.dlq_url = None
        self.sns_topic_arn = None
        
        # Collected messages/events
        self._sns_messages = []
        self._dlq_messages = []
        self._lambda_invocations = []
        
        self.setup_complete = False
    
    def setup_infrastructure(self):
        """Set up all required AWS infrastructure for testing."""
        # Initialize AWS clients
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.lambda_client = boto3.client('lambda', region_name='us-east-1')
        self.sns_client = boto3.client('sns', region_name='us-east-1')
        self.sqs_client = boto3.client('sqs', region_name='us-east-1')
        
        # Create S3 buckets
        self.s3_client.create_bucket(Bucket=self.raw_bucket)
        self.s3_client.create_bucket(Bucket=self.processed_bucket)
        
        # Create DynamoDB table
        self._create_tracking_table()
        
        # Create SNS topic
        response = self.sns_client.create_topic(Name='test-flight-data-alerts')
        self.sns_topic_arn = response['TopicArn']
        
        # Create DLQ
        dlq_response = self.sqs_client.create_queue(QueueName='test-flight-data-dlq')
        self.dlq_url = dlq_response['QueueUrl']
        
        # Mock Lambda functions
        self._setup_lambda_mocks()
        
        self.setup_complete = True
    
    def _create_tracking_table(self):
        """Create DynamoDB table for processing tracking."""
        try:
            self.tracking_table_resource = self.dynamodb.create_table(
                TableName=self.tracking_table,
                KeySchema=[
                    {
                        'AttributeName': 'file_key',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'file_key',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            # Wait for table to be ready
            self.tracking_table_resource.wait_until_exists()
            
        except Exception as e:
            print(f"Warning: Could not create tracking table: {e}")
            self.tracking_table_resource = None
    
    def _setup_lambda_mocks(self):
        """Set up Lambda function mocks."""
        # Mock ETL Lambda function
        def etl_lambda_handler(event, context):
            return self._mock_etl_processing(event)
        
        # Mock Quality Validator Lambda function  
        def quality_validator_handler(event, context):
            return self._mock_quality_validation(event)
        
        self.etl_handler = etl_lambda_handler
        self.quality_handler = quality_validator_handler
    
    def _mock_etl_processing(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Mock ETL processing logic."""
        try:
            processing_start = time.time()
            
            # Extract S3 event information
            s3_record = event['Records'][0]['s3']
            bucket = s3_record['bucket']['name']
            key = s3_record['object']['key']
            
            # Simulate downloading and processing
            try:
                obj = self.s3_client.get_object(Bucket=bucket, Key=key)
                content = obj['Body'].read().decode('utf-8')
                
                # Parse JSON
                data = json.loads(content)
                if not isinstance(data, list):
                    data = [data]  # Ensure it's a list
                
                records_processed = len(data)
                
                # Simulate processing time
                processing_delay = min(0.1 * records_processed / 100, 2.0)  # Max 2 second delay
                time.sleep(processing_delay)
                
                # Generate output Parquet file key
                output_key = key.replace('raw/', 'processed/').replace('.json', '.parquet')
                
                # Simulate creating Parquet file
                df = pd.DataFrame(data)
                df['processed_timestamp'] = datetime.now(timezone.utc).isoformat()
                
                # Upload to processed bucket
                parquet_buffer = io.BytesIO()
                df.to_parquet(parquet_buffer, index=False)
                parquet_buffer.seek(0)
                
                self.s3_client.put_object(
                    Bucket=self.processed_bucket,
                    Key=output_key,
                    Body=parquet_buffer.getvalue(),
                    ContentType='application/octet-stream'
                )
                
                processing_duration = (time.time() - processing_start) * 1000
                
                # Update DynamoDB tracking
                if self.tracking_table_resource:
                    self.tracking_table_resource.put_item(
                        Item={
                            'file_key': key,
                            'status': 'COMPLETED',
                            'records_processed': records_processed,
                            'processing_duration_ms': int(processing_duration),
                            'output_file': output_key,
                            'processed_timestamp': datetime.now(timezone.utc).isoformat(),
                            'memory_used_mb': psutil.Process().memory_info().rss / 1024 / 1024
                        }
                    )
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'status': 'SUCCESS',
                        'records_processed': records_processed,
                        'output_file': output_key,
                        'processing_duration_ms': processing_duration
                    })
                }
                
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON format: {str(e)}"
                self._record_processing_error(key, error_msg)
                return self._error_response(400, error_msg)
                
            except Exception as e:
                error_msg = f"Processing error: {str(e)}"
                self._record_processing_error(key, error_msg)
                return self._error_response(500, error_msg)
                
        except Exception as e:
            return self._error_response(500, f"Lambda execution error: {str(e)}")
    
    def _mock_quality_validation(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Mock quality validation logic."""
        try:
            # Extract file information from event
            if 'Records' in event:
                # S3 trigger event
                s3_record = event['Records'][0]['s3']
                bucket = s3_record['bucket']['name']
                key = s3_record['object']['key']
            else:
                # Direct invocation
                bucket = event.get('bucket', self.processed_bucket)
                key = event.get('key')
            
            if not key:
                return self._error_response(400, "No file key provided")
            
            try:
                # Download Parquet file
                obj = self.s3_client.get_object(Bucket=bucket, Key=key)
                df = pd.read_parquet(io.BytesIO(obj['Body'].read()))
                
                # Simulate quality validation
                total_records = len(df)
                
                # Simple quality scoring
                completeness_issues = df.isnull().sum().sum()
                completeness_score = max(0, 1 - (completeness_issues / (total_records * len(df.columns))))
                
                # Check for invalid coordinates
                if 'latitude' in df.columns and 'longitude' in df.columns:
                    invalid_coords = ((df['latitude'].abs() > 90) | (df['longitude'].abs() > 180)).sum()
                    validity_score = max(0, 1 - (invalid_coords / total_records))
                else:
                    validity_score = 0.8  # Default score
                
                # Overall quality score
                overall_score = (completeness_score + validity_score) / 2
                
                # Determine quality grade
                if overall_score >= 0.9:
                    grade = 'A'
                    passed_checks = 8
                    failed_checks = 2
                elif overall_score >= 0.8:
                    grade = 'B'
                    passed_checks = 7
                    failed_checks = 3
                elif overall_score >= 0.7:
                    grade = 'C'
                    passed_checks = 6
                    failed_checks = 4
                else:
                    grade = 'F'
                    passed_checks = 4
                    failed_checks = 6
                
                passed_threshold = overall_score >= 0.8
                
                # Send alert if quality is low
                if not passed_threshold:
                    alert_message = {
                        'alert_type': 'DATA_QUALITY_ISSUE',
                        'file': key,
                        'overall_score': overall_score,
                        'quality_grade': grade,
                        'total_records': total_records
                    }
                    
                    self._send_sns_alert(
                        f"Flight Data Quality Alert - Score: {overall_score:.3f}",
                        json.dumps(alert_message, indent=2)
                    )
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'status': 'SUCCESS',
                        'validated_files': [{
                            'file': f"s3://{bucket}/{key}",
                            'overall_score': round(overall_score, 3),
                            'quality_grade': grade,
                            'passed_threshold': passed_threshold,
                            'total_records': total_records,
                            'passed_checks': passed_checks,
                            'failed_checks': failed_checks
                        }],
                        'total_files_validated': 1
                    })
                }
                
            except Exception as e:
                error_msg = f"Quality validation error: {str(e)}"
                return self._error_response(500, error_msg)
                
        except Exception as e:
            return self._error_response(500, f"Quality validation execution error: {str(e)}")
    
    def _record_processing_error(self, file_key: str, error_message: str):
        """Record processing error in DynamoDB."""
        if self.tracking_table_resource:
            try:
                self.tracking_table_resource.put_item(
                    Item={
                        'file_key': file_key,
                        'status': 'FAILED',
                        'error_message': error_message,
                        'processed_timestamp': datetime.now(timezone.utc).isoformat()
                    }
                )
            except Exception as e:
                print(f"Failed to record error in DynamoDB: {e}")
    
    def _error_response(self, status_code: int, error_message: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            'statusCode': status_code,
            'body': json.dumps({
                'status': 'ERROR',
                'error_message': error_message
            })
        }
    
    def _send_sns_alert(self, subject: str, message: str):
        """Send SNS alert and record for testing."""
        try:
            self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
            # Record for test verification
            self._sns_messages.append({
                'Subject': subject,
                'Message': message,
                'Timestamp': time.time()
            })
            
        except Exception as e:
            print(f"Failed to send SNS alert: {e}")
    
    def upload_to_raw_bucket(self, key: str, content: str) -> bool:
        """Upload content to raw data bucket."""
        try:
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            self.s3_client.put_object(
                Bucket=self.raw_bucket,
                Key=key,
                Body=content,
                ContentType='application/json'
            )
            return True
        except Exception as e:
            print(f"Failed to upload to raw bucket: {e}")
            return False
    
    def create_s3_event(self, key: str, size: int = 1024) -> Dict[str, Any]:
        """Create S3 event for Lambda triggering."""
        return {
            'Records': [
                {
                    'eventVersion': '2.1',
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    'eventTime': datetime.now(timezone.utc).isoformat(),
                    's3': {
                        'bucket': {
                            'name': self.raw_bucket
                        },
                        'object': {
                            'key': key,
                            'size': size
                        }
                    }
                }
            ]
        }
    
    def trigger_etl_lambda(self, s3_event: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """Trigger ETL Lambda function."""
        context = Mock()
        context.remaining_time_in_millis = lambda: timeout * 1000
        context.function_name = 'test-etl-processor'
        
        try:
            result = self.etl_handler(s3_event, context)
            self._lambda_invocations.append({
                'function': 'etl',
                'event': s3_event,
                'result': result,
                'timestamp': time.time()
            })
            return result
        except Exception as e:
            error_result = self._error_response(500, f"Lambda invocation failed: {str(e)}")
            self._lambda_invocations.append({
                'function': 'etl',
                'event': s3_event,
                'result': error_result,
                'error': str(e),
                'timestamp': time.time()
            })
            return error_result
    
    def trigger_quality_validator(self, parquet_key: str) -> Dict[str, Any]:
        """Trigger quality validation Lambda."""
        s3_event = {
            'Records': [
                {
                    'eventVersion': '2.1',
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {
                            'name': self.processed_bucket
                        },
                        'object': {
                            'key': parquet_key
                        }
                    }
                }
            ]
        }
        
        context = Mock()
        context.remaining_time_in_millis = lambda: 30000
        context.function_name = 'test-quality-validator'
        
        try:
            result = self.quality_handler(s3_event, context)
            self._lambda_invocations.append({
                'function': 'quality',
                'event': s3_event,
                'result': result,
                'timestamp': time.time()
            })
            return result
        except Exception as e:
            error_result = self._error_response(500, f"Quality validation failed: {str(e)}")
            self._lambda_invocations.append({
                'function': 'quality',
                'event': s3_event,
                'result': error_result,
                'error': str(e),
                'timestamp': time.time()
            })
            return error_result
    
    def check_processed_file_exists(self, key: str) -> bool:
        """Check if processed file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.processed_bucket, Key=key)
            return True
        except:
            return False
    
    def download_parquet_file(self, key: str) -> Optional[pd.DataFrame]:
        """Download and parse Parquet file."""
        try:
            obj = self.s3_client.get_object(Bucket=self.processed_bucket, Key=key)
            return pd.read_parquet(io.BytesIO(obj['Body'].read()))
        except Exception as e:
            print(f"Failed to download Parquet file: {e}")
            return None
    
    def get_processing_record(self, file_key: str) -> Optional[Dict[str, Any]]:
        """Get processing record from DynamoDB."""
        if not self.tracking_table_resource:
            return None
        
        try:
            response = self.tracking_table_resource.get_item(
                Key={'file_key': file_key}
            )
            return response.get('Item')
        except Exception as e:
            print(f"Failed to get processing record: {e}")
            return None
    
    def get_sns_messages(self) -> List[Dict[str, Any]]:
        """Get collected SNS messages."""
        return self._sns_messages.copy()
    
    def get_dlq_messages(self) -> List[Dict[str, Any]]:
        """Get DLQ messages."""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.dlq_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1
            )
            
            messages = response.get('Messages', [])
            self._dlq_messages.extend(messages)
            return self._dlq_messages.copy()
        except Exception as e:
            print(f"Failed to get DLQ messages: {e}")
            return []
    
    def get_lambda_invocations(self) -> List[Dict[str, Any]]:
        """Get Lambda invocation history."""
        return self._lambda_invocations.copy()
    
    def cleanup(self):
        """Clean up test resources."""
        if not self.setup_complete:
            return
        
        try:
            # Clean up S3 buckets
            for bucket in [self.raw_bucket, self.processed_bucket]:
                try:
                    # Delete all objects first
                    objects = self.s3_client.list_objects_v2(Bucket=bucket).get('Contents', [])
                    if objects:
                        delete_objects = [{'Key': obj['Key']} for obj in objects]
                        self.s3_client.delete_objects(
                            Bucket=bucket,
                            Delete={'Objects': delete_objects}
                        )
                    
                    # Delete bucket
                    self.s3_client.delete_bucket(Bucket=bucket)
                except Exception as e:
                    print(f"Failed to clean up bucket {bucket}: {e}")
            
            # Clean up DynamoDB table
            if self.tracking_table_resource:
                try:
                    self.tracking_table_resource.delete()
                except Exception as e:
                    print(f"Failed to clean up DynamoDB table: {e}")
            
            # Clean up SNS topic
            if self.sns_topic_arn:
                try:
                    self.sns_client.delete_topic(TopicArn=self.sns_topic_arn)
                except Exception as e:
                    print(f"Failed to clean up SNS topic: {e}")
            
            # Clean up SQS queue
            if self.dlq_url:
                try:
                    self.sqs_client.delete_queue(QueueUrl=self.dlq_url)
                except Exception as e:
                    print(f"Failed to clean up SQS queue: {e}")
                    
        except Exception as e:
            print(f"Cleanup failed: {e}")


class ResourceManager:
    """Manage test resources and cleanup."""
    
    def __init__(self):
        self.resources = []
        self.cleanup_functions = []
    
    def register_resource(self, resource: Any, cleanup_func: callable):
        """Register a resource and its cleanup function."""
        self.resources.append(resource)
        self.cleanup_functions.append(cleanup_func)
    
    def cleanup_all(self):
        """Clean up all registered resources."""
        for cleanup_func in reversed(self.cleanup_functions):
            try:
                cleanup_func()
            except Exception as e:
                print(f"Cleanup failed: {e}")
    
    @contextmanager
    def managed_resource(self, resource: Any, cleanup_func: callable):
        """Context manager for automatic resource cleanup."""
        try:
            self.register_resource(resource, cleanup_func)
            yield resource
        finally:
            try:
                cleanup_func()
            except Exception as e:
                print(f"Resource cleanup failed: {e}")


class PerformanceMonitor:
    """Monitor system performance during tests."""
    
    def __init__(self):
        self.monitoring = False
        self.measurements = []
        self.monitor_thread = None
        self.start_time = None
    
    def start_monitoring(self, interval: float = 1.0):
        """Start performance monitoring."""
        self.monitoring = True
        self.start_time = time.time()
        self.measurements = []
        
        def monitor_loop():
            while self.monitoring:
                try:
                    process = psutil.Process()
                    cpu_percent = process.cpu_percent()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    self.measurements.append(ResourceUsage(
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                        timestamp=time.time()
                    ))
                    
                    time.sleep(interval)
                except Exception as e:
                    print(f"Performance monitoring error: {e}")
                    break
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return performance summary."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        if not self.measurements:
            return {'error': 'No measurements collected'}
        
        cpu_values = [m.cpu_percent for m in self.measurements]
        memory_values = [m.memory_mb for m in self.measurements]
        
        duration = self.measurements[-1].timestamp - self.measurements[0].timestamp
        
        return {
            'duration_seconds': duration,
            'measurement_count': len(self.measurements),
            'cpu_percent': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory_mb': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
                'peak_usage': max(memory_values)
            }
        }
    
    def get_measurements(self) -> List[ResourceUsage]:
        """Get all performance measurements."""
        return self.measurements.copy()
    
    @contextmanager
    def monitor_performance(self, interval: float = 1.0):
        """Context manager for performance monitoring."""
        self.start_monitoring(interval)
        try:
            yield self
        finally:
            return self.stop_monitoring()