"""
Advanced Error Recovery and Resilience System for ETL Pipeline.

This module provides comprehensive error recovery mechanisms including
exponential backoff, dead letter queue processing, partial failure handling,
and circuit breaker patterns for robust data processing.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import logging
import time
import json
import traceback
import random
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from collections import defaultdict, deque
import uuid
from datetime import datetime, timezone, timedelta

# Lazy imports
boto3_session = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _lazy_import_boto3():
    """Lazy import boto3 for AWS services."""
    global boto3_session
    if boto3_session is None:
        import boto3
        from botocore.exceptions import ClientError, BotoCoreError
        boto3_session = boto3.Session()
        boto3_session.ClientError = ClientError
        boto3_session.BotoCoreError = BotoCoreError
    return boto3_session


class ErrorType(Enum):
    """Classification of error types for different handling strategies."""
    TRANSIENT = "transient"        # Network timeouts, temporary service unavailability
    PERMANENT = "permanent"        # Invalid data format, missing required fields
    THROTTLING = "throttling"      # Rate limiting, quota exceeded
    RESOURCE = "resource"          # Memory limits, disk space, connection limits
    DATA_QUALITY = "data_quality"  # Corrupt data, validation failures
    UNKNOWN = "unknown"            # Unclassified errors


class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED = "fixed"                # Fixed delay between retries
    EXPONENTIAL = "exponential"    # Exponential backoff with jitter
    LINEAR = "linear"              # Linear increase in delay
    CUSTOM = "custom"              # Custom retry logic


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    
    # Error-specific retry strategies
    strategy_by_error: Dict[ErrorType, RetryStrategy] = field(default_factory=lambda: {
        ErrorType.TRANSIENT: RetryStrategy.EXPONENTIAL,
        ErrorType.THROTTLING: RetryStrategy.EXPONENTIAL,
        ErrorType.RESOURCE: RetryStrategy.LINEAR,
        ErrorType.DATA_QUALITY: RetryStrategy.FIXED,
        ErrorType.PERMANENT: RetryStrategy.FIXED,  # Usually no retry
        ErrorType.UNKNOWN: RetryStrategy.EXPONENTIAL
    })
    
    # Maximum retry attempts by error type
    max_attempts_by_error: Dict[ErrorType, int] = field(default_factory=lambda: {
        ErrorType.TRANSIENT: 5,
        ErrorType.THROTTLING: 10,
        ErrorType.RESOURCE: 3,
        ErrorType.DATA_QUALITY: 1,
        ErrorType.PERMANENT: 0,  # No retries for permanent errors
        ErrorType.UNKNOWN: 3
    })


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    
    failure_threshold: int = 5      # Number of failures before opening circuit
    timeout_seconds: int = 60       # How long to keep circuit open
    half_open_max_calls: int = 3    # Max calls to test in half-open state
    rolling_window_seconds: int = 300  # Window for failure rate calculation


@dataclass
class DeadLetterConfig:
    """Configuration for dead letter queue processing."""
    
    dlq_queue_url: Optional[str] = None
    dlq_bucket: Optional[str] = None
    dlq_prefix: str = "failed-records"
    
    # Retry from DLQ settings
    dlq_retry_enabled: bool = True
    dlq_retry_delay_hours: int = 24
    dlq_max_retries: int = 3
    
    # Error analysis
    enable_error_analysis: bool = True
    error_pattern_detection: bool = True


@dataclass
class ErrorRecord:
    """Represents an error occurrence with context."""
    
    error_id: str
    timestamp: datetime
    error_type: ErrorType
    error_message: str
    stack_trace: str
    operation: str
    input_data: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error record to dictionary."""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type.value,
            'error_message': self.error_message,
            'stack_trace': self.stack_trace,
            'operation': self.operation,
            'input_data': self.input_data,
            'retry_count': self.retry_count,
            'resolved': self.resolved,
            'resolution_timestamp': self.resolution_timestamp.isoformat() if self.resolution_timestamp else None
        }


