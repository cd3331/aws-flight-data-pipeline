"""
Performance Optimization Components for ETL Pipeline.

This module provides comprehensive performance optimizations including
connection pooling, caching strategies, lazy loading, and memory-efficient operations.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import logging
import time
import threading
import weakref
import gc
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from functools import wraps, lru_cache
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import hashlib
import pickle
from collections import OrderedDict
import psutil

# Lazy imports for performance
boto3_session = None
connection_pools = {}

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _lazy_import_boto3():
    """Lazy import boto3 with optimized session management."""
    global boto3_session
    if boto3_session is None:
        import boto3
        from botocore.config import Config
        
        # Create optimized session
        boto3_session = boto3.Session()
        
        # Configure default client settings
        boto3_session._default_config = Config(
            region_name='us-east-1',
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50,
            read_timeout=60,
            connect_timeout=10
        )
    
    return boto3_session


@dataclass
class PerformanceConfig:
    """Configuration for performance optimizations."""
    
    # Connection pooling
    enable_connection_pooling: bool = True
    max_pool_connections: int = 50
    pool_timeout_seconds: int = 30
    
    # Caching
    enable_caching: bool = True
    cache_size: int = 1000
    cache_ttl_seconds: int = 3600
    enable_memory_cache: bool = True
    enable_disk_cache: bool = False
    cache_directory: str = '/tmp/etl_cache'
    
    # Memory optimization
    enable_memory_monitoring: bool = True
    memory_limit_mb: int = 1536  # Lambda memory limit
    memory_threshold_percent: float = 0.8  # Trigger cleanup at 80%
    gc_frequency: int = 10  # Force GC every N operations
    
    # Parallel processing
    enable_parallel_processing: bool = True
    max_workers: int = 4
    use_process_pool: bool = False  # Use thread pool by default
    chunk_size: int = 1000
    
    # Lazy loading
    enable_lazy_imports: bool = True
    preload_critical_modules: bool = False
    
    # Library optimizations
    pandas_engine: str = 'c'  # Use C engine for pandas
    enable_numexpr: bool = True
    enable_bottleneck: bool = True
    
    # Network optimizations
    request_timeout: int = 30
    retry_backoff_factor: float = 0.3
    max_retries: int = 3


class ConnectionPoolManager:
    """Thread-safe connection pool manager for AWS services."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            self.pools = {}
            self.config = PerformanceConfig()
            self._lock = threading.RLock()
            self._initialized = True
    
    def get_client(self, service_name: str, region_name: str = None) -> Any:
        """Get pooled AWS client."""
        session = _lazy_import_boto3()
        
        pool_key = f"{service_name}_{region_name or 'default'}"
        
        with self._lock:
            if pool_key not in self.pools:
                client = session.client(
                    service_name,
                    region_name=region_name,
                    config=session._default_config
                )
                self.pools[pool_key] = client
                logger.debug(f"Created new connection pool for {service_name}")
            
            return self.pools[pool_key]
    
    def clear_pools(self):
        """Clear all connection pools."""
        with self._lock:
            self.pools.clear()
            logger.info("Cleared all connection pools")


class CacheManager:
    """Advanced caching system with multiple strategies."""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self._memory_cache = OrderedDict()
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._memory_cache:
                # Move to end (LRU)
                self._memory_cache.move_to_end(key)
                self._cache_stats['hits'] += 1
                return self._memory_cache[key]['value']
            
            self._cache_stats['misses'] += 1
            return None
    
    def put(self, key: str, value: Any, ttl: int = None) -> None:
        """Put value into cache."""
        with self._lock:
            ttl = ttl or self.config.cache_ttl_seconds
            
            # Check cache size limit
            if len(self._memory_cache) >= self.config.cache_size:
                # Remove oldest item
                self._memory_cache.popitem(last=False)
                self._cache_stats['evictions'] += 1
            
            self._memory_cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl
            }
    
    def is_expired(self, key: str) -> bool:
        """Check if cache entry is expired."""
        with self._lock:
            if key not in self._memory_cache:
                return True
            
            entry = self._memory_cache[key]
            age = time.time() - entry['timestamp']
            return age > entry['ttl']
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key in self._memory_cache
                if self.is_expired(key)
            ]
            
            for key in expired_keys:
                del self._memory_cache[key]
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = self._cache_stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._memory_cache),
            'max_size': self.config.cache_size,
            'hit_rate': hit_rate,
            'total_hits': self._cache_stats['hits'],
            'total_misses': self._cache_stats['misses'],
            'evictions': self._cache_stats['evictions']
        }
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._memory_cache.clear()


