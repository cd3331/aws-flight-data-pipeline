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
        
        # Environment variables
        self.raw_bucket = os.environ.get('RAW_DATA_BUCKET')
        self.opensky_api_url = "https://opensky-network.org/api/states/all"
        self.timeout = int(os.environ.get('API_TIMEOUT', 30))
        self.max_retries = int(os.environ.get('MAX_RETRIES', 3))
        
        if not self.raw_bucket:
            raise ValueError("Required environment variable RAW_DATA_BUCKET must be set")
        
        # Debug: Print bucket name
        print(f"DEBUG: Using S3 bucket: {self.raw_bucket}")
        logger.info(f"Using S3 bucket: {self.raw_bucket}")
    
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
            
            logger.info(f"Storing data in S3 bucket: {self.raw_bucket}, key: {s3_key}")
            logger.info(f"Data size: {len(json_data)} characters")
            
            self.s3_client.put_object(
                Bucket=self.raw_bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            logger.info(f"Successfully stored data in S3: s3://{self.raw_bucket}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store data in S3: {str(e)}")
            return False
    


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Simplified Lambda handler for flight data ingestion
    """
    execution_id = str(uuid.uuid4())
    logger.info(f"Starting flight data ingestion - Execution ID: {execution_id}")
    
    try:
        # Initialize ingestion class (uses RAW_DATA_BUCKET environment variable)
        ingestion = FlightDataIngestion()
        
        # Fetch flight data from OpenSky API
        raw_data, error_msg = ingestion.fetch_flight_data()
        if error_msg:
            logger.error(f"Failed to fetch flight data: {error_msg}")
            raise Exception(f"API fetch failed: {error_msg}")
        
        # Validate and enrich the flight data
        try:
            enriched_data = ingestion.validate_and_enrich_data(raw_data)
        except Exception as e:
            logger.error(f"Data validation failed: {str(e)}")
            raise Exception(f"Data validation failed: {str(e)}")
        
        # Generate partitioned S3 key and store data
        s3_key = ingestion.generate_s3_key(enriched_data['time'])
        if not ingestion.store_data_in_s3(enriched_data, s3_key):
            logger.error("S3 storage failed")
            raise Exception("S3 storage failed")
        
        # Optional DynamoDB tracking (continue if it fails)
        try:
            # DynamoDB tracking would go here if implemented
            logger.info("DynamoDB tracking skipped (not implemented)")
        except Exception as e:
            logger.warning(f"DynamoDB tracking failed, continuing: {str(e)}")
        
        logger.info("Flight data ingestion completed successfully")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'SUCCESS',
                's3_key': s3_key,
                'records_processed': enriched_data['metadata']['total_records'],
                'valid_records': enriched_data['metadata']['valid_records']
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Flight data ingestion failed: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_message': error_msg
            })
        }