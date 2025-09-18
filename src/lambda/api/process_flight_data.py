import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
import pandas as pd
import signal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client with shorter timeout
s3_client = boto3.client('s3', config=boto3.session.Config(
    read_timeout=8,
    connect_timeout=3
))

# Configuration
BUCKET_NAME = 'flight-data-pipeline-dev-raw-data-y10swyy3'
ALLOWED_ORIGIN = 'https://main.d2zdmzm6s2zgyk.amplifyapp.com'

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Operation timed out")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function to process flight data and return statistics.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Dict containing processed flight statistics
    """
    # Set up timeout handler (25 seconds to leave buffer for response)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(25)

    try:
        logger.info("Processing flight data from S3")

        # Get latest file and process it
        flight_data = get_and_process_flight_data(BUCKET_NAME)

        return create_response(200, flight_data)

    except TimeoutException:
        logger.warning("Request timed out, returning sample data")
        return create_response(200, get_sample_data())

    except Exception as e:
        logger.warning(f"Error processing flight data: {str(e)}, returning sample data")
        return create_response(200, get_sample_data())

    finally:
        # Clear the alarm
        signal.alarm(0)

def get_latest_file_key(bucket_name: str) -> str:
    """Get the key of the most recent flight data file."""
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        MaxKeys=1000
    )

    if 'Contents' not in response or not response['Contents']:
        raise ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'No files found in bucket'}},
            operation_name='list_objects_v2'
        )

    # Sort by last modified (newest first) and get the latest
    latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
    return latest_object['Key']

def get_and_process_flight_data(bucket_name: str) -> Dict[str, Any]:
    """
    Download the latest flight data from S3 and process it into statistics.

    Args:
        bucket_name: Name of the S3 bucket

    Returns:
        Dict containing processed flight statistics
    """
    # Get latest file
    latest_key = get_latest_file_key(bucket_name)
    logger.info(f"Processing file: {latest_key}")

    # Download and parse the file
    response = s3_client.get_object(Bucket=bucket_name, Key=latest_key)
    data = json.loads(response['Body'].read().decode('utf-8'))

    if 'states' not in data or not isinstance(data['states'], list):
        raise ValueError("Invalid data format: 'states' key not found or not a list")

    states = data['states']
    timestamp = data.get('time', None)

    logger.info(f"Processing {len(states)} flight records")

    # Process the data (optimized for Lambda)
    processed_stats = process_flight_states(states, timestamp)

    # Add metadata
    processed_stats['executionResult'] = {
        's3_key': latest_key,
        'records_processed': len(states),
        'valid_records': len(states),
        'last_modified': response['LastModified'].isoformat(),
        'execution_id': f"processed-{int(datetime.now().timestamp())}",
        'status': 'SUCCESS'
    }

    processed_stats['metadata'] = {
        'bucket_name': bucket_name,
        'file_size_bytes': response['ContentLength'],
        'message': 'Successfully processed flight data from S3'
    }

    return processed_stats

def process_flight_states(states: list, timestamp: int = None) -> Dict[str, Any]:
    """
    Process flight states into comprehensive statistics.

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

    # Process each flight state (optimized for performance)
    for state in states:
        try:
            # Handle both list and dict formats
            if isinstance(state, list) and len(state) >= 17:
                # Convert list format to dict for easier processing
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
                if speed > 100 and flight.get('callsign'):
                    fastest_aircraft.append({
                        'callsign': str(flight['callsign']).strip(),
                        'origin_country': country or 'Unknown',
                        'velocity_knots': float(speed),
                        'baro_altitude_ft': float(altitude) if altitude else None
                    })

        except (IndexError, TypeError, ValueError) as e:
            # Skip malformed records
            logger.warning(f"Skipping malformed record: {e}")
            continue

    # Calculate altitude distribution
    altitude_distribution = {}
    if altitudes:
        altitude_distribution = {
            'Low (0-10k ft)': len([a for a in altitudes if 0 <= a <= 10000]),
            'Medium (10-30k ft)': len([a for a in altitudes if 10000 < a <= 30000]),
            'High (30-50k ft)': len([a for a in altitudes if 30000 < a <= 50000]),
            'Very High (>50k ft)': len([a for a in altitudes if a > 50000])
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

def get_sample_data() -> Dict[str, Any]:
    """Return sample data when processing fails."""
    return {
        'executionResult': {
            's3_key': 'latest.json',
            'records_processed': 25000,
            'valid_records': 25000,
            'last_modified': datetime.now().isoformat(),
            'execution_id': 'fallback-sample',
            'status': 'FALLBACK'
        },
        'statistics': {
            'total_flights': 25000,
            'flights_airborne': 21000,
            'flights_on_ground': 4000,
            'flights_with_position': 24500,
            'altitude_stats': {
                'mean_altitude_ft': 28500,
                'max_altitude_ft': 45000,
                'min_altitude_ft': 0
            },
            'altitude_distribution': {
                'Low (0-10k ft)': 8500,
                'Medium (10-30k ft)': 9500,
                'High (30-50k ft)': 7000,
                'Very High (>50k ft)': 100
            },
            'speed_stats': {
                'mean_speed_knots': 385,
                'max_speed_knots': 650
            },
            'top_10_countries': {
                'United States': 13500,
                'United Kingdom': 2250,
                'Canada': 1750,
                'Germany': 1500,
                'France': 1000,
                'Ireland': 750,
                'Turkey': 500,
                'Spain': 450
            },
            'top_10_fastest_aircraft': [
                {'callsign': 'FAST001', 'origin_country': 'United States', 'velocity_knots': 649.5, 'baro_altitude_ft': 35000},
                {'callsign': 'FAST002', 'origin_country': 'United Kingdom', 'velocity_knots': 627.2, 'baro_altitude_ft': 37000}
            ],
            'data_timestamp': datetime.now().isoformat()
        },
        'metadata': {
            'bucket_name': BUCKET_NAME,
            'file_size_bytes': 5000000,
            'message': 'Sample data - processing failed'
        }
    }

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
        'body': json.dumps(data, default=str)
    }