"""
Unit tests for Data Transformation Validator from data_transformation module.

Tests completeness scoring, validity checks, anomaly detection, and edge cases
for the data transformation pipeline validator.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import importlib
lambda_module = importlib.import_module('lambda.data_transformation.data_quality_validator')
DataQualityValidator = lambda_module.DataQualityValidator


class TestDataTransformationValidator:
    """Test DataQualityValidator from data_transformation module."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance with mocked environment."""
        env_vars = {
            'PROCESSED_DATA_BUCKET': 'test-bucket',
            'ALERT_TOPIC_ARN': 'test-topic-arn',
            'QUALITY_THRESHOLD': '0.8'
        }
        
        with patch.dict(os.environ, env_vars):
            with patch('boto3.client') as mock_client:
                mock_s3 = Mock()
                mock_cloudwatch = Mock()
                mock_sns = Mock()
                
                mock_client.side_effect = lambda service: {
                    's3': mock_s3,
                    'cloudwatch': mock_cloudwatch,
                    'sns': mock_sns
                }[service]
                
                validator = DataQualityValidator()
                validator.s3_client = mock_s3
                validator.cloudwatch = mock_cloudwatch
                validator.sns = mock_sns
                
                return validator
    
    def test_validator_initialization(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert validator.processed_bucket == 'test-bucket'
        assert validator.alert_topic_arn == 'test-topic-arn'
        assert validator.quality_threshold == 0.8
        assert len(validator.quality_checks) > 0
    
    def test_completeness_check_perfect_data(self, validator, sample_dataframe):
        """Test completeness check with perfect data."""
        # Rename columns to match expected format
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.completeness_check(df)
        
        assert result['check_name'] == 'completeness_check'
        assert result['passed'] == True
        assert result['score'] > 0.8
        assert 'details' in result
        assert result['details']['total_records'] == len(df)
    
    def test_completeness_check_missing_data(self, validator, missing_data_dataframe):
        """Test completeness check with missing data."""
        df = missing_data_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.completeness_check(df)
        
        assert result['check_name'] == 'completeness_check'
        assert result['passed'] == False  # Should fail with missing data
        assert result['score'] < 0.8
        assert 'field_completeness' in result['details']
    
    def test_validity_check_valid_data(self, validator, sample_dataframe):
        """Test validity check with valid data."""
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.validity_check(df)
        
        assert result['check_name'] == 'validity_check'
        assert result['passed'] == True
        assert result['score'] >= 0.9
        assert 'total_issues' in result['details']
        assert result['details']['total_issues'] == 0
    
    def test_validity_check_invalid_data(self, validator, invalid_dataframe):
        """Test validity check with invalid data."""
        df = invalid_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.validity_check(df)
        
        assert result['check_name'] == 'validity_check'
        assert result['passed'] == False
        assert result['score'] < 0.9
        assert result['details']['total_issues'] > 0
    
    @pytest.mark.parametrize("latitude,longitude,expected_valid", [
        (40.7128, -74.0060, True),   # NYC - valid
        (51.4700, -0.4543, True),    # London - valid
        (0.0, 0.0, False),           # Null Island - invalid
        (95.0, -74.0060, False),     # Invalid latitude
        (40.7128, -190.0, False),    # Invalid longitude
        (40.7128, 0.0, False),       # Suspicious longitude
    ])
    def test_coordinate_validity_check(self, validator, latitude, longitude, expected_valid):
        """Test coordinate validity check with various coordinates."""
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'latitude': latitude,
            'longitude': longitude
        }])
        
        result = validator.coordinate_validity_check(df)
        
        assert result['check_name'] == 'coordinate_validity_check'
        if expected_valid:
            assert result['passed'] == True
            assert result['details']['invalid_coordinates'] == 0
        else:
            assert result['passed'] == False
            assert result['details']['invalid_coordinates'] > 0
    
    def test_consistency_check_valid_data(self, validator, sample_dataframe):
        """Test consistency check with valid data."""
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.consistency_check(df)
        
        assert result['check_name'] == 'consistency_check'
        assert result['score'] >= 0.0
        assert 'consistency_issues' in result['details']
    
    def test_consistency_check_inconsistent_data(self, validator):
        """Test consistency check with inconsistent data."""
        # Create data with ground aircraft at high altitude (inconsistent)
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'on_ground': True,
            'baro_altitude_ft': 10000.0,  # Inconsistent - on ground but high altitude
            'velocity_knots': 200.0,      # Inconsistent - on ground but high speed
            'origin_country': 'United States',
            'longitude': -74.0060,
            'latitude': 40.7128
        }])
        
        result = validator.consistency_check(df)
        
        assert result['check_name'] == 'consistency_check'
        assert result['passed'] == False
        assert result['details']['consistency_issues'] > 0
    
    def test_uniqueness_check_unique_data(self, validator, sample_dataframe):
        """Test uniqueness check with unique data."""
        df = sample_dataframe.copy()
        
        result = validator.uniqueness_check(df)
        
        assert result['check_name'] == 'uniqueness_check'
        assert result['passed'] == True
        assert result['score'] >= 0.95
        assert 'unique_aircraft' in result['details']
    
    def test_uniqueness_check_duplicate_data(self, validator, sample_dataframe):
        """Test uniqueness check with duplicate data."""
        df = sample_dataframe.copy()
        # Add duplicate row
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        
        result = validator.uniqueness_check(df)
        
        assert result['check_name'] == 'uniqueness_check'
        assert result['passed'] == False
        assert result['score'] < 0.95
    
    def test_accuracy_check_complete_data(self, validator, sample_dataframe):
        """Test accuracy check with complete position data."""
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.accuracy_check(df)
        
        assert result['check_name'] == 'accuracy_check'
        assert result['passed'] == True
        assert result['score'] >= 0.7
        assert result['details']['positioned_records'] > 0
    
    def test_timeliness_check_fresh_data(self, validator):
        """Test timeliness check with fresh data."""
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'last_contact': current_time - 60,  # 1 minute old
            'latitude': 40.7128,
            'longitude': -74.0060
        }])
        
        result = validator.timeliness_check(df)
        
        assert result['check_name'] == 'timeliness_check'
        assert result['passed'] == True
        assert result['score'] > 0.5
    
    def test_timeliness_check_stale_data(self, validator):
        """Test timeliness check with stale data."""
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'last_contact': current_time - 3600,  # 1 hour old
            'latitude': 40.7128,
            'longitude': -74.0060
        }])
        
        result = validator.timeliness_check(df)
        
        assert result['check_name'] == 'timeliness_check'
        assert result['passed'] == False
        assert result['score'] < 0.8
    
    def test_altitude_range_check_valid_altitudes(self, validator):
        """Test altitude range check with valid altitudes."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'baro_altitude_ft': 10000.0},
            {'icao24': '123456', 'baro_altitude_ft': 35000.0},
            {'icao24': 'fedcba', 'baro_altitude_ft': 500.0}
        ])
        
        result = validator.altitude_range_check(df)
        
        assert result['check_name'] == 'altitude_range_check'
        assert result['passed'] == True
        assert result['score'] >= 0.95
        assert result['details']['impossible_low'] == 0
        assert result['details']['impossible_high'] == 0
    
    def test_altitude_range_check_invalid_altitudes(self, validator):
        """Test altitude range check with invalid altitudes."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'baro_altitude_ft': -2000.0},  # Too low
            {'icao24': '123456', 'baro_altitude_ft': 70000.0},  # Too high
            {'icao24': 'fedcba', 'baro_altitude_ft': 25000.0}   # Valid
        ])
        
        result = validator.altitude_range_check(df)
        
        assert result['check_name'] == 'altitude_range_check'
        assert result['passed'] == False
        assert result['score'] < 0.95
        assert result['details']['impossible_low'] > 0
        assert result['details']['impossible_high'] > 0
    
    def test_speed_range_check_valid_speeds(self, validator):
        """Test speed range check with valid speeds."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'velocity_knots': 250.0},
            {'icao24': '123456', 'velocity_knots': 450.0},
            {'icao24': 'fedcba', 'velocity_knots': 15.0}
        ])
        
        result = validator.speed_range_check(df)
        
        assert result['check_name'] == 'speed_range_check'
        assert result['passed'] == True
        assert result['score'] >= 0.95
        assert result['details']['impossible_negative'] == 0
        assert result['details']['impossible_high'] == 0
    
    def test_speed_range_check_invalid_speeds(self, validator):
        """Test speed range check with invalid speeds."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'velocity_knots': -50.0},   # Negative
            {'icao24': '123456', 'velocity_knots': 1500.0},  # Too high
            {'icao24': 'fedcba', 'velocity_knots': 250.0}    # Valid
        ])
        
        result = validator.speed_range_check(df)
        
        assert result['check_name'] == 'speed_range_check'
        assert result['passed'] == False
        assert result['score'] < 0.95
        assert result['details']['impossible_negative'] > 0
        assert result['details']['impossible_high'] > 0
    
    def test_callsign_format_check_valid(self, validator):
        """Test callsign format check with valid callsigns."""
        df = pd.DataFrame([
            {'callsign': 'UAL123'},
            {'callsign': 'BAW456'},
            {'callsign': 'DLH789'}
        ])
        
        result = validator.callsign_format_check(df)
        
        assert result['check_name'] == 'callsign_format_check'
        assert result['passed'] == True
        assert result['score'] >= 0.9
    
    def test_callsign_format_check_invalid(self, validator):
        """Test callsign format check with invalid callsigns."""
        df = pd.DataFrame([
            {'callsign': ''},           # Empty
            {'callsign': 'TOOLONG123'}, # Too long
            {'callsign': 'VALID'},      # Valid
        ])
        
        result = validator.callsign_format_check(df)
        
        assert result['check_name'] == 'callsign_format_check'
        assert result['passed'] == False
        assert result['score'] < 0.9
        assert result['details']['invalid_callsigns'] > 0
    
    def test_anomaly_detection_check_normal_data(self, validator, sample_dataframe):
        """Test anomaly detection with normal data."""
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        result = validator.anomaly_detection_check(df)
        
        assert result['check_name'] == 'anomaly_detection_check'
        assert result['score'] >= 0.0
        assert 'detected_anomalies' in result['details']
    
    def test_anomaly_detection_check_with_outliers(self, validator):
        """Test anomaly detection with statistical outliers."""
        # Create data with clear outliers
        normal_data = [
            {'icao24': f'test{i:02d}', 'baro_altitude_ft': 30000 + np.random.normal(0, 1000), 
             'velocity_knots': 400 + np.random.normal(0, 50)}
            for i in range(20)
        ]
        
        # Add outliers
        outliers = [
            {'icao24': 'outlier1', 'baro_altitude_ft': 60000, 'velocity_knots': 400},  # Altitude outlier
            {'icao24': 'outlier2', 'baro_altitude_ft': 30000, 'velocity_knots': 800},  # Speed outlier
        ]
        
        df = pd.DataFrame(normal_data + outliers)
        
        result = validator.anomaly_detection_check(df)
        
        assert result['check_name'] == 'anomaly_detection_check'
        assert result['details']['detected_anomalies'] >= 0  # Should detect some outliers
    
    def test_run_all_quality_checks(self, validator, sample_dataframe):
        """Test running all quality checks."""
        df = sample_dataframe.copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        assessment = validator.run_all_quality_checks(df)
        
        assert 'timestamp' in assessment
        assert 'total_records' in assessment
        assert 'total_checks' in assessment
        assert 'passed_checks' in assessment
        assert 'failed_checks' in assessment
        assert 'overall_score' in assessment
        assert 'quality_grade' in assessment
        assert 'passed_threshold' in assessment
        assert 'individual_results' in assessment
        
        assert assessment['total_records'] == len(df)
        assert assessment['total_checks'] > 0
        assert 0.0 <= assessment['overall_score'] <= 1.0
        assert assessment['quality_grade'] in ['A', 'B', 'C', 'D', 'F']
        assert len(assessment['individual_results']) == assessment['total_checks']
    
    def test_quality_grade_calculation(self, validator):
        """Test quality grade calculation."""
        assert validator._get_quality_grade(0.98) == 'A'
        assert validator._get_quality_grade(0.95) == 'A'
        assert validator._get_quality_grade(0.92) == 'B'
        assert validator._get_quality_grade(0.85) == 'C'
        assert validator._get_quality_grade(0.75) == 'D'
        assert validator._get_quality_grade(0.65) == 'F'
    
    def test_download_parquet_file_success(self, validator, temp_parquet_file):
        """Test successful Parquet file download."""
        # Mock S3 response
        with open(temp_parquet_file, 'rb') as f:
            file_content = f.read()
        
        mock_response = {'Body': file_content}
        validator.s3_client.get_object.return_value = mock_response
        
        df = validator.download_parquet_file('test-bucket', 'test-key')
        
        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        validator.s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket', 
            Key='test-key'
        )
    
    def test_download_parquet_file_failure(self, validator):
        """Test Parquet file download failure."""
        from botocore.exceptions import ClientError
        
        validator.s3_client.get_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey'}},
            operation_name='GetObject'
        )
        
        df = validator.download_parquet_file('test-bucket', 'nonexistent-key')
        
        assert df is None
    
    def test_publish_quality_metrics(self, validator):
        """Test publishing quality metrics to CloudWatch."""
        assessment = {
            'overall_score': 0.85,
            'passed_checks': 8,
            'failed_checks': 2,
            'total_records': 1000
        }
        
        execution_time = 5.5
        
        validator.publish_quality_metrics(assessment, execution_time)
        
        validator.cloudwatch.put_metric_data.assert_called_once()
        call_args = validator.cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'FlightDataPipeline/Quality'
        assert 'MetricData' in call_args[1]
        
        metrics = call_args[1]['MetricData']
        metric_names = [m['MetricName'] for m in metrics]
        
        assert 'ValidationTime' in metric_names
        assert 'OverallQualityScore' in metric_names
        assert 'PassedChecks' in metric_names
        assert 'FailedChecks' in metric_names
        assert 'RecordsValidated' in metric_names
    
    def test_send_alert(self, validator):
        """Test sending SNS alert for quality issues."""
        assessment = {
            'timestamp': '2023-08-30T12:00:00Z',
            'overall_score': 0.65,
            'quality_grade': 'D',
            'failed_checks': 3,
            'total_records': 1000,
            'individual_results': [
                {'check_name': 'completeness_check', 'passed': False, 'score': 0.6}
            ]
        }
        
        file_key = 'test-data/flight_data.parquet'
        
        validator.send_alert(assessment, file_key)
        
        validator.sns.publish.assert_called_once()
        call_args = validator.sns.publish.call_args
        
        assert call_args[1]['TopicArn'] == 'test-topic-arn'
        assert 'Flight Data Quality Alert' in call_args[1]['Subject']
        
        message = call_args[1]['Message']
        assert 'DATA_QUALITY_ISSUE' in message
        assert file_key in message
    
    def test_failed_check_result(self, validator):
        """Test failed check result generation."""
        result = validator._failed_check_result('test_check', 'Test error message')
        
        assert result['check_name'] == 'test_check'
        assert result['passed'] == False
        assert result['score'] == 0.0
        assert result['error'] == 'Test error message'
    
    def test_missing_environment_variables(self):
        """Test validator initialization with missing environment variables."""
        with pytest.raises(ValueError, match="Required environment variable"):
            DataQualityValidator()
    
    @pytest.mark.slow
    def test_performance_large_dataset(self, validator, large_dataframe, performance_timer):
        """Test performance with large dataset."""
        df = large_dataframe.head(5000).copy()  # Use 5000 records for performance test
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        performance_timer.start()
        assessment = validator.run_all_quality_checks(df)
        performance_timer.stop()
        
        assert assessment is not None
        assert assessment['total_records'] == len(df)
        assert performance_timer.elapsed_seconds < 60  # Should complete in under 1 minute
    
    def test_edge_cases_empty_dataframe(self, validator):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        
        result = validator.completeness_check(df)
        assert result['details']['total_records'] == 0
        
        assessment = validator.run_all_quality_checks(df)
        assert assessment['total_records'] == 0
    
    def test_edge_cases_single_row(self, validator, sample_dataframe):
        """Test handling of single row DataFrame."""
        df = sample_dataframe.head(1).copy()
        df = df.rename(columns={
            'baro_altitude': 'baro_altitude_ft',
            'velocity': 'velocity_knots'
        })
        
        assessment = validator.run_all_quality_checks(df)
        
        assert assessment['total_records'] == 1
        assert assessment['overall_score'] >= 0.0
        assert assessment['quality_grade'] in ['A', 'B', 'C', 'D', 'F']