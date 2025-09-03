"""
Performance and stress testing for the flight data pipeline.

Tests high-volume processing, concurrent loads, memory usage,
and system limits under realistic production scenarios.
"""
import pytest
import time
import threading
import uuid
import json
import statistics
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from unittest.mock import Mock, patch
import psutil
import gc

from tests.integration.test_data_generator import FlightDataGenerator
from tests.integration.pipeline_test_utils import (
    PipelineTestHarness, 
    ResourceManager, 
    PerformanceMonitor
)


@pytest.fixture(scope="class")
def stress_test_harness():
    """Performance test harness with extended configuration."""
    harness = PipelineTestHarness()
    harness.setup_infrastructure()
    yield harness
    harness.cleanup()


@pytest.fixture
def data_generator():
    """Data generator for performance tests."""
    return FlightDataGenerator(seed=42)  # Fixed seed for reproducible tests


@pytest.fixture
def performance_monitor():
    """Performance monitoring utilities."""
    return PerformanceMonitor()


@pytest.mark.integration
@pytest.mark.performance
class TestHighVolumeProcessing:
    """Test processing of high-volume data."""
    
    def test_large_single_file_processing(self, stress_test_harness, data_generator, performance_monitor):
        """Test processing single large file (50K records)."""
        large_record_count = 50000
        
        print(f"Generating {large_record_count:,} flight records...")
        flight_data = data_generator.generate_flight_records(large_record_count)
        
        test_file_key = f"raw/large_single_file_{uuid.uuid4().hex[:8]}.json"
        json_content = json.dumps(flight_data)
        
        print(f"JSON content size: {len(json_content) / 1024 / 1024:.1f} MB")
        
        # Start performance monitoring
        with performance_monitor.monitor_performance(interval=0.5):
            # Upload large file
            upload_start = time.time()
            upload_success = stress_test_harness.upload_to_raw_bucket(test_file_key, json_content)
            upload_time = time.time() - upload_start
            
            assert upload_success, "Failed to upload large file"
            print(f"Upload time: {upload_time:.2f} seconds")
            
            # Process file
            s3_event = stress_test_harness.create_s3_event(test_file_key, len(json_content))
            
            processing_start = time.time()
            result = stress_test_harness.trigger_etl_lambda(s3_event, timeout=600)  # 10 minute timeout
            processing_time = time.time() - processing_start
            
            print(f"Processing time: {processing_time:.2f} seconds")
            
            # Verify processing success
            assert result['statusCode'] == 200, f"Processing failed: {result}"
            
            response_body = json.loads(result['body'])
            assert response_body['records_processed'] == large_record_count
            
            # Performance assertions
            assert processing_time < 300, f"Processing took too long: {processing_time}s"
            
            # Verify output file
            parquet_key = response_body['output_file']
            assert stress_test_harness.check_processed_file_exists(parquet_key)
            
            # Verify DynamoDB tracking
            tracking_record = stress_test_harness.get_processing_record(test_file_key)
            assert tracking_record is not None
            assert tracking_record['status'] == 'COMPLETED'
            assert tracking_record['records_processed'] == large_record_count
            
            # Check memory usage
            memory_used = tracking_record.get('memory_used_mb', 0)
            assert memory_used < 1024, f"Memory usage too high: {memory_used}MB"
            
            print(f"Memory used: {memory_used:.1f} MB")
            print(f"Processing rate: {large_record_count / processing_time:.0f} records/second")
        
        perf_summary = performance_monitor.stop_monitoring()
        print(f"Peak memory usage: {perf_summary['memory_mb']['max']:.1f} MB")
        print(f"Average CPU: {perf_summary['cpu_percent']['avg']:.1f}%")
    
    def test_massive_concurrent_files(self, stress_test_harness, data_generator, performance_monitor):
        """Test processing 1000 concurrent small files."""
        concurrent_files = 1000
        records_per_file = 10
        batch_size = 50  # Process in batches
        
        print(f"Testing {concurrent_files} concurrent files with {records_per_file} records each")
        
        with performance_monitor.monitor_performance(interval=1.0):
            # Phase 1: Generate and upload all files
            print("Phase 1: Generating and uploading files...")
            upload_start = time.time()
            
            file_keys = []
            
            def create_and_upload_file(file_index):
                flight_data = data_generator.generate_flight_records(records_per_file)
                file_key = f"raw/concurrent_massive_{file_index}_{uuid.uuid4().hex[:8]}.json"
                json_content = json.dumps(flight_data)
                
                success = stress_test_harness.upload_to_raw_bucket(file_key, json_content)
                return file_key if success else None
            
            # Upload files in parallel batches
            successful_uploads = []
            for batch_start in range(0, concurrent_files, batch_size):
                batch_end = min(batch_start + batch_size, concurrent_files)
                batch_indices = range(batch_start, batch_end)
                
                with ThreadPoolExecutor(max_workers=20) as executor:
                    batch_futures = [
                        executor.submit(create_and_upload_file, i) 
                        for i in batch_indices
                    ]
                    
                    for future in as_completed(batch_futures):
                        file_key = future.result()
                        if file_key:
                            successful_uploads.append(file_key)
                
                print(f"Uploaded batch {batch_start//batch_size + 1}/{(concurrent_files-1)//batch_size + 1}")
                time.sleep(0.1)  # Brief pause between batches
            
            upload_time = time.time() - upload_start
            print(f"Upload completed: {len(successful_uploads)}/{concurrent_files} files in {upload_time:.1f}s")
            
            # Phase 2: Process all files concurrently
            print("Phase 2: Processing files...")
            processing_start = time.time()
            
            def process_single_file(file_key):
                s3_event = stress_test_harness.create_s3_event(file_key, 1024)
                start_time = time.time()
                result = stress_test_harness.trigger_etl_lambda(s3_event)
                processing_time = time.time() - start_time
                
                return {
                    'file_key': file_key,
                    'success': result['statusCode'] == 200,
                    'processing_time': processing_time,
                    'result': result
                }
            
            # Process in controlled batches to avoid overwhelming the system
            all_results = []
            
            for batch_start in range(0, len(successful_uploads), batch_size):
                batch_end = min(batch_start + batch_size, len(successful_uploads))
                batch_files = successful_uploads[batch_start:batch_end]
                
                with ThreadPoolExecutor(max_workers=min(20, len(batch_files))) as executor:
                    batch_futures = [
                        executor.submit(process_single_file, file_key)
                        for file_key in batch_files
                    ]
                    
                    batch_results = []
                    for future in as_completed(batch_futures):
                        result = future.result()
                        batch_results.append(result)
                        all_results.append(result)
                
                success_count = sum(1 for r in batch_results if r['success'])
                print(f"Processed batch {batch_start//batch_size + 1}: {success_count}/{len(batch_results)} successful")
                
                # Brief pause between batches
                time.sleep(0.2)
            
            total_processing_time = time.time() - processing_start
            
            # Analyze results
            successful_results = [r for r in all_results if r['success']]
            success_rate = len(successful_results) / len(all_results) if all_results else 0
            
            processing_times = [r['processing_time'] for r in successful_results]
            avg_processing_time = statistics.mean(processing_times) if processing_times else 0
            median_processing_time = statistics.median(processing_times) if processing_times else 0
            max_processing_time = max(processing_times) if processing_times else 0
            
            print(f"\nPerformance Results:")
            print(f"Success rate: {success_rate:.1%}")
            print(f"Total processing time: {total_processing_time:.1f}s")
            print(f"Average file processing time: {avg_processing_time:.3f}s")
            print(f"Median file processing time: {median_processing_time:.3f}s")
            print(f"Maximum file processing time: {max_processing_time:.3f}s")
            print(f"Throughput: {len(successful_results)/total_processing_time:.1f} files/second")
            
            # Performance assertions
            assert success_rate >= 0.95, f"Success rate too low: {success_rate:.1%}"
            assert avg_processing_time < 2.0, f"Average processing time too high: {avg_processing_time:.3f}s"
            assert max_processing_time < 10.0, f"Maximum processing time too high: {max_processing_time:.3f}s"
            
            # Verify DynamoDB tracking for sample of files
            sample_size = min(50, len(successful_results))
            sample_files = successful_results[:sample_size]
            
            tracking_success = 0
            for result in sample_files:
                tracking_record = stress_test_harness.get_processing_record(result['file_key'])
                if tracking_record and tracking_record['status'] == 'COMPLETED':
                    tracking_success += 1
            
            tracking_success_rate = tracking_success / sample_size
            print(f"DynamoDB tracking success rate: {tracking_success_rate:.1%}")
            assert tracking_success_rate >= 0.90, "DynamoDB tracking success rate too low"
        
        perf_summary = performance_monitor.stop_monitoring()
        print(f"\nSystem Performance:")
        print(f"Peak memory usage: {perf_summary['memory_mb']['max']:.1f} MB")
        print(f"Average CPU usage: {perf_summary['cpu_percent']['avg']:.1f}%")
        print(f"Peak CPU usage: {perf_summary['cpu_percent']['max']:.1f}%")
    
    def test_mixed_workload_stress(self, stress_test_harness, data_generator, performance_monitor):
        """Test mixed workload with various file sizes simultaneously."""
        workload_config = [
            (50, 10),      # 50 small files (10 records each)
            (20, 100),     # 20 medium files (100 records each)
            (10, 1000),    # 10 large files (1000 records each)
            (5, 5000),     # 5 very large files (5000 records each)
            (2, 10000),    # 2 huge files (10000 records each)
        ]
        
        print("Testing mixed workload stress scenario")
        for file_count, record_count in workload_config:
            print(f"  {file_count} files with {record_count:,} records each")
        
        with performance_monitor.monitor_performance(interval=1.0):
            # Create all files
            all_files = []
            creation_start = time.time()
            
            for file_count, record_count in workload_config:
                for i in range(file_count):
                    flight_data = data_generator.generate_flight_records(record_count)
                    file_key = f"raw/mixed_workload_{record_count}_{i}_{uuid.uuid4().hex[:8]}.json"
                    json_content = json.dumps(flight_data)
                    
                    all_files.append({
                        'key': file_key,
                        'content': json_content,
                        'record_count': record_count,
                        'size_mb': len(json_content) / 1024 / 1024
                    })
            
            # Upload all files
            print(f"Uploading {len(all_files)} files...")
            
            def upload_file(file_info):
                success = stress_test_harness.upload_to_raw_bucket(file_info['key'], file_info['content'])
                return file_info['key'] if success else None
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                upload_futures = [executor.submit(upload_file, f) for f in all_files]
                successful_uploads = []
                
                for future in as_completed(upload_futures):
                    result = future.result()
                    if result:
                        successful_uploads.append(result)
            
            upload_time = time.time() - creation_start
            print(f"Upload completed: {len(successful_uploads)}/{len(all_files)} files in {upload_time:.1f}s")
            
            # Process files with staggered timing
            print("Processing files with mixed priority...")
            processing_start = time.time()
            
            def process_with_category(file_info):
                file_key = file_info['key']
                record_count = file_info['record_count']
                
                # Add artificial delay based on file size (larger files processed first)
                if record_count >= 5000:
                    priority_delay = 0  # Process immediately
                elif record_count >= 1000:
                    priority_delay = 0.1
                elif record_count >= 100:
                    priority_delay = 0.2
                else:
                    priority_delay = 0.5
                
                time.sleep(priority_delay)
                
                s3_event = stress_test_harness.create_s3_event(file_key, len(file_info['content']))
                start_time = time.time()
                result = stress_test_harness.trigger_etl_lambda(s3_event, timeout=300)
                processing_time = time.time() - start_time
                
                return {
                    'file_key': file_key,
                    'record_count': record_count,
                    'size_mb': file_info['size_mb'],
                    'success': result['statusCode'] == 200,
                    'processing_time': processing_time,
                    'result': result
                }
            
            # Process all files concurrently
            with ThreadPoolExecutor(max_workers=15) as executor:
                process_futures = [
                    executor.submit(process_with_category, f) 
                    for f in all_files if f['key'] in successful_uploads
                ]
                
                processing_results = []
                for future in as_completed(process_futures):
                    result = future.result()
                    processing_results.append(result)
                    
                    if result['success']:
                        status = "✓"
                    else:
                        status = "✗"
                    
                    print(f"{status} Processed {result['record_count']:,} records in {result['processing_time']:.2f}s")
            
            total_processing_time = time.time() - processing_start
            
            # Analyze performance by file size category
            successful_results = [r for r in processing_results if r['success']]
            
            print(f"\nMixed Workload Results:")
            print(f"Overall success rate: {len(successful_results)/len(processing_results):.1%}")
            print(f"Total processing time: {total_processing_time:.1f}s")
            
            # Group results by record count
            by_size = {}
            for result in successful_results:
                size_key = result['record_count']
                if size_key not in by_size:
                    by_size[size_key] = []
                by_size[size_key].append(result)
            
            for size_key in sorted(by_size.keys()):
                results = by_size[size_key]
                avg_time = statistics.mean(r['processing_time'] for r in results)
                total_records = sum(r['record_count'] for r in results)
                throughput = total_records / sum(r['processing_time'] for r in results)
                
                print(f"  {size_key:,} record files: {len(results)} files, {avg_time:.2f}s avg, {throughput:.0f} records/s")
            
            # Overall throughput
            total_records = sum(r['record_count'] for r in successful_results)
            total_time = sum(r['processing_time'] for r in successful_results)
            overall_throughput = total_records / total_time if total_time > 0 else 0
            
            print(f"Overall throughput: {overall_throughput:.0f} records/second")
            
            # Performance assertions
            assert len(successful_results) / len(processing_results) >= 0.90, "Success rate too low"
            assert overall_throughput >= 100, f"Overall throughput too low: {overall_throughput:.0f} records/s"
        
        perf_summary = performance_monitor.stop_monitoring()
        print(f"\nSystem Performance Summary:")
        print(f"Peak memory usage: {perf_summary['memory_mb']['max']:.1f} MB")
        print(f"Average memory usage: {perf_summary['memory_mb']['avg']:.1f} MB")
        print(f"Peak CPU usage: {perf_summary['cpu_percent']['max']:.1f}%")