class MemoryMonitor:
    """Memory usage monitoring and optimization."""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.process = psutil.Process()
        self._peak_memory = 0
        self._gc_counter = 0
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        
        memory_mb = memory_info.rss / 1024 / 1024
        self._peak_memory = max(self._peak_memory, memory_mb)
        
        return {
            'current_mb': memory_mb,
            'peak_mb': self._peak_memory,
            'percent': memory_percent,
            'limit_mb': self.config.memory_limit_mb,
            'threshold_mb': self.config.memory_limit_mb * self.config.memory_threshold_percent
        }
    
    def is_memory_pressure(self) -> bool:
        """Check if system is under memory pressure."""
        memory_stats = self.get_memory_usage()
        return memory_stats['current_mb'] > memory_stats['threshold_mb']
    
    def force_gc(self) -> Dict[str, int]:
        """Force garbage collection and return statistics."""
        collected = gc.collect()
        self._gc_counter += 1
        
        return {
            'objects_collected': collected,
            'gc_runs': self._gc_counter,
            'memory_after_gc': self.get_memory_usage()['current_mb']
        }
    
    @contextmanager
    def memory_context(self, operation_name: str = "operation"):
        """Context manager for memory monitoring."""
        start_memory = self.get_memory_usage()
        start_time = time.time()
        
        try:
            yield
        finally:
            end_memory = self.get_memory_usage()
            duration = time.time() - start_time
            
            memory_delta = end_memory['current_mb'] - start_memory['current_mb']
            
            logger.debug(f"{operation_name}: memory delta {memory_delta:.1f}MB, "
                        f"duration {duration:.2f}s")
            
            # Force GC if memory pressure detected
            if self.is_memory_pressure():
                gc_stats = self.force_gc()
                logger.info(f"Memory pressure detected, forced GC: {gc_stats}")


def cached(ttl: int = None, key_func: Callable = None):
    """Decorator for caching function results."""
    def decorator(func):
        cache = CacheManager(PerformanceConfig())
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_data = f"{func.__name__}_{str(args)}_{str(sorted(kwargs.items()))}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.put(cache_key, result, ttl)
            
            return result
        
        wrapper._cache = cache
        return wrapper
    
    return decorator


