"""
Global pytest configuration and shared fixtures.
"""
import os
import json
import pytest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws
import tempfile
import io

# Test data constants
SAMPLE_FLIGHT_DATA = [
    {
        'icao24': 'abcdef',
        'latitude': 40.7128,
        'longitude': -74.0060,
        'baro_altitude': 10000.0,
        'velocity': 250.5,
        'heading': 90.0,
        'vertical_rate': 0.0,
        'callsign': 'UAL123',
        'origin_country': 'United States',
        'time_position': 1693401600,
        'last_contact': 1693401605,
        'on_ground': False,
        'squawk': '1200'
    },
    {
        'icao24': '123456',
        'latitude': 51.4700,
        'longitude': -0.4543,
        'baro_altitude': 35000.0,
        'velocity': 450.0,
        'heading': 270.0,
        'vertical_rate': -500.0,
        'callsign': 'BAW456',
        'origin_country': 'United Kingdom',
        'time_position': 1693401620,
        'last_contact': 1693401625,
        'on_ground': False,
        'squawk': '2000'
    },
    {
        'icao24': 'fedcba',
        'latitude': 35.6762,
        'longitude': 139.6503,
        'baro_altitude': 0.0,
        'velocity': 15.0,
        'heading': 180.0,
        'vertical_rate': 0.0,
        'callsign': 'JAL789',
        'origin_country': 'Japan',
        'time_position': 1693401640,
        'last_contact': 1693401645,
        'on_ground': True,
        'squawk': '0000'
    }
]

# Invalid test data for testing edge cases
INVALID_FLIGHT_DATA = [
    {
        'icao24': 'invalid',  # Wrong format
        'latitude': 95.0,  # Invalid latitude
        'longitude': -190.0,  # Invalid longitude
        'baro_altitude': -2000.0,  # Invalid altitude
        'velocity': -50.0,  # Invalid velocity
        'heading': 450.0,  # Invalid heading
        'vertical_rate': 10000.0,  # Invalid vertical rate
        'callsign': '',  # Empty callsign
        'origin_country': None,  # Missing country
        'time_position': None,  # Missing timestamp
        'last_contact': None,  # Missing timestamp
        'on_ground': None,  # Missing ground status
        'squawk': 'invalid'  # Invalid squawk
    }
]

# Missing data test cases
MISSING_DATA_CASES = [
    {
        'icao24': 'abcdef',
        'latitude': None,
        'longitude': None,
        'baro_altitude': None,
        'velocity': None,
        'heading': None,
        'vertical_rate': None,
        'callsign': None,
        'origin_country': None,
        'time_position': 1693401600,
        'last_contact': 1693401605,
        'on_ground': False,
        'squawk': None
    }
]

@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def sample_flight_data():
    """Sample valid flight data for testing."""
    return SAMPLE_FLIGHT_DATA.copy()

@pytest.fixture
def invalid_flight_data():
    """Sample invalid flight data for testing."""
    return INVALID_FLIGHT_DATA.copy()

@pytest.fixture
def missing_data_cases():
    """Sample data with missing values for testing."""
    return MISSING_DATA_CASES.copy()

@pytest.fixture
def sample_dataframe():
    """Sample pandas DataFrame with flight data."""
    return pd.DataFrame(SAMPLE_FLIGHT_DATA)

@pytest.fixture
def invalid_dataframe():
    """Sample pandas DataFrame with invalid flight data."""
    return pd.DataFrame(INVALID_FLIGHT_DATA)

@pytest.fixture
def missing_data_dataframe():
    """Sample pandas DataFrame with missing data."""
    return pd.DataFrame(MISSING_DATA_CASES)

@pytest.fixture
def large_dataframe():
    """Large DataFrame for performance testing."""
    # Create 10,000 records with variations
    import random
    data = []
    base_time = int(datetime.now(timezone.utc).timestamp())
    
    for i in range(10000):
        record = {
            'icao24': f'{random.randint(100000, 999999):06x}',
            'latitude': random.uniform(-90, 90),
            'longitude': random.uniform(-180, 180),
            'baro_altitude': random.uniform(0, 40000),
            'velocity': random.uniform(0, 600),
            'heading': random.uniform(0, 360),
            'vertical_rate': random.uniform(-3000, 3000),
            'callsign': f'FLT{random.randint(100, 999)}',
            'origin_country': random.choice(['United States', 'United Kingdom', 'Germany', 'France']),
            'time_position': base_time + i * 10,
            'last_contact': base_time + i * 10 + 5,
            'on_ground': random.choice([True, False]),
            'squawk': f'{random.randint(1000, 9999)}'
        }
        data.append(record)
    
    return pd.DataFrame(data)

