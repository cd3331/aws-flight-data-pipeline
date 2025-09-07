import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
import signal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client with shorter timeout
s3_client = boto3.client('s3', config=boto3.session.Config(
    read_timeout=2,
    connect_timeout=2
))

# Configuration
BUCKET_NAME = 'flight-data-pipeline-dev-raw-data-y10swyy3'
ALLOWED_ORIGIN = 'https://main.d2zdmzm6s2zgyk.amplifyapp.com'

# Sample static data fallback
SAMPLE_DATA = {
    'bucket_name': BUCKET_NAME,
    'latest_file_key': 'flight_data/2024/09/flight_data_20240907_120000.json',
    'file_size_bytes': 2547832,
    'last_modified': '2024-09-07T12:00:00Z',
    'message': 'Sample data - S3 connection failed'
}


class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Operation timed out")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function to return metadata about the latest flight data file in S3.
    
    Args:
        event: Lambda event object
        context: Lambda context object
    
    Returns:
        Dict containing metadata about the latest file in S3
    """
    # Set up timeout handler (2.5 seconds to leave buffer for response)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(2)
    
    try:
        logger.info("Getting latest flight data file metadata from S3")
        
        # Get latest file metadata from S3
        metadata = get_latest_file_metadata(BUCKET_NAME)
        
        return create_response(200, metadata)
        
    except TimeoutException:
        logger.warning("Request timed out, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.warning(f"AWS S3 error: {error_code}, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except NoCredentialsError:
        logger.warning("AWS credentials not found, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except Exception as e:
        logger.warning(f"Unexpected error: {str(e)}, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    finally:
        # Clear the alarm
        signal.alarm(0)


def get_latest_file_metadata(bucket_name: str) -> Dict[str, Any]:
    """
    Get metadata about the latest file in S3 bucket without downloading content.
    
    Args:
        bucket_name: Name of the S3 bucket
    
    Returns:
        Dict containing metadata about the latest file
    """
    # List objects in the bucket (limit to first page for speed)
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        MaxKeys=1000  # Get enough to find the latest
    )
    
    if 'Contents' not in response or not response['Contents']:
        raise ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'No files found in bucket'}},
            operation_name='list_objects_v2'
        )
    
    # Sort by last modified (newest first) and get the latest
    latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
    
    # Return metadata without downloading file content
    return {
        'bucket_name': bucket_name,
        'latest_file_key': latest_object['Key'],
        'file_size_bytes': latest_object['Size'],
        'last_modified': latest_object['LastModified'].isoformat(),
        'message': 'Successfully retrieved latest file metadata from S3'
    }


def create_response(status_code: int, data: Any) -> Dict[str, Any]:
    """
    Create a properly formatted Lambda response with CORS headers.
    
    Args:
        status_code: HTTP status code
        data: Response data
    
    Returns:
        Formatted Lambda response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400'
        },
        'body': json.dumps(data, default=str)  # default=str handles datetime objects
    }


