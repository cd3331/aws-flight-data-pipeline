"""
Complete Pipeline Integration Tests

Tests end-to-end data flow, error scenarios, and performance
with actual AWS services (mocked) and realistic data volumes.
"""
import pytest
import json
import time
import threading
import uuid
import gzip
import io
import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws
import pandas as pd

from tests.integration.test_data_generator import (
    FlightDataGenerator, 
    create_malformed_json_files,
    create_oversized_files
)
from tests.integration.pipeline_test_utils import (
    PipelineTestHarness,
    ResourceManager,
    PerformanceMonitor
)


@pytest.fixture(scope="class")
def pipeline_harness():
    """Complete pipeline test harness with all AWS services."""
    with mock_aws():
        harness = PipelineTestHarness()
        harness.setup_infrastructure()
        yield harness
        harness.cleanup()


@pytest.fixture
def data_generator():
    """Test data generator for realistic flight data."""
    return FlightDataGenerator()


@pytest.fixture
def performance_monitor():
    """Performance monitoring utilities."""
    return PerformanceMonitor()


@pytest.mark.integration
class TestEndToEndDataFlow:
    """Test complete end-to-end data flow through the pipeline."""
    
    def test_single_file_complete_flow(self, pipeline_harness, data_generator):
        """Test complete flow: JSON upload -> Processing -> Parquet output -> DynamoDB tracking."""
        # Generate test data
        flight_data = data_generator.generate_flight_records(100)
        test_file_key = f"raw/test_data_{uuid.uuid4().hex[:8]}.json"
        
        # Upload JSON to raw S3 bucket
        json_content = json.dumps(flight_data, indent=2)
        pipeline_harness.upload_to_raw_bucket(test_file_key, json_content)
        
        # Simulate Lambda trigger
        s3_event = pipeline_harness.create_s3_event(test_file_key, len(json_content))
        processing_result = pipeline_harness.trigger_etl_lambda(s3_event)
        
        # Verify processing success
        assert processing_result['statusCode'] == 200
        
        response_body = json.loads(processing_result['body'])
        assert response_body['status'] == 'SUCCESS'
        assert response_body['records_processed'] == 100
        
        # Check Parquet file was created
        parquet_key = response_body['output_file']
        parquet_exists = pipeline_harness.check_processed_file_exists(parquet_key)
        assert parquet_exists, f"Parquet file not found: {parquet_key}"
        
        # Validate Parquet content
        parquet_data = pipeline_harness.download_parquet_file(parquet_key)
        assert len(parquet_data) == 100
        assert 'icao24' in parquet_data.columns
        assert 'processed_timestamp' in parquet_data.columns
        
        # Verify DynamoDB tracking
        tracking_record = pipeline_harness.get_processing_record(test_file_key)
        assert tracking_record is not None
        assert tracking_record['status'] == 'COMPLETED'
        assert tracking_record['records_processed'] == 100
        assert 'processing_duration_ms' in tracking_record
        
        # Verify quality validation was triggered
        quality_validation_result = pipeline_harness.trigger_quality_validator(parquet_key)
        assert quality_validation_result['statusCode'] == 200
        
        quality_body = json.loads(quality_validation_result['body'])
        assert quality_body['status'] == 'SUCCESS'
        assert quality_body['validated_files'][0]['total_records'] == 100
        assert quality_body['validated_files'][0]['overall_score'] > 0.0
    
    def test_multiple_files_concurrent_processing(self, pipeline_harness, data_generator):
        """Test concurrent processing of multiple files."""
        file_count = 5
        records_per_file = 50
        
        # Generate and upload multiple files
        upload_futures = []
        file_keys = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            for i in range(file_count):
                flight_data = data_generator.generate_flight_records(records_per_file)
                file_key = f"raw/concurrent_test_{i}_{uuid.uuid4().hex[:8]}.json"
                file_keys.append(file_key)
                
                json_content = json.dumps(flight_data, indent=2)
                future = executor.submit(
                    pipeline_harness.upload_to_raw_bucket, 
                    file_key, 
                    json_content
                )
                upload_futures.append(future)
            
            # Wait for all uploads
            for future in as_completed(upload_futures):
                future.result()
        
        # Process all files concurrently
        processing_futures = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            for file_key in file_keys:
                s3_event = pipeline_harness.create_s3_event(file_key, 1024)
                future = executor.submit(
                    pipeline_harness.trigger_etl_lambda, 
                    s3_event
                )
                processing_futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(processing_futures):
                result = future.result()
                results.append(result)
        
        # Verify all processing succeeded
        successful_results = [r for r in results if r['statusCode'] == 200]
        assert len(successful_results) == file_count
        
        # Verify all DynamoDB records created
        tracking_records = []
        for file_key in file_keys:
            record = pipeline_harness.get_processing_record(file_key)
            tracking_records.append(record)
        
        completed_records = [r for r in tracking_records if r and r['status'] == 'COMPLETED']
        assert len(completed_records) == file_count
        
        # Verify total records processed
        total_processed = sum(r['records_processed'] for r in completed_records)
        assert total_processed == file_count * records_per_file
    
    def test_large_file_processing(self, pipeline_harness, data_generator):
        """Test processing of large files (10K+ records)."""
        large_record_count = 10000
        flight_data = data_generator.generate_flight_records(large_record_count)
        
        test_file_key = f"raw/large_file_{uuid.uuid4().hex[:8]}.json"
        json_content = json.dumps(flight_data, indent=2)
        
        # Upload large file
        pipeline_harness.upload_to_raw_bucket(test_file_key, json_content)
        
        # Process with extended timeout
        s3_event = pipeline_harness.create_s3_event(test_file_key, len(json_content))
        
        start_time = time.time()
        processing_result = pipeline_harness.trigger_etl_lambda(s3_event, timeout=300)  # 5 minutes
        processing_time = time.time() - start_time
        
        # Verify processing completed within reasonable time
        assert processing_result['statusCode'] == 200
        assert processing_time < 180  # Should complete within 3 minutes
        
        response_body = json.loads(processing_result['body'])
        assert response_body['records_processed'] == large_record_count
        
        # Verify memory usage was reasonable (check logs or metrics)
        tracking_record = pipeline_harness.get_processing_record(test_file_key)
        assert tracking_record['memory_used_mb'] < 512  # Should stay within Lambda limits
    
    def test_data_quality_integration(self, pipeline_harness, data_generator):
        """Test integration with data quality validation pipeline."""
        # Generate data with known quality issues
        good_records = data_generator.generate_flight_records(80)
        bad_records = data_generator.generate_invalid_records(20)
        
        mixed_data = good_records + bad_records
        test_file_key = f"raw/quality_test_{uuid.uuid4().hex[:8]}.json"
        
        json_content = json.dumps(mixed_data, indent=2)
        pipeline_harness.upload_to_raw_bucket(test_file_key, json_content)
        
        # Process data
        s3_event = pipeline_harness.create_s3_event(test_file_key, len(json_content))
        processing_result = pipeline_harness.trigger_etl_lambda(s3_event)
        
        assert processing_result['statusCode'] == 200
        
        response_body = json.loads(processing_result['body'])
        parquet_key = response_body['output_file']
        
        # Trigger quality validation
        quality_result = pipeline_harness.trigger_quality_validator(parquet_key)
        assert quality_result['statusCode'] == 200
        
        quality_body = json.loads(quality_result['body'])
        validated_file = quality_body['validated_files'][0]
        
        # Should detect quality issues
        assert validated_file['overall_score'] < 0.9  # Mixed quality data
        assert validated_file['failed_checks'] > 0
        assert not validated_file['passed_threshold']  # Should fail quality threshold
        
        # Verify alert was sent for low quality
        alerts_sent = pipeline_harness.get_sns_messages()
        quality_alerts = [msg for msg in alerts_sent if 'Quality Alert' in msg['Subject']]
        assert len(quality_alerts) > 0


