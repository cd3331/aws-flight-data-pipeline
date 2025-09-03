"""
Comprehensive Benchmarking Suite for ETL Performance Optimization.

This module provides detailed performance benchmarking capabilities to measure
and compare the effectiveness of various ETL optimizations including conversion
speeds, memory usage, throughput improvements, and error recovery performance.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import logging
import time
import json
import statistics
import traceback
import gc
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import tempfile
import os
import psutil
from contextlib import contextmanager
import pandas as pd
import numpy as np

# Import our optimized components
from optimized_converter import OptimizedJsonToParquetConverter, ConversionConfig
from data_transformer import FlightDataTransformer, TransformationConfig
from performance_optimizer import PerformanceOptimizer, PerformanceConfig
from error_recovery import ErrorRecoveryOrchestrator, RetryConfig, CircuitBreakerConfig

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark tests."""
    
    # Test data parameters
    test_data_sizes: List[int] = field(default_factory=lambda: [100, 1000, 10000, 50000])
    record_complexity: str = "medium"  # simple, medium, complex
    
    # Performance test settings
    warmup_iterations: int = 2
    test_iterations: int = 5
    memory_sampling_interval: float = 0.1  # seconds
    
    # Comparison scenarios
    test_scenarios: List[str] = field(default_factory=lambda: [
        "baseline",
        "optimized_conversion",
        "optimized_transformation",
        "full_optimization",
        "with_error_recovery"
    ])
    
    # Output settings
    detailed_logging: bool = True
    save_results: bool = True
    output_directory: str = "/tmp/benchmark_results"


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""
    
    # Time measurements (seconds)
    total_time: float = 0.0
    processing_time: float = 0.0
    io_time: float = 0.0
    
    # Memory measurements (MB)
    peak_memory_mb: float = 0.0
    average_memory_mb: float = 0.0
    memory_delta_mb: float = 0.0
    
    # Throughput measurements
    records_per_second: float = 0.0
    mb_per_second: float = 0.0
    
    # Quality measurements
    success_rate: float = 1.0
    error_count: int = 0
    retry_count: int = 0
    
    # File size measurements (MB)
    input_size_mb: float = 0.0
    output_size_mb: float = 0.0
    compression_ratio: float = 0.0
    
    # Additional metrics
    cpu_percent: float = 0.0
    gc_count: int = 0
    cache_hit_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'total_time': self.total_time,
            'processing_time': self.processing_time,
            'io_time': self.io_time,
            'peak_memory_mb': self.peak_memory_mb,
            'average_memory_mb': self.average_memory_mb,
            'memory_delta_mb': self.memory_delta_mb,
            'records_per_second': self.records_per_second,
            'mb_per_second': self.mb_per_second,
            'success_rate': self.success_rate,
            'error_count': self.error_count,
            'retry_count': self.retry_count,
            'input_size_mb': self.input_size_mb,
            'output_size_mb': self.output_size_mb,
            'compression_ratio': self.compression_ratio,
            'cpu_percent': self.cpu_percent,
            'gc_count': self.gc_count,
            'cache_hit_rate': self.cache_hit_rate
        }


class MemoryProfiler:
    """Memory usage profiler for detailed memory tracking."""
    
    def __init__(self, sampling_interval: float = 0.1):
        self.sampling_interval = sampling_interval
        self.process = psutil.Process()
        self.memory_samples = []
        self.start_memory = 0
        self.monitoring = False
    
    def start_monitoring(self):
        """Start memory monitoring."""
        self.start_memory = self.process.memory_info().rss / 1024 / 1024
        self.memory_samples = []
        self.monitoring = True
    
    def stop_monitoring(self) -> Dict[str, float]:
        """Stop monitoring and return memory statistics."""
        self.monitoring = False
        
        if not self.memory_samples:
            return {
                'peak_mb': self.start_memory,
                'average_mb': self.start_memory,
                'delta_mb': 0.0
            }
        
        peak_mb = max(self.memory_samples)
        average_mb = statistics.mean(self.memory_samples)
        delta_mb = peak_mb - self.start_memory
        
        return {
            'peak_mb': peak_mb,
            'average_mb': average_mb,
            'delta_mb': delta_mb
        }
    
    def sample_memory(self):
        """Take a memory sample."""
        if self.monitoring:
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            self.memory_samples.append(memory_mb)


