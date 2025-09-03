"""
Shared utility functions for the flight data pipeline Lambda functions
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AWSUtils:
    """Utility class for AWS service interactions"""
    
    @staticmethod
    def get_s3_client():
        """Get S3 client with error handling"""
        try:
            return boto3.client('s3')
        except Exception as e:
            logger.error(f"Failed to create S3 client: {str(e)}")
            raise
    
    @staticmethod
    def get_dynamodb_resource():
        """Get DynamoDB resource with error handling"""
        try:
            return boto3.resource('dynamodb')
        except Exception as e:
            logger.error(f"Failed to create DynamoDB resource: {str(e)}")
            raise
    
    @staticmethod
    def get_cloudwatch_client():
        """Get CloudWatch client with error handling"""
        try:
            return boto3.client('cloudwatch')
        except Exception as e:
            logger.error(f"Failed to create CloudWatch client: {str(e)}")
            raise
    
    @staticmethod
    def get_sns_client():
        """Get SNS client with error handling"""
        try:
            return boto3.client('sns')
        except Exception as e:
            logger.error(f"Failed to create SNS client: {str(e)}")
            raise

class S3Utils:
    """Utility class for S3 operations"""
    
    def __init__(self, s3_client=None):
        self.s3_client = s3_client or AWSUtils.get_s3_client()
    
    def upload_json_to_s3(self, bucket: str, key: str, data: Dict, metadata: Optional[Dict] = None) -> bool:
        """
        Upload JSON data to S3 with optional metadata
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            data: Data to upload as JSON
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            
            put_args = {
                'Bucket': bucket,
                'Key': key,
                'Body': json_data,
                'ContentType': 'application/json'
            }
            
            if metadata:
                # Convert all metadata values to strings
                string_metadata = {k: str(v) for k, v in metadata.items()}
                put_args['Metadata'] = string_metadata
            
            self.s3_client.put_object(**put_args)
            logger.info(f"Successfully uploaded JSON to s3://{bucket}/{key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload JSON to S3: {str(e)}")
            return False
    
    def download_json_from_s3(self, bucket: str, key: str) -> Optional[Dict]:
        """
        Download and parse JSON data from S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Parsed JSON data or None if failed
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
            
        except ClientError as e:
            logger.error(f"Failed to download JSON from S3: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return None
    
    def check_object_exists(self, bucket: str, key: str) -> bool:
        """
        Check if an S3 object exists
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking object existence: {str(e)}")
                return False
    
    def copy_object(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str) -> bool:
        """
        Copy an S3 object from one location to another
        
        Args:
            source_bucket: Source bucket name
            source_key: Source object key
            dest_bucket: Destination bucket name
            dest_key: Destination object key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key
            )
            logger.info(f"Successfully copied s3://{source_bucket}/{source_key} to s3://{dest_bucket}/{dest_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to copy S3 object: {str(e)}")
            return False

class DataValidationUtils:
    """Utility class for data validation operations"""
    
    @staticmethod
    def validate_flight_record(record: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single flight record
        
        Args:
            record: Flight record dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields check
        required_fields = ['icao24', 'last_contact']
        for field in required_fields:
            if field not in record or record[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # ICAO24 format validation
        if 'icao24' in record and record['icao24']:
            if not isinstance(record['icao24'], str) or len(record['icao24']) != 6:
                errors.append("Invalid ICAO24 format (must be 6 characters)")
        
        # Coordinate validation
        if 'longitude' in record and record['longitude'] is not None:
            if not -180 <= record['longitude'] <= 180:
                errors.append(f"Invalid longitude: {record['longitude']}")
        
        if 'latitude' in record and record['latitude'] is not None:
            if not -90 <= record['latitude'] <= 90:
                errors.append(f"Invalid latitude: {record['latitude']}")
        
        # Altitude validation
        if 'baro_altitude_ft' in record and record['baro_altitude_ft'] is not None:
            if record['baro_altitude_ft'] < -1000 or record['baro_altitude_ft'] > 60000:
                errors.append(f"Invalid barometric altitude: {record['baro_altitude_ft']}")
        
        # Speed validation
        if 'velocity_knots' in record and record['velocity_knots'] is not None:
            if record['velocity_knots'] < 0 or record['velocity_knots'] > 1200:
                errors.append(f"Invalid velocity: {record['velocity_knots']}")
        
        # Timestamp validation
        if 'last_contact' in record and record['last_contact'] is not None:
            current_time = datetime.now(timezone.utc).timestamp()
            if record['last_contact'] > current_time:
                errors.append("Last contact time cannot be in the future")
            if record['last_contact'] < current_time - 86400:  # Older than 24 hours
                errors.append("Last contact time is too old (>24 hours)")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def calculate_completeness_score(record: Dict, fields: List[str]) -> float:
        """
        Calculate completeness score for a record based on specified fields
        
        Args:
            record: Data record
            fields: List of fields to check
            
        Returns:
            Completeness score (0.0 to 1.0)
        """
        if not fields:
            return 1.0
        
        present_fields = sum(1 for field in fields if field in record and record[field] is not None)
        return present_fields / len(fields)
    
    @staticmethod
    def detect_outliers(values: List[Union[int, float]], method: str = 'iqr') -> List[bool]:
        """
        Detect outliers in a list of numeric values
        
        Args:
            values: List of numeric values
            method: Method to use ('iqr' or 'zscore')
            
        Returns:
            List of boolean flags indicating outliers
        """
        if not values or len(values) < 3:
            return [False] * len(values)
        
        if method == 'iqr':
            sorted_values = sorted(values)
            n = len(sorted_values)
            q1_idx = n // 4
            q3_idx = 3 * n // 4
            
            q1 = sorted_values[q1_idx]
            q3 = sorted_values[q3_idx]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            return [v < lower_bound or v > upper_bound for v in values]
        
        elif method == 'zscore':
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            if std_dev == 0:
                return [False] * len(values)
            
            z_scores = [(v - mean_val) / std_dev for v in values]
            return [abs(z) > 3 for z in z_scores]
        
        else:
            raise ValueError(f"Unknown outlier detection method: {method}")

class MetricsUtils:
    """Utility class for CloudWatch metrics operations"""
    
    def __init__(self, cloudwatch_client=None):
        self.cloudwatch = cloudwatch_client or AWSUtils.get_cloudwatch_client()
    
    def put_metric(self, namespace: str, metric_name: str, value: Union[int, float], 
                   unit: str = 'Count', dimensions: Optional[Dict[str, str]] = None) -> bool:
        """
        Put a single metric to CloudWatch
        
        Args:
            namespace: CloudWatch namespace
            metric_name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Optional dimensions dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=namespace,
                MetricData=[metric_data]
            )
            
            logger.debug(f"Put metric: {namespace}/{metric_name} = {value}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to put metric: {str(e)}")
            return False
    
    def put_multiple_metrics(self, namespace: str, metrics: List[Dict]) -> bool:
        """
        Put multiple metrics to CloudWatch in a single call
        
        Args:
            namespace: CloudWatch namespace
            metrics: List of metric dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # CloudWatch accepts max 20 metrics per call
            chunk_size = 20
            
            for i in range(0, len(metrics), chunk_size):
                chunk = metrics[i:i + chunk_size]
                self.cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=chunk
                )
            
            logger.info(f"Put {len(metrics)} metrics to {namespace}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to put multiple metrics: {str(e)}")
            return False

class LambdaUtils:
    """Utility class for Lambda function operations"""
    
    @staticmethod
    def extract_s3_event_info(event: Dict) -> List[Dict[str, str]]:
        """
        Extract S3 event information from Lambda event
        
        Args:
            event: Lambda event dictionary
            
        Returns:
            List of dictionaries with bucket and key information
        """
        s3_info = []
        
        try:
            for record in event.get('Records', []):
                if 's3' in record:
                    bucket = record['s3']['bucket']['name']
                    key = record['s3']['object']['key']
                    
                    # URL decode the key
                    from urllib.parse import unquote_plus
                    key = unquote_plus(key)
                    
                    s3_info.append({
                        'bucket': bucket,
                        'key': key,
                        'size': record['s3']['object'].get('size', 0),
                        'event_name': record.get('eventName', '')
                    })
            
        except KeyError as e:
            logger.error(f"Error parsing S3 event: {str(e)}")
        
        return s3_info
    
    @staticmethod
    def create_lambda_response(status_code: int, body: Union[str, Dict], 
                             headers: Optional[Dict] = None) -> Dict:
        """
        Create a standardized Lambda response
        
        Args:
            status_code: HTTP status code
            body: Response body (string or dictionary)
            headers: Optional headers dictionary
            
        Returns:
            Lambda response dictionary
        """
        response = {
            'statusCode': status_code,
            'body': json.dumps(body) if isinstance(body, dict) else body
        }
        
        if headers:
            response['headers'] = headers
        
        return response
    
    @staticmethod
    def get_environment_variable(name: str, default: Optional[str] = None, 
                                required: bool = False) -> Optional[str]:
        """
        Get environment variable with validation
        
        Args:
            name: Environment variable name
            default: Default value if not found
            required: Whether the variable is required
            
        Returns:
            Environment variable value or default
            
        Raises:
            ValueError: If required variable is missing
        """
        value = os.environ.get(name, default)
        
        if required and not value:
            raise ValueError(f"Required environment variable {name} is not set")
        
        return value

class DateTimeUtils:
    """Utility class for date and time operations"""
    
    @staticmethod
    def get_current_timestamp() -> int:
        """Get current UTC timestamp as integer"""
        return int(datetime.now(timezone.utc).timestamp())
    
    @staticmethod
    def get_current_iso_timestamp() -> str:
        """Get current UTC timestamp as ISO string"""
        return datetime.now(timezone.utc).isoformat()
    
    @staticmethod
    def timestamp_to_iso(timestamp: int) -> str:
        """Convert Unix timestamp to ISO string"""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    
    @staticmethod
    def iso_to_timestamp(iso_string: str) -> int:
        """Convert ISO string to Unix timestamp"""
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return int(dt.timestamp())
    
    @staticmethod
    def get_partition_path(timestamp: int) -> str:
        """
        Generate partition path from timestamp for S3 storage
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Partition path string (year=YYYY/month=MM/day=DD/hour=HH)
        """
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}"

class ErrorHandlingUtils:
    """Utility class for error handling and logging"""
    
    @staticmethod
    def log_error_with_context(logger_instance: logging.Logger, error: Exception, 
                              context: Dict[str, Any]) -> None:
        """
        Log error with additional context
        
        Args:
            logger_instance: Logger instance
            error: Exception object
            context: Additional context dictionary
        """
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }
        
        logger_instance.error(f"Error occurred: {json.dumps(error_details, default=str)}")
    
    @staticmethod
    def create_error_response(execution_id: str, error: Exception, 
                            execution_time: float = 0) -> Dict[str, Any]:
        """
        Create standardized error response
        
        Args:
            execution_id: Execution ID
            error: Exception object
            execution_time: Execution time in seconds
            
        Returns:
            Error response dictionary
        """
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_type': type(error).__name__,
                'error_message': str(error),
                'execution_time': execution_time,
                'timestamp': DateTimeUtils.get_current_iso_timestamp()
            })
        }

# Global utility instances for easy import
s3_utils = S3Utils()
metrics_utils = MetricsUtils()
validation_utils = DataValidationUtils()
lambda_utils = LambdaUtils()
datetime_utils = DateTimeUtils()
error_utils = ErrorHandlingUtils()