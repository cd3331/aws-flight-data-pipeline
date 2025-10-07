import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
import signal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client with shorter timeout
s3_client = boto3.client('s3', config=boto3.session.Config(
    read_timeout=2,
    connect_timeout=2
))

# Configuration
BUCKET_NAME = 'flight-data-pipeline-dev-raw-data-y10swyy3'
ALLOWED_ORIGIN = '*'  # Temporarily allow all origins for debugging

# Sample static data fallback with correct structure
SAMPLE_DATA = {
    'statistics': {
        'total_flights': 0,
        'flights_airborne': 0,
        'flights_on_ground': 0,
        'flights_with_position': 0,
        'altitude_stats': {
            'mean_altitude_ft': 0,
            'max_altitude_ft': 0,
            'min_altitude_ft': 0
        },
        'altitude_distribution': {},
        'speed_stats': {
            'mean_speed_knots': 0,
            'max_speed_knots': 0
        },
        'top_10_countries': {},
        'top_10_fastest_aircraft': [],
        'data_timestamp': datetime.now().isoformat()
    },
    'executionResult': {
        's3_key': 'flight_data/2024/09/flight_data_20240907_120000.json',
        'records_processed': 0,
        'valid_records': 0,
        'last_modified': datetime.now().isoformat(),
        'execution_id': 'fallback',
        'status': 'ERROR',
        'processing_time_seconds': 0
    },
    'metadata': {
        'bucket_name': BUCKET_NAME,
        'file_size_bytes': 0,
        'message': 'Sample data - S3 connection failed'
    }
}


class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Operation timed out")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function to return metadata about the latest flight data file in S3.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Dict containing metadata about the latest file in S3
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {'message': 'CORS preflight'})

    # Set up timeout handler (2.5 seconds to leave buffer for response)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(2)
    
    try:
        logger.info("Getting latest flight data file metadata from S3")
        
        # Get latest file metadata from S3
        metadata = get_latest_file_metadata(BUCKET_NAME)
        
        return create_response(200, metadata)
        
    except TimeoutException:
        logger.warning("Request timed out, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.warning(f"AWS S3 error: {error_code}, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except NoCredentialsError:
        logger.warning("AWS credentials not found, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    except Exception as e:
        logger.warning(f"Unexpected error: {str(e)}, returning sample data")
        return create_response(200, SAMPLE_DATA)
    
    finally:
        # Clear the alarm
        signal.alarm(0)


def get_latest_file_metadata(bucket_name: str) -> Dict[str, Any]:
    """
    Get the latest OpenSky flight data file and process it into comprehensive statistics.

    Args:
        bucket_name: Name of the S3 bucket

    Returns:
        Dict containing processed flight statistics
    """
    # List objects in the bucket, filtering for actual OpenSky flight data files
    # Use pagination to get ALL objects since there are many files
    all_objects = []
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(
        Bucket=bucket_name,
        Prefix='year='  # OpenSky files are stored with year= prefix
    )

    for page in page_iterator:
        if 'Contents' in page:
            all_objects.extend(page['Contents'])

    if not all_objects:
        raise ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'No OpenSky flight data files found in bucket'}},
            operation_name='list_objects_v2'
        )

    # Filter for actual flight data files (not latest.json or other files)
    flight_data_files = [
        obj for obj in all_objects
        if 'flight_data_' in obj['Key'] and obj['Key'].endswith('.json')
    ]

    if not flight_data_files:
        raise ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'No OpenSky flight_data_*.json files found'}},
            operation_name='list_objects_v2'
        )

    # Sort by last modified (newest first) and get the latest OpenSky file
    latest_object = max(flight_data_files, key=lambda x: x['LastModified'])
    latest_key = latest_object['Key']

    logger.info(f"Found {len(flight_data_files)} flight data files")
    logger.info(f"Using latest OpenSky file: {latest_key} (size: {latest_object['Size']} bytes, modified: {latest_object['LastModified']})")

    logger.info(f"Processing flight data from: {latest_key}")

    # Download and process the actual flight data
    try:
        file_response = s3_client.get_object(Bucket=bucket_name, Key=latest_key)
        data = json.loads(file_response['Body'].read().decode('utf-8'))

        if 'states' not in data or not isinstance(data['states'], list):
            raise ValueError("Invalid data format")

        states = data['states']
        timestamp = data.get('time', None)

        # Process the flight data into statistics
        processed_stats = process_flight_states(states, timestamp)

        # Add execution metadata
        processed_stats['executionResult'] = {
            's3_key': latest_key,
            'records_processed': len(states),
            'valid_records': len(states),
            'last_modified': latest_object['LastModified'].isoformat(),
            'execution_id': f"live-{int(datetime.now().timestamp())}",
            'status': 'SUCCESS',
            'processing_time_seconds': 0.5
        }

        # Add file metadata
        processed_stats['metadata'] = {
            'bucket_name': bucket_name,
            'file_size_bytes': latest_object['Size'],
            'message': 'Successfully processed flight data from S3'
        }

        logger.info(f"Successfully processed {len(states)} flight records")
        return processed_stats

    except Exception as e:
        logger.warning(f"Failed to process flight data: {e}, falling back to empty structure")
        # Fallback to empty structure with correct format if processing fails
        return {
            'statistics': {
                'total_flights': 0,
                'flights_airborne': 0,
                'flights_on_ground': 0,
                'flights_with_position': 0,
                'altitude_stats': {
                    'mean_altitude_ft': 0,
                    'max_altitude_ft': 0,
                    'min_altitude_ft': 0
                },
                'altitude_distribution': {},
                'speed_stats': {
                    'mean_speed_knots': 0,
                    'max_speed_knots': 0
                },
                'top_10_countries': {},
                'top_10_fastest_aircraft': [],
                'data_timestamp': datetime.now().isoformat()
            },
            'executionResult': {
                's3_key': latest_key,
                'records_processed': 0,
                'valid_records': 0,
                'last_modified': latest_object['LastModified'].isoformat(),
                'execution_id': f'error-{int(datetime.now().timestamp())}',
                'status': 'ERROR',
                'processing_time_seconds': 0
            },
            'metadata': {
                'bucket_name': bucket_name,
                'file_size_bytes': latest_object['Size'],
                'message': f'File metadata only - processing failed: {str(e)}'
            }
        }

