"""
Test data generator for integration tests.

Generates realistic flight data, malformed data, and large datasets
for comprehensive pipeline testing.
"""
import json
import random
import uuid
import gzip
import io
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
import numpy as np


class FlightDataGenerator:
    """Generate realistic flight data for testing."""
    
    def __init__(self, seed: int = None):
        """Initialize generator with optional seed for reproducible tests."""
        if seed:
            random.seed(seed)
            np.random.seed(seed)
        
        # Real airport coordinates for realistic routes
        self.airports = {
            'JFK': (40.6413, -73.7781),  # New York JFK
            'LAX': (33.9425, -118.4081),  # Los Angeles
            'LHR': (51.4700, -0.4543),   # London Heathrow  
            'CDG': (49.0097, 2.5479),    # Paris Charles de Gaulle
            'NRT': (35.7720, 140.3929),  # Tokyo Narita
            'DXB': (25.2532, 55.3657),   # Dubai
            'SIN': (1.3644, 103.9915),   # Singapore Changi
            'SYD': (-33.9399, 151.1753), # Sydney
            'FRA': (50.0379, 8.5622),    # Frankfurt
            'AMS': (52.3105, 4.7683),    # Amsterdam Schiphol
        }
        
        # Airlines and their typical aircraft
        self.airlines = {
            'UAL': ['B787', 'B777', 'A320', 'B737'],  # United
            'AAL': ['B787', 'A321', 'B737', 'A319'],  # American
            'DAL': ['A330', 'B737', 'A321', 'B757'],  # Delta
            'BAW': ['A380', 'B777', 'A320', 'B787'],  # British Airways
            'AFR': ['A380', 'A330', 'A320', 'B777'],  # Air France
            'LUF': ['A380', 'A330', 'A320', 'B747'],  # Lufthansa
            'SIA': ['A380', 'B777', 'A350', 'B787'],  # Singapore Airlines
            'QFA': ['A380', 'B787', 'A330', 'B737'],  # Qantas
        }
        
        # Realistic altitude ranges by aircraft type
        self.aircraft_profiles = {
            'A380': {'cruise_alt': (35000, 43000), 'max_speed': 560},
            'B777': {'cruise_alt': (35000, 42000), 'max_speed': 590},
            'B787': {'cruise_alt': (35000, 42000), 'max_speed': 587},
            'A330': {'cruise_alt': (35000, 42000), 'max_speed': 550},
            'A321': {'cruise_alt': (30000, 39000), 'max_speed': 511},
            'A320': {'cruise_alt': (30000, 39000), 'max_speed': 511},
            'B737': {'cruise_alt': (30000, 41000), 'max_speed': 544},
            'B747': {'cruise_alt': (35000, 43000), 'max_speed': 570},
        }
    
    def generate_flight_records(self, count: int, flight_phases: List[str] = None) -> List[Dict[str, Any]]:
        """Generate realistic flight data records."""
        if flight_phases is None:
            flight_phases = ['ground', 'taxi', 'takeoff', 'climb', 'cruise', 'descent', 'approach', 'landing']
        
        records = []
        base_time = int(datetime.now(timezone.utc).timestamp())
        
        for i in range(count):
            # Select random airline and aircraft
            airline = random.choice(list(self.airlines.keys()))
            aircraft_type = random.choice(self.airlines[airline])
            aircraft_profile = self.aircraft_profiles.get(aircraft_type, self.aircraft_profiles['B737'])
            
            # Generate ICAO24 (6 hex characters)
            icao24 = f"{random.randint(0, 0xFFFFFF):06x}"
            
            # Select flight phase
            phase = random.choice(flight_phases)
            
            # Generate position based on phase
            if phase == 'ground':
                # On ground at random airport
                airport = random.choice(list(self.airports.keys()))
                lat, lon = self.airports[airport]
                # Add small random offset for ground position
                lat += random.uniform(-0.01, 0.01)
                lon += random.uniform(-0.01, 0.01)
                
                altitude = random.uniform(0, 100)  # Ground level
                velocity = random.uniform(0, 15)   # Stationary or taxi
                vertical_rate = 0
                on_ground = True
                
            elif phase == 'taxi':
                airport = random.choice(list(self.airports.keys()))
                lat, lon = self.airports[airport]
                lat += random.uniform(-0.02, 0.02)
                lon += random.uniform(-0.02, 0.02)
                
                altitude = random.uniform(0, 50)
                velocity = random.uniform(5, 30)
                vertical_rate = 0
                on_ground = True
                
            elif phase == 'takeoff':
                airport = random.choice(list(self.airports.keys()))
                lat, lon = self.airports[airport]
                lat += random.uniform(-0.05, 0.05)
                lon += random.uniform(-0.05, 0.05)
                
                altitude = random.uniform(0, 3000)
                velocity = random.uniform(120, 200)
                vertical_rate = random.uniform(1500, 3000)
                on_ground = False
                
            elif phase == 'climb':
                # En route position
                lat = random.uniform(25, 60)  # Northern hemisphere bias
                lon = random.uniform(-120, 10)
                
                altitude = random.uniform(3000, 25000)
                velocity = random.uniform(200, 350)
                vertical_rate = random.uniform(500, 2000)
                on_ground = False
                
            elif phase == 'cruise':
                lat = random.uniform(25, 60)
                lon = random.uniform(-120, 10)
                
                cruise_alt_range = aircraft_profile['cruise_alt']
                altitude = random.uniform(*cruise_alt_range)
                velocity = random.uniform(450, aircraft_profile['max_speed'])
                vertical_rate = random.uniform(-100, 100)  # Minor variations
                on_ground = False
                
            elif phase == 'descent':
                lat = random.uniform(25, 60)
                lon = random.uniform(-120, 10)
                
                altitude = random.uniform(10000, 35000)
                velocity = random.uniform(250, 450)
                vertical_rate = random.uniform(-2000, -300)
                on_ground = False
                
            elif phase == 'approach':
                airport = random.choice(list(self.airports.keys()))
                lat, lon = self.airports[airport]
                # Offset for approach path
                lat += random.uniform(-0.2, 0.2)
                lon += random.uniform(-0.2, 0.2)
                
                altitude = random.uniform(500, 5000)
                velocity = random.uniform(140, 250)
                vertical_rate = random.uniform(-1500, -200)
                on_ground = False
                
            else:  # landing
                airport = random.choice(list(self.airports.keys()))
                lat, lon = self.airports[airport]
                lat += random.uniform(-0.05, 0.05)
                lon += random.uniform(-0.05, 0.05)
                
                altitude = random.uniform(0, 1000)
                velocity = random.uniform(60, 160)
                vertical_rate = random.uniform(-800, 0)
                on_ground = random.choice([True, False])
            
            # Generate flight number
            flight_num = random.randint(1, 9999)
            callsign = f"{airline}{flight_num:04d}"
            
            # Select origin country based on airline
            country_mapping = {
                'UAL': 'United States', 'AAL': 'United States', 'DAL': 'United States',
                'BAW': 'United Kingdom', 'AFR': 'France', 'LUF': 'Germany',
                'SIA': 'Singapore', 'QFA': 'Australia'
            }
            origin_country = country_mapping.get(airline, 'United States')
            
            # Calculate heading (simplified)
            heading = random.uniform(0, 360)
            
            # Generate squawk code
            squawk = f"{random.randint(1000, 7777):04d}"
            
            # Timestamps
            time_offset = random.randint(-300, 300)  # ±5 minutes variation
            time_position = base_time + i * 10 + time_offset
            last_contact = time_position + random.randint(0, 30)
            
            record = {
                'icao24': icao24,
                'callsign': callsign,
                'origin_country': origin_country,
                'time_position': time_position,
                'last_contact': last_contact,
                'longitude': round(lon, 4),
                'latitude': round(lat, 4),
                'baro_altitude': round(altitude, 0) if altitude > 0 else None,
                'on_ground': on_ground,
                'velocity': round(velocity, 1) if velocity > 0 else None,
                'true_track': round(heading, 1),
                'vertical_rate': round(vertical_rate, 0) if abs(vertical_rate) > 10 else None,
                'sensors': None,  # Not used in this simulation
                'geo_altitude': round(altitude + random.uniform(-100, 100), 0) if altitude > 0 else None,
                'squawk': squawk,
                'spi': False,
                'position_source': random.randint(0, 3),
                'aircraft_type': aircraft_type,
                'flight_phase': phase
            }
            
            records.append(record)
        
        return records
    
    def generate_invalid_records(self, count: int) -> List[Dict[str, Any]]:
        """Generate records with known quality issues for testing."""
        invalid_records = []
        
        for i in range(count):
            record_type = random.choice([
                'missing_icao24', 'invalid_coordinates', 'invalid_altitude', 
                'invalid_speed', 'missing_timestamp', 'extreme_values'
            ])
            
            base_record = {
                'icao24': f"{random.randint(0, 0xFFFFFF):06x}",
                'callsign': f"TST{i:04d}",
                'origin_country': 'Test Country',
                'time_position': int(datetime.now(timezone.utc).timestamp()) + i * 10,
                'last_contact': int(datetime.now(timezone.utc).timestamp()) + i * 10 + 5,
                'longitude': -74.0060,
                'latitude': 40.7128,
                'baro_altitude': 10000,
                'on_ground': False,
                'velocity': 250,
                'true_track': 90,
                'vertical_rate': 0,
                'squawk': '1200'
            }
            
            if record_type == 'missing_icao24':
                base_record['icao24'] = None
            elif record_type == 'invalid_coordinates':
                base_record['latitude'] = 95.0  # Invalid latitude
                base_record['longitude'] = -190.0  # Invalid longitude
            elif record_type == 'invalid_altitude':
                base_record['baro_altitude'] = -5000  # Invalid altitude
            elif record_type == 'invalid_speed':
                base_record['velocity'] = -100  # Negative speed
            elif record_type == 'missing_timestamp':
                base_record['time_position'] = None
                base_record['last_contact'] = None
            elif record_type == 'extreme_values':
                base_record['baro_altitude'] = float('inf')
                base_record['velocity'] = float('nan')
                base_record['vertical_rate'] = 50000  # Impossible climb rate
            
            invalid_records.append(base_record)
        
        return invalid_records
    
    def generate_time_series_flight(self, aircraft_id: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """Generate a time series of records for a single flight."""
        records = []
        
        # Flight phases with durations (minutes)
        phases = [
            ('ground', 5),
            ('taxi', 10), 
            ('takeoff', 5),
            ('climb', 15),
            ('cruise', duration_minutes - 45),
            ('descent', 10)
        ]
        
        base_time = int(datetime.now(timezone.utc).timestamp())
        current_time = base_time
        
        # Starting position (departure airport)
        start_airport = random.choice(list(self.airports.keys()))
        start_lat, start_lon = self.airports[start_airport]
        
        # Destination airport
        dest_airport = random.choice([a for a in self.airports.keys() if a != start_airport])
        dest_lat, dest_lon = self.airports[dest_airport]
        
        current_lat, current_lon = start_lat, start_lon
        current_altitude = 0
        
        for phase_name, phase_duration in phases:
            phase_records = int(phase_duration * 6)  # 6 records per minute (every 10 seconds)
            
            for i in range(phase_records):
                # Update position based on phase
                if phase_name in ['ground', 'taxi']:
                    # Stay near departure airport
                    current_lat = start_lat + random.uniform(-0.02, 0.02)
                    current_lon = start_lon + random.uniform(-0.02, 0.02)
                    current_altitude = random.uniform(0, 100)
                    velocity = random.uniform(0, 30)
                    vertical_rate = 0
                    on_ground = True
                    
                elif phase_name == 'takeoff':
                    # Move away from airport, gain altitude
                    progress = i / phase_records
                    current_lat += (dest_lat - start_lat) * 0.1 * progress
                    current_lon += (dest_lon - start_lon) * 0.1 * progress
                    current_altitude = 3000 * progress
                    velocity = 120 + 80 * progress
                    vertical_rate = 2000
                    on_ground = False
                    
                elif phase_name == 'climb':
                    # Continue toward destination, climb to cruise
                    progress = i / phase_records
                    current_lat += (dest_lat - start_lat) * 0.3 * progress
                    current_lon += (dest_lon - start_lon) * 0.3 * progress
                    current_altitude = 3000 + 32000 * progress
                    velocity = 200 + 250 * progress
                    vertical_rate = 1500 * (1 - progress)
                    on_ground = False
                    
                elif phase_name == 'cruise':
                    # Linear progress toward destination
                    progress = i / phase_records
                    current_lat = start_lat + (dest_lat - start_lat) * (0.4 + 0.5 * progress)
                    current_lon = start_lon + (dest_lon - start_lon) * (0.4 + 0.5 * progress)
                    current_altitude = 35000 + random.uniform(-1000, 1000)
                    velocity = 450 + random.uniform(-20, 20)
                    vertical_rate = random.uniform(-50, 50)
                    on_ground = False
                    
                elif phase_name == 'descent':
                    # Approach destination, lose altitude
                    progress = i / phase_records
                    current_lat = dest_lat + (start_lat - dest_lat) * 0.1 * (1 - progress)
                    current_lon = dest_lon + (start_lon - dest_lon) * 0.1 * (1 - progress)
                    current_altitude = 35000 * (1 - progress)
                    velocity = 450 - 200 * progress
                    vertical_rate = -1500
                    on_ground = False
                
                record = {
                    'icao24': aircraft_id,
                    'callsign': f"TST{random.randint(100, 999)}",
                    'origin_country': 'Test Country',
                    'time_position': current_time,
                    'last_contact': current_time + random.randint(1, 5),
                    'longitude': round(current_lon, 4),
                    'latitude': round(current_lat, 4),
                    'baro_altitude': round(current_altitude, 0) if current_altitude > 0 else None,
                    'on_ground': on_ground,
                    'velocity': round(velocity, 1),
                    'true_track': random.uniform(0, 360),
                    'vertical_rate': round(vertical_rate, 0) if abs(vertical_rate) > 10 else None,
                    'squawk': '1200',
                    'flight_phase': phase_name
                }
                
                records.append(record)
                current_time += 10  # 10-second intervals
        
        return records


def create_malformed_json_files() -> Dict[str, str]:
    """Create various malformed JSON files for error testing."""
    return {
        'invalid_json_syntax.json': '{"records": [{"icao24": "abcdef", "incomplete": }',
        'empty_file.json': '',
        'non_json_content.json': 'This is plain text, not JSON',
        'invalid_unicode.json': '{"records": [{"icao24": "\x00\x01\x02invalid"}]}',
        'extremely_nested.json': '{"a":{"b":{"c":{"d":' * 1000 + '"value"' + '}' * 1000 + '}',
        'invalid_number_format.json': '{"records": [{"altitude": 1.2.3.4}]}',
        'unescaped_quotes.json': '{"message": "This has "unescaped" quotes"}',
        'incomplete_array.json': '{"records": [{"icao24": "abcdef"}, {"icao24": "123456"',
        'mixed_encoding.json': json.dumps({"records": [{"icao24": "café"}]}).encode('utf-8').decode('latin-1'),
        'circular_reference.json': '{"a": {"b": {"ref": {"$ref": "#/a"}}}}',
    }


def create_oversized_files() -> Dict[str, str]:
    """Create files of various large sizes for testing limits."""
    oversized_files = {}
    
    # 1MB file
    large_record = {"icao24": "x" * 1000, "data": "y" * 1000}
    large_records = [large_record] * 500  # ~1MB
    oversized_files['1mb_file.json'] = json.dumps(large_records)
    
    # 10MB file  
    huge_records = [large_record] * 5000  # ~10MB
    oversized_files['10mb_file.json'] = json.dumps(huge_records)
    
    # File with single huge record
    monster_record = {"icao24": "abcdef", "huge_field": "x" * 5000000}  # 5MB single field
    oversized_files['monster_record.json'] = json.dumps([monster_record])
    
    # Many small records (100k records)
    small_record = {"icao24": "abcdef", "lat": 40.0, "lon": -74.0}
    many_records = [small_record] * 100000
    oversized_files['many_records.json'] = json.dumps(many_records)
    
    return oversized_files


def create_compressed_test_files() -> Dict[str, bytes]:
    """Create compressed test files."""
    generator = FlightDataGenerator()
    compressed_files = {}
    
    # Standard gzip compressed file
    flight_data = generator.generate_flight_records(1000)
    json_content = json.dumps(flight_data, indent=2)
    
    # Gzip compression
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as gz_file:
        gz_file.write(json_content.encode('utf-8'))
    compressed_files['normal_data.json.gz'] = buffer.getvalue()
    
    # Highly compressed (repetitive data)
    repetitive_data = [generator.generate_flight_records(1)[0]] * 10000  # Same record repeated
    repetitive_json = json.dumps(repetitive_data)
    
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as gz_file:
        gz_file.write(repetitive_json.encode('utf-8'))
    compressed_files['repetitive_data.json.gz'] = buffer.getvalue()
    
    return compressed_files


def create_edge_case_data() -> List[Dict[str, Any]]:
    """Create edge case flight data for boundary testing."""
    edge_cases = []
    
    # Boundary coordinates
    edge_cases.extend([
        # North pole
        {"icao24": "edge01", "latitude": 89.999, "longitude": 0, "baro_altitude": 35000},
        # South pole  
        {"icao24": "edge02", "latitude": -89.999, "longitude": 0, "baro_altitude": 35000},
        # International date line
        {"icao24": "edge03", "latitude": 40, "longitude": 179.999, "baro_altitude": 35000},
        {"icao24": "edge04", "latitude": 40, "longitude": -179.999, "baro_altitude": 35000},
        # Equator
        {"icao24": "edge05", "latitude": 0.001, "longitude": 0, "baro_altitude": 35000},
        # Prime meridian
        {"icao24": "edge06", "latitude": 51.477, "longitude": 0.001, "baro_altitude": 35000},
    ])
    
    # Extreme altitudes
    edge_cases.extend([
        # Dead Sea level
        {"icao24": "edge07", "latitude": 31.5, "longitude": 35.5, "baro_altitude": -1388},
        # Mount Everest level
        {"icao24": "edge08", "latitude": 28, "longitude": 87, "baro_altitude": 29032},
        # Commercial ceiling
        {"icao24": "edge09", "latitude": 40, "longitude": -74, "baro_altitude": 42000},
        # Military ceiling
        {"icao24": "edge10", "latitude": 40, "longitude": -74, "baro_altitude": 60000},
    ])
    
    # Time boundaries
    current_time = int(datetime.now(timezone.utc).timestamp())
    edge_cases.extend([
        # Very recent
        {"icao24": "edge11", "latitude": 40, "longitude": -74, "time_position": current_time - 1},
        # Exactly now
        {"icao24": "edge12", "latitude": 40, "longitude": -74, "time_position": current_time},
        # Future (should be flagged)
        {"icao24": "edge13", "latitude": 40, "longitude": -74, "time_position": current_time + 3600},
        # Very old (should be flagged)
        {"icao24": "edge14", "latitude": 40, "longitude": -74, "time_position": current_time - 86400},
    ])
    
    # Speed boundaries
    edge_cases.extend([
        # Stationary
        {"icao24": "edge15", "latitude": 40, "longitude": -74, "velocity": 0},
        # Taxi speed
        {"icao24": "edge16", "latitude": 40, "longitude": -74, "velocity": 25},
        # Sound barrier
        {"icao24": "edge17", "latitude": 40, "longitude": -74, "velocity": 661.5},  # Mach 1
        # Supersonic
        {"icao24": "edge18", "latitude": 40, "longitude": -74, "velocity": 1200},
    ])
    
    return edge_cases