@pytest.fixture
def sample_arrow_table():
    """Sample PyArrow table with flight data."""
    df = pd.DataFrame(SAMPLE_FLIGHT_DATA)
    # Add timestamp column that transformer expects
    df['timestamp'] = pd.to_datetime(df['time_position'], unit='s')
    return pa.Table.from_pandas(df)

@pytest.fixture
def temp_parquet_file(sample_dataframe):
    """Temporary Parquet file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        sample_dataframe.to_parquet(tmp.name, index=False)
        yield tmp.name
    os.unlink(tmp.name)

@pytest.fixture
def temp_json_file(sample_flight_data):
    """Temporary JSON file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(sample_flight_data, tmp, indent=2)
        tmp.flush()
        yield tmp.name
    os.unlink(tmp.name)

@pytest.fixture
def mock_s3():
    """Mock S3 client for testing."""
    with mock_aws():
        yield boto3.client('s3', region_name='us-east-1')

@pytest.fixture
def mock_cloudwatch():
    """Mock CloudWatch client for testing."""
    with mock_aws():
        yield boto3.client('cloudwatch', region_name='us-east-1')

@pytest.fixture
def mock_sns():
    """Mock SNS client for testing."""
    with mock_aws():
        yield boto3.client('sns', region_name='us-east-1')

@pytest.fixture
def s3_bucket(mock_s3):
    """Create a test S3 bucket."""
    bucket_name = 'test-flight-data-bucket'
    mock_s3.create_bucket(Bucket=bucket_name)
    return bucket_name

@pytest.fixture
def s3_parquet_file(mock_s3, s3_bucket, sample_dataframe):
    """Upload sample Parquet file to S3."""
    key = 'test-data/flight_data.parquet'
    
    # Convert DataFrame to Parquet bytes
    buffer = io.BytesIO()
    sample_dataframe.to_parquet(buffer, index=False)
    buffer.seek(0)
    
    # Upload to S3
    mock_s3.put_object(
        Bucket=s3_bucket,
        Key=key,
        Body=buffer.getvalue(),
        ContentType='application/octet-stream'
    )
    
    return {'bucket': s3_bucket, 'key': key}

@pytest.fixture
def sns_topic(mock_sns):
    """Create a test SNS topic."""
    response = mock_sns.create_topic(Name='test-flight-data-alerts')
    return response['TopicArn']

@pytest.fixture
def quality_config_basic():
    """Basic quality configuration for testing."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    import importlib
    lambda_module = importlib.import_module('lambda.data_quality.quality_validator')
    QualityConfig = lambda_module.QualityConfig
    
    return QualityConfig(
        completeness_weight=0.30,
        validity_weight=0.30,
        consistency_weight=0.25,
        timeliness_weight=0.15,
        quarantine_threshold=0.30,
        critical_fields_required=['icao24', 'latitude', 'longitude', 'time_position', 'last_contact'],
        important_fields_optional=['baro_altitude', 'velocity', 'callsign', 'origin_country']
    )

@pytest.fixture
def quality_config_strict():
    """Strict quality configuration for testing."""
    return {
        'completeness_weight': 0.30,
        'validity_weight': 0.30,
        'consistency_weight': 0.25,
        'timeliness_weight': 0.15,
        'quarantine_threshold': 0.95,
        'excellent_quality_threshold': 0.98,
        'good_quality_threshold': 0.95,
        'acceptable_quality_threshold': 0.90,
        'critical_fields_required': ['icao24', 'latitude', 'longitude', 'time_position', 'last_contact'],
        'important_fields_optional': ['baro_altitude', 'velocity', 'callsign', 'origin_country']
    }

@pytest.fixture
def transformation_config_basic():
    """Basic transformation configuration for testing."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    import importlib
    lambda_module = importlib.import_module('lambda.etl.data_transformer')
    TransformationConfig = lambda_module.TransformationConfig
    
    return TransformationConfig(
        enable_altitude_ft=True,
        enable_speed_knots=True,
        enable_distance_calculations=False,
        enable_rate_calculations=False,
        enable_flight_phase_detection=False,
        enable_speed_categorization=False,
        duplicate_detection_enabled=True,
        chunk_size=10000
    )