@pytest.mark.integration
class TestErrorScenarios:
    """Test various error scenarios and recovery mechanisms."""
    
    def test_malformed_json_handling(self, pipeline_harness):
        """Test handling of malformed JSON files."""
        malformed_files = create_malformed_json_files()
        
        results = []
        for file_name, content in malformed_files.items():
            file_key = f"raw/malformed_{file_name}"
            pipeline_harness.upload_to_raw_bucket(file_key, content)
            
            s3_event = pipeline_harness.create_s3_event(file_key, len(content))
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            results.append((file_name, result))
        
        # Verify error handling
        for file_name, result in results:
            # Should return error status but not crash
            assert result['statusCode'] in [400, 500]
            
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'ERROR'
            assert 'error_message' in response_body
            
            # Verify DynamoDB tracking for errors
            tracking_record = pipeline_harness.get_processing_record(f"raw/malformed_{file_name}")
            assert tracking_record is not None
            assert tracking_record['status'] == 'FAILED'
            assert 'error_message' in tracking_record
        
        # Verify DLQ messages for malformed files
        dlq_messages = pipeline_harness.get_dlq_messages()
        assert len(dlq_messages) >= len(malformed_files)
    
    def test_oversized_file_handling(self, pipeline_harness):
        """Test handling of files exceeding size limits."""
        oversized_files = create_oversized_files()
        
        for file_name, content in oversized_files.items():
            file_key = f"raw/oversized_{file_name}"
            
            # Should handle large uploads appropriately
            upload_result = pipeline_harness.upload_to_raw_bucket(file_key, content)
            
            if upload_result:  # If upload succeeded
                s3_event = pipeline_harness.create_s3_event(file_key, len(content))
                result = pipeline_harness.trigger_etl_lambda(s3_event, timeout=600)  # Extended timeout
                
                # Should either process or gracefully fail
                assert result['statusCode'] in [200, 413, 500]  # Success, too large, or server error
                
                response_body = json.loads(result['body'])
                if result['statusCode'] != 200:
                    assert response_body['status'] == 'ERROR'
                    assert 'size' in response_body['error_message'].lower()
    
    def test_permission_errors(self, pipeline_harness):
        """Test handling of permission errors."""
        test_file_key = f"raw/permission_test_{uuid.uuid4().hex[:8]}.json"
        test_data = json.dumps([{"icao24": "abcdef", "latitude": 40.0}])
        
        pipeline_harness.upload_to_raw_bucket(test_file_key, test_data)
        
        # Mock permission errors for different AWS services
        with patch.object(pipeline_harness.s3_client, 'get_object') as mock_get:
            mock_get.side_effect = Exception("Access Denied")
            
            s3_event = pipeline_harness.create_s3_event(test_file_key, len(test_data))
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            
            # Should handle permission error gracefully
            assert result['statusCode'] in [403, 500]
            
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'ERROR'
            assert 'access' in response_body['error_message'].lower()
    
    def test_dlq_functionality(self, pipeline_harness):
        """Test Dead Letter Queue functionality."""
        # Create scenarios that should trigger DLQ
        error_scenarios = [
            ("invalid_json.json", '{"invalid": json}'),
            ("empty_file.json", ""),
            ("non_json.json", "This is not JSON at all"),
        ]
        
        for file_name, content in error_scenarios:
            file_key = f"raw/dlq_test_{file_name}"
            pipeline_harness.upload_to_raw_bucket(file_key, content)
            
            s3_event = pipeline_harness.create_s3_event(file_key, len(content))
            
            # Trigger Lambda (should fail and go to DLQ)
            try:
                result = pipeline_harness.trigger_etl_lambda(s3_event)
                # If it doesn't crash, verify it returns error
                if result['statusCode'] not in [200]:
                    pass  # Expected error
            except Exception:
                pass  # Expected for some severe errors
        
        # Verify DLQ received messages
        dlq_messages = pipeline_harness.get_dlq_messages()
        assert len(dlq_messages) >= len(error_scenarios)
        
        # Verify DLQ messages contain relevant error information
        for message in dlq_messages:
            assert 'errorMessage' in message or 'Records' in message
    
    def test_downstream_service_failures(self, pipeline_harness, data_generator):
        """Test handling when downstream services fail."""
        flight_data = data_generator.generate_flight_records(50)
        test_file_key = f"raw/downstream_test_{uuid.uuid4().hex[:8]}.json"
        json_content = json.dumps(flight_data)
        
        pipeline_harness.upload_to_raw_bucket(test_file_key, json_content)
        
        # Mock DynamoDB failure
        with patch.object(pipeline_harness.dynamodb, 'put_item') as mock_put:
            mock_put.side_effect = Exception("DynamoDB service unavailable")
            
            s3_event = pipeline_harness.create_s3_event(test_file_key, len(json_content))
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            
            # Should complete processing but log DynamoDB error
            # (depending on implementation, might still succeed for core processing)
            assert result['statusCode'] in [200, 500]
            
        # Mock S3 put failure (for output)
        with patch.object(pipeline_harness.s3_client, 'put_object') as mock_put_obj:
            mock_put_obj.side_effect = Exception("S3 service unavailable")
            
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            
            # Should fail when cannot write output
            assert result['statusCode'] == 500
            
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'ERROR'


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceScenarios:
    """Test performance under various load conditions."""
    
    def test_concurrent_file_processing(self, pipeline_harness, data_generator, performance_monitor):
        """Test processing 1000 concurrent files."""
        concurrent_files = 100  # Reduced from 1000 for test environment
        records_per_file = 10
        
        performance_monitor.start_monitoring()
        
        # Generate files
        file_keys = []
        upload_start = time.time()
        
        def upload_file(file_index):
            flight_data = data_generator.generate_flight_records(records_per_file)
            file_key = f"raw/concurrent_{file_index}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            pipeline_harness.upload_to_raw_bucket(file_key, json_content)
            return file_key
        
        # Upload files concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            upload_futures = [
                executor.submit(upload_file, i) 
                for i in range(concurrent_files)
            ]
            
            for future in as_completed(upload_futures):
                file_key = future.result()
                file_keys.append(file_key)
        
        upload_time = time.time() - upload_start
        print(f"Upload time for {concurrent_files} files: {upload_time:.2f}s")
        
        # Process files concurrently
        process_start = time.time()
        
        def process_file(file_key):
            s3_event = pipeline_harness.create_s3_event(file_key, 1024)
            start_time = time.time()
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            processing_time = time.time() - start_time
            
            return {
                'file_key': file_key,
                'result': result,
                'processing_time': processing_time,
                'timestamp': time.time()
            }
        
        # Process with controlled concurrency
        results = []
        batch_size = 10  # Process in batches to avoid overwhelming
        
        for i in range(0, len(file_keys), batch_size):
            batch_files = file_keys[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                batch_futures = [
                    executor.submit(process_file, file_key) 
                    for file_key in batch_files
                ]
                
                for future in as_completed(batch_futures):
                    result = future.result()
                    results.append(result)
            
            # Small delay between batches
            time.sleep(0.1)
        
        total_process_time = time.time() - process_start
        print(f"Total processing time: {total_process_time:.2f}s")
        
        performance_monitor.stop_monitoring()
        
        # Analyze results
        successful_results = [r for r in results if r['result']['statusCode'] == 200]
        success_rate = len(successful_results) / len(results)
        
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"
        
        # Performance metrics
        processing_times = [r['processing_time'] for r in successful_results]
        avg_processing_time = sum(processing_times) / len(processing_times)
        max_processing_time = max(processing_times)
        
        print(f"Average processing time: {avg_processing_time:.2f}s")
        print(f"Max processing time: {max_processing_time:.2f}s")
        
        # Performance assertions
        assert avg_processing_time < 5.0, "Average processing time too high"
        assert max_processing_time < 15.0, "Maximum processing time too high"
        
        # Verify all records were tracked
        successful_tracking_records = 0
        for result in successful_results:
            file_key = result['file_key']
            tracking_record = pipeline_harness.get_processing_record(file_key)
            if tracking_record and tracking_record['status'] == 'COMPLETED':
                successful_tracking_records += 1
        
        tracking_success_rate = successful_tracking_records / len(successful_results)
        assert tracking_success_rate >= 0.90, "DynamoDB tracking success rate too low"
    
    def test_processing_latency_measurement(self, pipeline_harness, data_generator):
        """Measure end-to-end processing latency."""
        latency_measurements = []
        
        for i in range(10):  # 10 samples for latency measurement
            flight_data = data_generator.generate_flight_records(100)
            file_key = f"raw/latency_test_{i}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            # Measure upload latency
            upload_start = time.time()
            pipeline_harness.upload_to_raw_bucket(file_key, json_content)
            upload_latency = time.time() - upload_start
            
            # Measure processing latency
            s3_event = pipeline_harness.create_s3_event(file_key, len(json_content))
            
            processing_start = time.time()
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            processing_latency = time.time() - processing_start
            
            # Measure end-to-end latency (including output verification)
            if result['statusCode'] == 200:
                response_body = json.loads(result['body'])
                parquet_key = response_body['output_file']
                
                verify_start = time.time()
                exists = pipeline_harness.check_processed_file_exists(parquet_key)
                verify_latency = time.time() - verify_start
                
                total_latency = upload_latency + processing_latency + verify_latency
                
                latency_measurements.append({
                    'upload_latency': upload_latency,
                    'processing_latency': processing_latency,
                    'verify_latency': verify_latency,
                    'total_latency': total_latency,
                    'records_count': 100
                })
        
        # Analyze latency metrics
        avg_processing_latency = sum(m['processing_latency'] for m in latency_measurements) / len(latency_measurements)
        avg_total_latency = sum(m['total_latency'] for m in latency_measurements) / len(latency_measurements)
        
        p95_processing_latency = sorted([m['processing_latency'] for m in latency_measurements])[int(0.95 * len(latency_measurements))]
        
        print(f"Average processing latency: {avg_processing_latency:.3f}s")
        print(f"Average total latency: {avg_total_latency:.3f}s")
        print(f"95th percentile processing latency: {p95_processing_latency:.3f}s")
        
        # Performance assertions
        assert avg_processing_latency < 3.0, "Average processing latency too high"
        assert p95_processing_latency < 8.0, "95th percentile latency too high"
    
    def test_memory_usage_monitoring(self, pipeline_harness, data_generator):
        """Test memory usage with varying file sizes."""
        file_sizes = [100, 500, 1000, 2000, 5000]  # Records per file
        memory_measurements = []
        
        for size in file_sizes:
            flight_data = data_generator.generate_flight_records(size)
            file_key = f"raw/memory_test_{size}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            pipeline_harness.upload_to_raw_bucket(file_key, json_content)
            
            s3_event = pipeline_harness.create_s3_event(file_key, len(json_content))
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            
            if result['statusCode'] == 200:
                # Get memory usage from tracking record
                tracking_record = pipeline_harness.get_processing_record(file_key)
                if tracking_record and 'memory_used_mb' in tracking_record:
                    memory_measurements.append({
                        'record_count': size,
                        'memory_used_mb': tracking_record['memory_used_mb'],
                        'processing_time': tracking_record['processing_duration_ms'] / 1000
                    })
        
        # Analyze memory scaling
        if memory_measurements:
            max_memory_used = max(m['memory_used_mb'] for m in memory_measurements)
            
            print(f"Memory usage by file size: {memory_measurements}")
            print(f"Maximum memory used: {max_memory_used}MB")
            
            # Memory usage should be reasonable
            assert max_memory_used < 256, "Memory usage too high"
            
            # Memory should scale reasonably with data size
            if len(memory_measurements) > 1:
                smallest = min(memory_measurements, key=lambda x: x['record_count'])
                largest = max(memory_measurements, key=lambda x: x['record_count'])
                
                memory_scale_factor = largest['memory_used_mb'] / smallest['memory_used_mb']
                record_scale_factor = largest['record_count'] / smallest['record_count']
                
                # Memory scaling should be sub-linear (good efficiency)
                assert memory_scale_factor < record_scale_factor * 1.5, "Memory scaling inefficient"
    
    def test_auto_scaling_simulation(self, pipeline_harness, data_generator):
        """Simulate auto-scaling behavior under load."""
        # Simulate burst load
        burst_files = 50
        
        # Phase 1: Gradual ramp-up
        ramp_up_results = []
        for i in range(10):
            flight_data = data_generator.generate_flight_records(50)
            file_key = f"raw/ramp_up_{i}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            pipeline_harness.upload_to_raw_bucket(file_key, json_content)
            
            s3_event = pipeline_harness.create_s3_event(file_key, len(json_content))
            
            start_time = time.time()
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            processing_time = time.time() - start_time
            
            ramp_up_results.append({
                'phase': 'ramp_up',
                'file_index': i,
                'processing_time': processing_time,
                'success': result['statusCode'] == 200
            })
            
            time.sleep(0.5)  # Gradual ramp-up
        
        # Phase 2: Burst load
        burst_results = []
        
        def process_burst_file(file_index):
            flight_data = data_generator.generate_flight_records(100)
            file_key = f"raw/burst_{file_index}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            pipeline_harness.upload_to_raw_bucket(file_key, json_content)
            
            s3_event = pipeline_harness.create_s3_event(file_key, len(json_content))
            
            start_time = time.time()
            result = pipeline_harness.trigger_etl_lambda(s3_event)
            processing_time = time.time() - start_time
            
            return {
                'phase': 'burst',
                'file_index': file_index,
                'processing_time': processing_time,
                'success': result['statusCode'] == 200
            }
        
        # Submit burst load
        with ThreadPoolExecutor(max_workers=20) as executor:
            burst_futures = [
                executor.submit(process_burst_file, i) 
                for i in range(burst_files)
            ]
            
            for future in as_completed(burst_futures):
                result = future.result()
                burst_results.append(result)
        
        # Analyze scaling behavior
        ramp_up_success_rate = sum(1 for r in ramp_up_results if r['success']) / len(ramp_up_results)
        burst_success_rate = sum(1 for r in burst_results if r['success']) / len(burst_results)
        
        avg_ramp_up_time = sum(r['processing_time'] for r in ramp_up_results if r['success']) / len([r for r in ramp_up_results if r['success']])
        avg_burst_time = sum(r['processing_time'] for r in burst_results if r['success']) / len([r for r in burst_results if r['success']])
        
        print(f"Ramp-up success rate: {ramp_up_success_rate:.2%}")
        print(f"Burst success rate: {burst_success_rate:.2%}")
        print(f"Average ramp-up processing time: {avg_ramp_up_time:.2f}s")
        print(f"Average burst processing time: {avg_burst_time:.2f}s")
        
        # Performance expectations
        assert ramp_up_success_rate >= 0.90, "Ramp-up success rate too low"
        assert burst_success_rate >= 0.80, "Burst load success rate too low"
        
        # Burst processing might be slower but should be reasonable
        assert avg_burst_time < avg_ramp_up_time * 3.0, "Burst processing time degradation too high"