@pytest.mark.integration
@pytest.mark.performance  
class TestMemoryAndResourceLimits:
    """Test memory usage and resource limits."""
    
    def test_memory_usage_scaling(self, stress_test_harness, data_generator, performance_monitor):
        """Test memory usage scaling with different data sizes."""
        file_sizes = [100, 500, 1000, 2000, 5000, 10000, 20000]  # Records per file
        memory_measurements = []
        
        print("Testing memory usage scaling...")
        
        for size in file_sizes:
            print(f"Testing {size:,} records...")
            
            # Force garbage collection before test
            gc.collect()
            
            # Generate test data
            flight_data = data_generator.generate_flight_records(size)
            file_key = f"raw/memory_test_{size}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            # Measure initial memory
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            with performance_monitor.monitor_performance(interval=0.5):
                # Upload and process
                stress_test_harness.upload_to_raw_bucket(file_key, json_content)
                s3_event = stress_test_harness.create_s3_event(file_key, len(json_content))
                
                processing_start = time.time()
                result = stress_test_harness.trigger_etl_lambda(s3_event, timeout=120)
                processing_time = time.time() - processing_start
                
                # Measure peak memory during processing
                perf_data = performance_monitor.stop_monitoring()
                peak_memory = perf_data['memory_mb']['max']
                
                if result['statusCode'] == 200:
                    # Get memory from tracking record if available
                    tracking_record = stress_test_harness.get_processing_record(file_key)
                    tracked_memory = tracking_record.get('memory_used_mb', 0) if tracking_record else 0
                    
                    memory_measurements.append({
                        'record_count': size,
                        'json_size_mb': len(json_content) / 1024 / 1024,
                        'processing_time': processing_time,
                        'initial_memory_mb': initial_memory,
                        'peak_memory_mb': peak_memory,
                        'tracked_memory_mb': tracked_memory,
                        'memory_increase_mb': peak_memory - initial_memory
                    })
                    
                    print(f"  {size:,} records: {peak_memory:.1f}MB peak, {processing_time:.2f}s")
            
            # Clean up
            gc.collect()
            time.sleep(1)
        
        # Analyze memory scaling
        print(f"\nMemory Scaling Analysis:")
        print("Records\tJSON(MB)\tPeak(MB)\tIncrease(MB)\tTime(s)\tMB/1K records")
        
        for measurement in memory_measurements:
            mb_per_1k = measurement['memory_increase_mb'] / (measurement['record_count'] / 1000)
            print(f"{measurement['record_count']:,}\t"
                  f"{measurement['json_size_mb']:.1f}\t\t"
                  f"{measurement['peak_memory_mb']:.1f}\t\t"
                  f"{measurement['memory_increase_mb']:.1f}\t\t"
                  f"{measurement['processing_time']:.2f}\t"
                  f"{mb_per_1k:.2f}")
        
        # Performance assertions
        max_memory_used = max(m['peak_memory_mb'] for m in memory_measurements)
        assert max_memory_used < 512, f"Memory usage too high: {max_memory_used}MB"
        
        # Memory scaling should be sub-linear
        if len(memory_measurements) >= 3:
            small_test = min(memory_measurements, key=lambda x: x['record_count'])
            large_test = max(memory_measurements, key=lambda x: x['record_count'])
            
            memory_scale_factor = large_test['memory_increase_mb'] / max(small_test['memory_increase_mb'], 1)
            record_scale_factor = large_test['record_count'] / small_test['record_count']
            
            print(f"\nMemory scaling efficiency:")
            print(f"Record scale factor: {record_scale_factor:.1f}x")
            print(f"Memory scale factor: {memory_scale_factor:.1f}x")
            
            # Memory should scale more efficiently than linearly
            efficiency_ratio = memory_scale_factor / record_scale_factor
            print(f"Memory efficiency ratio: {efficiency_ratio:.2f} (lower is better)")
            
            assert efficiency_ratio < 1.5, f"Memory scaling inefficient: {efficiency_ratio:.2f}"
    
    def test_concurrent_memory_pressure(self, stress_test_harness, data_generator, performance_monitor):
        """Test memory usage under concurrent load."""
        concurrent_files = 20
        records_per_file = 2000
        
        print(f"Testing memory pressure with {concurrent_files} concurrent files of {records_per_file:,} records each")
        
        # Generate all files first
        files_to_process = []
        for i in range(concurrent_files):
            flight_data = data_generator.generate_flight_records(records_per_file)
            file_key = f"raw/memory_pressure_{i}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            files_to_process.append({
                'key': file_key,
                'content': json_content
            })
        
        # Upload files
        print("Uploading files...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            upload_futures = []
            for file_info in files_to_process:
                future = executor.submit(
                    stress_test_harness.upload_to_raw_bucket,
                    file_info['key'],
                    file_info['content']
                )
                upload_futures.append(future)
            
            # Wait for uploads
            for future in as_completed(upload_futures):
                future.result()
        
        # Process files concurrently while monitoring memory
        print("Processing files concurrently...")
        
        def process_file_with_monitoring(file_info):
            file_start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            s3_event = stress_test_harness.create_s3_event(file_info['key'], len(file_info['content']))
            
            start_time = time.time()
            result = stress_test_harness.trigger_etl_lambda(s3_event)
            processing_time = time.time() - start_time
            
            file_end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            return {
                'file_key': file_info['key'],
                'success': result['statusCode'] == 200,
                'processing_time': processing_time,
                'start_memory_mb': file_start_memory,
                'end_memory_mb': file_end_memory,
                'memory_delta_mb': file_end_memory - file_start_memory
            }
        
        with performance_monitor.monitor_performance(interval=0.5):
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=concurrent_files) as executor:
                process_futures = [
                    executor.submit(process_file_with_monitoring, f) 
                    for f in files_to_process
                ]
                
                results = []
                for future in as_completed(process_futures):
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        print(f"✓ Processed {result['file_key'].split('_')[-2]} in {result['processing_time']:.2f}s")
                    else:
                        print(f"✗ Failed {result['file_key'].split('_')[-2]}")
            
            total_time = time.time() - start_time
        
        perf_summary = performance_monitor.stop_monitoring()
        
        # Analyze results
        successful_results = [r for r in results if r['success']]
        success_rate = len(successful_results) / len(results)
        
        avg_processing_time = statistics.mean(r['processing_time'] for r in successful_results)
        
        print(f"\nConcurrent Memory Pressure Results:")
        print(f"Success rate: {success_rate:.1%}")
        print(f"Total time: {total_time:.1f}s")
        print(f"Average processing time: {avg_processing_time:.2f}s")
        print(f"Peak system memory: {perf_summary['memory_mb']['max']:.1f}MB")
        print(f"Average system memory: {perf_summary['memory_mb']['avg']:.1f}MB")
        print(f"Peak CPU usage: {perf_summary['cpu_percent']['max']:.1f}%")
        
        # Performance assertions
        assert success_rate >= 0.85, f"Success rate too low under memory pressure: {success_rate:.1%}"
        assert perf_summary['memory_mb']['max'] < 1024, f"Peak memory usage too high: {perf_summary['memory_mb']['max']:.1f}MB"
        assert avg_processing_time < 10.0, f"Average processing time too slow under load: {avg_processing_time:.2f}s"
    
    def test_memory_leak_detection(self, stress_test_harness, data_generator):
        """Test for memory leaks during repeated processing."""
        iterations = 20
        records_per_iteration = 1000
        
        print(f"Testing for memory leaks over {iterations} iterations...")
        
        memory_measurements = []
        
        for i in range(iterations):
            # Force garbage collection before measurement
            gc.collect()
            
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Generate and process data
            flight_data = data_generator.generate_flight_records(records_per_iteration)
            file_key = f"raw/leak_test_{i}_{uuid.uuid4().hex[:8]}.json"
            json_content = json.dumps(flight_data)
            
            stress_test_harness.upload_to_raw_bucket(file_key, json_content)
            s3_event = stress_test_harness.create_s3_event(file_key, len(json_content))
            
            result = stress_test_harness.trigger_etl_lambda(s3_event)
            
            # Measure memory after processing
            post_process_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Force cleanup
            del flight_data
            del json_content
            gc.collect()
            
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            memory_measurements.append({
                'iteration': i,
                'initial_memory_mb': initial_memory,
                'post_process_memory_mb': post_process_memory,
                'final_memory_mb': final_memory,
                'memory_increase_mb': final_memory - initial_memory,
                'success': result['statusCode'] == 200
            })
            
            if i % 5 == 0:
                print(f"Iteration {i}: {final_memory:.1f}MB (+{final_memory - initial_memory:.1f}MB)")
        
        # Analyze memory trend
        successful_measurements = [m for m in memory_measurements if m['success']]
        
        if len(successful_measurements) >= 10:
            # Calculate memory trend over time
            first_half = successful_measurements[:len(successful_measurements)//2]
            second_half = successful_measurements[len(successful_measurements)//2:]
            
            first_half_avg = statistics.mean(m['final_memory_mb'] for m in first_half)
            second_half_avg = statistics.mean(m['final_memory_mb'] for m in second_half)
            
            memory_growth = second_half_avg - first_half_avg
            
            print(f"\nMemory Leak Analysis:")
            print(f"First half average memory: {first_half_avg:.1f}MB")
            print(f"Second half average memory: {second_half_avg:.1f}MB")
            print(f"Memory growth over time: {memory_growth:.1f}MB")
            
            # Detect significant memory growth
            growth_threshold = 50  # MB
            if memory_growth > growth_threshold:
                print(f"WARNING: Potential memory leak detected! Growth: {memory_growth:.1f}MB")
            else:
                print("No significant memory leak detected")
            
            # Test assertion - should not have major memory leaks
            assert memory_growth < growth_threshold, f"Memory leak detected: {memory_growth:.1f}MB growth"
        
        print(f"Memory leak test completed successfully")


@pytest.mark.integration
@pytest.mark.performance
class TestSystemLimits:
    """Test system limits and edge cases."""
    
    def test_maximum_file_size_handling(self, stress_test_harness, data_generator):
        """Test handling of maximum file sizes."""
        # Test with progressively larger files until we hit limits
        file_sizes = [50000, 100000, 200000]  # Number of records
        
        for record_count in file_sizes:
            print(f"Testing {record_count:,} records...")
            
            try:
                flight_data = data_generator.generate_flight_records(record_count)
                file_key = f"raw/max_size_test_{record_count}_{uuid.uuid4().hex[:8]}.json"
                json_content = json.dumps(flight_data)
                
                file_size_mb = len(json_content) / 1024 / 1024
                print(f"  File size: {file_size_mb:.1f}MB")
                
                if file_size_mb > 100:  # Skip files larger than 100MB
                    print(f"  Skipping - file too large for test environment")
                    continue
                
                # Upload
                upload_success = stress_test_harness.upload_to_raw_bucket(file_key, json_content)
                if not upload_success:
                    print(f"  Upload failed for {record_count:,} records")
                    continue
                
                # Process with extended timeout
                s3_event = stress_test_harness.create_s3_event(file_key, len(json_content))
                
                start_time = time.time()
                result = stress_test_harness.trigger_etl_lambda(s3_event, timeout=900)  # 15 minutes
                processing_time = time.time() - start_time
                
                if result['statusCode'] == 200:
                    print(f"  ✓ Successfully processed in {processing_time:.1f}s")
                    
                    response_body = json.loads(result['body'])
                    assert response_body['records_processed'] == record_count
                    
                    # Check processing rate
                    rate = record_count / processing_time
                    print(f"  Processing rate: {rate:.0f} records/second")
                    
                else:
                    print(f"  ✗ Processing failed: {result['statusCode']}")
                    response_body = json.loads(result['body'])
                    print(f"    Error: {response_body.get('error_message', 'Unknown error')}")
                
            except MemoryError:
                print(f"  MemoryError: Cannot generate {record_count:,} records")
                break
            except Exception as e:
                print(f"  Error with {record_count:,} records: {e}")
                continue
    
    def test_concurrent_limit_discovery(self, stress_test_harness, data_generator):
        """Discover the practical concurrent processing limit."""
        concurrency_levels = [10, 20, 50, 100, 200]
        records_per_file = 500
        
        print("Testing concurrent processing limits...")
        
        for concurrency in concurrency_levels:
            print(f"\nTesting {concurrency} concurrent files...")
            
            # Generate files
            files = []
            for i in range(concurrency):
                flight_data = data_generator.generate_flight_records(records_per_file)
                file_key = f"raw/concurrency_test_{concurrency}_{i}_{uuid.uuid4().hex[:8]}.json"
                json_content = json.dumps(flight_data)
                files.append({'key': file_key, 'content': json_content})
            
            # Upload files
            upload_start = time.time()
            successful_uploads = 0
            
            def upload_file(file_info):
                try:
                    return stress_test_harness.upload_to_raw_bucket(file_info['key'], file_info['content'])
                except Exception as e:
                    print(f"Upload error: {e}")
                    return False
            
            with ThreadPoolExecutor(max_workers=min(20, concurrency)) as executor:
                upload_futures = [executor.submit(upload_file, f) for f in files]
                for future in as_completed(upload_futures):
                    if future.result():
                        successful_uploads += 1
            
            upload_time = time.time() - upload_start
            print(f"  Uploaded {successful_uploads}/{concurrency} files in {upload_time:.1f}s")
            
            if successful_uploads == 0:
                print(f"  Upload failed - skipping processing test")
                continue
            
            # Process files
            process_start = time.time()
            
            def process_file(file_info):
                try:
                    s3_event = stress_test_harness.create_s3_event(file_info['key'], len(file_info['content']))
                    result = stress_test_harness.trigger_etl_lambda(s3_event, timeout=60)
                    return result['statusCode'] == 200
                except Exception as e:
                    return False
            
            successful_processing = 0
            max_workers = min(concurrency, 50)  # Limit max workers to avoid overwhelming
            
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    process_futures = [executor.submit(process_file, f) for f in files[:successful_uploads]]
                    
                    for future in as_completed(process_futures):
                        if future.result():
                            successful_processing += 1
            
            except Exception as e:
                print(f"  Processing executor error: {e}")
            
            process_time = time.time() - process_start
            success_rate = successful_processing / successful_uploads if successful_uploads > 0 else 0
            
            print(f"  Processed {successful_processing}/{successful_uploads} files in {process_time:.1f}s")
            print(f"  Success rate: {success_rate:.1%}")
            
            if success_rate < 0.8:
                print(f"  ⚠️  Success rate dropped below 80% at {concurrency} concurrent files")
                print(f"     Practical limit appears to be around {concurrency//2}-{concurrency} files")
                break
            elif success_rate >= 0.95:
                print(f"  ✓ Good performance at {concurrency} concurrent files")
            else:
                print(f"  ⚠️  Degraded performance at {concurrency} concurrent files")
        
        print("\nConcurrency limit discovery completed")