class DataGenerator:
    """Generates test data with various complexity levels."""
    
    @staticmethod
    def generate_flight_record(complexity: str = "medium", timestamp: int = None) -> Dict[str, Any]:
        """Generate a single flight data record."""
        import random
        
        timestamp = timestamp or int(time.time())
        
        base_record = {
            "icao24": f"{''.join(random.choices('0123456789abcdef', k=6))}",
            "timestamp": timestamp,
            "latitude": round(random.uniform(25.0, 48.0), 6),
            "longitude": round(random.uniform(-125.0, -66.0), 6),
            "altitude": random.randint(0, 45000),
            "velocity": random.randint(0, 600),
            "heading": random.randint(0, 359),
            "vertical_rate": random.randint(-3000, 3000),
            "on_ground": random.choice([True, False])
        }
        
        if complexity in ["medium", "complex"]:
            base_record.update({
                "callsign": f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}{random.randint(100, 999)}",
                "squawk": f"{random.randint(1000, 7777):04d}",
                "spi": random.choice([True, False, None]),
                "position_source": random.choice([0, 1, 2, 3]),
                "category": random.choice([0, 1, 2, 3, 4, 5])
            })
        
        if complexity == "complex":
            base_record.update({
                "geoaltitude": base_record["altitude"] + random.randint(-100, 100),
                "last_position": {
                    "latitude": base_record["latitude"] + random.uniform(-0.001, 0.001),
                    "longitude": base_record["longitude"] + random.uniform(-0.001, 0.001),
                    "timestamp": timestamp - random.randint(1, 60)
                },
                "aircraft_info": {
                    "model": random.choice(["A320", "B737", "A330", "B777", "A380", "B747"]),
                    "registration": f"N{random.randint(100, 999)}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
                    "operator": random.choice(["American", "Delta", "United", "Southwest", "JetBlue"])
                },
                "flight_plan": {
                    "origin": ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4)),
                    "destination": ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4)),
                    "planned_altitude": random.randint(25000, 42000),
                    "estimated_arrival": timestamp + random.randint(3600, 18000)
                }
            })
        
        return base_record
    
    @classmethod
    def generate_test_data(cls, num_records: int, complexity: str = "medium") -> List[Dict[str, Any]]:
        """Generate test dataset."""
        records = []
        base_timestamp = int(time.time()) - (num_records * 10)  # 10 seconds apart
        
        for i in range(num_records):
            record = cls.generate_flight_record(complexity, base_timestamp + (i * 10))
            records.append(record)
        
        return records
    
    @classmethod
    def save_test_data_as_json(cls, records: List[Dict[str, Any]], filename: str) -> str:
        """Save test data to JSON file."""
        with open(filename, 'w') as f:
            for record in records:
                f.write(json.dumps(record) + '\n')
        return filename