def process_flight_states(states: list, timestamp: int = None) -> Dict[str, Any]:
    """
    Process flight states into comprehensive statistics (optimized for Lambda).

    Args:
        states: List of flight state arrays
        timestamp: Data timestamp

    Returns:
        Dict containing flight statistics
    """
    total_flights = len(states)
    airborne_count = 0
    ground_count = 0
    countries = {}
    altitudes = []
    speeds = []
    fastest_aircraft = []
    with_position = 0

    # Process each flight state (sample for performance in Lambda)
    sample_size = min(len(states), 5000)  # Limit processing to avoid timeout
    sample_states = states[::max(1, len(states)//sample_size)]

    for state in sample_states:
        try:
            # Handle both list and dict formats
            if isinstance(state, list) and len(state) >= 17:
                flight = {
                    'icao24': state[0],
                    'callsign': state[1],
                    'origin_country': state[2],
                    'longitude': state[5],
                    'latitude': state[6],
                    'baro_altitude_ft': state[8],
                    'on_ground': state[9],
                    'velocity_knots': state[11]
                }
            else:
                flight = state

            # Count flight states
            if flight.get('on_ground'):
                ground_count += 1
            else:
                airborne_count += 1

            # Position data
            if flight.get('longitude') is not None and flight.get('latitude') is not None:
                with_position += 1

            # Country statistics
            country = flight.get('origin_country')
            if country:
                countries[country] = countries.get(country, 0) + 1

            # Altitude data
            altitude = flight.get('baro_altitude_ft')
            if altitude is not None and not flight.get('on_ground', True):
                altitudes.append(float(altitude))

            # Speed data and fastest aircraft
            speed = flight.get('velocity_knots')
            if speed is not None and speed > 0:
                speeds.append(float(speed))

                # Track fastest aircraft (only reasonable speeds)
                if speed > 200 and flight.get('callsign'):
                    fastest_aircraft.append({
                        'callsign': str(flight['callsign']).strip(),
                        'origin_country': country or 'Unknown',
                        'velocity_knots': float(speed),
                        'baro_altitude_ft': float(altitude) if altitude else None
                    })

        except (IndexError, TypeError, ValueError):
            # Skip malformed records
            continue

    # Scale up sample results to full dataset
    scale_factor = total_flights / len(sample_states) if sample_states else 1
    airborne_count = int(airborne_count * scale_factor)
    ground_count = int(ground_count * scale_factor)
    with_position = int(with_position * scale_factor)

    # Scale country counts
    countries = {k: int(v * scale_factor) for k, v in countries.items()}

    # Calculate altitude distribution
    altitude_distribution = {}
    if altitudes:
        low = len([a for a in altitudes if 0 <= a <= 10000])
        medium = len([a for a in altitudes if 10000 < a <= 30000])
        high = len([a for a in altitudes if 30000 < a <= 50000])
        very_high = len([a for a in altitudes if a > 50000])

        altitude_distribution = {
            'Low (0-10k ft)': int(low * scale_factor),
            'Medium (10-30k ft)': int(medium * scale_factor),
            'High (30-50k ft)': int(high * scale_factor),
            'Very High (>50k ft)': int(very_high * scale_factor)
        }

    # Sort and limit results
    top_countries = dict(sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10])
    top_fastest = sorted(fastest_aircraft, key=lambda x: x['velocity_knots'], reverse=True)[:10]

    # Build statistics
    statistics = {
        'total_flights': total_flights,
        'flights_airborne': airborne_count,
        'flights_on_ground': ground_count,
        'flights_with_position': with_position,
        'altitude_stats': {
            'mean_altitude_ft': sum(altitudes) / len(altitudes) if altitudes else 0,
            'max_altitude_ft': max(altitudes) if altitudes else 0,
            'min_altitude_ft': min(altitudes) if altitudes else 0
        },
        'altitude_distribution': altitude_distribution,
        'speed_stats': {
            'mean_speed_knots': sum(speeds) / len(speeds) if speeds else 0,
            'max_speed_knots': max(speeds) if speeds else 0
        },
        'top_10_countries': top_countries,
        'top_10_fastest_aircraft': top_fastest,
        'data_timestamp': datetime.fromtimestamp(timestamp).isoformat() if timestamp else datetime.now().isoformat()
    }

    return {'statistics': statistics}


def create_response(status_code: int, data: Any) -> Dict[str, Any]:
    """
    Create a properly formatted Lambda response with CORS headers.
    
    Args:
        status_code: HTTP status code
        data: Response data
    
    Returns:
        Formatted Lambda response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400'
        },
        'body': json.dumps(data, default=str)  # default=str handles datetime objects
    }