class CircuitBreaker:
    """Circuit breaker implementation for failure isolation."""
    
    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        self.config = config
        self.name = name
        
        # State management
        self.state = "closed"  # closed, open, half-open
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        
        # Rolling window for failure tracking
        self.failure_times = deque()
        self._lock = threading.RLock()
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                    self.half_open_calls = 0
                    logger.info(f"Circuit breaker '{self.name}' moved to half-open state")
                else:
                    raise CircuitBreakerError(f"Circuit breaker '{self.name}' is open")
            
            if self.state == "half-open" and self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' half-open call limit exceeded")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset from open to half-open."""
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout_seconds
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self.state == "half-open":
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self.state = "closed"
                    self.failure_count = 0
                    self.failure_times.clear()
                    logger.info(f"Circuit breaker '{self.name}' closed after successful half-open test")
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            current_time = time.time()
            self.failure_count += 1
            self.last_failure_time = current_time
            self.failure_times.append(current_time)
            
            # Clean old failures outside rolling window
            cutoff_time = current_time - self.config.rolling_window_seconds
            while self.failure_times and self.failure_times[0] < cutoff_time:
                self.failure_times.popleft()
            
            # Check if should open circuit
            if self.state != "open" and len(self.failure_times) >= self.config.failure_threshold:
                self.state = "open"
                logger.warning(f"Circuit breaker '{self.name}' opened due to {len(self.failure_times)} failures")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            'name': self.name,
            'state': self.state,
            'failure_count': self.failure_count,
            'failures_in_window': len(self.failure_times),
            'last_failure_time': self.last_failure_time,
            'half_open_calls': self.half_open_calls if self.state == "half-open" else None
        }


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker prevents execution."""
    pass


class RetryableError(Exception):
    """Base exception for errors that should be retried."""
    
    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN, original_error: Exception = None):
        super().__init__(message)
        self.error_type = error_type
        self.original_error = original_error


class ErrorClassifier:
    """Classifies errors to determine appropriate handling strategy."""
    
    @staticmethod
    def classify_error(error: Exception) -> ErrorType:
        """Classify an error to determine retry strategy."""
        error_msg = str(error).lower()
        error_name = type(error).__name__.lower()
        
        # AWS specific error classification
        if hasattr(error, 'response'):
            error_code = error.response.get('Error', {}).get('Code', '').lower()
            
            # Throttling errors
            if error_code in ['throttling', 'throttlingexception', 'requestlimitexceeded', 'toomanyrequests']:
                return ErrorType.THROTTLING
            
            # Transient service errors
            if error_code in ['serviceunavailable', 'internalerror', 'requesttimeout']:
                return ErrorType.TRANSIENT
            
            # Resource limits
            if error_code in ['limitexceeded', 'quotaexceeded']:
                return ErrorType.RESOURCE
            
            # Permanent errors
            if error_code in ['validationexception', 'invalidparameter', 'accessdenied']:
                return ErrorType.PERMANENT
        
        # Network and connection errors
        if any(term in error_msg for term in ['timeout', 'connection', 'network', 'dns']):
            return ErrorType.TRANSIENT
        
        # Memory and resource errors
        if any(term in error_name for term in ['memory', 'resource', 'limit']):
            return ErrorType.RESOURCE
        
        # Data quality errors
        if any(term in error_msg for term in ['json', 'parse', 'format', 'invalid', 'corrupt']):
            return ErrorType.DATA_QUALITY
        
        # Default to unknown for unclassified errors
        return ErrorType.UNKNOWN


class RetryManager:
    """Manages retry logic with multiple strategies and error classification."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.classifier = ErrorClassifier()
        
        # Retry statistics
        self.retry_stats = defaultdict(lambda: {
            'attempts': 0,
            'successes': 0,
            'permanent_failures': 0,
            'max_retries_exceeded': 0
        })
    
    def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with intelligent retry and backoff."""
        operation_name = func.__name__
        last_error = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                
                # Update success stats
                self.retry_stats[operation_name]['successes'] += 1
                
                if attempt > 1:
                    logger.info(f"Operation '{operation_name}' succeeded on attempt {attempt}")
                
                return result
                
            except Exception as error:
                last_error = error
                error_type = self.classifier.classify_error(error)
                
                self.retry_stats[operation_name]['attempts'] += 1
                
                # Check if error should be retried
                max_attempts = self.config.max_attempts_by_error.get(error_type, self.config.max_attempts)
                
                if attempt >= max_attempts:
                    if error_type == ErrorType.PERMANENT:
                        self.retry_stats[operation_name]['permanent_failures'] += 1
                        logger.error(f"Permanent error in '{operation_name}': {str(error)}")
                    else:
                        self.retry_stats[operation_name]['max_retries_exceeded'] += 1
                        logger.error(f"Max retries exceeded for '{operation_name}' after {attempt} attempts")
                    
                    raise error
                
                # Calculate delay
                delay = self._calculate_delay(attempt, error_type)
                
                logger.warning(f"Attempt {attempt} failed for '{operation_name}': {str(error)}, "
                             f"retrying in {delay:.1f}s")
                
                time.sleep(delay)
        
        # Should not reach here, but raise last error if it does
        raise last_error
    
    def _calculate_delay(self, attempt: int, error_type: ErrorType) -> float:
        """Calculate delay for next retry attempt."""
        strategy = self.config.strategy_by_error.get(error_type, RetryStrategy.EXPONENTIAL)
        
        if strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay_seconds
        elif strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay_seconds * attempt
        elif strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay_seconds * (self.config.backoff_multiplier ** (attempt - 1))
        else:
            delay = self.config.base_delay_seconds
        
        # Apply jitter to prevent thundering herd
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            jitter = random.uniform(-jitter_range, jitter_range)
            delay += jitter
        
        # Ensure delay doesn't exceed maximum
        return min(delay, self.config.max_delay_seconds)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        return dict(self.retry_stats)


class DeadLetterManager:
    """Manages dead letter queue processing and failed record recovery."""
    
    def __init__(self, config: DeadLetterConfig):
        self.config = config
        
        # AWS clients (lazy initialized)
        self._sqs_client = None
        self._s3_client = None
        
        # Error tracking
        self.error_records = {}
        self._lock = threading.RLock()
    
    @property
    def sqs_client(self):
        """Lazy-initialized SQS client."""
        if self._sqs_client is None:
            session = _lazy_import_boto3()
            self._sqs_client = session.client('sqs')
        return self._sqs_client
    
    @property
    def s3_client(self):
        """Lazy-initialized S3 client."""
        if self._s3_client is None:
            session = _lazy_import_boto3()
            self._s3_client = session.client('s3')
        return self._s3_client
    
    def send_to_dlq(self, operation: str, input_data: Any, error: Exception) -> str:
        """Send failed record to dead letter queue."""
        error_id = str(uuid.uuid4())
        error_record = ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(timezone.utc),
            error_type=ErrorClassifier.classify_error(error),
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            operation=operation,
            input_data=input_data if isinstance(input_data, dict) else {'raw_data': str(input_data)}
        )
        
        with self._lock:
            self.error_records[error_id] = error_record
        
        try:
            # Send to SQS DLQ if configured
            if self.config.dlq_queue_url:
                self._send_to_sqs_dlq(error_record)
            
            # Store in S3 DLQ if configured
            if self.config.dlq_bucket:
                self._store_in_s3_dlq(error_record)
            
            logger.info(f"Sent record to DLQ: {error_id}")
            return error_id
            
        except Exception as dlq_error:
            logger.error(f"Failed to send record to DLQ: {str(dlq_error)}")
            raise
    
    def _send_to_sqs_dlq(self, error_record: ErrorRecord):
        """Send error record to SQS dead letter queue."""
        message_body = json.dumps(error_record.to_dict())
        
        self.sqs_client.send_message(
            QueueUrl=self.config.dlq_queue_url,
            MessageBody=message_body,
            MessageAttributes={
                'error_type': {
                    'StringValue': error_record.error_type.value,
                    'DataType': 'String'
                },
                'operation': {
                    'StringValue': error_record.operation,
                    'DataType': 'String'
                },
                'retry_count': {
                    'StringValue': str(error_record.retry_count),
                    'DataType': 'Number'
                }
            }
        )
    
    def _store_in_s3_dlq(self, error_record: ErrorRecord):
        """Store error record in S3 dead letter bucket."""
        key = f"{self.config.dlq_prefix}/{error_record.timestamp.strftime('%Y/%m/%d')}/{error_record.error_id}.json"
        
        self.s3_client.put_object(
            Bucket=self.config.dlq_bucket,
            Key=key,
            Body=json.dumps(error_record.to_dict(), indent=2),
            ContentType='application/json',
            Metadata={
                'error_type': error_record.error_type.value,
                'operation': error_record.operation,
                'retry_count': str(error_record.retry_count)
            }
        )
    
    def process_dlq_records(self, processing_func: Callable, max_records: int = 10) -> List[str]:
        """Process records from dead letter queue."""
        if not self.config.dlq_queue_url:
            logger.warning("DLQ URL not configured")
            return []
        
        processed_records = []
        
        try:
            # Receive messages from DLQ
            response = self.sqs_client.receive_message(
                QueueUrl=self.config.dlq_queue_url,
                MaxNumberOfMessages=min(max_records, 10),
                WaitTimeSeconds=5,
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            logger.info(f"Processing {len(messages)} DLQ records")
            
            for message in messages:
                try:
                    # Parse error record
                    error_data = json.loads(message['Body'])
                    error_record = ErrorRecord(
                        error_id=error_data['error_id'],
                        timestamp=datetime.fromisoformat(error_data['timestamp']),
                        error_type=ErrorType(error_data['error_type']),
                        error_message=error_data['error_message'],
                        stack_trace=error_data['stack_trace'],
                        operation=error_data['operation'],
                        input_data=error_data.get('input_data'),
                        retry_count=error_data.get('retry_count', 0)
                    )
                    
                    # Check if retry should be attempted
                    if self._should_retry_dlq_record(error_record):
                        # Process the record
                        processing_func(error_record.input_data)
                        
                        # Mark as resolved
                        error_record.resolved = True
                        error_record.resolution_timestamp = datetime.now(timezone.utc)
                        
                        # Delete from DLQ
                        self.sqs_client.delete_message(
                            QueueUrl=self.config.dlq_queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        
                        processed_records.append(error_record.error_id)
                        logger.info(f"Successfully reprocessed DLQ record: {error_record.error_id}")
                    
                    else:
                        logger.info(f"Skipping DLQ record {error_record.error_id} - not eligible for retry")
                
                except Exception as e:
                    logger.error(f"Failed to process DLQ message: {str(e)}")
                    # Leave message in queue for later processing
        
        except Exception as e:
            logger.error(f"Failed to process DLQ records: {str(e)}")
        
        return processed_records
    
    def _should_retry_dlq_record(self, error_record: ErrorRecord) -> bool:
        """Determine if a DLQ record should be retried."""
        # Check if max DLQ retries exceeded
        if error_record.retry_count >= self.config.dlq_max_retries:
            return False
        
        # Check if sufficient time has passed
        age_hours = (datetime.now(timezone.utc) - error_record.timestamp).total_seconds() / 3600
        if age_hours < self.config.dlq_retry_delay_hours:
            return False
        
        # Don't retry permanent errors
        if error_record.error_type == ErrorType.PERMANENT:
            return False
        
        return True
    
    def get_dlq_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics."""
        with self._lock:
            total_errors = len(self.error_records)
            resolved_errors = sum(1 for r in self.error_records.values() if r.resolved)
            
            error_type_counts = defaultdict(int)
            for record in self.error_records.values():
                error_type_counts[record.error_type.value] += 1
        
        return {
            'total_errors': total_errors,
            'resolved_errors': resolved_errors,
            'pending_errors': total_errors - resolved_errors,
            'error_type_distribution': dict(error_type_counts)
        }


