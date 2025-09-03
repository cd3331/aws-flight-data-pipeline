import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import time
import boto3
import requests
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class FlightDataIngestion:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.cloudwatch = boto3.client('cloudwatch')
        
        # Environment variables
        self.raw_bucket = os.environ.get('RAW_DATA_BUCKET')
        self.tracking_table = os.environ.get('TRACKING_TABLE')
        self.opensky_api_url = "https://opensky-network.org/api/states/all"
        self.timeout = int(os.environ.get('API_TIMEOUT', 30))
        self.max_retries = int(os.environ.get('MAX_RETRIES', 3))
        
        if not self.raw_bucket or not self.tracking_table:
            raise ValueError("Required environment variables RAW_DATA_BUCKET and TRACKING_TABLE must be set")
        
        # DynamoDB table
        self.table = self.dynamodb.Table(self.tracking_table)
    
    def fetch_flight_data(self) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Fetch real-time flight data from OpenSky Network API with retry logic
        
        Returns:
            Tuple of (data, error_message)
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching flight data from OpenSky API (attempt {attempt + 1})")
                
                response = requests.get(
                    self.opensky_api_url,
                    timeout=self.timeout,
                    headers={
                        'User-Agent': 'FlightDataPipeline/1.0',
                        'Accept': 'application/json'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully fetched data with {len(data.get('states', []))} flight records")
                    return data, None
                
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                    continue
                
                else:
                    error_msg = f"API returned status code {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    if attempt == self.max_retries - 1:
                        return None, error_msg
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.Timeout:
                error_msg = f"Request timeout after {self.timeout} seconds"
                logger.error(error_msg)
                if attempt == self.max_retries - 1:
                    return None, error_msg
                time.sleep(2 ** attempt)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Request failed: {str(e)}"
                logger.error(error_msg)
                if attempt == self.max_retries - 1:
                    return None, error_msg
                time.sleep(2 ** attempt)
                
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return None, error_msg
        
        return None, "Max retries exceeded"
    
    def validate_and_enrich_data(self, raw_data: Dict) -> Dict:
        """
        Validate and enrich flight data with calculated fields
        
        Args:
            raw_data: Raw data from OpenSky API
            
        Returns:
            Enriched and validated data
        """
        if not raw_data or 'states' not in raw_data:
            raise ValueError("Invalid data structure: missing 'states' field")
        
        enriched_states = []
        valid_records = 0
        invalid_records = 0
        
        for state in raw_data.get('states', []):
            try:
                if not state or len(state) < 17:
                    invalid_records += 1
                    continue
                
                # Extract fields according to OpenSky API documentation
                icao24 = state[0]
                callsign = state[1]
                origin_country = state[2]
                time_position = state[3]
                last_contact = state[4]
                longitude = state[5]
                latitude = state[6]
                baro_altitude = state[7]  # meters
                on_ground = state[8]
                velocity = state[9]  # m/s
                true_track = state[10]
                vertical_rate = state[11]
                sensors = state[12]
                geo_altitude = state[13]  # meters
                squawk = state[14]
                spi = state[15]
                position_source = state[16]
                
                # Basic validation
                if not icao24 or not isinstance(icao24, str):
                    invalid_records += 1
                    continue
                
                # Enrich with calculated fields
                enriched_state = {
                    'icao24': icao24,
                    'callsign': callsign.strip() if callsign else None,
                    'origin_country': origin_country,
                    'time_position': time_position,
                    'last_contact': last_contact,
                    'longitude': longitude,
                    'latitude': latitude,
                    'baro_altitude_m': baro_altitude,
                    'baro_altitude_ft': round(baro_altitude * 3.28084, 2) if baro_altitude else None,  # Convert to feet
                    'on_ground': on_ground,
                    'velocity_ms': velocity,
                    'velocity_knots': round(velocity * 1.94384, 2) if velocity else None,  # Convert to knots
                    'true_track': true_track,
                    'vertical_rate': vertical_rate,
                    'sensors': sensors,
                    'geo_altitude_m': geo_altitude,
                    'geo_altitude_ft': round(geo_altitude * 3.28084, 2) if geo_altitude else None,
                    'squawk': squawk,
                    'spi': spi,
                    'position_source': position_source,
                    'has_position': longitude is not None and latitude is not None,
                    'has_altitude': baro_altitude is not None or geo_altitude is not None,
                    'has_velocity': velocity is not None
                }
                
                enriched_states.append(enriched_state)
                valid_records += 1
                
            except (IndexError, TypeError, ValueError) as e:
                logger.warning(f"Error processing flight record: {str(e)}")
                invalid_records += 1
                continue
        
        # Add metadata
        enriched_data = {
            'time': raw_data.get('time', int(datetime.now(timezone.utc).timestamp())),
            'states': enriched_states,
            'metadata': {
                'ingestion_timestamp': datetime.now(timezone.utc).isoformat(),
                'total_records': len(raw_data.get('states', [])),
                'valid_records': valid_records,
                'invalid_records': invalid_records,
                'data_quality_ratio': valid_records / len(raw_data.get('states', [])) if raw_data.get('states') else 0,
                'source': 'opensky_network',
                'api_version': '1.0',
                'enrichment_fields': ['baro_altitude_ft', 'geo_altitude_ft', 'velocity_knots', 'has_position', 'has_altitude', 'has_velocity']
            }
        }
        
        logger.info(f"Data validation complete: {valid_records} valid, {invalid_records} invalid records")
        return enriched_data
    
    def generate_s3_key(self, timestamp: int) -> str:
        """
        Generate S3 key with year/month/day/hour partitioning
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            S3 key path
        """
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        execution_id = str(uuid.uuid4())[:8]
        
        key = f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}/flight_data_{dt.strftime('%Y%m%d_%H%M%S')}_{execution_id}.json"
        return key
    
    def store_data_in_s3(self, data: Dict, s3_key: str) -> bool:
        """
        Store enriched flight data in S3
        
        Args:
            data: Enriched flight data
            s3_key: S3 key for storage
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            
            self.s3_client.put_object(
                Bucket=self.raw_bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json',
                Metadata={
                    'ingestion-timestamp': data['metadata']['ingestion_timestamp'],
                    'total-records': str(data['metadata']['total_records']),
                    'valid-records': str(data['metadata']['valid_records']),
                    'source': data['metadata']['source']
                }
            )
            
            logger.info(f"Successfully stored data in S3: s3://{self.raw_bucket}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to store data in S3: {str(e)}")
            return False
    
    def track_execution(self, execution_id: str, s3_key: str, metadata: Dict, status: str, error_message: Optional[str] = None) -> None:
        """
        Track execution details in DynamoDB
        
        Args:
            execution_id: Unique execution identifier
            s3_key: S3 key where data was stored
            metadata: Execution metadata
            status: Execution status (SUCCESS, ERROR)
            error_message: Error message if status is ERROR
        """
        try:
            item = {
                'execution_id': execution_id,
                'timestamp': int(datetime.now(timezone.utc).timestamp()),
                'iso_timestamp': datetime.now(timezone.utc).isoformat(),
                'status': status,
                'function_name': 'flight_data_ingestion',
                'metadata': metadata
            }
            
            if s3_key:
                item['s3_key'] = s3_key
                item['s3_bucket'] = self.raw_bucket
            
            if error_message:
                item['error_message'] = error_message
            
            self.table.put_item(Item=item)
            logger.info(f"Execution tracking recorded: {execution_id}")
            
        except ClientError as e:
            logger.error(f"Failed to track execution in DynamoDB: {str(e)}")
    
    def publish_metrics(self, metadata: Dict, execution_time: float, status: str) -> None:
        """
        Publish metrics to CloudWatch
        
        Args:
            metadata: Execution metadata
            execution_time: Total execution time in seconds
            status: Execution status
        """
        try:
            metrics = [
                {
                    'MetricName': 'ExecutionTime',
                    'Value': execution_time,
                    'Unit': 'Seconds',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_ingestion'},
                        {'Name': 'Status', 'Value': status}
                    ]
                },
                {
                    'MetricName': 'RecordsProcessed',
                    'Value': metadata.get('total_records', 0),
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_ingestion'}
                    ]
                },
                {
                    'MetricName': 'ValidRecords',
                    'Value': metadata.get('valid_records', 0),
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_ingestion'}
                    ]
                },
                {
                    'MetricName': 'DataQualityRatio',
                    'Value': metadata.get('data_quality_ratio', 0),
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'flight_data_ingestion'}
                    ]
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace='FlightDataPipeline/Ingestion',
                MetricData=metrics
            )
            
            logger.info("Metrics published to CloudWatch")
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {str(e)}")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for flight data ingestion
    
    Args:
        event: Lambda event data
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    start_time = time.time()
    execution_id = str(uuid.uuid4())
    
    logger.info(f"Starting flight data ingestion - Execution ID: {execution_id}")
    
    try:
        ingestion = FlightDataIngestion()
        
        # Fetch flight data
        raw_data, error_msg = ingestion.fetch_flight_data()
        if error_msg:
            raise Exception(f"Failed to fetch flight data: {error_msg}")
        
        # Validate and enrich data
        enriched_data = ingestion.validate_and_enrich_data(raw_data)
        
        # Generate S3 key
        s3_key = ingestion.generate_s3_key(enriched_data['time'])
        
        # Store data in S3
        if not ingestion.store_data_in_s3(enriched_data, s3_key):
            raise Exception("Failed to store data in S3")
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Track execution
        ingestion.track_execution(
            execution_id=execution_id,
            s3_key=s3_key,
            metadata=enriched_data['metadata'],
            status='SUCCESS'
        )
        
        # Publish metrics
        ingestion.publish_metrics(
            metadata=enriched_data['metadata'],
            execution_time=execution_time,
            status='SUCCESS'
        )
        
        logger.info(f"Flight data ingestion completed successfully in {execution_time:.2f} seconds")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'SUCCESS',
                's3_key': s3_key,
                'execution_time': execution_time,
                'records_processed': enriched_data['metadata']['total_records'],
                'valid_records': enriched_data['metadata']['valid_records'],
                'data_quality_ratio': enriched_data['metadata']['data_quality_ratio']
            })
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Flight data ingestion failed: {error_msg}")
        
        try:
            ingestion = FlightDataIngestion()
            
            # Track failed execution
            ingestion.track_execution(
                execution_id=execution_id,
                s3_key=None,
                metadata={'error': error_msg},
                status='ERROR',
                error_message=error_msg
            )
            
            # Publish error metrics
            ingestion.publish_metrics(
                metadata={'total_records': 0, 'valid_records': 0, 'data_quality_ratio': 0},
                execution_time=execution_time,
                status='ERROR'
            )
            
        except Exception as track_error:
            logger.error(f"Failed to track error execution: {str(track_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_message': error_msg,
                'execution_time': execution_time
            })
        }