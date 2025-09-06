#!/usr/bin/env python3
"""
Flight Data Dashboard API Server
Provides S3 data access for the dashboard with proper authentication
"""

import json
import os
import sys
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configuration
BUCKET_NAME = 'flight-data-pipeline-dev-raw-data-y10swyy3'
PORT = 8000

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3')
            self.s3_available = True
            print("✅ S3 client initialized successfully")
        except (ClientError, NoCredentialsError) as e:
            self.s3_client = None
            self.s3_available = False
            print(f"⚠️  S3 client initialization failed: {e}")
        
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # Handle API endpoints
        if parsed_path.path == '/api/flight-data':
            self.handle_flight_data_api()
        elif parsed_path.path == '/api/flight-summary':
            self.handle_flight_summary_api()
        elif parsed_path.path == '/api/latest-stats':
            self.handle_stats_api()
        elif parsed_path.path == '/api/health':
            self.handle_health_api()
        else:
            # Serve static files normally
            super().do_GET()
    
    def handle_flight_data_api(self):
        """Fetch the latest flight data from S3"""
        try:
            if not self.s3_available:
                raise Exception("S3 client not available")
            
            # Find the most recent flight data file
            latest_key = self.get_latest_flight_data_key()
            if not latest_key:
                raise Exception("No recent flight data found")
            
            # Get the object from S3
            response = self.s3_client.get_object(Bucket=BUCKET_NAME, Key=latest_key)
            flight_data = json.loads(response['Body'].read())
            
            # Return the data with metadata
            result = {
                'success': True,
                'data': flight_data,
                'metadata': {
                    'key': latest_key,
                    'last_modified': response['LastModified'].isoformat(),
                    'size': response['ContentLength']
                }
            }
            
            self.send_json_response(result)
            print(f"✅ Served flight data from: {latest_key}")
            
        except Exception as e:
            error_response = {
                'success': False,
                'error': str(e),
                'message': 'Failed to fetch flight data from S3'
            }
            self.send_json_response(error_response, status_code=500)
            print(f"❌ Flight data API error: {e}")
    
    def handle_flight_summary_api(self):
        """Fetch and process flight data, return only summary statistics"""
        try:
            if not self.s3_available:
                raise Exception("S3 client not available")
            
            # Find the most recent flight data file
            latest_key = self.get_latest_flight_data_key()
            if not latest_key:
                raise Exception("No recent flight data found")
            
            # Get the object from S3
            response = self.s3_client.get_object(Bucket=BUCKET_NAME, Key=latest_key)
            flight_data = json.loads(response['Body'].read())
            
            # Process the data to generate statistics (lightweight)
            states = flight_data.get('states', [])
            total_flights = len(states)
            airborne_count = sum(1 for state in states if not state.get('on_ground', True))
            ground_count = total_flights - airborne_count
            
            # Process countries and speeds (sample for performance)
            countries = {}
            speeds = []
            altitudes = []
            fastest_aircraft = []
            
            for i, state_data in enumerate(states):
                # Convert array format to dict format for easier processing
                if isinstance(state_data, list) and len(state_data) >= 17:
                    state = {
                        'icao24': state_data[0],
                        'callsign': state_data[1],
                        'origin_country': state_data[2],
                        'baro_altitude_ft': state_data[8],
                        'on_ground': state_data[9],
                        'velocity_knots': state_data[11]
                    }
                else:
                    state = state_data
                
                # Count countries
                if state.get('origin_country'):
                    country = state['origin_country']
                    countries[country] = countries.get(country, 0) + 1
                
                # Collect speeds and altitudes (sample every 10th for performance)
                if i % 10 == 0:
                    if state.get('velocity_knots') and state['velocity_knots'] > 0:
                        speeds.append(state['velocity_knots'])
                        
                        # Track fastest aircraft
                        if state['velocity_knots'] > 200 and state.get('callsign'):
                            fastest_aircraft.append({
                                'callsign': str(state['callsign']).strip(),
                                'origin_country': state.get('origin_country', 'Unknown'),
                                'velocity_knots': state['velocity_knots'],
                                'baro_altitude_ft': state.get('baro_altitude_ft')
                            })
                    
                    if state.get('baro_altitude_ft') and state['baro_altitude_ft'] > 0:
                        altitudes.append(state['baro_altitude_ft'])
            
            # Calculate statistics
            altitude_distribution = {
                'Low (0-10k ft)': len([a for a in altitudes if 0 <= a <= 10000]),
                'Medium (10-30k ft)': len([a for a in altitudes if 10000 < a <= 30000]),
                'High (30-50k ft)': len([a for a in altitudes if 30000 < a <= 50000]),
                'Very High (>50k ft)': len([a for a in altitudes if a > 50000])
            }
            
            # Sort countries and fastest aircraft
            top_countries = dict(sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10])
            top_fastest = sorted(fastest_aircraft, key=lambda x: x['velocity_knots'], reverse=True)[:10]
            
            # Build summary response
            summary = {
                'total_flights': total_flights,
                'flights_airborne': airborne_count,
                'flights_on_ground': ground_count,
                'flights_with_position': sum(1 for state in states[:100] if state.get('longitude') is not None),
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
                'data_timestamp': datetime.fromtimestamp(flight_data.get('time', 0)).isoformat()
            }
            
            result = {
                'success': True,
                'executionResult': {
                    's3_key': latest_key,
                    'records_processed': total_flights,
                    'valid_records': total_flights,
                    'last_modified': response['LastModified'].isoformat()
                },
                'statistics': summary
            }
            
            self.send_json_response(result)
            print(f"✅ Served flight summary from: {latest_key} ({total_flights} flights)")
            
        except Exception as e:
            error_response = {
                'success': False,
                'error': str(e),
                'message': 'Failed to process flight summary'
            }
            self.send_json_response(error_response, status_code=500)
            print(f"❌ Flight summary API error: {e}")
    
    def handle_stats_api(self):
        """Return processed flight statistics"""
        try:
            # Try to read local statistics file
            with open('flight_statistics.json', 'r') as f:
                stats = json.load(f)
            
            result = {
                'success': True,
                'data': stats,
                'source': 'local_cache'
            }
            
            self.send_json_response(result)
            print("✅ Served local flight statistics")
            
        except Exception as e:
            error_response = {
                'success': False,
                'error': str(e),
                'message': 'Failed to load flight statistics'
            }
            self.send_json_response(error_response, status_code=500)
            print(f"❌ Stats API error: {e}")
    
    def handle_health_api(self):
        """Health check endpoint"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            's3_available': self.s3_available,
            'bucket': BUCKET_NAME
        }
        
        self.send_json_response(health_status)
    
    def get_latest_flight_data_key(self):
        """Find the most recent flight data file in S3"""
        if not self.s3_available:
            return None
        
        # Try current day and previous days
        for days_back in range(4):  # Try current day and 3 previous days
            target_date = datetime.now() - timedelta(days=days_back)
            prefix = target_date.strftime('year=%Y/month=%m/day=%d/')
            
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    Prefix=prefix,
                    MaxKeys=10
                )
                
                if 'Contents' in response and response['Contents']:
                    # Sort by last modified (most recent first)
                    sorted_objects = sorted(
                        response['Contents'],
                        key=lambda x: x['LastModified'],
                        reverse=True
                    )
                    return sorted_objects[0]['Key']
                    
            except ClientError as e:
                print(f"⚠️  No data found for {prefix}: {e}")
                continue
        
        return None
    
    def send_json_response(self, data, status_code=200):
        """Send JSON response with CORS headers"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        json_data = json.dumps(data, indent=2, default=str)
        self.wfile.write(json_data.encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def main():
    try:
        # Change to the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        server = HTTPServer(('localhost', PORT), DashboardHandler)
        
        print(f"🚀 Flight Data Dashboard API Server starting...")
        print(f"📊 Dashboard: http://localhost:{PORT}/dashboard.html")
        print(f"🔧 API Health: http://localhost:{PORT}/api/health")
        print(f"📡 API Endpoints:")
        print(f"   - /api/flight-data (latest S3 data)")
        print(f"   - /api/latest-stats (processed statistics)")
        print(f"⏹️  Press Ctrl+C to stop")
        print()
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
        server.shutdown()
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()