def memory_efficient(threshold_mb: int = 1024):
    """Decorator to ensure memory-efficient execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = MemoryMonitor(PerformanceConfig())
            
            with monitor.memory_context(func.__name__):
                # Check memory before execution
                if monitor.is_memory_pressure():
                    monitor.force_gc()
                
                result = func(*args, **kwargs)
                
                # Periodic GC during execution
                monitor._gc_counter += 1
                if monitor._gc_counter % 10 == 0:
                    if monitor.is_memory_pressure():
                        monitor.force_gc()
                
                return result
        
        return wrapper
    return decorator


class ParallelProcessor:
    """Optimized parallel processing with smart work distribution."""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.memory_monitor = MemoryMonitor(config)
    
    def process_chunks(self, data: List[Any], processing_func: Callable,
                      chunk_size: int = None, use_processes: bool = None) -> List[Any]:
        """Process data in parallel chunks."""
        chunk_size = chunk_size or self.config.chunk_size
        use_processes = use_processes or self.config.use_process_pool
        
        # Split data into chunks
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        
        if not self.config.enable_parallel_processing or len(chunks) == 1:
            # Sequential processing
            return [processing_func(chunk) for chunk in chunks]
        
        # Parallel processing
        executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        max_workers = min(self.config.max_workers, len(chunks))
        
        results = []
        
        with executor_class(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {executor.submit(processing_func, chunk): i for i, chunk in enumerate(chunks)}
            
            # Collect results maintaining order
            chunk_results = [None] * len(chunks)
            
            for future in as_completed(futures):
                chunk_index = futures[future]
                try:
                    result = future.result()
                    chunk_results[chunk_index] = result
                    
                    # Memory monitoring
                    if self.memory_monitor.is_memory_pressure():
                        logger.warning("Memory pressure detected during parallel processing")
                        
                except Exception as e:
                    logger.error(f"Chunk {chunk_index} processing failed: {str(e)}")
                    chunk_results[chunk_index] = None
        
        # Filter out failed chunks
        results = [r for r in chunk_results if r is not None]
        
        return results


class LazyImportManager:
    """Manages lazy importing of heavy libraries."""
    
    _imports = {}
    _lock = threading.Lock()
    
    @classmethod
    def lazy_import(cls, module_name: str, alias: str = None):
        """Lazy import a module."""
        alias = alias or module_name
        
        with cls._lock:
            if alias not in cls._imports:
                try:
                    import importlib
                    module = importlib.import_module(module_name)
                    cls._imports[alias] = module
                    logger.debug(f"Lazily imported {module_name} as {alias}")
                except ImportError as e:
                    logger.error(f"Failed to import {module_name}: {str(e)}")
                    cls._imports[alias] = None
            
            return cls._imports[alias]
    
    @classmethod
    def get_module(cls, alias: str):
        """Get a lazily imported module."""
        return cls._imports.get(alias)
    
    @classmethod
    def preload_modules(cls, modules: List[Tuple[str, str]]):
        """Preload a list of modules."""
        for module_name, alias in modules:
            cls.lazy_import(module_name, alias)


class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()
        
        # Initialize components
        self.connection_pool = ConnectionPoolManager()
        self.cache_manager = CacheManager(self.config)
        self.memory_monitor = MemoryMonitor(self.config)
        self.parallel_processor = ParallelProcessor(self.config)
        self.lazy_imports = LazyImportManager()
        
        # Performance tracking
        self.stats = {
            'operations_count': 0,
            'total_processing_time_ms': 0,
            'cache_hit_rate': 0.0,
            'memory_peak_mb': 0.0,
            'gc_runs': 0
        }
        
        # Configure library optimizations
        self._configure_libraries()
        
        logger.info("PerformanceOptimizer initialized with optimized settings")
    
    def _configure_libraries(self):
        """Configure library-specific optimizations."""
        # Configure pandas optimizations
        try:
            pd = self.lazy_imports.lazy_import('pandas', 'pd')
            if pd:
                pd.options.mode.chained_assignment = None
                pd.options.compute.use_bottleneck = self.config.enable_bottleneck
                pd.options.compute.use_numexpr = self.config.enable_numexpr
        except Exception as e:
            logger.warning(f"Failed to configure pandas optimizations: {str(e)}")
        
        # Configure numpy optimizations
        try:
            np = self.lazy_imports.lazy_import('numpy', 'np')
            if np and hasattr(np, 'seterr'):
                np.seterr(all='ignore')  # Ignore numeric warnings for performance
        except Exception as e:
            logger.warning(f"Failed to configure numpy optimizations: {str(e)}")
    
    def get_aws_client(self, service_name: str, region_name: str = None):
        """Get optimized AWS client with connection pooling."""
        return self.connection_pool.get_client(service_name, region_name)
    
    def cache_result(self, key: str, value: Any, ttl: int = None):
        """Cache a result with automatic cleanup."""
        self.cache_manager.put(key, value, ttl)
        
        # Periodic cache cleanup
        if self.stats['operations_count'] % 100 == 0:
            expired_count = self.cache_manager.cleanup_expired()
            if expired_count > 0:
                logger.debug(f"Cleaned up {expired_count} expired cache entries")
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result if available."""
        return self.cache_manager.get(key)
    
    @contextmanager
    def optimized_context(self, operation_name: str = "operation"):
        """Context manager providing comprehensive optimizations."""
        start_time = time.time()
        
        with self.memory_monitor.memory_context(operation_name):
            try:
                yield self
                
            finally:
                # Update performance stats
                duration_ms = (time.time() - start_time) * 1000
                self.stats['operations_count'] += 1
                self.stats['total_processing_time_ms'] += duration_ms
                
                # Update cache stats
                cache_stats = self.cache_manager.get_stats()
                self.stats['cache_hit_rate'] = cache_stats['hit_rate']
                
                # Update memory stats
                memory_stats = self.memory_monitor.get_memory_usage()
                self.stats['memory_peak_mb'] = max(
                    self.stats['memory_peak_mb'],
                    memory_stats['peak_mb']
                )
                
                # Periodic cleanup
                if self.stats['operations_count'] % self.config.gc_frequency == 0:
                    if self.memory_monitor.is_memory_pressure():
                        gc_stats = self.memory_monitor.force_gc()
                        self.stats['gc_runs'] += 1
                        logger.debug(f"Periodic GC run: {gc_stats}")
    
    def process_parallel(self, data: List[Any], processing_func: Callable,
                        chunk_size: int = None) -> List[Any]:
        """Process data with optimal parallelization."""
        return self.parallel_processor.process_chunks(data, processing_func, chunk_size)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        cache_stats = self.cache_manager.get_stats()
        memory_stats = self.memory_monitor.get_memory_usage()
        
        avg_processing_time = (
            self.stats['total_processing_time_ms'] / max(1, self.stats['operations_count'])
        )
        
        return {
            'operations': {
                'total_count': self.stats['operations_count'],
                'total_processing_time_ms': self.stats['total_processing_time_ms'],
                'average_processing_time_ms': avg_processing_time
            },
            'cache': cache_stats,
            'memory': {
                'current_mb': memory_stats['current_mb'],
                'peak_mb': memory_stats['peak_mb'],
                'limit_mb': memory_stats['limit_mb'],
                'gc_runs': self.stats['gc_runs']
            },
            'configuration': {
                'connection_pooling': self.config.enable_connection_pooling,
                'caching_enabled': self.config.enable_caching,
                'parallel_processing': self.config.enable_parallel_processing,
                'max_workers': self.config.max_workers,
                'memory_monitoring': self.config.enable_memory_monitoring
            }
        }
    
    def cleanup(self):
        """Cleanup resources and caches."""
        self.cache_manager.clear()
        self.connection_pool.clear_pools()
        gc.collect()
        
        logger.info("Performance optimizer cleanup completed")