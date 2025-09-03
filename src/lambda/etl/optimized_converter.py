"""
Optimized JSON to Parquet ETL Processing System.

This module provides high-performance conversion of JSON flight data to Parquet format
with advanced chunking, compression, and memory optimization techniques.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import json
import logging
import os
import time
import gc
from typing import Dict, List, Any, Optional, Iterator, Tuple, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import io

# Lazy imports for performance
pyarrow = None
pandas = None
boto3_session = None
s3_transfer = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _lazy_import_pyarrow():
    """Lazy import PyArrow to reduce cold start time."""
    global pyarrow
    if pyarrow is None:
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.compute as pc
        pyarrow = pa
        pyarrow.parquet = pq
        pyarrow.compute = pc
    return pyarrow


def _lazy_import_pandas():
    """Lazy import pandas to reduce cold start time."""
    global pandas
    if pandas is None:
        import pandas as pd
        # Optimize pandas settings
        pd.options.mode.chained_assignment = None
        pd.options.display.max_columns = None
        pandas = pd
    return pandas


def _lazy_import_boto3():
    """Lazy import boto3 with session reuse."""
    global boto3_session, s3_transfer
    if boto3_session is None:
        import boto3
        from boto3.s3.transfer import TransferConfig
        boto3_session = boto3.Session()
        s3_transfer = TransferConfig(
            multipart_threshold=1024 * 25,  # 25MB
            max_concurrency=10,
            multipart_chunksize=1024 * 25,
            use_threads=True
        )
    return boto3_session, s3_transfer


@dataclass
class ConversionConfig:
    """Configuration for JSON to Parquet conversion."""
    
    # Chunking configuration
    chunk_size: int = 10000              # Records per chunk
    max_memory_mb: int = 512             # Maximum memory usage per chunk
    
    # Compression settings
    compression: str = 'snappy'          # snappy, gzip, lz4, zstd
    compression_level: Optional[int] = None
    
    # PyArrow optimization
    use_dictionary_encoding: bool = True  # Optimize string columns
    row_group_size: int = 50000          # Rows per row group
    
    # Performance settings
    max_workers: int = 4                 # Thread pool size
    buffer_size: int = 8192              # IO buffer size in bytes
    
    # Schema optimization
    infer_schema_sample_size: int = 1000 # Records to sample for schema inference
    use_nullable_dtypes: bool = True     # Use nullable pandas dtypes
    
    # Memory management
    enable_gc_per_chunk: bool = True     # Force GC after each chunk
    clear_cache_frequency: int = 10      # Clear caches every N chunks


@dataclass
class ChunkMetadata:
    """Metadata for processing chunks."""
    chunk_id: int
    start_record: int
    end_record: int
    memory_usage_mb: float
    processing_time_ms: int
    record_count: int
    error_count: int = 0


class OptimizedJsonToParquetConverter:
    """High-performance JSON to Parquet converter with advanced optimizations."""
    
    def __init__(self, config: ConversionConfig = None):
        """Initialize the converter with configuration."""
        self.config = config or ConversionConfig()
        
        # Performance tracking
        self.stats = {
            'total_records_processed': 0,
            'total_chunks_processed': 0,
            'total_processing_time_ms': 0,
            'total_memory_peak_mb': 0,
            'compression_ratio': 0.0,
            'throughput_records_per_sec': 0.0
        }
        
        # Schema caching
        self._schema_cache = {}
        self._type_cache = {}
        
        logger.info(f"OptimizedConverter initialized with chunk_size={self.config.chunk_size}, "
                   f"compression={self.config.compression}")
    
    def convert_file(self, json_file_path: str, parquet_file_path: str,
                    schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert JSON file to Parquet with optimized processing.
        
        Args:
            json_file_path: Path to input JSON file
            parquet_file_path: Path to output Parquet file
            schema: Optional predefined schema
            
        Returns:
            Conversion statistics and metadata
        """
        start_time = time.time()
        
        try:
            # Initialize lazy imports
            pa = _lazy_import_pyarrow()
            
            # Determine processing strategy based on file size
            file_size_mb = os.path.getsize(json_file_path) / (1024 * 1024)
            use_chunked_processing = file_size_mb > (self.config.max_memory_mb / 2)
            
            logger.info(f"Converting {json_file_path} ({file_size_mb:.1f}MB) to Parquet, "
                       f"chunked_processing={use_chunked_processing}")
            
            if use_chunked_processing:
                return self._convert_large_file_chunked(json_file_path, parquet_file_path, schema)
            else:
                return self._convert_small_file_direct(json_file_path, parquet_file_path, schema)
                
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            raise
        finally:
            total_time = (time.time() - start_time) * 1000
            self.stats['total_processing_time_ms'] = total_time
            
            # Calculate throughput
            if total_time > 0:
                self.stats['throughput_records_per_sec'] = \
                    (self.stats['total_records_processed'] / total_time) * 1000
    
    def _convert_small_file_direct(self, json_file_path: str, parquet_file_path: str,
                                  schema: Optional[Dict] = None) -> Dict[str, Any]:
        """Convert small files directly without chunking."""
        pa = _lazy_import_pyarrow()
        
        # Read all data at once
        with open(json_file_path, 'r', buffering=self.config.buffer_size) as f:
            records = []
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        # Convert to Arrow Table
        table = self._records_to_arrow_table(records, schema)
        
        # Write Parquet file
        self._write_parquet_optimized(table, parquet_file_path)
        
        # Update stats
        self.stats['total_records_processed'] = len(records)
        self.stats['total_chunks_processed'] = 1
        
        return {
            'status': 'success',
            'records_processed': len(records),
            'chunks_processed': 1,
            'output_file': parquet_file_path,
            'compression_ratio': self._calculate_compression_ratio(json_file_path, parquet_file_path),
            'stats': self.stats
        }
    
    def _convert_large_file_chunked(self, json_file_path: str, parquet_file_path: str,
                                  schema: Optional[Dict] = None) -> Dict[str, Any]:
        """Convert large files using chunked processing with parallel execution."""
        pa = _lazy_import_pyarrow()
        
        # Create temporary directory for chunk files
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix='parquet_chunks_')
        chunk_files = []
        chunk_metadata = []
        
        try:
            # Process chunks in parallel
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                # Submit chunk processing tasks
                futures = []
                
                for chunk_id, chunk_data in enumerate(self._read_json_chunks(json_file_path)):
                    future = executor.submit(
                        self._process_chunk,
                        chunk_id,
                        chunk_data,
                        temp_dir,
                        schema
                    )
                    futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    try:
                        chunk_file, metadata = future.result()
                        chunk_files.append(chunk_file)
                        chunk_metadata.append(metadata)
                        
                        # Force garbage collection periodically
                        if self.config.enable_gc_per_chunk:
                            gc.collect()
                            
                    except Exception as e:
                        logger.error(f"Chunk processing failed: {str(e)}")
                        raise
            
            # Merge chunk files into final Parquet file
            self._merge_chunk_files(chunk_files, parquet_file_path)
            
            # Calculate final stats
            total_records = sum(m.record_count for m in chunk_metadata)
            total_time = sum(m.processing_time_ms for m in chunk_metadata)
            
            self.stats['total_records_processed'] = total_records
            self.stats['total_chunks_processed'] = len(chunk_metadata)
            
            return {
                'status': 'success',
                'records_processed': total_records,
                'chunks_processed': len(chunk_metadata),
                'chunk_metadata': [m.__dict__ for m in chunk_metadata],
                'output_file': parquet_file_path,
                'compression_ratio': self._calculate_compression_ratio(json_file_path, parquet_file_path),
                'stats': self.stats
            }
            
        finally:
            # Cleanup temporary files
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {str(e)}")
    
    def _read_json_chunks(self, json_file_path: str) -> Iterator[List[Dict[str, Any]]]:
        """Generator that yields chunks of JSON records."""
        chunk = []
        chunk_memory = 0
        record_count = 0
        
        with open(json_file_path, 'r', buffering=self.config.buffer_size) as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    chunk.append(record)
                    
                    # Estimate memory usage (rough approximation)
                    chunk_memory += len(line.encode('utf-8'))
                    record_count += 1
                    
                    # Yield chunk if size or memory limits reached
                    if (len(chunk) >= self.config.chunk_size or 
                        chunk_memory >= self.config.max_memory_mb * 1024 * 1024):
                        
                        yield chunk
                        chunk = []
                        chunk_memory = 0
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON at line {record_count + 1}: {str(e)}")
                    continue
        
        # Yield remaining records
        if chunk:
            yield chunk
    
    def _process_chunk(self, chunk_id: int, chunk_data: List[Dict[str, Any]], 
                      temp_dir: str, schema: Optional[Dict] = None) -> Tuple[str, ChunkMetadata]:
        """Process a single chunk of data."""
        start_time = time.time()
        pa = _lazy_import_pyarrow()
        
        try:
            # Convert chunk to Arrow table
            table = self._records_to_arrow_table(chunk_data, schema)
            
            # Generate chunk file path
            chunk_file = os.path.join(temp_dir, f'chunk_{chunk_id:06d}.parquet')
            
            # Write chunk to Parquet
            self._write_parquet_optimized(table, chunk_file)
            
            # Calculate memory usage (approximate)
            memory_usage = table.nbytes / (1024 * 1024)  # MB
            processing_time = int((time.time() - start_time) * 1000)  # ms
            
            metadata = ChunkMetadata(
                chunk_id=chunk_id,
                start_record=chunk_id * self.config.chunk_size,
                end_record=chunk_id * self.config.chunk_size + len(chunk_data),
                memory_usage_mb=memory_usage,
                processing_time_ms=processing_time,
                record_count=len(chunk_data)
            )
            
            logger.debug(f"Chunk {chunk_id} processed: {len(chunk_data)} records, "
                        f"{memory_usage:.1f}MB, {processing_time}ms")
            
            return chunk_file, metadata
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id}: {str(e)}")
            raise
    
    def _records_to_arrow_table(self, records: List[Dict[str, Any]], 
                               schema: Optional[Dict] = None) -> 'pyarrow.Table':
        """Convert JSON records to Arrow Table with optimizations."""
        pa = _lazy_import_pyarrow()
        
        if not records:
            # Return empty table with schema if provided
            if schema:
                return pa.table([], schema=pa.schema(schema))
            else:
                return pa.table([])
        
        # Infer or use provided schema
        if schema is None:
            schema = self._infer_optimized_schema(records)
        
        # Convert records to Arrow format
        try:
            # Use Arrow's JSON parsing for better performance
            json_strings = [json.dumps(record) for record in records]
            json_buffer = '\n'.join(json_strings).encode('utf-8')
            
            # Parse JSON buffer
            parse_options = pa.json.ParseOptions(
                explicit_schema=schema if isinstance(schema, pa.Schema) else None
            )
            
            read_options = pa.json.ReadOptions(
                use_threads=True,
                block_size=1024 * 1024  # 1MB blocks
            )
            
            table = pa.json.read_json(
                io.BytesIO(json_buffer),
                parse_options=parse_options,
                read_options=read_options
            )
            
            return table
            
        except Exception as e:
            logger.warning(f"Arrow JSON parsing failed, falling back to pandas: {str(e)}")
            return self._records_to_arrow_via_pandas(records, schema)
    
    def _records_to_arrow_via_pandas(self, records: List[Dict[str, Any]], 
                                    schema: Optional[Dict] = None) -> 'pyarrow.Table':
        """Fallback method using pandas for complex JSON structures."""
        pd = _lazy_import_pandas()
        pa = _lazy_import_pyarrow()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Optimize DataFrame dtypes
        df = self._optimize_dataframe_dtypes(df)
        
        # Convert DataFrame to Arrow Table
        table = pa.Table.from_pandas(df, preserve_index=False)
        
        # Apply dictionary encoding for string columns if enabled
        if self.config.use_dictionary_encoding:
            table = self._apply_dictionary_encoding(table)
        
        return table
    
    def _infer_optimized_schema(self, records: List[Dict[str, Any]]) -> Optional['pyarrow.Schema']:
        """Infer optimized Arrow schema from sample records."""
        pa = _lazy_import_pyarrow()
        
        if not records:
            return None
        
        # Use cache if available
        schema_key = str(sorted(records[0].keys()))
        if schema_key in self._schema_cache:
            return self._schema_cache[schema_key]
        
        # Sample records for schema inference
        sample_size = min(len(records), self.config.infer_schema_sample_size)
        sample_records = records[:sample_size]
        
        # Analyze field types
        field_types = {}
        for record in sample_records:
            for field, value in record.items():
                if field not in field_types:
                    field_types[field] = []
                field_types[field].append(type(value).__name__)
        
        # Build Arrow schema
        schema_fields = []
        for field, types in field_types.items():
            arrow_type = self._infer_arrow_type(field, types, sample_records)
            schema_fields.append(pa.field(field, arrow_type))
        
        schema = pa.schema(schema_fields)
        self._schema_cache[schema_key] = schema
        
        return schema
    
    def _infer_arrow_type(self, field_name: str, python_types: List[str], 
                         sample_records: List[Dict]) -> 'pyarrow.DataType':
        """Infer optimal Arrow data type for a field."""
        pa = _lazy_import_pyarrow()
        
        # Get sample values for the field
        values = [record.get(field_name) for record in sample_records if field_name in record]
        non_null_values = [v for v in values if v is not None]
        
        if not non_null_values:
            return pa.string()  # Default to string for all-null fields
        
        # Analyze value patterns
        unique_types = set(python_types)
        
        # Integer optimization
        if unique_types <= {'int', 'NoneType'}:
            max_val = max(abs(v) for v in non_null_values if isinstance(v, int))
            if max_val < 2**31:
                return pa.int32()
            else:
                return pa.int64()
        
        # Float optimization
        if unique_types <= {'float', 'int', 'NoneType'}:
            return pa.float64()
        
        # Boolean optimization
        if unique_types <= {'bool', 'NoneType'}:
            return pa.bool_()
        
        # String optimization with dictionary encoding
        if unique_types <= {'str', 'NoneType'}:
            unique_values = len(set(str(v) for v in non_null_values))
            total_values = len(non_null_values)
            
            # Use dictionary encoding if cardinality is low
            if unique_values / total_values < 0.5 and self.config.use_dictionary_encoding:
                return pa.dictionary(pa.int32(), pa.string())
            else:
                return pa.string()
        
        # Timestamp detection
        if field_name.lower() in ['timestamp', 'time', 'datetime', 'date']:
            return pa.timestamp('ms')
        
        # Default to string for complex types
        return pa.string()
    
    def _optimize_dataframe_dtypes(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Optimize pandas DataFrame dtypes for memory efficiency."""
        pd = _lazy_import_pandas()
        
        for col in df.columns:
            col_type = df[col].dtype
            
            # Optimize integer columns
            if col_type == 'int64':
                if df[col].min() >= 0 and df[col].max() < 2**32:
                    df[col] = df[col].astype('int32')
                elif df[col].min() >= -2**31 and df[col].max() < 2**31:
                    df[col] = df[col].astype('int32')
            
            # Optimize float columns
            elif col_type == 'float64':
                if df[col].min() >= -3.4e38 and df[col].max() <= 3.4e38:
                    df[col] = df[col].astype('float32')
            
            # Optimize object columns (strings)
            elif col_type == 'object':
                # Try converting to categorical if cardinality is low
                unique_ratio = df[col].nunique() / len(df[col])
                if unique_ratio < 0.5:
                    df[col] = df[col].astype('category')
        
        return df
    
    def _apply_dictionary_encoding(self, table: 'pyarrow.Table') -> 'pyarrow.Table':
        """Apply dictionary encoding to string columns."""
        pa = _lazy_import_pyarrow()
        
        columns = []
        for i, field in enumerate(table.schema):
            column = table.column(i)
            
            # Apply dictionary encoding to string columns
            if pa.types.is_string(field.type):
                unique_ratio = len(pa.compute.unique(column)) / len(column)
                if unique_ratio < 0.5:  # Only if cardinality is low
                    column = pa.compute.dictionary_encode(column)
            
            columns.append(column)
        
        return pa.table(columns, names=table.column_names)
    
    def _write_parquet_optimized(self, table: 'pyarrow.Table', output_path: str) -> None:
        """Write Arrow table to Parquet with optimized settings."""
        pa = _lazy_import_pyarrow()
        
        # Determine compression level
        compression_level = self.config.compression_level
        if compression_level is None:
            # Set optimal compression levels
            compression_levels = {
                'snappy': None,  # Snappy doesn't use levels
                'gzip': 6,       # Good balance of speed/compression
                'lz4': None,     # LZ4 doesn't use levels
                'zstd': 3        # Good balance for ZSTD
            }
            compression_level = compression_levels.get(self.config.compression)
        
        # Configure write options
        write_options = {
            'compression': self.config.compression,
            'row_group_size': self.config.row_group_size,
            'use_dictionary': self.config.use_dictionary_encoding,
            'write_statistics': True,
            'use_deprecated_int96_timestamps': False,
            'coerce_timestamps': 'ms'
        }
        
        if compression_level is not None:
            write_options['compression_level'] = compression_level
        
        # Write Parquet file
        pa.parquet.write_table(table, output_path, **write_options)
    
    def _merge_chunk_files(self, chunk_files: List[str], output_path: str) -> None:
        """Merge multiple Parquet chunk files into a single file."""
        pa = _lazy_import_pyarrow()
        
        if not chunk_files:
            raise ValueError("No chunk files to merge")
        
        # Read and concatenate all chunk files
        tables = []
        for chunk_file in sorted(chunk_files):  # Sort to maintain order
            table = pa.parquet.read_table(chunk_file)
            tables.append(table)
        
        # Concatenate tables
        merged_table = pa.concat_tables(tables)
        
        # Write merged table
        self._write_parquet_optimized(merged_table, output_path)
        
        logger.info(f"Merged {len(chunk_files)} chunks into {output_path}")
    
    def _calculate_compression_ratio(self, json_path: str, parquet_path: str) -> float:
        """Calculate compression ratio between JSON and Parquet files."""
        try:
            json_size = os.path.getsize(json_path)
            parquet_size = os.path.getsize(parquet_path)
            ratio = json_size / parquet_size if parquet_size > 0 else 0
            self.stats['compression_ratio'] = ratio
            return ratio
        except Exception as e:
            logger.warning(f"Could not calculate compression ratio: {str(e)}")
            return 0.0
    
    @contextmanager
    def memory_monitor(self):
        """Context manager to monitor memory usage."""
        import psutil
        process = psutil.Process()
        
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        try:
            yield
        finally:
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            peak_memory = max(start_memory, end_memory)
            self.stats['total_memory_peak_mb'] = max(
                self.stats.get('total_memory_peak_mb', 0), 
                peak_memory
            )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            'processing_stats': self.stats,
            'configuration': {
                'chunk_size': self.config.chunk_size,
                'max_memory_mb': self.config.max_memory_mb,
                'compression': self.config.compression,
                'max_workers': self.config.max_workers,
                'use_dictionary_encoding': self.config.use_dictionary_encoding
            },
            'cache_stats': {
                'schema_cache_size': len(self._schema_cache),
                'type_cache_size': len(self._type_cache)
            }
        }


class S3OptimizedConverter(OptimizedJsonToParquetConverter):
    """S3-optimized version with direct S3 I/O and connection pooling."""
    
    def __init__(self, config: ConversionConfig = None, aws_region: str = None):
        """Initialize S3-optimized converter."""
        super().__init__(config)
        
        # Initialize AWS clients with connection pooling
        self.session, self.transfer_config = _lazy_import_boto3()
        self.s3_client = self.session.client(
            's3',
            region_name=aws_region,
            config=boto3.Config(
                max_pool_connections=50,
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
        )
    
    def convert_s3_file(self, s3_input_path: str, s3_output_path: str,
                       schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert JSON file from S3 to Parquet in S3.
        
        Args:
            s3_input_path: S3 URI (s3://bucket/key)
            s3_output_path: S3 URI for output Parquet file
            schema: Optional predefined schema
            
        Returns:
            Conversion statistics
        """
        import tempfile
        
        # Parse S3 URIs
        input_bucket, input_key = self._parse_s3_uri(s3_input_path)
        output_bucket, output_key = self._parse_s3_uri(s3_output_path)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download from S3
            temp_json = os.path.join(temp_dir, 'input.json')
            temp_parquet = os.path.join(temp_dir, 'output.parquet')
            
            logger.info(f"Downloading {s3_input_path} to temporary file")
            self.s3_client.download_file(
                input_bucket, input_key, temp_json,
                Config=self.transfer_config
            )
            
            # Convert using parent class method
            result = self.convert_file(temp_json, temp_parquet, schema)
            
            # Upload to S3
            logger.info(f"Uploading converted file to {s3_output_path}")
            self.s3_client.upload_file(
                temp_parquet, output_bucket, output_key,
                Config=self.transfer_config
            )
            
            result['s3_input'] = s3_input_path
            result['s3_output'] = s3_output_path
            
            return result
    
    def _parse_s3_uri(self, s3_uri: str) -> Tuple[str, str]:
        """Parse S3 URI into bucket and key."""
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        return parts[0], parts[1]