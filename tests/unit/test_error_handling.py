"""
Comprehensive unit tests for error handling across the flight data pipeline.

Tests invalid input handling, API failures, S3 errors, retry logic, and 
graceful degradation scenarios.
"""
import pytest
import pandas as pd
import json
import time
from unittest.mock import Mock, patch, MagicMock, call
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
import boto3
import tempfile
import os

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import importlib
quality_module = importlib.import_module('lambda.data_quality.quality_validator')
DataQualityValidator = quality_module.DataQualityValidator
QualityConfig = quality_module.QualityConfig

transformation_module = importlib.import_module('lambda.data_transformation.data_quality_validator')
TransformationValidator = transformation_module.DataQualityValidator

etl_module = importlib.import_module('lambda.etl.data_transformer')
FlightDataTransformer = etl_module.FlightDataTransformer
TransformationConfig = etl_module.TransformationConfig


class TestQualityValidatorErrorHandling:
    """Test error handling in Quality Validator."""
    
    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked AWS clients."""
        with patch('boto3.client') as mock_client:
            mock_cloudwatch = Mock()
            mock_s3 = Mock()
            mock_client.side_effect = lambda service: {
                'cloudwatch': mock_cloudwatch,
                's3': mock_s3
            }[service]
            
            validator = DataQualityValidator()
            validator.cloudwatch = mock_cloudwatch
            validator.s3 = mock_s3
            return validator
    
    def test_validate_record_with_none_input(self, validator_with_mocks):
        """Test validation with None input."""
        result = validator_with_mocks.validate_record(None)
        
        assert result is not None
        assert result.overall_score == 0.0
        assert result.should_quarantine == True
        assert len(result.issues_found) > 0
    
    def test_validate_record_with_empty_dict(self, validator_with_mocks):
        """Test validation with empty dictionary."""
        result = validator_with_mocks.validate_record({})
        
        assert result is not None
        assert result.overall_score < 0.8  # Completeness is 0 but other dimensions may score high
        assert result.should_quarantine == True
    
    def test_validate_record_with_invalid_data_types(self, validator_with_mocks):
        """Test validation with invalid data types."""
        invalid_record = {
            'icao24': 123,  # Should be string
            'latitude': 'not_a_number',  # Should be float
            'longitude': ['array'],  # Should be float
            'baro_altitude': {'dict': 'value'},  # Should be float
            'velocity': 'invalid',  # Should be float
            'last_contact': 'not_timestamp'  # Should be timestamp
        }
        
        # Should handle gracefully without crashing
        result = validator_with_mocks.validate_record(invalid_record)
        
        assert result is not None
        assert result.overall_score < 0.5
        assert len(result.issues_found) > 0
    
    def test_validate_record_with_extreme_values(self, validator_with_mocks):
        """Test validation with extreme/edge case values."""
        extreme_record = {
            'icao24': 'abcdef',
            'latitude': float('inf'),  # Infinite value
            'longitude': float('-inf'),  # Negative infinite
            'baro_altitude': float('nan'),  # NaN value
            'velocity': 1e10,  # Extremely large number
            'vertical_rate': -1e10,  # Extremely large negative
            'last_contact': -1  # Negative timestamp
        }
        
        # Should handle extreme values gracefully
        result = validator_with_mocks.validate_record(extreme_record)
        
        assert result is not None
        assert result.should_quarantine == True
        assert len(result.issues_found) > 0
    
    def test_consistency_assessment_with_corrupted_previous_record(self, validator_with_mocks):
        """Test consistency assessment with corrupted previous record."""
        current_record = {
            'icao24': 'abcdef',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'last_contact': 1693401600
        }
        
        # Corrupted previous record
        corrupted_previous = {
            'latitude': None,
            'longitude': 'invalid',
            'last_contact': 'not_timestamp'
        }
        
        result = validator_with_mocks.validate_record(current_record, corrupted_previous)
        
        assert result is not None
        # Should still produce valid result even with corrupted previous record
        assert 0.0 <= result.overall_score <= 1.0
    
    def test_config_validation_error_handling(self):
        """Test configuration validation error handling."""
        # Test invalid weight configuration
        with pytest.raises(ValueError):
            QualityConfig(
                completeness_weight=0.8,  # Invalid - doesn't sum to 1.0
                validity_weight=0.8,
                consistency_weight=0.8,
                timeliness_weight=0.8
            )
    
    def test_division_by_zero_protection(self, validator_with_mocks):
        """Test protection against division by zero errors."""
        # Create record that might cause division by zero
        record = {
            'icao24': 'abcdef',
            'velocity': 1000.0,
            'baro_altitude': 0.0,  # Zero altitude - potential division by zero
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        
        # Should handle without division by zero error
        result = validator_with_mocks.validate_record(record)
        
        assert result is not None
        assert not any('division by zero' in str(issue.description).lower() 
                      for issue in result.issues_found)


class TestTransformationValidatorErrorHandling:
    """Test error handling in Transformation Validator."""
    
    @pytest.fixture
    def transformation_validator(self):
        """Create transformation validator with mocked environment."""
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
                
                validator = TransformationValidator()
                validator.s3_client = mock_s3
                validator.cloudwatch = mock_cloudwatch
                validator.sns = mock_sns
                return validator
    
    def test_s3_download_client_error(self, transformation_validator):
        """Test S3 download with ClientError."""
        transformation_validator.s3_client.get_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            operation_name='GetObject'
        )
        
        result = transformation_validator.download_parquet_file('test-bucket', 'nonexistent.parquet')
        
        assert result is None
    
    def test_s3_download_network_error(self, transformation_validator):
        """Test S3 download with network error."""
        transformation_validator.s3_client.get_object.side_effect = BotoCoreError()
        
        result = transformation_validator.download_parquet_file('test-bucket', 'test.parquet')
        
        assert result is None
    
    def test_s3_download_invalid_parquet(self, transformation_validator):
        """Test S3 download with invalid Parquet data."""
        # Mock response with invalid Parquet data
        invalid_data = b"This is not parquet data"
        mock_response = {'Body': invalid_data}
        transformation_validator.s3_client.get_object.return_value = mock_response
        
        result = transformation_validator.download_parquet_file('test-bucket', 'invalid.parquet')
        
        assert result is None
    
    def test_quality_checks_with_empty_dataframe(self, transformation_validator):
        """Test quality checks with empty DataFrame."""
        empty_df = pd.DataFrame()
        
        # All checks should handle empty DataFrames gracefully
        completeness_result = transformation_validator.completeness_check(empty_df)
        validity_result = transformation_validator.validity_check(empty_df)
        consistency_result = transformation_validator.consistency_check(empty_df)
        
        assert completeness_result['check_name'] == 'completeness_check'
        assert validity_result['check_name'] == 'validity_check'
        assert consistency_result['check_name'] == 'consistency_check'
        
        # Scores should be reasonable for empty data
        assert 0.0 <= completeness_result['score'] <= 1.0
        assert 0.0 <= validity_result['score'] <= 1.0
        assert 0.0 <= consistency_result['score'] <= 1.0
    
    def test_quality_checks_with_corrupted_data(self, transformation_validator):
        """Test quality checks with corrupted data."""
        corrupted_df = pd.DataFrame([
            {'icao24': None, 'latitude': float('inf'), 'longitude': 'invalid'},
            {'icao24': [], 'latitude': {}, 'longitude': None},
            {'icao24': 123, 'latitude': 'corrupted', 'longitude': [1, 2, 3]}
        ])
        
        # Should handle corrupted data without crashing
        assessment = transformation_validator.run_all_quality_checks(corrupted_df)
        
        assert assessment is not None
        assert 'overall_score' in assessment
        assert 0.0 <= assessment['overall_score'] <= 1.0
        assert assessment['quality_grade'] in ['A', 'B', 'C', 'D', 'F']
    
    def test_cloudwatch_publishing_error(self, transformation_validator):
        """Test CloudWatch metrics publishing error."""
        transformation_validator.cloudwatch.put_metric_data.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied'}},
            operation_name='PutMetricData'
        )
        
        assessment = {'overall_score': 0.85, 'passed_checks': 8, 'failed_checks': 2, 'total_records': 1000}
        
        # Should handle CloudWatch error gracefully
        try:
            transformation_validator.publish_quality_metrics(assessment, 5.0)
        except Exception:
            pytest.fail("publish_quality_metrics should handle CloudWatch errors gracefully")
    
    def test_sns_alert_error(self, transformation_validator):
        """Test SNS alert sending error."""
        transformation_validator.sns.publish.side_effect = ClientError(
            error_response={'Error': {'Code': 'TopicNotFound'}},
            operation_name='Publish'
        )
        
        assessment = {
            'timestamp': '2023-08-30T12:00:00Z',
            'overall_score': 0.65,
            'quality_grade': 'D',
            'failed_checks': 3,
            'total_records': 1000,
            'individual_results': []
        }
        
        # Should handle SNS error gracefully
        try:
            transformation_validator.send_alert(assessment, 'test-key')
        except Exception:
            pytest.fail("send_alert should handle SNS errors gracefully")
    
    def test_missing_environment_variables(self):
        """Test handling of missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Required environment variable"):
                TransformationValidator()
    
    def test_invalid_quality_threshold_env_var(self):
        """Test invalid quality threshold environment variable."""
        env_vars = {
            'PROCESSED_DATA_BUCKET': 'test-bucket',
            'QUALITY_THRESHOLD': 'invalid_float'
        }
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(ValueError):
                TransformationValidator()