class ConversionBenchmark:
    """Benchmark JSON to Parquet conversion performance."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.data_generator = DataGenerator()
    
    def benchmark_conversion_scenarios(self) -> Dict[str, Any]:
        """Benchmark different conversion scenarios."""
        results = {}
        
        for data_size in self.config.test_data_sizes:
            logger.info(f"Benchmarking conversion with {data_size} records")
            
            # Generate test data
            test_data = self.data_generator.generate_test_data(data_size, self.config.record_complexity)
            
            size_results = {}
            
            for scenario in self.config.test_scenarios:
                if scenario in ["baseline", "optimized_conversion", "full_optimization"]:
                    metrics = self._benchmark_conversion_scenario(test_data, scenario)
                    size_results[scenario] = metrics
            
            results[f"{data_size}_records"] = size_results
        
        return results
    
    def _benchmark_conversion_scenario(self, test_data: List[Dict[str, Any]], scenario: str) -> PerformanceMetrics:
        """Benchmark a specific conversion scenario."""
        metrics_list = []
        
        # Warmup runs
        for _ in range(self.config.warmup_iterations):
            self._run_conversion_test(test_data, scenario, warmup=True)
        
        # Actual test runs
        for _ in range(self.config.test_iterations):
            metrics = self._run_conversion_test(test_data, scenario, warmup=False)
            metrics_list.append(metrics)
        
        # Average the results
        return self._average_metrics(metrics_list)
    
    def _run_conversion_test(self, test_data: List[Dict[str, Any]], scenario: str, warmup: bool = False) -> PerformanceMetrics:
        """Run a single conversion test."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = os.path.join(temp_dir, 'input.json')
            output_file = os.path.join(temp_dir, 'output.parquet')
            
            # Save test data to JSON file
            self.data_generator.save_test_data_as_json(test_data, input_file)
            
            # Memory profiler
            profiler = MemoryProfiler(self.config.memory_sampling_interval)
            
            # Start monitoring
            profiler.start_monitoring()
            gc_start = len(gc.get_objects())
            cpu_start = psutil.cpu_percent()
            start_time = time.time()
            
            try:
                if scenario == "baseline":
                    result = self._baseline_conversion(input_file, output_file)
                elif scenario == "optimized_conversion":
                    result = self._optimized_conversion(input_file, output_file)
                elif scenario == "full_optimization":
                    result = self._full_optimized_conversion(input_file, output_file)
                else:
                    raise ValueError(f"Unknown scenario: {scenario}")
                
                success_rate = 1.0
                error_count = 0
                retry_count = 0
                
            except Exception as e:
                if not warmup:
                    logger.error(f"Test failed for scenario {scenario}: {str(e)}")
                success_rate = 0.0
                error_count = 1
                retry_count = 0
                result = {}
            
            # Stop monitoring
            end_time = time.time()
            cpu_end = psutil.cpu_percent()
            gc_end = len(gc.get_objects())
            memory_stats = profiler.stop_monitoring()
            
            # Calculate metrics
            metrics = PerformanceMetrics()
            metrics.total_time = end_time - start_time
            metrics.processing_time = result.get('processing_time_ms', 0) / 1000.0
            metrics.peak_memory_mb = memory_stats['peak_mb']
            metrics.average_memory_mb = memory_stats['average_mb']
            metrics.memory_delta_mb = memory_stats['delta_mb']
            metrics.success_rate = success_rate
            metrics.error_count = error_count
            metrics.retry_count = retry_count
            metrics.cpu_percent = (cpu_end - cpu_start) / 2.0  # Average
            metrics.gc_count = max(0, gc_end - gc_start)
            
            # File size metrics
            if os.path.exists(input_file):
                metrics.input_size_mb = os.path.getsize(input_file) / 1024 / 1024
            if os.path.exists(output_file):
                metrics.output_size_mb = os.path.getsize(output_file) / 1024 / 1024
                if metrics.input_size_mb > 0:
                    metrics.compression_ratio = metrics.input_size_mb / metrics.output_size_mb
            
            # Throughput metrics
            if metrics.total_time > 0:
                metrics.records_per_second = len(test_data) / metrics.total_time
                metrics.mb_per_second = metrics.input_size_mb / metrics.total_time
            
            return metrics
    
    def _baseline_conversion(self, input_file: str, output_file: str) -> Dict[str, Any]:
        """Baseline conversion using simple pandas approach."""
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        start_time = time.time()
        
        # Read JSON with pandas
        records = []
        with open(input_file, 'r') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        df = pd.DataFrame(records)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_file)
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            'processing_time_ms': processing_time,
            'records_processed': len(records)
        }
    
    def _optimized_conversion(self, input_file: str, output_file: str) -> Dict[str, Any]:
        """Optimized conversion using our OptimizedConverter."""
        config = ConversionConfig(
            chunk_size=5000,
            compression='snappy',
            use_dictionary_encoding=True,
            max_workers=2
        )
        
        converter = OptimizedJsonToParquetConverter(config)
        result = converter.convert_file(input_file, output_file)
        
        return {
            'processing_time_ms': converter.stats['total_processing_time_ms'],
            'records_processed': result['records_processed']
        }
    
    def _full_optimized_conversion(self, input_file: str, output_file: str) -> Dict[str, Any]:
        """Fully optimized conversion with all optimizations enabled."""
        perf_config = PerformanceConfig(
            enable_connection_pooling=True,
            enable_caching=True,
            enable_parallel_processing=True,
            max_workers=4
        )
        
        conv_config = ConversionConfig(
            chunk_size=10000,
            compression='zstd',
            use_dictionary_encoding=True,
            max_workers=4
        )
        
        optimizer = PerformanceOptimizer(perf_config)
        
        with optimizer.optimized_context("conversion"):
            converter = OptimizedJsonToParquetConverter(conv_config)
            result = converter.convert_file(input_file, output_file)
        
        return {
            'processing_time_ms': converter.stats['total_processing_time_ms'],
            'records_processed': result['records_processed'],
            'optimizer_stats': optimizer.get_performance_stats()
        }
    
    def _average_metrics(self, metrics_list: List[PerformanceMetrics]) -> PerformanceMetrics:
        """Average multiple performance metrics."""
        if not metrics_list:
            return PerformanceMetrics()
        
        avg_metrics = PerformanceMetrics()
        
        # Average all numeric fields
        numeric_fields = [
            'total_time', 'processing_time', 'io_time',
            'peak_memory_mb', 'average_memory_mb', 'memory_delta_mb',
            'records_per_second', 'mb_per_second',
            'input_size_mb', 'output_size_mb', 'compression_ratio',
            'cpu_percent', 'cache_hit_rate'
        ]
        
        for field in numeric_fields:
            values = [getattr(m, field) for m in metrics_list]
            setattr(avg_metrics, field, statistics.mean(values))
        
        # Sum integer fields
        avg_metrics.error_count = sum(m.error_count for m in metrics_list)
        avg_metrics.retry_count = sum(m.retry_count for m in metrics_list)
        avg_metrics.gc_count = int(statistics.mean([m.gc_count for m in metrics_list]))
        
        # Average success rate
        avg_metrics.success_rate = statistics.mean([m.success_rate for m in metrics_list])
        
        return avg_metrics


