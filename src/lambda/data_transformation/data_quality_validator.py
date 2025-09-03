import json
import logging
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import unquote_plus
import statistics
import boto3
import pandas as pd
import pyarrow.parquet as pq
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DataQualityValidator:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns')
        
        # Environment variables
        self.processed_bucket = os.environ.get('PROCESSED_DATA_BUCKET')
        self.alert_topic_arn = os.environ.get('ALERT_TOPIC_ARN')
        self.quality_threshold = float(os.environ.get('QUALITY_THRESHOLD', 0.8))
        
        if not self.processed_bucket:
            raise ValueError("Required environment variable PROCESSED_DATA_BUCKET must be set")
        
        # Quality check configuration
        self.quality_checks = [
            'completeness_check',
            'validity_check',
            'consistency_check',
            'uniqueness_check',
            'accuracy_check',
            'timeliness_check',
            'altitude_range_check',
            'speed_range_check',
            'coordinate_validity_check',
            'callsign_format_check',
            'country_code_check',
            'timestamp_consistency_check',
            'position_accuracy_check',
            'altitude_consistency_check',
            'speed_consistency_check',
            'anomaly_detection_check'
        ]
    
    def download_parquet_file(self, bucket: str, key: str) -> Optional[pd.DataFrame]:
        """
        Download and read Parquet file from S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            DataFrame or None if failed
        """
        try:
            logger.info(f"Downloading Parquet file: s3://{bucket}/{key}")
            
            obj = self.s3_client.get_object(Bucket=bucket, Key=key)
            df = pd.read_parquet(obj['Body'])
            
            logger.info(f"Successfully loaded DataFrame with {len(df)} rows and {len(df.columns)} columns")
            return df
            
        except ClientError as e:
            logger.error(f"Failed to download Parquet file: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to read Parquet file: {str(e)}")
            return None
    
    def completeness_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data completeness (missing values)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Completeness check results
        """
        try:
            critical_fields = [
                'icao24', 'longitude', 'latitude', 'baro_altitude_ft', 
                'velocity_knots', 'last_contact'
            ]
            
            total_records = len(df)
            completeness_scores = {}
            
            for field in critical_fields:
                if field in df.columns:
                    non_null_count = df[field].notna().sum()
                    completeness_scores[field] = non_null_count / total_records if total_records > 0 else 0
                else:
                    completeness_scores[field] = 0
            
            overall_completeness = sum(completeness_scores.values()) / len(completeness_scores)
            
            result = {
                'check_name': 'completeness_check',
                'passed': overall_completeness >= 0.8,
                'score': round(overall_completeness, 3),
                'details': {
                    'field_completeness': completeness_scores,
                    'total_records': total_records,
                    'threshold': 0.8
                }
            }
            
            logger.info(f"Completeness check: {overall_completeness:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Completeness check failed: {str(e)}")
            return self._failed_check_result('completeness_check', str(e))
    
    def validity_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data validity (correct formats and ranges)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Validity check results
        """
        try:
            validity_issues = 0
            total_records = len(df)
            
            # Check coordinate validity
            if 'longitude' in df.columns:
                invalid_lon = ((df['longitude'] < -180) | (df['longitude'] > 180)).sum()
                validity_issues += invalid_lon
            
            if 'latitude' in df.columns:
                invalid_lat = ((df['latitude'] < -90) | (df['latitude'] > 90)).sum()
                validity_issues += invalid_lat
            
            # Check altitude validity (reasonable range)
            if 'baro_altitude_ft' in df.columns:
                invalid_alt = ((df['baro_altitude_ft'] < -1000) | (df['baro_altitude_ft'] > 60000)).sum()
                validity_issues += invalid_alt
            
            # Check speed validity
            if 'velocity_knots' in df.columns:
                invalid_speed = ((df['velocity_knots'] < 0) | (df['velocity_knots'] > 1200)).sum()
                validity_issues += invalid_speed
            
            # Check ICAO24 format (should be 6 hex characters)
            if 'icao24' in df.columns:
                invalid_icao = 0
                for icao in df['icao24'].dropna():
                    if not isinstance(icao, str) or len(icao) != 6:
                        invalid_icao += 1
                validity_issues += invalid_icao
            
            validity_score = 1 - (validity_issues / (total_records * 5)) if total_records > 0 else 0  # 5 validity checks
            
            result = {
                'check_name': 'validity_check',
                'passed': validity_score >= 0.9,
                'score': round(max(0, validity_score), 3),
                'details': {
                    'total_issues': validity_issues,
                    'total_records': total_records,
                    'threshold': 0.9
                }
            }
            
            logger.info(f"Validity check: {validity_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Validity check failed: {str(e)}")
            return self._failed_check_result('validity_check', str(e))
    
    def consistency_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data consistency (logical relationships between fields)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Consistency check results
        """
        try:
            consistency_issues = 0
            total_records = len(df)
            
            # Check ground vs altitude consistency
            if 'on_ground' in df.columns and 'baro_altitude_ft' in df.columns:
                ground_with_altitude = ((df['on_ground'] == True) & (df['baro_altitude_ft'] > 1000)).sum()
                consistency_issues += ground_with_altitude
            
            # Check speed vs ground consistency
            if 'on_ground' in df.columns and 'velocity_knots' in df.columns:
                ground_with_high_speed = ((df['on_ground'] == True) & (df['velocity_knots'] > 100)).sum()
                consistency_issues += ground_with_high_speed
            
            # Check position vs country consistency (basic check)
            if all(col in df.columns for col in ['longitude', 'latitude', 'origin_country']):
                # This is a simplified check - in reality, you'd need a geo-database
                for idx, row in df.iterrows():
                    if pd.notna(row['longitude']) and pd.notna(row['latitude']) and pd.notna(row['origin_country']):
                        # Very basic consistency check for major regions
                        lon, lat, country = row['longitude'], row['latitude'], row['origin_country']
                        if country == 'United States' and not (-125 <= lon <= -66 and 20 <= lat <= 50):
                            if abs(lon) < 50 and abs(lat) < 50:  # Likely not in US airspace
                                consistency_issues += 1
            
            consistency_score = 1 - (consistency_issues / total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'consistency_check',
                'passed': consistency_score >= 0.85,
                'score': round(max(0, consistency_score), 3),
                'details': {
                    'consistency_issues': consistency_issues,
                    'total_records': total_records,
                    'threshold': 0.85
                }
            }
            
            logger.info(f"Consistency check: {consistency_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Consistency check failed: {str(e)}")
            return self._failed_check_result('consistency_check', str(e))
    
    def uniqueness_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data uniqueness (duplicate records)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Uniqueness check results
        """
        try:
            total_records = len(df)
            
            if 'icao24' in df.columns:
                unique_aircraft = df['icao24'].nunique()
                duplicate_icao_records = total_records - len(df.drop_duplicates(subset=['icao24'], keep='first'))
                uniqueness_score = 1 - (duplicate_icao_records / total_records) if total_records > 0 else 0
            else:
                duplicate_records = len(df) - len(df.drop_duplicates())
                uniqueness_score = 1 - (duplicate_records / total_records) if total_records > 0 else 0
                unique_aircraft = 0
            
            result = {
                'check_name': 'uniqueness_check',
                'passed': uniqueness_score >= 0.95,
                'score': round(uniqueness_score, 3),
                'details': {
                    'total_records': total_records,
                    'unique_aircraft': unique_aircraft,
                    'threshold': 0.95
                }
            }
            
            logger.info(f"Uniqueness check: {uniqueness_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Uniqueness check failed: {str(e)}")
            return self._failed_check_result('uniqueness_check', str(e))
    
    def accuracy_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data accuracy (presence of position and essential data)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Accuracy check results
        """
        try:
            total_records = len(df)
            
            # Count records with position data
            positioned_records = 0
            if all(col in df.columns for col in ['longitude', 'latitude']):
                positioned_records = ((df['longitude'].notna()) & (df['latitude'].notna())).sum()
            
            # Count records with altitude data
            altitude_records = 0
            if 'baro_altitude_ft' in df.columns:
                altitude_records = df['baro_altitude_ft'].notna().sum()
            
            # Count records with speed data
            speed_records = 0
            if 'velocity_knots' in df.columns:
                speed_records = df['velocity_knots'].notna().sum()
            
            accuracy_score = (positioned_records + altitude_records + speed_records) / (3 * total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'accuracy_check',
                'passed': accuracy_score >= 0.7,
                'score': round(accuracy_score, 3),
                'details': {
                    'positioned_records': positioned_records,
                    'altitude_records': altitude_records,
                    'speed_records': speed_records,
                    'total_records': total_records,
                    'threshold': 0.7
                }
            }
            
            logger.info(f"Accuracy check: {accuracy_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Accuracy check failed: {str(e)}")
            return self._failed_check_result('accuracy_check', str(e))
    
    def timeliness_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data timeliness (recent contact times)
        
        Args:
            df: Input DataFrame
            
        Returns:
            Timeliness check results
        """
        try:
            current_timestamp = int(datetime.now(timezone.utc).timestamp())
            total_records = len(df)
            
            if 'last_contact' in df.columns:
                # Consider data timely if last contact was within 5 minutes (300 seconds)
                timely_records = ((current_timestamp - df['last_contact']) <= 300).sum()
                timeliness_score = timely_records / total_records if total_records > 0 else 0
                
                # Average age of data
                avg_age = (current_timestamp - df['last_contact']).mean() if total_records > 0 else 0
            else:
                timeliness_score = 0
                avg_age = float('inf')
            
            result = {
                'check_name': 'timeliness_check',
                'passed': timeliness_score >= 0.8,
                'score': round(timeliness_score, 3),
                'details': {
                    'timely_records': timely_records if 'last_contact' in df.columns else 0,
                    'total_records': total_records,
                    'avg_age_seconds': round(avg_age, 1) if avg_age != float('inf') else None,
                    'threshold': 0.8
                }
            }
            
            logger.info(f"Timeliness check: {timeliness_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Timeliness check failed: {str(e)}")
            return self._failed_check_result('timeliness_check', str(e))
    
    def altitude_range_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check for reasonable altitude ranges and detect anomalies
        
        Args:
            df: Input DataFrame
            
        Returns:
            Altitude range check results
        """
        try:
            if 'baro_altitude_ft' not in df.columns:
                return self._failed_check_result('altitude_range_check', 'Missing altitude data')
            
            altitude_data = df['baro_altitude_ft'].dropna()
            total_records = len(altitude_data)
            
            if total_records == 0:
                return self._failed_check_result('altitude_range_check', 'No altitude data available')
            
            # Check for impossible altitudes
            impossible_low = (altitude_data < -1000).sum()  # Below sea level by more than 1000ft
            impossible_high = (altitude_data > 60000).sum()  # Above typical aircraft ceiling
            
            # Check for anomalous altitudes (statistical outliers)
            if total_records > 10:
                q1 = altitude_data.quantile(0.25)
                q3 = altitude_data.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr
                upper_bound = q3 + 3 * iqr
                
                outliers = ((altitude_data < lower_bound) | (altitude_data > upper_bound)).sum()
            else:
                outliers = 0
            
            anomaly_count = impossible_low + impossible_high + outliers
            altitude_score = 1 - (anomaly_count / total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'altitude_range_check',
                'passed': altitude_score >= 0.95,
                'score': round(max(0, altitude_score), 3),
                'details': {
                    'impossible_low': impossible_low,
                    'impossible_high': impossible_high,
                    'statistical_outliers': outliers,
                    'total_altitude_records': total_records,
                    'min_altitude': float(altitude_data.min()),
                    'max_altitude': float(altitude_data.max()),
                    'threshold': 0.95
                }
            }
            
            logger.info(f"Altitude range check: {altitude_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Altitude range check failed: {str(e)}")
            return self._failed_check_result('altitude_range_check', str(e))
    
    def speed_range_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check for reasonable speed ranges and detect anomalies
        
        Args:
            df: Input DataFrame
            
        Returns:
            Speed range check results
        """
        try:
            if 'velocity_knots' not in df.columns:
                return self._failed_check_result('speed_range_check', 'Missing speed data')
            
            speed_data = df['velocity_knots'].dropna()
            total_records = len(speed_data)
            
            if total_records == 0:
                return self._failed_check_result('speed_range_check', 'No speed data available')
            
            # Check for impossible speeds
            impossible_negative = (speed_data < 0).sum()
            impossible_high = (speed_data > 1200).sum()  # Above typical aircraft max speed
            
            # Check for anomalous speeds (statistical outliers)
            if total_records > 10:
                q1 = speed_data.quantile(0.25)
                q3 = speed_data.quantile(0.75)
                iqr = q3 - q1
                upper_bound = q3 + 3 * iqr
                
                outliers = (speed_data > upper_bound).sum()
            else:
                outliers = 0
            
            anomaly_count = impossible_negative + impossible_high + outliers
            speed_score = 1 - (anomaly_count / total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'speed_range_check',
                'passed': speed_score >= 0.95,
                'score': round(max(0, speed_score), 3),
                'details': {
                    'impossible_negative': impossible_negative,
                    'impossible_high': impossible_high,
                    'statistical_outliers': outliers,
                    'total_speed_records': total_records,
                    'min_speed': float(speed_data.min()),
                    'max_speed': float(speed_data.max()),
                    'threshold': 0.95
                }
            }
            
            logger.info(f"Speed range check: {speed_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Speed range check failed: {str(e)}")
            return self._failed_check_result('speed_range_check', str(e))
    
    def coordinate_validity_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Comprehensive coordinate validation
        
        Args:
            df: Input DataFrame
            
        Returns:
            Coordinate validity check results
        """
        try:
            if not all(col in df.columns for col in ['longitude', 'latitude']):
                return self._failed_check_result('coordinate_validity_check', 'Missing coordinate data')
            
            coord_data = df[['longitude', 'latitude']].dropna()
            total_records = len(coord_data)
            
            if total_records == 0:
                return self._failed_check_result('coordinate_validity_check', 'No coordinate data available')
            
            invalid_coords = 0
            
            for _, row in coord_data.iterrows():
                lon, lat = row['longitude'], row['latitude']
                
                # Basic range checks
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    invalid_coords += 1
                    continue
                
                # Check for null island (0,0) which is often invalid
                if abs(lon) < 0.1 and abs(lat) < 0.1:
                    invalid_coords += 1
                    continue
                
                # Check for other common invalid coordinates
                if lon == 0 or lat == 0 or lon == lat:  # Suspicious patterns
                    invalid_coords += 1
            
            coordinate_score = 1 - (invalid_coords / total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'coordinate_validity_check',
                'passed': coordinate_score >= 0.98,
                'score': round(coordinate_score, 3),
                'details': {
                    'invalid_coordinates': invalid_coords,
                    'total_coordinate_records': total_records,
                    'threshold': 0.98
                }
            }
            
            logger.info(f"Coordinate validity check: {coordinate_score:.3f} (passed: {result['passed']})")
            return result
            
        except Exception as e:
            logger.error(f"Coordinate validity check failed: {str(e)}")
            return self._failed_check_result('coordinate_validity_check', str(e))
    
    def callsign_format_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check callsign format validity
        """
        try:
            if 'callsign' not in df.columns:
                return self._failed_check_result('callsign_format_check', 'Missing callsign data')
            
            callsign_data = df['callsign'].dropna()
            total_records = len(callsign_data)
            
            if total_records == 0:
                return {'check_name': 'callsign_format_check', 'passed': True, 'score': 1.0, 'details': {'total_records': 0}}
            
            invalid_callsigns = 0
            for callsign in callsign_data:
                if not isinstance(callsign, str) or len(callsign.strip()) == 0 or len(callsign.strip()) > 8:
                    invalid_callsigns += 1
            
            callsign_score = 1 - (invalid_callsigns / total_records)
            
            result = {
                'check_name': 'callsign_format_check',
                'passed': callsign_score >= 0.9,
                'score': round(callsign_score, 3),
                'details': {
                    'invalid_callsigns': invalid_callsigns,
                    'total_callsign_records': total_records,
                    'threshold': 0.9
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('callsign_format_check', str(e))
    
    def country_code_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check country code validity
        """
        try:
            if 'origin_country' not in df.columns:
                return self._failed_check_result('country_code_check', 'Missing country data')
            
            country_data = df['origin_country'].dropna()
            total_records = len(country_data)
            
            if total_records == 0:
                return {'check_name': 'country_code_check', 'passed': True, 'score': 1.0, 'details': {'total_records': 0}}
            
            # Basic validation - non-empty strings
            valid_countries = sum(1 for country in country_data if isinstance(country, str) and len(country.strip()) > 0)
            country_score = valid_countries / total_records
            
            result = {
                'check_name': 'country_code_check',
                'passed': country_score >= 0.95,
                'score': round(country_score, 3),
                'details': {
                    'valid_countries': valid_countries,
                    'total_country_records': total_records,
                    'threshold': 0.95
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('country_code_check', str(e))
    
    def timestamp_consistency_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check timestamp consistency
        """
        try:
            timestamp_cols = ['last_contact', 'time_position']
            available_cols = [col for col in timestamp_cols if col in df.columns]
            
            if not available_cols:
                return self._failed_check_result('timestamp_consistency_check', 'Missing timestamp data')
            
            current_time = int(datetime.now(timezone.utc).timestamp())
            consistent_records = 0
            total_records = 0
            
            for col in available_cols:
                col_data = df[col].dropna()
                total_records += len(col_data)
                
                # Check if timestamps are reasonable (not in future, not too old)
                reasonable_timestamps = ((col_data <= current_time) & (col_data >= current_time - 86400)).sum()  # Within last 24 hours
                consistent_records += reasonable_timestamps
            
            consistency_score = consistent_records / total_records if total_records > 0 else 0
            
            result = {
                'check_name': 'timestamp_consistency_check',
                'passed': consistency_score >= 0.9,
                'score': round(consistency_score, 3),
                'details': {
                    'consistent_timestamps': consistent_records,
                    'total_timestamp_records': total_records,
                    'threshold': 0.9
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('timestamp_consistency_check', str(e))
    
    def position_accuracy_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check position accuracy and precision
        """
        try:
            if not all(col in df.columns for col in ['longitude', 'latitude']):
                return self._failed_check_result('position_accuracy_check', 'Missing position data')
            
            position_data = df[['longitude', 'latitude']].dropna()
            total_records = len(position_data)
            
            if total_records == 0:
                return self._failed_check_result('position_accuracy_check', 'No position data available')
            
            # Check for precision (too many decimal places might indicate fake data)
            high_precision_records = 0
            for _, row in position_data.iterrows():
                lon_str = str(row['longitude'])
                lat_str = str(row['latitude'])
                
                lon_decimals = len(lon_str.split('.')[-1]) if '.' in lon_str else 0
                lat_decimals = len(lat_str.split('.')[-1]) if '.' in lat_str else 0
                
                if lon_decimals <= 6 and lat_decimals <= 6:  # Reasonable precision
                    high_precision_records += 1
            
            accuracy_score = high_precision_records / total_records
            
            result = {
                'check_name': 'position_accuracy_check',
                'passed': accuracy_score >= 0.95,
                'score': round(accuracy_score, 3),
                'details': {
                    'reasonable_precision_records': high_precision_records,
                    'total_position_records': total_records,
                    'threshold': 0.95
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('position_accuracy_check', str(e))
    
    def altitude_consistency_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check altitude consistency between barometric and geometric altitude
        """
        try:
            if not all(col in df.columns for col in ['baro_altitude_ft', 'geo_altitude_ft']):
                return {'check_name': 'altitude_consistency_check', 'passed': True, 'score': 1.0, 'details': {'message': 'Insufficient altitude data'}}
            
            both_altitudes = df[['baro_altitude_ft', 'geo_altitude_ft']].dropna()
            total_records = len(both_altitudes)
            
            if total_records == 0:
                return {'check_name': 'altitude_consistency_check', 'passed': True, 'score': 1.0, 'details': {'total_records': 0}}
            
            consistent_records = 0
            for _, row in both_altitudes.iterrows():
                baro_alt = row['baro_altitude_ft']
                geo_alt = row['geo_altitude_ft']
                
                # Allow reasonable difference (up to 1000 feet)
                if abs(baro_alt - geo_alt) <= 1000:
                    consistent_records += 1
            
            consistency_score = consistent_records / total_records
            
            result = {
                'check_name': 'altitude_consistency_check',
                'passed': consistency_score >= 0.8,
                'score': round(consistency_score, 3),
                'details': {
                    'consistent_altitude_records': consistent_records,
                    'total_dual_altitude_records': total_records,
                    'threshold': 0.8
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('altitude_consistency_check', str(e))
    
    def speed_consistency_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check speed consistency with flight phase
        """
        try:
            if not all(col in df.columns for col in ['velocity_knots', 'on_ground']):
                return self._failed_check_result('speed_consistency_check', 'Missing speed or ground status data')
            
            speed_ground_data = df[['velocity_knots', 'on_ground']].dropna()
            total_records = len(speed_ground_data)
            
            if total_records == 0:
                return self._failed_check_result('speed_consistency_check', 'No speed/ground data available')
            
            consistent_records = 0
            for _, row in speed_ground_data.iterrows():
                speed = row['velocity_knots']
                on_ground = row['on_ground']
                
                # Ground aircraft should have lower speeds
                if on_ground and speed <= 60:  # Reasonable taxi speed
                    consistent_records += 1
                elif not on_ground and speed >= 80:  # Reasonable airborne speed
                    consistent_records += 1
                elif not on_ground and speed < 80 and speed >= 40:  # Approach/departure
                    consistent_records += 1
            
            consistency_score = consistent_records / total_records
            
            result = {
                'check_name': 'speed_consistency_check',
                'passed': consistency_score >= 0.8,
                'score': round(consistency_score, 3),
                'details': {
                    'consistent_speed_records': consistent_records,
                    'total_speed_ground_records': total_records,
                    'threshold': 0.8
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('speed_consistency_check', str(e))
    
    def anomaly_detection_check(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Advanced anomaly detection using statistical methods
        """
        try:
            anomalies = 0
            total_records = len(df)
            
            if total_records < 10:
                return {'check_name': 'anomaly_detection_check', 'passed': True, 'score': 1.0, 'details': {'message': 'Insufficient data for anomaly detection'}}
            
            # Detect anomalies in altitude
            if 'baro_altitude_ft' in df.columns:
                altitude_data = df['baro_altitude_ft'].dropna()
                if len(altitude_data) > 0:
                    alt_mean = altitude_data.mean()
                    alt_std = altitude_data.std()
                    altitude_anomalies = ((altitude_data - alt_mean).abs() > 3 * alt_std).sum()
                    anomalies += altitude_anomalies
            
            # Detect anomalies in speed
            if 'velocity_knots' in df.columns:
                speed_data = df['velocity_knots'].dropna()
                if len(speed_data) > 0:
                    speed_mean = speed_data.mean()
                    speed_std = speed_data.std()
                    speed_anomalies = ((speed_data - speed_mean).abs() > 3 * speed_std).sum()
                    anomalies += speed_anomalies
            
            anomaly_score = 1 - (anomalies / total_records) if total_records > 0 else 0
            
            result = {
                'check_name': 'anomaly_detection_check',
                'passed': anomaly_score >= 0.95,
                'score': round(max(0, anomaly_score), 3),
                'details': {
                    'detected_anomalies': anomalies,
                    'total_records': total_records,
                    'threshold': 0.95
                }
            }
            
            return result
            
        except Exception as e:
            return self._failed_check_result('anomaly_detection_check', str(e))
    
    def _failed_check_result(self, check_name: str, error_message: str) -> Dict[str, Any]:
        """
        Generate a failed check result
        
        Args:
            check_name: Name of the failed check
            error_message: Error message
            
        Returns:
            Failed check result dictionary
        """
        return {
            'check_name': check_name,
            'passed': False,
            'score': 0.0,
            'error': error_message
        }
    
    def run_all_quality_checks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Run all quality checks on the DataFrame
        
        Args:
            df: Input DataFrame
            
        Returns:
            Complete quality assessment results
        """
        logger.info(f"Running {len(self.quality_checks)} quality checks on {len(df)} records")
        
        results = []
        
        for check_name in self.quality_checks:
            try:
                check_method = getattr(self, check_name)
                result = check_method(df)
                results.append(result)
                
            except AttributeError:
                logger.error(f"Quality check method not found: {check_name}")
                results.append(self._failed_check_result(check_name, f"Method not implemented: {check_name}"))
            except Exception as e:
                logger.error(f"Quality check failed: {check_name} - {str(e)}")
                results.append(self._failed_check_result(check_name, str(e)))
        
        # Calculate overall quality score
        passed_checks = sum(1 for result in results if result['passed'])
        total_checks = len(results)
        overall_score = sum(result['score'] for result in results) / total_checks if total_checks > 0 else 0
        
        quality_assessment = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_records': len(df),
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': total_checks - passed_checks,
            'overall_score': round(overall_score, 3),
            'quality_grade': self._get_quality_grade(overall_score),
            'passed_threshold': overall_score >= self.quality_threshold,
            'individual_results': results
        }
        
        logger.info(f"Quality assessment complete: {overall_score:.3f} ({quality_assessment['quality_grade']})")
        return quality_assessment
    
    def _get_quality_grade(self, score: float) -> str:
        """
        Convert quality score to letter grade
        
        Args:
            score: Quality score (0-1)
            
        Returns:
            Letter grade (A-F)
        """
        if score >= 0.95:
            return 'A'
        elif score >= 0.9:
            return 'B'
        elif score >= 0.8:
            return 'C'
        elif score >= 0.7:
            return 'D'
        else:
            return 'F'
    
    def publish_quality_metrics(self, assessment: Dict[str, Any], execution_time: float) -> None:
        """
        Publish quality metrics to CloudWatch
        
        Args:
            assessment: Quality assessment results
            execution_time: Execution time in seconds
        """
        try:
            metrics = [
                {
                    'MetricName': 'ValidationTime',
                    'Value': execution_time,
                    'Unit': 'Seconds',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'data_quality_validator'}
                    ]
                },
                {
                    'MetricName': 'OverallQualityScore',
                    'Value': assessment['overall_score'] * 100,
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'data_quality_validator'}
                    ]
                },
                {
                    'MetricName': 'PassedChecks',
                    'Value': assessment['passed_checks'],
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'data_quality_validator'}
                    ]
                },
                {
                    'MetricName': 'FailedChecks',
                    'Value': assessment['failed_checks'],
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'data_quality_validator'}
                    ]
                },
                {
                    'MetricName': 'RecordsValidated',
                    'Value': assessment['total_records'],
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': 'data_quality_validator'}
                    ]
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace='FlightDataPipeline/Quality',
                MetricData=metrics
            )
            
            logger.info("Quality metrics published to CloudWatch")
            
        except ClientError as e:
            logger.error(f"Failed to publish quality metrics: {str(e)}")
    
    def send_alert(self, assessment: Dict[str, Any], file_key: str) -> None:
        """
        Send SNS alert for quality issues
        
        Args:
            assessment: Quality assessment results
            file_key: S3 file key that failed validation
        """
        try:
            if not self.alert_topic_arn:
                logger.warning("No alert topic ARN configured, skipping alert")
                return
            
            message = {
                'alert_type': 'DATA_QUALITY_ISSUE',
                'timestamp': assessment['timestamp'],
                'file': file_key,
                'overall_score': assessment['overall_score'],
                'quality_grade': assessment['quality_grade'],
                'failed_checks': assessment['failed_checks'],
                'total_records': assessment['total_records'],
                'threshold': self.quality_threshold,
                'failed_check_details': [
                    result for result in assessment['individual_results'] 
                    if not result['passed']
                ]
            }
            
            self.sns.publish(
                TopicArn=self.alert_topic_arn,
                Subject=f"Flight Data Quality Alert - Score: {assessment['overall_score']:.3f}",
                Message=json.dumps(message, indent=2)
            )
            
            logger.info(f"Quality alert sent for file: {file_key}")
            
        except ClientError as e:
            logger.error(f"Failed to send SNS alert: {str(e)}")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for data quality validation triggered by S3 events
    
    Args:
        event: S3 event data
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    start_time = time.time()
    execution_id = str(uuid.uuid4())
    
    logger.info(f"Starting data quality validation - Execution ID: {execution_id}")
    
    try:
        validator = DataQualityValidator()
        
        validated_files = []
        
        # Process each S3 record in the event
        for record in event.get('Records', []):
            try:
                # Extract S3 information
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Validating file: s3://{bucket}/{key}")
                
                # Download and read Parquet file
                df = validator.download_parquet_file(bucket, key)
                if df is None:
                    logger.error(f"Failed to load DataFrame from: s3://{bucket}/{key}")
                    continue
                
                # Run quality checks
                quality_assessment = validator.run_all_quality_checks(df)
                
                # Add file information to assessment
                quality_assessment['source_file'] = f"s3://{bucket}/{key}"
                quality_assessment['execution_id'] = execution_id
                
                # Send alert if quality is below threshold
                if not quality_assessment['passed_threshold']:
                    validator.send_alert(quality_assessment, key)
                
                validated_files.append({
                    'file': f"s3://{bucket}/{key}",
                    'overall_score': quality_assessment['overall_score'],
                    'quality_grade': quality_assessment['quality_grade'],
                    'passed_threshold': quality_assessment['passed_threshold'],
                    'total_records': quality_assessment['total_records'],
                    'passed_checks': quality_assessment['passed_checks'],
                    'failed_checks': quality_assessment['failed_checks']
                })
                
            except Exception as file_error:
                logger.error(f"Error validating file {key}: {str(file_error)}")
                continue
        
        total_execution_time = time.time() - start_time
        
        # Publish overall metrics
        if validated_files:
            avg_quality_score = sum(f['overall_score'] for f in validated_files) / len(validated_files)
            overall_assessment = {
                'overall_score': avg_quality_score,
                'passed_checks': sum(f['passed_checks'] for f in validated_files),
                'failed_checks': sum(f['failed_checks'] for f in validated_files),
                'total_records': sum(f['total_records'] for f in validated_files)
            }
            validator.publish_quality_metrics(overall_assessment, total_execution_time)
        
        logger.info(f"Data quality validation completed in {total_execution_time:.2f} seconds")
        logger.info(f"Validated {len(validated_files)} files")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'SUCCESS',
                'validated_files': validated_files,
                'execution_time': total_execution_time,
                'total_files_validated': len(validated_files)
            })
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Data quality validation failed: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'ERROR',
                'error_message': error_msg,
                'execution_time': execution_time
            })
        }