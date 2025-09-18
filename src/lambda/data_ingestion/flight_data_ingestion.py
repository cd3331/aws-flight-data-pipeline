import boto3
import requests
import json
import time
import os
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client('ssm')
s3 = boto3.client('s3')

class FlightDataIngestion:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.ssm_client = boto3.client('ssm')
        
        # Environment variables
        self.raw_bucket = os.environ.get('RAW_DATA_BUCKET')
        self.opensky_api_url = "https://opensky-network.org/api/states/all"
        self.opensky_token_url = "https://opensky-network.org/api/auth/token"
        self.timeout = int(os.environ.get('API_TIMEOUT', 30))
        self.max_retries = int(os.environ.get('MAX_RETRIES', 3))
        
        # OAuth2 credentials from SSM
        self.client_id_param = "/flight-pipeline/opensky-client-id"
        self.client_secret_param = "/flight-pipeline/opensky-client-secret"
        
        # Token cache
        self.access_token = None
        self.token_expires_at = None
        
        if not self.raw_bucket:
            raise ValueError("Required environment variable RAW_DATA_BUCKET must be set")
        
        logger.info(f"Using S3 bucket: {self.raw_bucket}")
    
    def get_ssm_parameter(self, parameter_name: str, decrypt: bool = True) -> Optional[str]:
        """
        Retrieve parameter from AWS SSM Parameter Store
        
        Args:
            parameter_name: SSM parameter name
            decrypt: Whether to decrypt the parameter
            
        Returns:
            Parameter value or None if not found
        """
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=decrypt
            )
            return response['Parameter']['Value']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.warning(f"SSM parameter not found: {parameter_name}")
            else:
                logger.error(f"Error retrieving SSM parameter {parameter_name}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving SSM parameter {parameter_name}: {str(e)}")
            return None
    
    def get_oauth2_token(self) -> Optional[str]:
        """
        Get OAuth2 access token from OpenSky Network
        
        Returns:
            Access token or None if authentication fails
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at:
            if datetime.now(timezone.utc) < self.token_expires_at:
                logger.info("Using cached OAuth2 token")
                return self.access_token
        
        # Get credentials from SSM
        client_id = self.get_ssm_parameter(self.client_id_param)
        client_secret = self.get_ssm_parameter(self.client_secret_param)
        
        if not client_id or not client_secret:
            logger.warning("OAuth2 credentials not available in SSM Parameter Store")
            return None
        
        try:
            logger.info("Requesting new OAuth2 token from OpenSky Network")
            
            # Prepare OAuth2 token request
            token_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            response = requests.post(
                self.opensky_token_url,
                data=token_data,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'FlightDataPipeline/1.0'
                }
            )
            
            if response.status_code == 200:
                token_response = response.json()
                self.access_token = token_response.get('access_token')
                expires_in = token_response.get('expires_in', 3600)  # Default 1 hour
                
                # Cache token with 5-minute buffer before expiration
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
                
                logger.info(f"Successfully obtained OAuth2 token, expires in {expires_in} seconds")
                return self.access_token
            else:
                logger.error(f"OAuth2 token request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"OAuth2 token request failed: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OAuth2 token response: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during OAuth2 authentication: {str(e)}")
            return None
    
    def fetch_flight_data(self) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Fetch real-time flight data from OpenSky Network API with OAuth2 authentication and fallback
        
        Returns:
            Tuple of (data, error_message)
        """
        # Try OAuth2 authentication first
        access_token = self.get_oauth2_token()
        auth_methods = []
        
        if access_token:
            auth_methods.append(('oauth2', {'Authorization': f'Bearer {access_token}'}))
            logger.info("Will attempt OAuth2 authentication")
        
        # Always add anonymous fallback
        auth_methods.append(('anonymous', {}))
        logger.info("Anonymous access available as fallback")
        
        for auth_method, auth_headers in auth_methods:
            logger.info(f"Attempting to fetch data using {auth_method} authentication")
            
            for attempt in range(self.max_retries):
                try:
                    headers = {
                        'User-Agent': 'FlightDataPipeline/1.0',
                        'Accept': 'application/json'
                    }
                    headers.update(auth_headers)
                    
                    logger.info(f"Fetching flight data from OpenSky API (method: {auth_method}, attempt {attempt + 1})")
                    
                    response = requests.get(
                        self.opensky_api_url,
                        timeout=self.timeout,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Successfully fetched data using {auth_method} with {len(data.get('states', []))} flight records")
                        return data, None
                    
                    elif response.status_code == 401:  # Unauthorized
                        logger.warning(f"{auth_method} authentication failed with 401 - Unauthorized")
                        if auth_method == 'oauth2':
                            # Clear cached token and try next auth method
                            self.access_token = None
                            self.token_expires_at = None
                            break
                        else:
                            error_msg = f"Anonymous access denied: {response.text}"
                            logger.error(error_msg)
                            return None, error_msg
                    
                    elif response.status_code == 403:  # Forbidden
                        logger.warning(f"{auth_method} authentication failed with 403 - Forbidden")
                        if auth_method == 'oauth2':
                            break  # Try next auth method
                        else:
                            error_msg = f"Access forbidden: {response.text}"
                            logger.error(error_msg)
                            return None, error_msg
                    
                    elif response.status_code == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time} seconds before retry")
                        time.sleep(wait_time)
                        continue
                    
                    else:
                        error_msg = f"API returned status code {response.status_code}: {response.text}"
                        logger.error(error_msg)
                        if attempt == self.max_retries - 1:
                            if auth_method == 'oauth2':
                                break  # Try next auth method
                            else:
                                return None, error_msg
                        time.sleep(2 ** attempt)
                        
                except requests.exceptions.Timeout:
                    error_msg = f"Request timeout after {self.timeout} seconds"
                    logger.error(error_msg)
                    if attempt == self.max_retries - 1:
                        if auth_method == 'oauth2':
                            break  # Try next auth method
                        else:
                            return None, error_msg
                    time.sleep(2 ** attempt)
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"Request failed: {str(e)}"
                    logger.error(error_msg)
                    if attempt == self.max_retries - 1:
                        if auth_method == 'oauth2':
                            break  # Try next auth method
                        else:
                            return None, error_msg
                    time.sleep(2 ** attempt)
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to parse JSON response: {str(e)}"
                    logger.error(error_msg)
                    if auth_method == 'oauth2':
                        break  # Try next auth method
                    else:
                        return None, error_msg
                except Exception as e:
                    error_msg = f"Unexpected error during API request: {str(e)}"
                    logger.error(error_msg)
                    if auth_method == 'oauth2':
                        break  # Try next auth method
                    else:
                        return None, error_msg
        
        return None, "All authentication methods failed"
    
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

            # Store the timestamped file
            self.s3_client.put_object(
                Bucket=self.raw_bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )

            logger.info(f"Successfully stored timestamped data in S3: s3://{self.raw_bucket}/{s3_key}")

            # Also store as latest.json for dashboard API
            try:
                self.s3_client.put_object(
                    Bucket=self.raw_bucket,
                    Key='latest.json',
                    Body=json_data,
                    ContentType='application/json'
                )
                logger.info(f"Successfully stored latest.json in S3: s3://{self.raw_bucket}/latest.json")
            except Exception as e:
                logger.warning(f"Failed to store latest.json (continuing anyway): {str(e)}")

            return True

        except Exception as e:
            logger.error(f"Failed to store data in S3: {str(e)}")
            return False
    


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Enhanced Lambda handler for flight data ingestion with OAuth2 support
    """
    execution_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    logger.info(f"Starting flight data ingestion - Execution ID: {execution_id}")
    logger.info(f"Lambda context: request_id={context.aws_request_id}, function_name={context.function_name}")
    
    ingestion = None
    auth_method_used = None
    
    try:
        # Initialize ingestion class
        try:
            ingestion = FlightDataIngestion()
            logger.info("Successfully initialized FlightDataIngestion")
        except Exception as e:
            logger.error(f"Failed to initialize FlightDataIngestion: {str(e)}")
            raise Exception(f"Initialization failed: {str(e)}")
        
        # Fetch flight data from OpenSky API with OAuth2 and fallback
        logger.info("Attempting to fetch flight data from OpenSky Network API")
        raw_data, error_msg = ingestion.fetch_flight_data()
        
        if error_msg:
            logger.error(f"Failed to fetch flight data: {error_msg}")
            raise Exception(f"API fetch failed: {error_msg}")
        
        if not raw_data:
            logger.error("No data returned from API")
            raise Exception("No data returned from API")
        
        logger.info("Successfully fetched flight data from API")
        
        # Validate and enrich the flight data
        try:
            logger.info("Starting data validation and enrichment")
            enriched_data = ingestion.validate_and_enrich_data(raw_data)
            logger.info(f"Data validation completed: {enriched_data['metadata']['valid_records']} valid records out of {enriched_data['metadata']['total_records']} total")
        except Exception as e:
            logger.error(f"Data validation failed: {str(e)}")
            raise Exception(f"Data validation failed: {str(e)}")
        
        # Generate partitioned S3 key and store data
        try:
            s3_key = ingestion.generate_s3_key(enriched_data['time'])
            logger.info(f"Generated S3 key: {s3_key}")
            
            if not ingestion.store_data_in_s3(enriched_data, s3_key):
                logger.error("S3 storage failed")
                raise Exception("S3 storage failed")
            
            logger.info("Successfully stored data in S3")
        except Exception as e:
            logger.error(f"S3 storage operation failed: {str(e)}")
            raise Exception(f"S3 storage failed: {str(e)}")
        
        # Calculate execution metrics
        end_time = datetime.now(timezone.utc)
        execution_duration = (end_time - start_time).total_seconds()
        
        # Optional DynamoDB tracking (continue if it fails)
        try:
            # DynamoDB tracking would go here if implemented
            logger.info("DynamoDB tracking skipped (not implemented)")
        except Exception as e:
            logger.warning(f"DynamoDB tracking failed, continuing: {str(e)}")
        
        logger.info(f"Flight data ingestion completed successfully in {execution_duration:.2f} seconds")
        
        # Prepare success response with enhanced metadata
        response_data = {
            'execution_id': execution_id,
            'status': 'SUCCESS',
            's3_key': s3_key,
            'records_processed': enriched_data['metadata']['total_records'],
            'valid_records': enriched_data['metadata']['valid_records'],
            'invalid_records': enriched_data['metadata']['invalid_records'],
            'data_quality_ratio': enriched_data['metadata']['data_quality_ratio'],
            'execution_duration_seconds': round(execution_duration, 2),
            'timestamp': end_time.isoformat(),
            'api_source': enriched_data['metadata']['source']
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except ValueError as e:
        # Configuration or validation errors
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg)
        
        return {
            'statusCode': 400,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'CONFIG_ERROR',
                'error_message': error_msg,
                'error_type': 'configuration'
            })
        }
        
    except ClientError as e:
        # AWS service errors (SSM, S3, etc.)
        error_code = e.response['Error']['Code']
        error_msg = f"AWS service error ({error_code}): {str(e)}"
        logger.error(error_msg)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'AWS_ERROR',
                'error_message': error_msg,
                'error_type': 'aws_service',
                'error_code': error_code
            })
        }
        
    except requests.exceptions.RequestException as e:
        # Network/API errors
        error_msg = f"Network error: {str(e)}"
        logger.error(error_msg)
        
        return {
            'statusCode': 502,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'NETWORK_ERROR',
                'error_message': error_msg,
                'error_type': 'network'
            })
        }
        
    except Exception as e:
        # General errors
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        logger.exception("Full traceback:")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_message': error_msg,
                'error_type': 'general'
            })
        }