class ErrorRecoveryOrchestrator:
    """Main orchestrator for error recovery and resilience."""
    
    def __init__(self, retry_config: RetryConfig = None, circuit_config: CircuitBreakerConfig = None,
                 dlq_config: DeadLetterConfig = None):
        
        self.retry_manager = RetryManager(retry_config)
        self.circuit_breakers = {}
        self.dlq_manager = DeadLetterManager(dlq_config) if dlq_config else None
        
        self.circuit_config = circuit_config or CircuitBreakerConfig()
        
        # Overall error statistics
        self.error_stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'recovered_operations': 0,
            'sent_to_dlq': 0
        }
    
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a specific operation."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(self.circuit_config, name)
        return self.circuit_breakers[name]
    
    def resilient_execution(self, func: Callable, operation_name: str = None,
                          use_circuit_breaker: bool = True, *args, **kwargs) -> Any:
        """Execute function with full error recovery capabilities."""
        operation_name = operation_name or func.__name__
        self.error_stats['total_operations'] += 1
        
        try:
            if use_circuit_breaker:
                circuit_breaker = self.get_circuit_breaker(operation_name)
                
                def protected_func(*f_args, **f_kwargs):
                    return self.retry_manager.retry_with_backoff(func, *f_args, **f_kwargs)
                
                result = circuit_breaker.call(protected_func, *args, **kwargs)
            else:
                result = self.retry_manager.retry_with_backoff(func, *args, **kwargs)
            
            self.error_stats['successful_operations'] += 1
            return result
            
        except Exception as error:
            self.error_stats['failed_operations'] += 1
            
            # Attempt recovery or send to DLQ
            try:
                if self.dlq_manager:
                    error_id = self.dlq_manager.send_to_dlq(operation_name, kwargs, error)
                    self.error_stats['sent_to_dlq'] += 1
                    logger.info(f"Operation '{operation_name}' failed, sent to DLQ: {error_id}")
                
                raise
                
            except Exception as dlq_error:
                logger.error(f"Failed to handle error for operation '{operation_name}': {str(dlq_error)}")
                raise error
    
    def partial_failure_handler(self, data_batch: List[Any], processing_func: Callable,
                               operation_name: str = "batch_processing") -> Tuple[List[Any], List[Any]]:
        """Handle partial failures in batch processing."""
        successful_results = []
        failed_items = []
        
        for i, item in enumerate(data_batch):
            try:
                result = self.resilient_execution(
                    processing_func,
                    f"{operation_name}_item_{i}",
                    use_circuit_breaker=False,  # Don't use circuit breaker for individual items
                    item
                )
                successful_results.append(result)
                
            except Exception as error:
                failed_items.append({
                    'index': i,
                    'item': item,
                    'error': str(error),
                    'error_type': ErrorClassifier.classify_error(error).value
                })
                
                logger.warning(f"Item {i} in batch failed: {str(error)}")
        
        success_rate = len(successful_results) / len(data_batch) if data_batch else 0
        logger.info(f"Batch processing completed: {len(successful_results)}/{len(data_batch)} successful "
                   f"({success_rate:.1%} success rate)")
        
        return successful_results, failed_items
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health and error status."""
        circuit_breaker_status = {}
        for name, cb in self.circuit_breakers.items():
            circuit_breaker_status[name] = cb.get_state()
        
        retry_stats = self.retry_manager.get_stats()
        dlq_stats = self.dlq_manager.get_dlq_stats() if self.dlq_manager else {}
        
        total_ops = self.error_stats['total_operations']
        success_rate = (self.error_stats['successful_operations'] / total_ops) if total_ops > 0 else 0
        
        return {
            'overall_health': 'healthy' if success_rate > 0.95 else 'degraded' if success_rate > 0.8 else 'unhealthy',
            'success_rate': success_rate,
            'error_statistics': self.error_stats,
            'retry_statistics': retry_stats,
            'circuit_breakers': circuit_breaker_status,
            'dead_letter_queue': dlq_stats
        }
    
    def cleanup(self):
        """Cleanup resources and reset state."""
        self.circuit_breakers.clear()
        self.error_stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'recovered_operations': 0,
            'sent_to_dlq': 0
        }
        logger.info("Error recovery orchestrator cleanup completed")


# Decorator functions for easy integration
def with_retry(max_attempts: int = 3, backoff_multiplier: float = 2.0):
    """Decorator to add retry capability to functions."""
    def decorator(func: Callable):
        config = RetryConfig(max_attempts=max_attempts, backoff_multiplier=backoff_multiplier)
        retry_manager = RetryManager(config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_manager.retry_with_backoff(func, *args, **kwargs)
        
        return wrapper
    return decorator


def with_circuit_breaker(failure_threshold: int = 5, timeout_seconds: int = 60):
    """Decorator to add circuit breaker protection to functions."""
    def decorator(func: Callable):
        config = CircuitBreakerConfig(failure_threshold=failure_threshold, timeout_seconds=timeout_seconds)
        circuit_breaker = CircuitBreaker(config, func.__name__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


def resilient(operation_name: str = None, max_attempts: int = 3, use_circuit_breaker: bool = True):
    """Comprehensive resilience decorator combining retry and circuit breaker."""
    def decorator(func: Callable):
        retry_config = RetryConfig(max_attempts=max_attempts)
        circuit_config = CircuitBreakerConfig()
        orchestrator = ErrorRecoveryOrchestrator(retry_config, circuit_config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return orchestrator.resilient_execution(
                func, operation_name or func.__name__, use_circuit_breaker, *args, **kwargs
            )
        
        wrapper._orchestrator = orchestrator
        return wrapper
    return decorator