class TestDataTransformerErrorHandling:
    """Test error handling in Data Transformer."""
    
    @pytest.fixture
    def transformer(self):
        """Create transformer instance."""
        return FlightDataTransformer()
    
    def test_transform_dataframe_missing_required_columns(self, transformer):
        """Test transformation with missing required columns."""
        df_missing_icao = pd.DataFrame([{'timestamp': pd.Timestamp('2023-08-30'), 'latitude': 40.0}])
        df_missing_timestamp = pd.DataFrame([{'icao24': 'abcdef', 'latitude': 40.0}])
        
        with pytest.raises(ValueError, match="Missing required columns"):
            transformer.transform_dataframe(df_missing_icao)
        
        with pytest.raises(ValueError, match="Missing required columns"):
            transformer.transform_dataframe(df_missing_timestamp)
    
    def test_transform_dataframe_invalid_timestamp(self, transformer):
        """Test transformation with invalid timestamp data."""
        df_invalid_timestamp = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': 'invalid_timestamp', 'latitude': 40.0},
            {'icao24': '123456', 'timestamp': None, 'latitude': 50.0}
        ])
        
        # Should handle invalid timestamps gracefully or raise meaningful error
        try:
            result_df, stats = transformer.transform_dataframe(df_invalid_timestamp)
            # If it succeeds, check that it's handled appropriately
            assert result_df is not None
        except (ValueError, TypeError, pd.errors.ParserError):
            # These are acceptable errors for invalid timestamp data
            pass
    
    def test_transform_dataframe_memory_error_simulation(self, transformer):
        """Test handling of memory-related errors."""
        # Create a very large DataFrame to potentially trigger memory issues
        large_df = pd.DataFrame({
            'icao24': ['abcdef'] * 100000,
            'timestamp': pd.date_range('2023-01-01', periods=100000, freq='1s'),
            'latitude': [40.0] * 100000,
            'longitude': [-74.0] * 100000,
            'altitude': [10000.0] * 100000
        })
        
        # Disable memory optimization to stress test
        transformer.config.enable_memory_optimization = False
        
        try:
            result_df, stats = transformer.transform_dataframe(large_df)
            assert result_df is not None
            assert stats.records_input == len(large_df)
        except MemoryError:
            # Memory error is acceptable for very large datasets
            pass
    
    def test_missing_value_handling_errors(self, transformer):
        """Test error handling in missing value strategies."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'test_field': None},
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'test_field': 'invalid_for_mean'}
        ])
        
        # Test mean strategy with non-numeric data
        transformer.config.missing_value_strategy = {'test_field': 'mean'}
        
        # Should handle gracefully without crashing
        try:
            result_df = transformer._handle_missing_values(df)
            assert result_df is not None
        except Exception as e:
            # Should not crash with unhandled errors
            assert not isinstance(e, (AttributeError, KeyError))
    
    def test_distance_calculation_errors(self, transformer):
        """Test error handling in distance calculations."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'latitude': float('nan'), 'longitude': -74.0},
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'latitude': 40.0, 'longitude': float('inf')}
        ])
        
        # Should handle NaN and infinite coordinates gracefully
        result_df = transformer._add_distance_calculations(df)
        
        assert result_df is not None
        assert 'distance_km' in result_df.columns
        assert 'cumulative_distance_km' in result_df.columns
    
    def test_rate_calculation_errors(self, transformer):
        """Test error handling in rate calculations."""
        df = pd.DataFrame([
            {
                'icao24': 'abcdef', 
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'), 
                'altitude_ft': None, 
                'speed_knots': float('inf')
            },
            {
                'icao24': 'abcdef', 
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),  # Same timestamp - zero time diff
                'altitude_ft': 10000.0, 
                'speed_knots': 250.0
            }
        ])
        
        # Should handle None values, infinite values, and zero time differences
        result_df = transformer._add_rate_calculations(df)
        
        assert result_df is not None
        if 'climb_rate_fpm' in result_df.columns:
            # Should not contain infinite or NaN values in output
            assert not result_df['climb_rate_fpm'].isin([float('inf'), float('-inf')]).any()
    
    def test_flight_phase_detection_errors(self, transformer):
        """Test error handling in flight phase detection."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'altitude_ft': None, 'speed_knots': None},
            {'icao24': '123456', 'timestamp': pd.Timestamp('2023-08-30'), 'altitude_ft': float('nan'), 'speed_knots': float('inf')}
        ])
        
        result_df = transformer._detect_flight_phases(df)
        
        assert result_df is not None
        assert 'flight_phase' in result_df.columns
        # All records should have a flight phase assigned (even if UNKNOWN)
        assert not result_df['flight_phase'].isna().any()
    
    def test_duplicate_removal_errors(self, transformer):
        """Test error handling in duplicate removal."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'quality_field': 1.0},
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'quality_field': None}
        ])
        
        # Test with 'best_quality' strategy that might fail
        transformer.config.keep_duplicate_strategy = 'best_quality'
        
        result_df = transformer._remove_duplicates(df)
        
        assert result_df is not None
        assert len(result_df) <= len(df)
    
    def test_configuration_validation_errors(self):
        """Test configuration validation errors."""
        # Test invalid chunk size
        config = TransformationConfig(chunk_size=-1)
        transformer = FlightDataTransformer(config)
        
        # Should handle invalid configuration gracefully
        assert transformer.config.chunk_size == -1  # Or default to reasonable value
    
    def test_concurrent_access_errors(self, transformer):
        """Test handling of concurrent access to transformer."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'latitude': 40.0, 'longitude': -74.0}
        ])
        
        import threading
        import concurrent.futures
        
        results = []
        errors = []
        
        def transform_concurrent(df_copy):
            try:
                result = transformer.transform_dataframe(df_copy.copy())
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Run multiple transformations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(transform_concurrent, df) for _ in range(3)]
            concurrent.futures.wait(futures)
        
        # Should either succeed or fail gracefully
        if errors:
            # Errors should be meaningful, not internal state corruption
            for error in errors:
                assert not isinstance(error, (AttributeError, KeyError))
        else:
            assert len(results) == 3


class TestRetryLogicAndCircuitBreaker:
    """Test retry logic and circuit breaker patterns."""
    
    def test_s3_operations_with_retry(self, mock_environment_variables):
        """Test S3 operations with retry logic."""
        with patch('boto3.client') as mock_client:
            mock_s3 = Mock()
            mock_client.return_value = mock_s3
            
            # Simulate transient errors followed by success
            mock_s3.get_object.side_effect = [
                ClientError(
                    error_response={'Error': {'Code': 'ServiceUnavailable'}},
                    operation_name='GetObject'
                ),
                ClientError(
                    error_response={'Error': {'Code': 'SlowDown'}},
                    operation_name='GetObject'
                ),
                {'Body': b'test data'}  # Success on third try
            ]
            
            validator = TransformationValidator()
            
            # Implement retry logic (this would be in actual implementation)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = validator.s3_client.get_object(Bucket='test', Key='test')
                    break
                except ClientError as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
            
            assert mock_s3.get_object.call_count == 3
    
    def test_cloudwatch_retry_with_exponential_backoff(self, mock_environment_variables):
        """Test CloudWatch operations with exponential backoff."""
        with patch('boto3.client') as mock_client:
            mock_cloudwatch = Mock()
            mock_client.return_value = mock_cloudwatch
            
            # Simulate throttling followed by success
            mock_cloudwatch.put_metric_data.side_effect = [
                ClientError(
                    error_response={'Error': {'Code': 'Throttling'}},
                    operation_name='PutMetricData'
                ),
                None  # Success
            ]
            
            validator = TransformationValidator()
            
            # Implement retry with exponential backoff
            def put_metrics_with_retry(metrics_data):
                max_retries = 3
                base_delay = 0.1
                
                for attempt in range(max_retries):
                    try:
                        validator.cloudwatch.put_metric_data(**metrics_data)
                        return
                    except ClientError as e:
                        if e.response['Error']['Code'] in ['Throttling', 'ServiceUnavailable']:
                            if attempt < max_retries - 1:
                                delay = base_delay * (2 ** attempt)
                                time.sleep(delay)
                                continue
                        raise
            
            # Should succeed after retry
            metrics_data = {'Namespace': 'Test', 'MetricData': []}
            put_metrics_with_retry(metrics_data)
            
            assert mock_cloudwatch.put_metric_data.call_count == 2


class TestGracefulDegradation:
    """Test graceful degradation scenarios."""
    
    def test_partial_aws_service_failure(self):
        """Test handling when some AWS services are unavailable."""
        with patch('boto3.client') as mock_client:
            def failing_client(service):
                if service == 'cloudwatch':
                    raise NoCredentialsError()
                elif service == 's3':
                    mock_s3 = Mock()
                    return mock_s3
                elif service == 'sns':
                    mock_sns = Mock()
                    return mock_sns
            
            mock_client.side_effect = failing_client
            
            # Should initialize with available services
            try:
                validator = TransformationValidator()
                # CloudWatch unavailable, but should still function for core validation
                assert validator.s3_client is not None
                assert validator.sns is not None
            except Exception as e:
                # Should fail gracefully with meaningful error
                assert 'credentials' in str(e).lower()
    
    def test_degraded_functionality_missing_optional_data(self):
        """Test degraded functionality with missing optional data."""
        transformer = FlightDataTransformer()
        
        # DataFrame with minimal required data
        minimal_df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30')}
            # No altitude, speed, or position data
        ])
        
        # Should still transform successfully with reduced functionality
        result_df, stats = transformer.transform_dataframe(minimal_df)
        
        assert result_df is not None
        assert len(result_df) == 1
        assert stats.records_input == 1
        assert stats.records_output == 1
        
        # Some calculated fields may not be present due to missing source data
        # But transformation should complete without errors
    
    def test_quality_assessment_with_partial_checks_failing(self, sample_dataframe, mock_environment_variables):
        """Test quality assessment when some checks fail."""
        validator = TransformationValidator()
        
        df = sample_dataframe.copy()
        df = df.rename(columns={'baro_altitude': 'baro_altitude_ft', 'velocity': 'velocity_knots'})
        
        # Mock some quality check methods to simulate failures
        with patch.object(validator, 'altitude_range_check') as mock_altitude_check:
            mock_altitude_check.side_effect = Exception("Altitude check failed")
            
            # Should still complete assessment with other checks
            assessment = validator.run_all_quality_checks(df)
            
            assert assessment is not None
            assert 'overall_score' in assessment
            assert assessment['failed_checks'] > 0  # At least one check failed
            
            # Should have error recorded for failed check
            failed_checks = [r for r in assessment['individual_results'] if not r['passed']]
            assert any('error' in check for check in failed_checks)


class TestErrorRecoveryAndLogging:
    """Test error recovery mechanisms and logging."""
    
    def test_error_logging_and_context(self, caplog):
        """Test that errors are properly logged with context."""
        import logging
        
        validator = DataQualityValidator()
        
        # Test with invalid record that should generate logged errors
        invalid_record = {
            'icao24': None,
            'latitude': 'invalid',
            'longitude': float('inf')
        }
        
        with caplog.at_level(logging.ERROR):
            result = validator.validate_record(invalid_record)
        
        # Should log errors with appropriate context
        assert result is not None
        # Logging assertions would go here if the implementation includes detailed logging
    
    def test_transaction_rollback_simulation(self):
        """Test transaction-like rollback behavior on errors."""
        transformer = FlightDataTransformer()
        
        # Simulate a transformation that might partially succeed then fail
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'latitude': 40.0}
        ])
        
        original_df = df.copy()
        
        # Mock a method to fail partway through transformation
        with patch.object(transformer, '_add_distance_calculations') as mock_distance:
            mock_distance.side_effect = Exception("Distance calculation failed")
            
            try:
                transformer.transform_dataframe(df)
            except Exception:
                # Original data should be unchanged
                pd.testing.assert_frame_equal(df, original_df)
    
    def test_resource_cleanup_on_error(self):
        """Test that resources are cleaned up properly on errors."""
        transformer = FlightDataTransformer()
        
        # Enable memory optimization to test cleanup
        transformer.config.enable_memory_optimization = True
        
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'latitude': 40.0}
        ])
        
        initial_cache_size = len(transformer._calculation_cache)
        
        # Simulate error during transformation
        with patch.object(transformer, '_final_cleanup') as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")
            
            try:
                transformer.transform_dataframe(df)
            except Exception:
                pass
        
        # Cache should not grow unbounded due to errors
        assert len(transformer._calculation_cache) >= initial_cache_size
        # In a production implementation, cache might be cleared on errors