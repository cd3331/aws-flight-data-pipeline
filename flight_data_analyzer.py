#!/usr/bin/env python3
"""
Flight Data Analyzer
Downloads flight data from S3, parses JSON, and provides comprehensive statistics.
"""

import json
import boto3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter, defaultdict
from datetime import datetime
import argparse
import sys
from typing import Dict, List, Any
import numpy as np

class FlightDataAnalyzer:
    def __init__(self, bucket_name: str, aws_region: str = 'us-east-1'):
        """
        Initialize the Flight Data Analyzer
        
        Args:
            bucket_name: S3 bucket name containing flight data
            aws_region: AWS region for S3 operations
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=aws_region)
        self.flight_data = []
        
    def list_available_files(self, prefix: str = '') -> List[str]:
        """List available flight data files in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents'] 
                        if obj['Key'].endswith('.json')]
            
            return sorted(files, reverse=True)  # Most recent first
            
        except Exception as e:
            print(f"Error listing S3 files: {e}")
            return []
    
    def download_flight_data(self, s3_key: str) -> bool:
        """
        Download and parse flight data from S3
        
        Args:
            s3_key: S3 object key for the flight data file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Downloading flight data from s3://{self.bucket_name}/{s3_key}")
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Extract flight states from the data
            if 'states' in data and isinstance(data['states'], list):
                self.flight_data = data['states']
                self.timestamp = data.get('time', None)
                print(f"Successfully loaded {len(self.flight_data)} flight records")
                return True
            else:
                print("Invalid data format: 'states' key not found or not a list")
                return False
                
        except Exception as e:
            print(f"Error downloading flight data: {e}")
            return False
    
    def parse_flight_data(self) -> pd.DataFrame:
        """
        Parse flight data into a pandas DataFrame for easier analysis
        
        Returns:
            pd.DataFrame: Parsed flight data
        """
        if not self.flight_data:
            print("No flight data available. Please download data first.")
            return pd.DataFrame()
        
        # Define column names based on the API structure
        columns = [
            'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
            'longitude', 'latitude', 'baro_altitude_m', 'baro_altitude_ft', 'on_ground',
            'velocity_ms', 'velocity_knots', 'true_track', 'vertical_rate', 'sensors',
            'geo_altitude_m', 'geo_altitude_ft', 'squawk', 'spi', 'position_source',
            'has_position', 'has_altitude', 'has_velocity'
        ]
        
        # Convert to DataFrame
        flights_df = pd.DataFrame(self.flight_data, columns=columns)
        
        # Clean and process data
        flights_df['callsign'] = flights_df['callsign'].astype(str).str.strip()
        flights_df['origin_country'] = flights_df['origin_country'].astype(str).str.strip()
        
        # Convert numeric columns
        numeric_cols = ['longitude', 'latitude', 'baro_altitude_m', 'baro_altitude_ft',
                       'velocity_ms', 'velocity_knots', 'true_track', 'vertical_rate',
                       'geo_altitude_m', 'geo_altitude_ft']
        
        for col in numeric_cols:
            flights_df[col] = pd.to_numeric(flights_df[col], errors='coerce')
        
        return flights_df
    
    def calculate_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate comprehensive flight statistics
        
        Args:
            df: DataFrame containing flight data
            
        Returns:
            Dict: Statistics summary
        """
        if df.empty:
            return {}
        
        stats = {}
        
        # Total flights
        stats['total_flights'] = len(df)
        stats['flights_on_ground'] = len(df[df['on_ground'] == True])
        stats['flights_airborne'] = len(df[df['on_ground'] == False])
        
        # Flights by country
        country_counts = df['origin_country'].value_counts()
        stats['flights_by_country'] = country_counts.to_dict()
        stats['top_10_countries'] = country_counts.head(10).to_dict()
        
        # Altitude distribution (for airborne flights)
        airborne_df = df[df['on_ground'] == False]
        if not airborne_df.empty:
            altitude_data = airborne_df['baro_altitude_ft'].dropna()
            if not altitude_data.empty:
                stats['altitude_stats'] = {
                    'mean_altitude_ft': altitude_data.mean(),
                    'median_altitude_ft': altitude_data.median(),
                    'min_altitude_ft': altitude_data.min(),
                    'max_altitude_ft': altitude_data.max(),
                    'std_altitude_ft': altitude_data.std()
                }
                
                # Altitude bands
                altitude_bands = {
                    'Low (0-10,000 ft)': len(altitude_data[altitude_data <= 10000]),
                    'Medium (10,001-30,000 ft)': len(altitude_data[(altitude_data > 10000) & (altitude_data <= 30000)]),
                    'High (30,001-50,000 ft)': len(altitude_data[(altitude_data > 30000) & (altitude_data <= 50000)]),
                    'Very High (>50,000 ft)': len(altitude_data[altitude_data > 50000])
                }
                stats['altitude_distribution'] = altitude_bands
        
        # Speed analysis (top 10 fastest aircraft)
        speed_data = df[df['velocity_knots'].notna() & (df['velocity_knots'] > 0)]
        if not speed_data.empty:
            top_speeds = speed_data.nlargest(10, 'velocity_knots')[
                ['callsign', 'icao24', 'origin_country', 'velocity_knots', 'baro_altitude_ft']
            ]
            stats['top_10_fastest_aircraft'] = top_speeds.to_dict('records')
            
            # Speed statistics
            stats['speed_stats'] = {
                'mean_speed_knots': speed_data['velocity_knots'].mean(),
                'median_speed_knots': speed_data['velocity_knots'].median(),
                'max_speed_knots': speed_data['velocity_knots'].max(),
                'min_speed_knots': speed_data['velocity_knots'].min()
            }
        
        # Geographic distribution
        position_data = df[(df['longitude'].notna()) & (df['latitude'].notna())]
        if not position_data.empty:
            stats['geographic_coverage'] = {
                'longitude_range': [position_data['longitude'].min(), position_data['longitude'].max()],
                'latitude_range': [position_data['latitude'].min(), position_data['latitude'].max()],
                'flights_with_position': len(position_data)
            }
        
        # Data timestamp
        if self.timestamp:
            stats['data_timestamp'] = datetime.fromtimestamp(self.timestamp).isoformat()
        
        return stats
    
    def create_visualizations(self, df: pd.DataFrame, output_dir: str = '.'):
        """
        Create visualizations for the flight data
        
        Args:
            df: DataFrame containing flight data
            output_dir: Directory to save plots
        """
        if df.empty:
            print("No data available for visualization")
            return
        
        plt.style.use('seaborn-v0_8')
        fig = plt.figure(figsize=(20, 15))
        
        # 1. Top 15 Countries by Flight Count
        plt.subplot(2, 3, 1)
        country_counts = df['origin_country'].value_counts().head(15)
        country_counts.plot(kind='bar')
        plt.title('Top 15 Countries by Flight Count')
        plt.xlabel('Country')
        plt.ylabel('Number of Flights')
        plt.xticks(rotation=45)
        
        # 2. Altitude Distribution
        plt.subplot(2, 3, 2)
        airborne_df = df[df['on_ground'] == False]
        altitude_data = airborne_df['baro_altitude_ft'].dropna()
        if not altitude_data.empty:
            plt.hist(altitude_data, bins=50, alpha=0.7, edgecolor='black')
            plt.title('Altitude Distribution (Airborne Aircraft)')
            plt.xlabel('Altitude (feet)')
            plt.ylabel('Number of Aircraft')
        
        # 3. Speed Distribution
        plt.subplot(2, 3, 3)
        speed_data = df['velocity_knots'].dropna()
        if not speed_data.empty:
            plt.hist(speed_data[speed_data > 0], bins=50, alpha=0.7, edgecolor='black')
            plt.title('Speed Distribution')
            plt.xlabel('Speed (knots)')
            plt.ylabel('Number of Aircraft')
        
        # 4. Ground vs Airborne
        plt.subplot(2, 3, 4)
        ground_status = df['on_ground'].value_counts()
        labels = ['Airborne', 'On Ground'] if False in ground_status.index else ['On Ground']
        colors = ['skyblue', 'lightcoral']
        plt.pie(ground_status.values, labels=labels, autopct='%1.1f%%', colors=colors[:len(labels)])
        plt.title('Aircraft Status Distribution')
        
        # 5. Speed vs Altitude Scatter
        plt.subplot(2, 3, 5)
        airborne_data = df[(df['on_ground'] == False) & 
                          (df['velocity_knots'].notna()) & 
                          (df['baro_altitude_ft'].notna())]
        if not airborne_data.empty:
            plt.scatter(airborne_data['velocity_knots'], airborne_data['baro_altitude_ft'], 
                       alpha=0.6, s=10)
            plt.title('Speed vs Altitude (Airborne Aircraft)')
            plt.xlabel('Speed (knots)')
            plt.ylabel('Altitude (feet)')
        
        # 6. Geographic Distribution
        plt.subplot(2, 3, 6)
        position_data = df[(df['longitude'].notna()) & (df['latitude'].notna())]
        if not position_data.empty:
            plt.scatter(position_data['longitude'], position_data['latitude'], 
                       alpha=0.6, s=1, c='red')
            plt.title('Geographic Distribution of Aircraft')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/flight_analysis_dashboard.png', dpi=300, bbox_inches='tight')
        print(f"Visualization saved as '{output_dir}/flight_analysis_dashboard.png'")
        plt.close()
    
    def print_summary(self, stats: Dict[str, Any]):
        """Print a comprehensive summary of flight statistics"""
        print("\n" + "="*80)
        print("FLIGHT DATA ANALYSIS SUMMARY")
        print("="*80)
        
        if stats.get('data_timestamp'):
            print(f"Data Timestamp: {stats['data_timestamp']}")
        
        print(f"\n📊 OVERALL STATISTICS")
        print(f"Total Flights: {stats.get('total_flights', 0):,}")
        print(f"Flights Airborne: {stats.get('flights_airborne', 0):,}")
        print(f"Flights on Ground: {stats.get('flights_on_ground', 0):,}")
        
        # Top countries
        if 'top_10_countries' in stats:
            print(f"\n🌍 TOP 10 COUNTRIES BY FLIGHT COUNT")
            for i, (country, count) in enumerate(stats['top_10_countries'].items(), 1):
                print(f"{i:2d}. {country:<20} {count:>6,} flights")
        
        # Altitude statistics
        if 'altitude_stats' in stats:
            alt_stats = stats['altitude_stats']
            print(f"\n✈️  ALTITUDE ANALYSIS (Airborne Aircraft)")
            print(f"Mean Altitude: {alt_stats['mean_altitude_ft']:,.0f} feet")
            print(f"Median Altitude: {alt_stats['median_altitude_ft']:,.0f} feet")
            print(f"Range: {alt_stats['min_altitude_ft']:,.0f} - {alt_stats['max_altitude_ft']:,.0f} feet")
            
            if 'altitude_distribution' in stats:
                print("\nAltitude Distribution:")
                for band, count in stats['altitude_distribution'].items():
                    print(f"  {band:<25} {count:>6,} aircraft")
        
        # Speed statistics
        if 'speed_stats' in stats:
            speed_stats = stats['speed_stats']
            print(f"\n🚀 SPEED ANALYSIS")
            print(f"Mean Speed: {speed_stats['mean_speed_knots']:,.1f} knots")
            print(f"Median Speed: {speed_stats['median_speed_knots']:,.1f} knots")
            print(f"Max Speed: {speed_stats['max_speed_knots']:,.1f} knots")
        
        # Top fastest aircraft
        if 'top_10_fastest_aircraft' in stats:
            print(f"\n🏆 TOP 10 FASTEST AIRCRAFT")
            print(f"{'Rank':<4} {'Callsign':<12} {'ICAO24':<8} {'Country':<15} {'Speed':<8} {'Altitude'}")
            print("-" * 70)
            for i, aircraft in enumerate(stats['top_10_fastest_aircraft'], 1):
                callsign = aircraft.get('callsign', 'N/A')[:11]
                icao = aircraft.get('icao24', 'N/A')[:7]
                country = aircraft.get('origin_country', 'N/A')[:14]
                speed = aircraft.get('velocity_knots', 0)
                altitude = aircraft.get('baro_altitude_ft', 0)
                altitude_str = f"{altitude:,.0f} ft" if altitude and not pd.isna(altitude) else "N/A"
                print(f"{i:<4} {callsign:<12} {icao:<8} {country:<15} {speed:<8.1f} {altitude_str}")
        
        # Geographic coverage
        if 'geographic_coverage' in stats:
            geo = stats['geographic_coverage']
            print(f"\n🌐 GEOGRAPHIC COVERAGE")
            print(f"Longitude Range: {geo['longitude_range'][0]:.2f}° to {geo['longitude_range'][1]:.2f}°")
            print(f"Latitude Range: {geo['latitude_range'][0]:.2f}° to {geo['latitude_range'][1]:.2f}°")
            print(f"Aircraft with Position Data: {geo['flights_with_position']:,}")
        
        print("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(description='Analyze flight data from S3')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--key', help='Specific S3 key to analyze')
    parser.add_argument('--prefix', default='', help='S3 prefix to search for files')
    parser.add_argument('--latest', action='store_true', help='Use the latest file')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--visualize', action='store_true', help='Create visualizations')
    parser.add_argument('--output-dir', default='.', help='Output directory for files')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = FlightDataAnalyzer(args.bucket, args.region)
    
    # Determine which file to analyze
    if args.key:
        s3_key = args.key
    elif args.latest:
        files = analyzer.list_available_files(args.prefix)
        if not files:
            print("No flight data files found!")
            sys.exit(1)
        s3_key = files[0]  # Most recent
        print(f"Using latest file: {s3_key}")
    else:
        files = analyzer.list_available_files(args.prefix)[:10]  # Show top 10
        if not files:
            print("No flight data files found!")
            sys.exit(1)
        
        print("Available files:")
        for i, file in enumerate(files, 1):
            print(f"{i:2d}. {file}")
        
        try:
            choice = int(input("\nSelect file number (or 0 for most recent): "))
            if choice == 0:
                s3_key = files[0]
            elif 1 <= choice <= len(files):
                s3_key = files[choice - 1]
            else:
                print("Invalid choice!")
                sys.exit(1)
        except (ValueError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(1)
    
    # Download and analyze data
    if not analyzer.download_flight_data(s3_key):
        sys.exit(1)
    
    # Parse data
    df = analyzer.parse_flight_data()
    if df.empty:
        print("Failed to parse flight data!")
        sys.exit(1)
    
    # Calculate statistics
    stats = analyzer.calculate_statistics(df)
    
    # Print summary
    analyzer.print_summary(stats)
    
    # Create visualizations if requested
    if args.visualize:
        print("\nCreating visualizations...")
        analyzer.create_visualizations(df, args.output_dir)
    
    # Save statistics to JSON
    stats_file = f"{args.output_dir}/flight_statistics.json"
    with open(stats_file, 'w') as f:
        # Convert numpy types to native Python types for JSON serialization
        def convert_numpy_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            return obj
        
        # Recursively convert numpy types in nested structures
        def clean_stats(stats_dict):
            if isinstance(stats_dict, dict):
                return {k: clean_stats(v) for k, v in stats_dict.items()}
            elif isinstance(stats_dict, list):
                return [clean_stats(item) for item in stats_dict]
            else:
                return convert_numpy_types(stats_dict)
        
        json.dump(clean_stats(stats), f, indent=2, default=str)
    
    print(f"\nStatistics saved to: {stats_file}")

if __name__ == "__main__":
    main()