class TransformationBenchmark:
    """Benchmark data transformation performance."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.data_generator = DataGenerator()
    
    def benchmark_transformation_scenarios(self) -> Dict[str, Any]:
        """Benchmark different transformation scenarios."""
        results = {}
        
        for data_size in self.config.test_data_sizes:
            logger.info(f"Benchmarking transformation with {data_size} records")
            
            # Generate test data as DataFrame
            test_data = self.data_generator.generate_test_data(data_size, self.config.record_complexity)
            df = pd.DataFrame(test_data)
            
            size_results = {}
            
            for scenario in ["baseline_transformation", "optimized_transformation", "full_optimization"]:
                metrics = self._benchmark_transformation_scenario(df, scenario)
                size_results[scenario] = metrics
            
            results[f"{data_size}_records"] = size_results
        
        return results
    
    def _benchmark_transformation_scenario(self, df: pd.DataFrame, scenario: str) -> PerformanceMetrics:
        """Benchmark a specific transformation scenario."""
        metrics_list = []
        
        # Warmup runs
        for _ in range(self.config.warmup_iterations):
            self._run_transformation_test(df.copy(), scenario, warmup=True)
        
        # Actual test runs
        for _ in range(self.config.test_iterations):
            metrics = self._run_transformation_test(df.copy(), scenario, warmup=False)
            metrics_list.append(metrics)
        
        return self._average_transformation_metrics(metrics_list)
    
    def _run_transformation_test(self, df: pd.DataFrame, scenario: str, warmup: bool = False) -> PerformanceMetrics:
        """Run a single transformation test."""
        profiler = MemoryProfiler(self.config.memory_sampling_interval)
        
        # Start monitoring
        profiler.start_monitoring()
        gc_start = len(gc.get_objects())
        start_time = time.time()
        
        try:
            if scenario == "baseline_transformation":
                result_df, stats = self._baseline_transformation(df)
            elif scenario == "optimized_transformation":
                result_df, stats = self._optimized_transformation(df)
            elif scenario == "full_optimization":
                result_df, stats = self._full_optimized_transformation(df)
            else:
                raise ValueError(f"Unknown scenario: {scenario}")
            
            success_rate = 1.0
            error_count = 0
            
        except Exception as e:
            if not warmup:
                logger.error(f"Transformation test failed for scenario {scenario}: {str(e)}")
            success_rate = 0.0
            error_count = 1
            stats = None
        
        # Stop monitoring
        end_time = time.time()
        gc_end = len(gc.get_objects())
        memory_stats = profiler.stop_monitoring()
        
        # Calculate metrics
        metrics = PerformanceMetrics()
        metrics.total_time = end_time - start_time
        if stats:
            metrics.processing_time = stats.processing_time_ms / 1000.0
        metrics.peak_memory_mb = memory_stats['peak_mb']
        metrics.average_memory_mb = memory_stats['average_mb']
        metrics.memory_delta_mb = memory_stats['delta_mb']
        metrics.success_rate = success_rate
        metrics.error_count = error_count
        metrics.gc_count = max(0, gc_end - gc_start)
        
        if metrics.total_time > 0:
            metrics.records_per_second = len(df) / metrics.total_time
        
        return metrics
    
    def _baseline_transformation(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Any]:
        """Baseline transformation using simple pandas operations."""
        start_time = time.time()
        
        # Simple transformations
        if 'altitude' in df.columns:
            df['altitude_ft'] = df['altitude'] * 3.28084
        
        if 'velocity' in df.columns:
            df['speed_knots'] = df['velocity'] * 1.94384
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['icao24', 'timestamp'])
        
        processing_time = (time.time() - start_time) * 1000
        
        # Create mock stats object
        stats = type('Stats', (), {
            'processing_time_ms': processing_time,
            'records_input': len(df),
            'records_output': len(df)
        })()
        
        return df, stats
    
    def _optimized_transformation(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Any]:
        """Optimized transformation using FlightDataTransformer."""
        config = TransformationConfig(
            enable_altitude_ft=True,
            enable_speed_knots=True,
            enable_distance_calculations=True,
            enable_rate_calculations=True,
            enable_flight_phase_detection=True,
            enable_speed_categorization=True,
            duplicate_detection_enabled=True,
            use_vectorized_operations=True,
            enable_memory_optimization=True
        )
        
        transformer = FlightDataTransformer(config)
        result_df, stats = transformer.transform_dataframe(df)
        
        return result_df, stats
    
    def _full_optimized_transformation(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Any]:
        """Fully optimized transformation with performance optimizer."""
        perf_config = PerformanceConfig(
            enable_caching=True,
            enable_memory_monitoring=True,
            enable_parallel_processing=True,
            max_workers=4
        )
        
        trans_config = TransformationConfig(
            enable_altitude_ft=True,
            enable_speed_knots=True,
            enable_distance_calculations=True,
            enable_rate_calculations=True,
            enable_flight_phase_detection=True,
            enable_speed_categorization=True,
            duplicate_detection_enabled=True,
            use_vectorized_operations=True,
            enable_memory_optimization=True,
            parallel_processing=True,
            max_workers=4
        )
        
        optimizer = PerformanceOptimizer(perf_config)
        transformer = FlightDataTransformer(trans_config)
        
        with optimizer.optimized_context("transformation"):
            result_df, stats = transformer.transform_dataframe(df)
        
        return result_df, stats
    
    def _average_transformation_metrics(self, metrics_list: List[PerformanceMetrics]) -> PerformanceMetrics:
        """Average transformation-specific metrics."""
        if not metrics_list:
            return PerformanceMetrics()
        
        avg_metrics = PerformanceMetrics()
        
        numeric_fields = [
            'total_time', 'processing_time', 
            'peak_memory_mb', 'average_memory_mb', 'memory_delta_mb',
            'records_per_second'
        ]
        
        for field in numeric_fields:
            values = [getattr(m, field) for m in metrics_list]
            setattr(avg_metrics, field, statistics.mean(values))
        
        avg_metrics.error_count = sum(m.error_count for m in metrics_list)
        avg_metrics.gc_count = int(statistics.mean([m.gc_count for m in metrics_list]))
        avg_metrics.success_rate = statistics.mean([m.success_rate for m in metrics_list])
        
        return avg_metrics


class ETLBenchmarkSuite:
    """Complete ETL benchmarking suite."""
    
    def __init__(self, config: BenchmarkConfig = None):
        self.config = config or BenchmarkConfig()
        
        # Create output directory
        os.makedirs(self.config.output_directory, exist_ok=True)
        
        # Initialize benchmark components
        self.conversion_benchmark = ConversionBenchmark(self.config)
        self.transformation_benchmark = TransformationBenchmark(self.config)
        
        logger.info("ETL Benchmark Suite initialized")
    
    def run_full_benchmark_suite(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        logger.info("Starting comprehensive ETL benchmark suite")
        
        suite_start_time = time.time()
        
        results = {
            'benchmark_config': {
                'test_data_sizes': self.config.test_data_sizes,
                'record_complexity': self.config.record_complexity,
                'test_iterations': self.config.test_iterations,
                'scenarios': self.config.test_scenarios
            },
            'system_info': self._get_system_info(),
            'conversion_benchmarks': {},
            'transformation_benchmarks': {},
            'end_to_end_benchmarks': {},
            'performance_improvements': {},
            'recommendations': []
        }
        
        try:
            # Run conversion benchmarks
            logger.info("Running conversion benchmarks...")
            results['conversion_benchmarks'] = self.conversion_benchmark.benchmark_conversion_scenarios()
            
            # Run transformation benchmarks
            logger.info("Running transformation benchmarks...")
            results['transformation_benchmarks'] = self.transformation_benchmark.benchmark_transformation_scenarios()
            
            # Analyze performance improvements
            logger.info("Analyzing performance improvements...")
            results['performance_improvements'] = self._analyze_performance_improvements(results)
            
            # Generate recommendations
            results['recommendations'] = self._generate_recommendations(results)
            
        except Exception as e:
            logger.error(f"Benchmark suite failed: {str(e)}")
            results['error'] = str(e)
            results['stack_trace'] = traceback.format_exc()
        
        results['total_benchmark_time'] = time.time() - suite_start_time
        
        # Save results
        if self.config.save_results:
            self._save_results(results)
        
        logger.info(f"Benchmark suite completed in {results['total_benchmark_time']:.1f} seconds")
        return results
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for benchmark context."""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_gb': psutil.virtual_memory().total / (1024**3),
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'platform': os.sys.platform
        }
    
    def _analyze_performance_improvements(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance improvements across scenarios."""
        improvements = {}
        
        # Analyze conversion improvements
        conv_results = results.get('conversion_benchmarks', {})
        for size_key, scenarios in conv_results.items():
            if 'baseline' in scenarios and 'full_optimization' in scenarios:
                baseline = scenarios['baseline']
                optimized = scenarios['full_optimization']
                
                improvements[f"conversion_{size_key}"] = {
                    'time_improvement': (baseline.total_time - optimized.total_time) / baseline.total_time * 100,
                    'memory_improvement': (baseline.peak_memory_mb - optimized.peak_memory_mb) / baseline.peak_memory_mb * 100,
                    'throughput_improvement': (optimized.records_per_second - baseline.records_per_second) / baseline.records_per_second * 100,
                    'compression_improvement': optimized.compression_ratio / baseline.compression_ratio if baseline.compression_ratio > 0 else 0
                }
        
        # Analyze transformation improvements
        trans_results = results.get('transformation_benchmarks', {})
        for size_key, scenarios in trans_results.items():
            if 'baseline_transformation' in scenarios and 'full_optimization' in scenarios:
                baseline = scenarios['baseline_transformation']
                optimized = scenarios['full_optimization']
                
                improvements[f"transformation_{size_key}"] = {
                    'time_improvement': (baseline.total_time - optimized.total_time) / baseline.total_time * 100,
                    'memory_improvement': (baseline.peak_memory_mb - optimized.peak_memory_mb) / baseline.peak_memory_mb * 100,
                    'throughput_improvement': (optimized.records_per_second - baseline.records_per_second) / baseline.records_per_second * 100
                }
        
        return improvements
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        improvements = results.get('performance_improvements', {})
        
        # Check overall improvement trends
        time_improvements = [v['time_improvement'] for v in improvements.values() if 'time_improvement' in v]
        memory_improvements = [v['memory_improvement'] for v in improvements.values() if 'memory_improvement' in v]
        
        if time_improvements:
            avg_time_improvement = statistics.mean(time_improvements)
            if avg_time_improvement > 50:
                recommendations.append("Excellent time performance improvements achieved (>50% faster)")
            elif avg_time_improvement > 20:
                recommendations.append("Good time performance improvements achieved (>20% faster)")
            elif avg_time_improvement < 0:
                recommendations.append("Warning: Optimizations are slowing down processing - review configuration")
        
        if memory_improvements:
            avg_memory_improvement = statistics.mean(memory_improvements)
            if avg_memory_improvement > 30:
                recommendations.append("Significant memory usage reduction achieved (>30% less memory)")
            elif avg_memory_improvement < 0:
                recommendations.append("Warning: Optimizations are using more memory - consider reducing chunk sizes")
        
        # Check system utilization
        system_info = results.get('system_info', {})
        if system_info.get('cpu_count', 1) > 4:
            recommendations.append("Consider increasing max_workers for parallel processing on multi-core system")
        
        if system_info.get('memory_gb', 0) > 8:
            recommendations.append("Consider increasing chunk_size and cache_size with available memory")
        
        return recommendations
    
    def _save_results(self, results: Dict[str, Any]):
        """Save benchmark results to files."""
        timestamp = int(time.time())
        
        # Save JSON results
        json_file = os.path.join(self.config.output_directory, f'benchmark_results_{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save CSV summary
        csv_file = os.path.join(self.config.output_directory, f'benchmark_summary_{timestamp}.csv')
        self._save_csv_summary(results, csv_file)
        
        logger.info(f"Results saved to {json_file} and {csv_file}")
    
    def _save_csv_summary(self, results: Dict[str, Any], csv_file: str):
        """Save summary results as CSV."""
        rows = []
        
        # Process conversion results
        conv_results = results.get('conversion_benchmarks', {})
        for size_key, scenarios in conv_results.items():
            for scenario, metrics in scenarios.items():
                row = {
                    'benchmark_type': 'conversion',
                    'data_size': size_key,
                    'scenario': scenario,
                    'total_time': metrics.total_time,
                    'peak_memory_mb': metrics.peak_memory_mb,
                    'records_per_second': metrics.records_per_second,
                    'compression_ratio': metrics.compression_ratio,
                    'success_rate': metrics.success_rate
                }
                rows.append(row)
        
        # Process transformation results
        trans_results = results.get('transformation_benchmarks', {})
        for size_key, scenarios in trans_results.items():
            for scenario, metrics in scenarios.items():
                row = {
                    'benchmark_type': 'transformation',
                    'data_size': size_key,
                    'scenario': scenario,
                    'total_time': metrics.total_time,
                    'peak_memory_mb': metrics.peak_memory_mb,
                    'records_per_second': metrics.records_per_second,
                    'compression_ratio': 0.0,  # Not applicable for transformations
                    'success_rate': metrics.success_rate
                }
                rows.append(row)
        
        # Save to CSV
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(csv_file, index=False)


def run_quick_benchmark():
    """Run a quick benchmark for testing purposes."""
    config = BenchmarkConfig(
        test_data_sizes=[100, 1000],
        test_iterations=2,
        warmup_iterations=1,
        save_results=True
    )
    
    suite = ETLBenchmarkSuite(config)
    results = suite.run_full_benchmark_suite()
    
    return results


if __name__ == "__main__":
    # Run benchmark suite
    results = run_quick_benchmark()
    print("Benchmark completed!")
    print(f"Results saved to: {results.get('output_directory', 'N/A')}")