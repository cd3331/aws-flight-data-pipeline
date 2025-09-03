import json
import logging
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import unquote_plus
import io
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class FlightDataProcessor:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.cloudwatch = boto3.client('cloudwatch')
        
        # Environment variables
        self.processed_bucket = os.environ.get('PROCESSED_DATA_BUCKET')
        self.raw_bucket = os.environ.get('RAW_DATA_BUCKET')
        
        if not self.processed_bucket or not self.raw_bucket:
            raise ValueError("Required environment variables PROCESSED_DATA_BUCKET and RAW_DATA_BUCKET must be set")
    
    def download_s3_object(self, bucket: str, key: str) -> Optional[bytes]:
        """
        Download object from S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Object content as bytes or None if failed
        """
        try:
            logger.info(f"Downloading s3://{bucket}/{key}")
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"Object not found: s3://{bucket}/{key}")
            else:
                logger.error(f"Failed to download object: {str(e)}")
            return None
    
    def parse_json_data(self, json_content: bytes) -> Optional[Dict]:
        """
        Parse JSON content
        
        Args:
            json_content: Raw JSON bytes
            
        Returns:
            Parsed JSON data or None if failed
        """
        try:
            return json.loads(json_content.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return None
    
    def apply_business_rules(self, flight_data: List[Dict]) -> List[Dict]:
        """
        Apply business rules and transformations to flight data
        
        Args:
            flight_data: List of flight records
            
        Returns:
            Transformed flight data
        """
        transformed_data = []
        
        for record in flight_data:
            try:
                # Create a copy to avoid modifying original data
                transformed_record = record.copy()
                
                # Business rule 1: Categorize altitude
                altitude_ft = record.get('baro_altitude_ft') or record.get('geo_altitude_ft')
                if altitude_ft is not None:
                    if altitude_ft < 1000:
                        transformed_record['altitude_category'] = 'LOW'
                    elif altitude_ft < 18000:
                        transformed_record['altitude_category'] = 'MEDIUM'
                    elif altitude_ft < 35000:
                        transformed_record['altitude_category'] = 'HIGH'
                    else:
                        transformed_record['altitude_category'] = 'VERY_HIGH'
                else:
                    transformed_record['altitude_category'] = 'UNKNOWN'
                
                # Business rule 2: Categorize speed
                velocity_knots = record.get('velocity_knots')
                if velocity_knots is not None:
                    if velocity_knots < 50:
                        transformed_record['speed_category'] = 'SLOW'
                    elif velocity_knots < 200:
                        transformed_record['speed_category'] = 'TAXI'
                    elif velocity_knots < 400:
                        transformed_record['speed_category'] = 'APPROACH'
                    elif velocity_knots < 600:
                        transformed_record['speed_category'] = 'CRUISE'
                    else:
                        transformed_record['speed_category'] = 'HIGH_SPEED'
                else:
                    transformed_record['speed_category'] = 'UNKNOWN'
                
                # Business rule 3: Flight phase estimation
                on_ground = record.get('on_ground', False)
                altitude_ft = record.get('baro_altitude_ft') or record.get('geo_altitude_ft')
                velocity_knots = record.get('velocity_knots')
                vertical_rate = record.get('vertical_rate')
                
                if on_ground:
                    transformed_record['estimated_phase'] = 'GROUND'
                elif altitude_ft and velocity_knots:
                    if altitude_ft < 1000:
                        if vertical_rate and vertical_rate > 0:
                            transformed_record['estimated_phase'] = 'TAKEOFF'
                        elif vertical_rate and vertical_rate < 0:
                            transformed_record['estimated_phase'] = 'LANDING'
                        else:
                            transformed_record['estimated_phase'] = 'LOW_ALTITUDE'
                    elif altitude_ft > 25000 and velocity_knots > 300:
                        transformed_record['estimated_phase'] = 'CRUISE'
                    else:
                        if vertical_rate and vertical_rate > 500:
                            transformed_record['estimated_phase'] = 'CLIMB'
                        elif vertical_rate and vertical_rate < -500:
                            transformed_record['estimated_phase'] = 'DESCENT'
                        else:
                            transformed_record['estimated_phase'] = 'LEVEL_FLIGHT'
                else:
                    transformed_record['estimated_phase'] = 'UNKNOWN'
                
                # Business rule 4: Data completeness score
                completeness_fields = [
                    'icao24', 'callsign', 'origin_country', 'longitude', 'latitude',
                    'baro_altitude_ft', 'velocity_knots', 'true_track'
                ]
                
                non_null_fields = sum(1 for field in completeness_fields if record.get(field) is not None)
                transformed_record['completeness_score'] = round(non_null_fields / len(completeness_fields), 3)
                
                # Business rule 5: Normalize callsign
                callsign = record.get('callsign')
                if callsign:
                    transformed_record['callsign_normalized'] = callsign.strip().upper()
                    # Extract airline code (first 3 characters)
                    transformed_record['airline_code'] = callsign.strip()[:3] if len(callsign.strip()) >= 3 else None
                else:
                    transformed_record['callsign_normalized'] = None
                    transformed_record['airline_code'] = None
                
                # Business rule 6: Geographic region
                longitude = record.get('longitude')
                latitude = record.get('latitude')
                if longitude is not None and latitude is not None:
                    if -125 <= longitude <= -66 and 20 <= latitude <= 72:
                        transformed_record['region'] = 'NORTH_AMERICA'
                    elif -15 <= longitude <= 55 and 35 <= latitude <= 70:
                        transformed_record['region'] = 'EUROPE'
                    elif 95 <= longitude <= 145 and -45 <= latitude <= 20:
                        transformed_record['region'] = 'ASIA_PACIFIC'
                    else:
                        transformed_record['region'] = 'OTHER'
                else:
                    transformed_record['region'] = 'UNKNOWN'
                
                # Add processing timestamp
                transformed_record['processed_timestamp'] = datetime.now(timezone.utc).isoformat()
                
                transformed_data.append(transformed_record)
                
            except Exception as e:
                logger.warning(f"Error applying business rules to record {record.get('icao24', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Applied business rules to {len(transformed_data)} records")
        return transformed_data
    
    def calculate_data_quality_score(self, data: List[Dict]) -> float:
        """
        Calculate overall data quality score (0-1 scale)
        
        Args:
            data: List of flight records
            
        Returns:
            Quality score between 0 and 1
        """
        if not data:
            return 0.0
        
        quality_metrics = {
            'completeness': 0,
            'validity': 0,
            'consistency': 0,
            'accuracy': 0
        }
        
        total_records = len(data)
        
        # Completeness check
        complete_records = sum(1 for record in data if record.get('completeness_score', 0) >= 0.7)
        quality_metrics['completeness'] = complete_records / total_records
        
        # Validity check
        valid_records = 0
        for record in data:
            is_valid = True
            
            # Check coordinate validity
            longitude = record.get('longitude')
            latitude = record.get('latitude')
            if longitude is not None and (longitude < -180 or longitude > 180):
                is_valid = False
            if latitude is not None and (latitude < -90 or latitude > 90):
                is_valid = False
            
            # Check altitude validity
            altitude_ft = record.get('baro_altitude_ft') or record.get('geo_altitude_ft')
            if altitude_ft is not None and (altitude_ft < -1000 or altitude_ft > 50000):
                is_valid = False
            
            # Check speed validity
            velocity_knots = record.get('velocity_knots')
            if velocity_knots is not None and (velocity_knots < 0 or velocity_knots > 1000):
                is_valid = False
            
            if is_valid:
                valid_records += 1
        
        quality_metrics['validity'] = valid_records / total_records
        
        # Consistency check (check for reasonable relationships between fields)
        consistent_records = 0
        for record in data:
            is_consistent = True
            
            # Ground vs altitude consistency
            on_ground = record.get('on_ground', False)
            altitude_ft = record.get('baro_altitude_ft') or record.get('geo_altitude_ft')
            
            if on_ground and altitude_ft and altitude_ft > 1000:
                is_consistent = False
            
            if is_consistent:
                consistent_records += 1
        
        quality_metrics['consistency'] = consistent_records / total_records
        
        # Accuracy check (presence of position data)
        positioned_records = sum(1 for record in data if record.get('has_position', False))
        quality_metrics['accuracy'] = positioned_records / total_records
        
        # Calculate weighted average
        weights = {'completeness': 0.3, 'validity': 0.3, 'consistency': 0.2, 'accuracy': 0.2}
        overall_score = sum(quality_metrics[metric] * weight for metric, weight in weights.items())
        
        logger.info(f"Data quality metrics: {quality_metrics}")
        logger.info(f"Overall quality score: {overall_score:.3f}")
        
        return round(overall_score, 3)
    
    def convert_to_parquet(self, data: List[Dict]) -> bytes:
        """
        Convert flight data to Parquet format with Snappy compression
        
        Args:
            data: Flight data records
            
        Returns:
            Parquet file content as bytes
        """
        try:
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Optimize data types
            df = self.optimize_datatypes(df)
            
            # Convert to PyArrow table
            table = pa.Table.from_pandas(df)
            
            # Write to parquet with Snappy compression
            parquet_buffer = io.BytesIO()
            pq.write_table(
                table,
                parquet_buffer,
                compression='snappy',
                use_dictionary=True,
                row_group_size=10000
            )
            
            parquet_content = parquet_buffer.getvalue()
            logger.info(f"Converted {len(data)} records to Parquet format ({len(parquet_content)} bytes)")
            
            return parquet_content
            
        except Exception as e:
            logger.error(f"Failed to convert data to Parquet: {str(e)}")
            raise
    
    def optimize_datatypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame data types for storage efficiency
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with optimized data types
        """
        try:
            # Numeric optimizations
            numeric_columns = [
                'baro_altitude_ft', 'geo_altitude_ft', 'velocity_knots',
                'longitude', 'latitude', 'true_track', 'vertical_rate'
            ]
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')
            
            # Integer optimizations
            int_columns = ['time_position', 'last_contact', 'squawk']
            for col in int_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int32')
            
            # Boolean optimizations
            bool_columns = ['on_ground', 'spi', 'has_position', 'has_altitude', 'has_velocity']
            for col in bool_columns:
                if col in df.columns:
                    df[col] = df[col].astype('boolean')
            
            # String optimizations
            string_columns = [
                'icao24', 'callsign', 'origin_country', 'altitude_category',
                'speed_category', 'estimated_phase', 'callsign_normalized',
                'airline_code', 'region'
            ]
            
            for col in string_columns:
                if col in df.columns:
                    df[col] = df[col].astype('string')
            
            logger.info("Data types optimized for Parquet storage")
            return df
            
        except Exception as e:
            logger.warning(f"Failed to optimize data types: {str(e)}")
            return df
    
    def generate_processed_s3_key(self, original_key: str) -> str:
        """
        Generate S3 key for processed data maintaining partitioning structure
        
        Args:
            original_key: Original S3 key from raw data
            
        Returns:
            New S3 key for processed data
        """
        # Extract partitioning information from original key
        # Expected format: year=2024/month=01/day=15/hour=14/flight_data_20240115_1430_abc123.json
        
        parts = original_key.split('/')
        partition_parts = []
        filename_part = parts[-1]
        
        for part in parts[:-1]:
            if '=' in part:
                partition_parts.append(part)
        
        # Generate new filename
        base_name = filename_part.replace('.json', '')
        processing_id = str(uuid.uuid4())[:8]
        new_filename = f"{base_name}_processed_{processing_id}.parquet"
        
        # Combine parts
        processed_key = '/'.join(partition_parts + [new_filename])
        
        return processed_key
    
    def upload_processed_data(self, parquet_content: bytes, s3_key: str, metadata: Dict) -> bool:
        """
        Upload processed Parquet data to S3
        
        Args:
            parquet_content: Parquet file content
            s3_key: S3 key for storage
            metadata: File metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.put_object(
                Bucket=self.processed_bucket,
                Key=s3_key,
                Body=parquet_content,
                ContentType='application/octet-stream',
                Metadata={
                    'processing-timestamp': metadata['processing_timestamp'],
                    'total-records': str(metadata['total_records']),
                    'quality-score': str(metadata['quality_score']),
                    'file-format': 'parquet',
                    'compression': 'snappy',
                    'source-file': metadata.get('source_file', '')
                }
            )
            
            logger.info(f"Successfully uploaded processed data: s3://{self.processed_bucket}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload processed data: {str(e)}")
            return False
    
    def publish_processing_metrics(self, metadata: Dict, execution_time: float) -> None:
        """
        Publish processing metrics to CloudWatch
        
        Args:
            metadata: Processing metadata
            execution_time: Total execution time in seconds
        """
        try:
            metrics = [
                {
                    'MetricName': 'ProcessingTime',
                    'Value': execution_time,
                    'Unit': 'Seconds',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_processor'}
                    ]
                },
                {
                    'MetricName': 'RecordsProcessed',
                    'Value': metadata.get('total_records', 0),
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_processor'}
                    ]
                },
                {
                    'MetricName': 'QualityScore',
                    'Value': metadata.get('quality_score', 0) * 100,
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_processor'}
                    ]
                },
                {
                    'MetricName': 'FileSizeReduction',
                    'Value': metadata.get('compression_ratio', 0) * 100,
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_processor'}
                    ]
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace='FlightDataPipeline/Processing',
                MetricData=metrics
            )
            
            logger.info("Processing metrics published to CloudWatch")
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics: {str(e)}")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for flight data processing triggered by S3 events
    
    Args:
        event: S3 event data
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    start_time = time.time()
    execution_id = str(uuid.uuid4())
    
    logger.info(f"Starting flight data processing - Execution ID: {execution_id}")
    
    try:
        processor = FlightDataProcessor()
        
        processed_files = []
        
        # Process each S3 record in the event
        for record in event.get('Records', []):
            try:
                # Extract S3 information
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Processing file: s3://{bucket}/{key}")
                
                # Download JSON file
                json_content = processor.download_s3_object(bucket, key)
                if not json_content:
                    logger.error(f"Failed to download file: s3://{bucket}/{key}")
                    continue
                
                # Parse JSON data
                json_data = processor.parse_json_data(json_content)
                if not json_data or 'states' not in json_data:
                    logger.error(f"Invalid JSON data in file: s3://{bucket}/{key}")
                    continue
                
                flight_states = json_data['states']
                if not flight_states:
                    logger.warning(f"No flight states found in file: s3://{bucket}/{key}")
                    continue
                
                # Apply business rules and transformations
                transformed_data = processor.apply_business_rules(flight_states)
                
                if not transformed_data:
                    logger.warning(f"No valid records after transformation: s3://{bucket}/{key}")
                    continue
                
                # Calculate data quality score
                quality_score = processor.calculate_data_quality_score(transformed_data)
                
                # Convert to Parquet
                parquet_content = processor.convert_to_parquet(transformed_data)
                
                # Generate processed S3 key
                processed_key = processor.generate_processed_s3_key(key)
                
                # Prepare metadata
                processing_metadata = {
                    'processing_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_records': len(transformed_data),
                    'quality_score': quality_score,
                    'source_file': f"s3://{bucket}/{key}",
                    'compression_ratio': 1 - (len(parquet_content) / len(json_content)) if json_content else 0,
                    'original_size_bytes': len(json_content),
                    'processed_size_bytes': len(parquet_content)
                }
                
                # Upload processed data
                if processor.upload_processed_data(parquet_content, processed_key, processing_metadata):
                    processed_files.append({
                        'source_file': f"s3://{bucket}/{key}",
                        'processed_file': f"s3://{processor.processed_bucket}/{processed_key}",
                        'records': len(transformed_data),
                        'quality_score': quality_score
                    })
                else:
                    logger.error(f"Failed to upload processed file: {processed_key}")
                
                # Publish metrics for this file
                execution_time = time.time() - start_time
                processor.publish_processing_metrics(processing_metadata, execution_time)
                
            except Exception as file_error:
                logger.error(f"Error processing file {key}: {str(file_error)}")
                continue
        
        total_execution_time = time.time() - start_time
        
        logger.info(f"Flight data processing completed in {total_execution_time:.2f} seconds")
        logger.info(f"Processed {len(processed_files)} files successfully")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'SUCCESS',
                'processed_files': processed_files,
                'execution_time': total_execution_time,
                'total_files_processed': len(processed_files)
            })
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Flight data processing failed: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_message': error_msg,
                'execution_time': execution_time
            })
        }