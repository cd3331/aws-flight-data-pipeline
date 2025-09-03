#!/usr/bin/env python3
"""
Flight Data Generator

Generates realistic test flight data for the flight data pipeline including:
- Valid flight records with realistic values
- Data quality issues for testing validation
- Proper OpenSky Network API format
- Edge cases and anomalies

Usage:
    python generate_sample_data.py [--records 1000] [--output data/sample/raw/]
"""

import json
import random
import argparse
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import math

class FlightDataGenerator:
    def __init__(self):
        # Major airports worldwide for realistic positioning
        self.major_airports = [
            # North America
            {"name": "JFK", "lat": 40.6413, "lon": -73.7781, "country": "United States"},
            {"name": "LAX", "lat": 33.9425, "lon": -118.4081, "country": "United States"},
            {"name": "ORD", "lat": 41.9742, "lon": -87.9073, "country": "United States"},
            {"name": "YYZ", "lat": 43.6777, "lon": -79.6248, "country": "Canada"},
            {"name": "MEX", "lat": 19.4363, "lon": -99.0721, "country": "Mexico"},
            
            # Europe
            {"name": "LHR", "lat": 51.4700, "lon": -0.4543, "country": "United Kingdom"},
            {"name": "CDG", "lat": 49.0097, "lon": 2.5479, "country": "France"},
            {"name": "FRA", "lat": 50.0379, "lon": 8.5622, "country": "Germany"},
            {"name": "AMS", "lat": 52.3086, "lon": 4.7639, "country": "Netherlands"},
            {"name": "MAD", "lat": 40.4839, "lon": -3.5680, "country": "Spain"},
            
            # Asia Pacific
            {"name": "NRT", "lat": 35.7720, "lon": 140.3929, "country": "Japan"},
            {"name": "PEK", "lat": 40.0799, "lon": 116.6031, "country": "China"},
            {"name": "SIN", "lat": 1.3644, "lon": 103.9915, "country": "Singapore"},
            {"name": "SYD", "lat": -33.9399, "lon": 151.1753, "country": "Australia"},
            {"name": "ICN", "lat": 37.4602, "lon": 126.4407, "country": "South Korea"},
            
            # Other regions
            {"name": "DXB", "lat": 25.2532, "lon": 55.3657, "country": "United Arab Emirates"},
            {"name": "JNB", "lat": -26.1392, "lon": 28.2460, "country": "South Africa"},
            {"name": "GRU", "lat": -23.4356, "lon": -46.4731, "country": "Brazil"},
        ]
        
        # Common airline codes and their typical callsign patterns
        self.airlines = [
            # US Airlines
            {"code": "AAL", "country": "United States", "pattern": "AAL{}"},
            {"code": "DAL", "country": "United States", "pattern": "DAL{}"},
            {"code": "UAL", "country": "United States", "pattern": "UAL{}"},
            {"code": "SWA", "country": "United States", "pattern": "SWA{}"},
            {"code": "JBU", "country": "United States", "pattern": "JBU{}"},
            
            # European Airlines
            {"code": "BAW", "country": "United Kingdom", "pattern": "BAW{}"},
            {"code": "AFR", "country": "France", "pattern": "AFR{}"},
            {"code": "DLH", "country": "Germany", "pattern": "DLH{}"},
            {"code": "KLM", "country": "Netherlands", "pattern": "KLM{}"},
            {"code": "IBE", "country": "Spain", "pattern": "IBE{}"},
            
            # Asian Airlines
            {"code": "JAL", "country": "Japan", "pattern": "JAL{}"},
            {"code": "ANA", "country": "Japan", "pattern": "ANA{}"},
            {"code": "CCA", "country": "China", "pattern": "CCA{}"},
            {"code": "SIA", "country": "Singapore", "pattern": "SIA{}"},
            {"code": "QFA", "country": "Australia", "pattern": "QFA{}"},
            
            # Others
            {"code": "UAE", "country": "United Arab Emirates", "pattern": "UAE{}"},
            {"code": "SAA", "country": "South Africa", "pattern": "SAA{}"},
            {"code": "TAM", "country": "Brazil", "pattern": "TAM{}"},
        ]
        
        # Aircraft types with realistic performance characteristics
        self.aircraft_types = [
            {"type": "A320", "max_alt": 39000, "cruise_speed": 450, "max_speed": 537},
            {"type": "A321", "max_alt": 39000, "cruise_speed": 454, "max_speed": 541},
            {"type": "A330", "max_alt": 41000, "cruise_speed": 470, "max_speed": 567},
            {"type": "A350", "max_alt": 43000, "cruise_speed": 488, "max_speed": 585},
            {"type": "A380", "max_alt": 43000, "cruise_speed": 488, "max_speed": 634},
            {"type": "B737", "max_alt": 41000, "cruise_speed": 453, "max_speed": 544},
            {"type": "B747", "max_alt": 45000, "cruise_speed": 490, "max_speed": 614},
            {"type": "B777", "max_alt": 43100, "cruise_speed": 490, "max_speed": 590},
            {"type": "B787", "max_alt": 43000, "cruise_speed": 488, "max_speed": 593},
            {"type": "E190", "max_alt": 41000, "cruise_speed": 447, "max_speed": 536},
        ]
        
        # Flight phases with typical characteristics
        self.flight_phases = {
            "ground": {"alt_range": (0, 100), "speed_range": (0, 60), "vertical_rate_range": (-50, 50)},
            "takeoff": {"alt_range": (0, 5000), "speed_range": (120, 250), "vertical_rate_range": (500, 3000)},
            "climb": {"alt_range": (5000, 35000), "speed_range": (250, 450), "vertical_rate_range": (500, 2500)},
            "cruise": {"alt_range": (28000, 42000), "speed_range": (400, 550), "vertical_rate_range": (-200, 200)},
            "descent": {"alt_range": (5000, 35000), "speed_range": (250, 450), "vertical_rate_range": (-2500, -200)},
            "approach": {"alt_range": (500, 8000), "speed_range": (150, 280), "vertical_rate_range": (-1500, -100)},
            "landing": {"alt_range": (0, 500), "speed_range": (120, 180), "vertical_rate_range": (-800, -100)},
        }
    
    def generate_icao24(self) -> str:
        """Generate realistic ICAO24 identifier (6 hex characters)"""
        return ''.join(random.choices('0123456789abcdef', k=6))
    
    def generate_callsign(self, origin_country: str) -> Optional[str]:
        """Generate realistic callsign based on origin country"""
        # Find airlines from the same country
        matching_airlines = [a for a in self.airlines if a['country'] == origin_country]
        
        if matching_airlines:
            airline = random.choice(matching_airlines)
        else:
            airline = random.choice(self.airlines)
        
        flight_number = random.randint(1, 9999)
        return airline['pattern'].format(flight_number)
    
    def generate_route_coordinates(self) -> Tuple[Dict, Dict, List[Tuple[float, float]]]:
        """Generate realistic flight route between two airports"""
        origin = random.choice(self.major_airports)
        destination = random.choice([a for a in self.major_airports if a != origin])
        
        # Generate intermediate waypoints for long flights
        waypoints = []
        
        # Calculate great circle distance
        lat1, lon1 = math.radians(origin['lat']), math.radians(origin['lon'])
        lat2, lon2 = math.radians(destination['lat']), math.radians(destination['lon'])
        
        # Simple linear interpolation for waypoints (simplified for demo)
        num_waypoints = random.randint(0, 5)
        for i in range(1, num_waypoints + 1):
            fraction = i / (num_waypoints + 1)
            wp_lat = origin['lat'] + fraction * (destination['lat'] - origin['lat'])
            wp_lon = origin['lon'] + fraction * (destination['lon'] - origin['lon'])
            
            # Add some randomness to simulate actual flight paths
            wp_lat += random.uniform(-2, 2)
            wp_lon += random.uniform(-2, 2)
            
            waypoints.append((wp_lat, wp_lon))
        
        return origin, destination, waypoints
    
    def generate_position_along_route(self, origin: Dict, destination: Dict, 
                                    waypoints: List[Tuple[float, float]], progress: float) -> Tuple[float, float]:
        """Generate position along flight route based on progress (0-1)"""
        if progress <= 0:
            return origin['lat'], origin['lon']
        elif progress >= 1:
            return destination['lat'], destination['lon']
        
        # Simple linear interpolation along route
        all_points = [(origin['lat'], origin['lon'])] + waypoints + [(destination['lat'], destination['lon'])]
        
        # Find which segment we're on
        segment_progress = progress * (len(all_points) - 1)
        segment_index = int(segment_progress)
        local_progress = segment_progress - segment_index
        
        if segment_index >= len(all_points) - 1:
            return all_points[-1]
        
        # Interpolate between points
        p1 = all_points[segment_index]
        p2 = all_points[segment_index + 1]
        
        lat = p1[0] + local_progress * (p2[0] - p1[0])
        lon = p1[1] + local_progress * (p2[1] - p1[1])
        
        return lat, lon
    
    def generate_flight_phase_data(self, phase: str, aircraft_type: Dict, 
                                 progress: float = 0.5) -> Dict:
        """Generate flight data based on flight phase"""
        phase_data = self.flight_phases[phase]
        aircraft = aircraft_type
        
        # Generate altitude based on phase and aircraft capabilities
        alt_min, alt_max = phase_data['alt_range']
        if phase == "cruise":
            # Cruise altitude varies by aircraft type
            alt_min = max(alt_min, aircraft['max_alt'] - 10000)
            alt_max = min(alt_max, aircraft['max_alt'])
        
        altitude_m = random.uniform(alt_min, alt_max) * 0.3048  # Convert ft to m
        
        # Generate speed based on phase and aircraft capabilities
        speed_min, speed_max = phase_data['speed_range']
        if phase == "cruise":
            speed_min = max(speed_min, aircraft['cruise_speed'] - 50)
            speed_max = min(speed_max, aircraft['max_speed'])
        
        velocity_ms = random.uniform(speed_min, speed_max) * 0.514444  # Convert knots to m/s
        
        # Generate vertical rate
        vr_min, vr_max = phase_data['vertical_rate_range']
        vertical_rate = random.uniform(vr_min, vr_max)
        
        # Generate other parameters
        true_track = random.uniform(0, 360)
        on_ground = phase == "ground"
        
        return {
            'baro_altitude_m': altitude_m,
            'velocity_ms': velocity_ms,
            'vertical_rate': vertical_rate,
            'true_track': true_track,
            'on_ground': on_ground
        }
    
    def introduce_data_quality_issues(self, record: Dict, issue_type: str) -> Dict:
        """Introduce specific data quality issues for testing"""
        modified_record = record.copy()
        
        if issue_type == "missing_critical":
            # Remove critical fields
            fields_to_remove = random.sample(['icao24', 'longitude', 'latitude'], 1)
            for field in fields_to_remove:
                modified_record[field] = None
                
        elif issue_type == "missing_optional":
            # Remove optional fields
            optional_fields = ['callsign', 'origin_country', 'squawk', 'sensors']
            fields_to_remove = random.sample(optional_fields, random.randint(1, 2))
            for field in fields_to_remove:
                if field in modified_record:
                    modified_record[field] = None
                    
        elif issue_type == "invalid_coordinates":
            # Invalid coordinate ranges
            if random.choice([True, False]):
                modified_record['longitude'] = random.uniform(-200, 200)  # Invalid range
            else:
                modified_record['latitude'] = random.uniform(-100, 100)   # Invalid range
                
        elif issue_type == "impossible_altitude":
            # Impossible altitudes
            impossible_alts = [-5000, 70000, 100000]  # Below sea level or too high
            modified_record['baro_altitude'] = random.choice(impossible_alts)
            
        elif issue_type == "impossible_speed":
            # Impossible speeds
            if random.choice([True, False]):
                modified_record['velocity'] = -50  # Negative speed
            else:
                modified_record['velocity'] = 1500 * 0.514444  # Supersonic for commercial aircraft
                
        elif issue_type == "inconsistent_ground":
            # Aircraft on ground but with high altitude/speed
            modified_record['on_ground'] = True
            modified_record['baro_altitude'] = random.uniform(10000, 30000) * 0.3048  # High altitude
            modified_record['velocity'] = random.uniform(300, 500) * 0.514444  # High speed
            
        elif issue_type == "future_timestamp":
            # Timestamps in the future
            future_time = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
            modified_record['last_contact'] = future_time
            modified_record['time_position'] = future_time
            
        elif issue_type == "old_timestamp":
            # Very old timestamps
            old_time = int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())
            modified_record['last_contact'] = old_time
            modified_record['time_position'] = old_time
            
        elif issue_type == "invalid_icao24":
            # Invalid ICAO24 format
            invalid_formats = ["12345", "1234567", "GGGGGG", "", "xyz123"]
            modified_record['icao24'] = random.choice(invalid_formats)
            
        elif issue_type == "null_island":
            # Coordinates at (0, 0) - often indicates missing/invalid data
            modified_record['longitude'] = 0.0
            modified_record['latitude'] = 0.0
            
        elif issue_type == "duplicate_icao24":
            # This will be used to create duplicates in the dataset
            modified_record['icao24'] = "aaaaaa"  # Common ICAO24 for duplicates
        
        return modified_record
    
    def generate_single_flight_record(self, current_time: int, with_issues: bool = False, 
                                    issue_type: str = None) -> List:
        """Generate a single flight record in OpenSky Network format"""
        
        # Choose aircraft type
        aircraft = random.choice(self.aircraft_types)
        
        # Generate route
        origin, destination, waypoints = self.generate_route_coordinates()
        
        # Determine flight phase and progress
        phases = list(self.flight_phases.keys())
        phase = random.choice(phases)
        progress = random.uniform(0.1, 0.9)
        
        # Generate position along route
        lat, lon = self.generate_position_along_route(origin, destination, waypoints, progress)
        
        # Add some realistic variation
        lat += random.uniform(-0.1, 0.1)
        lon += random.uniform(-0.1, 0.1)
        
        # Generate flight phase specific data
        phase_data = self.generate_flight_phase_data(phase, aircraft, progress)
        
        # Generate ICAO24 and callsign
        icao24 = self.generate_icao24()
        callsign = self.generate_callsign(origin['country'])
        
        # Generate timestamps
        time_variation = random.randint(-300, 0)  # Up to 5 minutes ago
        last_contact = current_time + time_variation
        time_position = last_contact + random.randint(-60, 0)  # Position update is older
        
        # Generate other fields
        squawk = None
        if random.random() < 0.7:  # 70% have squawk codes
            squawk = f"{random.randint(1000, 7777):04d}"
        
        sensors = random.choice([None] + list(range(1, 8)))
        geo_altitude = phase_data['baro_altitude_m'] + random.uniform(-100, 100)
        spi = random.choice([True, False]) if random.random() < 0.05 else False
        position_source = random.randint(0, 3)
        
        # OpenSky Network API format (array of 17 elements)
        record = [
            icao24,                                 # 0: icao24
            callsign.strip() if callsign else None, # 1: callsign  
            origin['country'],                      # 2: origin_country
            time_position if time_position > 0 else None,  # 3: time_position
            last_contact,                           # 4: last_contact
            lon,                                    # 5: longitude
            lat,                                    # 6: latitude
            phase_data['baro_altitude_m'],          # 7: baro_altitude
            phase_data['on_ground'],                # 8: on_ground
            phase_data['velocity_ms'],              # 9: velocity
            phase_data['true_track'],               # 10: true_track
            phase_data['vertical_rate'],            # 11: vertical_rate
            sensors,                                # 12: sensors
            geo_altitude,                           # 13: geo_altitude
            squawk,                                 # 14: squawk
            spi,                                    # 15: spi
            position_source                         # 16: position_source
        ]
        
        # Introduce data quality issues if requested
        if with_issues and issue_type:
            # Convert to dict for easier manipulation
            field_names = [
                'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
                'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity',
                'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk',
                'spi', 'position_source'
            ]
            
            record_dict = dict(zip(field_names, record))
            record_dict = self.introduce_data_quality_issues(record_dict, issue_type)
            
            # Convert back to array
            record = [record_dict.get(field) for field in field_names]
        
        return record
    
    def generate_dataset(self, num_records: int = 1000, quality_issues_percent: float = 0.15) -> Dict:
        """Generate complete flight dataset with good and problematic records"""
        
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Calculate number of problematic records
        num_issues = int(num_records * quality_issues_percent)
        num_good = num_records - num_issues
        
        # Define issue types and their distribution
        issue_types = [
            "missing_critical", "missing_optional", "invalid_coordinates", 
            "impossible_altitude", "impossible_speed", "inconsistent_ground",
            "future_timestamp", "old_timestamp", "invalid_icao24", 
            "null_island", "duplicate_icao24"
        ]
        
        states = []
        
        print(f"Generating {num_good} good records...")
        # Generate good records
        for i in range(num_good):
            if i % 100 == 0:
                print(f"  Generated {i}/{num_good} good records")
            
            record = self.generate_single_flight_record(current_time, with_issues=False)
            states.append(record)
        
        print(f"Generating {num_issues} problematic records...")
        # Generate problematic records
        for i in range(num_issues):
            if i % 20 == 0:
                print(f"  Generated {i}/{num_issues} problematic records")
            
            issue_type = random.choice(issue_types)
            record = self.generate_single_flight_record(current_time, with_issues=True, issue_type=issue_type)
            states.append(record)
        
        # Shuffle the records
        random.shuffle(states)
        
        # Create OpenSky Network format response
        dataset = {
            "time": current_time,
            "states": states
        }
        
        return dataset
    
    def save_dataset(self, dataset: Dict, output_dir: str, filename: str = None) -> str:
        """Save dataset to JSON file"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"flight_data_test_{timestamp}.json"
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"Dataset saved to: {filepath}")
        return filepath
    
    def generate_multiple_files(self, num_files: int, records_per_file: int, 
                              output_dir: str, quality_issues_percent: float = 0.15) -> List[str]:
        """Generate multiple test files for comprehensive testing"""
        
        files_created = []
        
        for i in range(num_files):
            print(f"\nGenerating file {i+1}/{num_files}...")
            
            # Vary the dataset size slightly
            num_records = records_per_file + random.randint(-50, 50)
            
            # Generate dataset
            dataset = self.generate_dataset(num_records, quality_issues_percent)
            
            # Save with timestamp and index
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"flight_data_test_{timestamp}_{i+1:03d}.json"
            
            filepath = self.save_dataset(dataset, output_dir, filename)
            files_created.append(filepath)
            
            # Add small delay to ensure different timestamps
            import time
            time.sleep(1)
        
        return files_created
    
    def print_dataset_summary(self, dataset: Dict) -> None:
        """Print summary statistics of the generated dataset"""
        
        states = dataset.get('states', [])
        total_records = len(states)
        
        if total_records == 0:
            print("No records in dataset")
            return
        
        # Analyze data quality
        missing_icao24 = sum(1 for s in states if not s[0])
        missing_coordinates = sum(1 for s in states if s[5] is None or s[6] is None)
        missing_callsign = sum(1 for s in states if not s[1])
        on_ground_count = sum(1 for s in states if s[8])
        
        # Altitude analysis
        altitudes = [s[7] for s in states if s[7] is not None]
        speeds = [s[9] for s in states if s[9] is not None]
        
        print(f"\n=== Dataset Summary ===")
        print(f"Total Records: {total_records}")
        print(f"Dataset Timestamp: {dataset['time']} ({datetime.fromtimestamp(dataset['time'], timezone.utc).isoformat()})")
        
        print(f"\n=== Data Quality Issues ===")
        print(f"Missing ICAO24: {missing_icao24} ({missing_icao24/total_records*100:.1f}%)")
        print(f"Missing Coordinates: {missing_coordinates} ({missing_coordinates/total_records*100:.1f}%)")
        print(f"Missing Callsign: {missing_callsign} ({missing_callsign/total_records*100:.1f}%)")
        
        print(f"\n=== Flight Status ===")
        print(f"On Ground: {on_ground_count} ({on_ground_count/total_records*100:.1f}%)")
        print(f"Airborne: {total_records - on_ground_count} ({(total_records - on_ground_count)/total_records*100:.1f}%)")
        
        if altitudes:
            print(f"\n=== Altitude Statistics (meters) ===")
            print(f"Min: {min(altitudes):.0f}m ({min(altitudes)*3.28084:.0f}ft)")
            print(f"Max: {max(altitudes):.0f}m ({max(altitudes)*3.28084:.0f}ft)")
            print(f"Avg: {sum(altitudes)/len(altitudes):.0f}m ({sum(altitudes)/len(altitudes)*3.28084:.0f}ft)")
        
        if speeds:
            print(f"\n=== Speed Statistics (m/s) ===")
            print(f"Min: {min(speeds):.1f}m/s ({min(speeds)*1.94384:.0f}kts)")
            print(f"Max: {max(speeds):.1f}m/s ({max(speeds)*1.94384:.0f}kts)")
            print(f"Avg: {sum(speeds)/len(speeds):.1f}m/s ({sum(speeds)/len(speeds)*1.94384:.0f}kts)")


def main():
    parser = argparse.ArgumentParser(description='Generate realistic test flight data')
    parser.add_argument('--records', type=int, default=1000, 
                       help='Number of records to generate (default: 1000)')
    parser.add_argument('--output', type=str, default='data/sample/raw/', 
                       help='Output directory (default: data/sample/raw/)')
    parser.add_argument('--files', type=int, default=1,
                       help='Number of files to generate (default: 1)')
    parser.add_argument('--quality-issues', type=float, default=0.15,
                       help='Percentage of records with quality issues (default: 0.15)')
    parser.add_argument('--summary', action='store_true',
                       help='Print dataset summary after generation')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.records < 1:
        print("Error: Number of records must be at least 1")
        return
    
    if not 0 <= args.quality_issues <= 1:
        print("Error: Quality issues percentage must be between 0 and 1")
        return
    
    # Create generator
    generator = FlightDataGenerator()
    
    print(f"Flight Data Generator")
    print(f"===================")
    print(f"Records per file: {args.records}")
    print(f"Number of files: {args.files}")
    print(f"Quality issues: {args.quality_issues*100:.1f}%")
    print(f"Output directory: {args.output}")
    
    try:
        if args.files == 1:
            # Generate single file
            print(f"\nGenerating dataset...")
            dataset = generator.generate_dataset(args.records, args.quality_issues)
            
            filepath = generator.save_dataset(dataset, args.output)
            
            if args.summary:
                generator.print_dataset_summary(dataset)
            
            print(f"\nGeneration complete!")
            print(f"File created: {filepath}")
            
        else:
            # Generate multiple files
            print(f"\nGenerating {args.files} files...")
            files_created = generator.generate_multiple_files(
                args.files, args.records, args.output, args.quality_issues
            )
            
            print(f"\nGeneration complete!")
            print(f"Files created: {len(files_created)}")
            for filepath in files_created:
                print(f"  - {filepath}")
    
    except KeyboardInterrupt:
        print("\nGeneration interrupted by user")
    except Exception as e:
        print(f"Error during generation: {str(e)}")
        raise


if __name__ == "__main__":
    main()