@pytest.fixture
def transformation_config_full():
    """Full transformation configuration for testing."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    import importlib
    lambda_module = importlib.import_module('lambda.etl.data_transformer')
    TransformationConfig = lambda_module.TransformationConfig
    
    return TransformationConfig(
        enable_altitude_ft=True,
        enable_speed_knots=True,
        enable_distance_calculations=True,
        enable_rate_calculations=True,
        enable_flight_phase_detection=True,
        enable_speed_categorization=True,
        duplicate_detection_enabled=True,
        chunk_size=10000
    )

@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for Lambda functions."""
    env_vars = {
        'PROCESSED_DATA_BUCKET': 'test-processed-data-bucket',
        'RAW_DATA_BUCKET': 'test-raw-data-bucket',
        'ALERT_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-alerts',
        'QUALITY_THRESHOLD': '0.8',
        'AWS_REGION': 'us-east-1'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars

@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = 'test-flight-data-processor'
    context.function_version = '1.0'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-flight-data-processor'
    context.memory_limit_in_mb = 512
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = 'test-request-id-123'
    return context

@pytest.fixture
def s3_event(s3_parquet_file):
    """Mock S3 event for Lambda testing."""
    return {
        'Records': [
            {
                'eventVersion': '2.1',
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                'eventTime': datetime.now(timezone.utc).isoformat(),
                's3': {
                    'bucket': {
                        'name': s3_parquet_file['bucket']
                    },
                    'object': {
                        'key': s3_parquet_file['key'],
                        'size': 1024
                    }
                }
            }
        ]
    }

@pytest.fixture
def api_failure_responses():
    """Mock API failure responses for testing error handling."""
    return {
        'timeout_error': Exception('Connection timeout'),
        'rate_limit_error': Exception('Rate limit exceeded'),
        'auth_error': Exception('Authentication failed'),
        'server_error': Exception('Internal server error'),
        'network_error': Exception('Network unreachable')
    }

@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = datetime.now()
        
        def stop(self):
            self.end_time = datetime.now()
        
        @property
        def elapsed_ms(self):
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time).total_seconds() * 1000
            return 0
        
        @property
        def elapsed_seconds(self):
            return self.elapsed_ms / 1000
    
    return Timer()

@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests."""
    import logging
    logging.getLogger().setLevel(logging.INFO)

# Parameterized test data
@pytest.fixture(params=[
    'completeness_check',
    'validity_check', 
    'consistency_check',
    'uniqueness_check',
    'accuracy_check',
    'timeliness_check',
    'altitude_range_check',
    'speed_range_check',
    'coordinate_validity_check',
    'anomaly_detection_check'
])
def quality_check_name(request):
    """Parameterized quality check names."""
    return request.param

@pytest.fixture(params=[
    ('drop', 'latitude'),
    ('interpolate', 'baro_altitude'),
    ('forward_fill', 'callsign'),
    ('backward_fill', 'squawk'),
    ('mode', 'origin_country'),
    ('mean', 'velocity')
])
def missing_value_strategy(request):
    """Parameterized missing value strategies."""
    return request.param

@pytest.fixture(params=[
    {'icao24': 'abcdef', 'expected': True},  # Valid
    {'icao24': '123456', 'expected': True},  # Valid
    {'icao24': 'ABCDEF', 'expected': True},  # Valid uppercase
    {'icao24': '12345', 'expected': False},  # Too short
    {'icao24': '1234567', 'expected': False},  # Too long
    {'icao24': 'GHIJKL', 'expected': False},  # Invalid hex
    {'icao24': '', 'expected': False},  # Empty
    {'icao24': None, 'expected': False},  # None
])
def icao24_test_case(request):
    """Parameterized ICAO24 test cases."""
    return request.param

@pytest.fixture(params=[
    {'lat': 40.7128, 'lon': -74.0060, 'expected': True},  # NYC
    {'lat': 51.4700, 'lon': -0.4543, 'expected': True},   # London
    {'lat': 0.0, 'lon': 0.0, 'expected': False},          # Null Island
    {'lat': 95.0, 'lon': -74.0060, 'expected': False},    # Invalid lat
    {'lat': 40.7128, 'lon': -190.0, 'expected': False},   # Invalid lon
    {'lat': None, 'lon': -74.0060, 'expected': False},    # Missing lat
    {'lat': 40.7128, 'lon': None, 'expected': False},     # Missing lon
])
def coordinate_test_case(request):
    """Parameterized coordinate test cases."""
    return request.param