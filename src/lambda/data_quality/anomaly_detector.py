"""
Advanced Anomaly Detection System for Flight Data.

This module provides sophisticated anomaly detection capabilities including:
- Statistical anomaly detection using IQR and Z-scores
- Geospatial boundary violations
- Impossible flight characteristics
- Stuck aircraft detection
- Temporal pattern anomalies

Author: Flight Data Pipeline Team
Version: 1.0
"""

import math
import numpy as np
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

from quality_validator import SeverityLevel

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    ALTITUDE_ANOMALY = "altitude_anomaly"
    VELOCITY_ANOMALY = "velocity_anomaly"
    POSITION_JUMP = "position_jump" 
    GEOGRAPHIC_BOUNDARY = "geographic_boundary"
    STUCK_AIRCRAFT = "stuck_aircraft"
    TEMPORAL_ANOMALY = "temporal_anomaly"
    IMPOSSIBLE_FLIGHT = "impossible_flight"
    DATA_CORRUPTION = "data_corruption"


@dataclass
class GeographicBoundary:
    """Defines geographic boundaries for anomaly detection."""
    name: str
    min_latitude: float
    max_latitude: float
    min_longitude: float  
    max_longitude: float
    description: str = ""
    
    def contains_point(self, latitude: float, longitude: float) -> bool:
        """Check if a point is within this boundary."""
        return (self.min_latitude <= latitude <= self.max_latitude and
                self.min_longitude <= longitude <= self.max_longitude)


@dataclass 
class AnomalyConfig:
    """Configuration for anomaly detection."""
    
    # Statistical thresholds
    z_score_threshold: float = 3.0         # Standard deviations for outlier detection
    iqr_multiplier: float = 1.5           # IQR multiplier for outlier detection
    percentile_threshold: float = 0.99    # Percentile threshold for extreme values
    
    # Physical impossibility thresholds
    max_altitude_feet: float = 60000.0    # Commercial aviation ceiling
    min_altitude_feet: float = -1000.0    # Death Valley level
    max_velocity_knots: float = 800.0     # Military aircraft maximum
    min_velocity_knots: float = 0.0       # Stationary
    max_vertical_rate_fpm: float = 8000.0 # Emergency descent rate
    
    # Position jump detection
    max_distance_per_second: float = 0.5  # miles per second (impossible speed)
    teleportation_threshold: float = 500.0 # miles (obvious teleportation)
    
    # Stuck aircraft detection
    stuck_position_radius: float = 0.05   # miles (essentially same position)
    stuck_time_threshold: float = 1800.0  # seconds (30 minutes)
    stuck_velocity_threshold: float = 5.0 # knots (essentially not moving)
    
    # Geographic boundaries (restricted/dangerous areas)
    forbidden_zones: List[GeographicBoundary] = None
    ocean_only_zones: List[GeographicBoundary] = None
    
    # Temporal anomaly detection
    max_time_gap_seconds: float = 3600.0   # 1 hour between updates
    future_data_threshold: float = 300.0   # 5 minutes in future is suspicious
    
    # Historical data requirements for statistical detection
    min_samples_for_stats: int = 100       # Minimum samples for statistical analysis
    historical_window_hours: int = 24      # Hours of historical data to consider
    
    def __post_init__(self):
        """Initialize default geographic boundaries."""
        if self.forbidden_zones is None:
            self.forbidden_zones = [
                # Example restricted zones (these would be configured per deployment)
                GeographicBoundary(
                    name="Area51_Restricted",
                    min_latitude=37.0, max_latitude=37.3,
                    min_longitude=-116.0, max_longitude=-115.7,
                    description="Restricted military area"
                ),
                # Antarctic flights (extremely rare for commercial aircraft)
                GeographicBoundary(
                    name="Antarctica",
                    min_latitude=-90.0, max_latitude=-60.0,
                    min_longitude=-180.0, max_longitude=180.0,
                    description="Antarctic region - unusual for commercial flights"
                )
            ]
        
        if self.ocean_only_zones is None:
            # Define major ocean areas where aircraft should only be in transit
            self.ocean_only_zones = [
                GeographicBoundary(
                    name="Pacific_Ocean_Central",
                    min_latitude=-30.0, max_latitude=50.0,
                    min_longitude=-180.0, max_longitude=-120.0,
                    description="Central Pacific Ocean"
                ),
                GeographicBoundary(
                    name="Atlantic_Ocean_Central", 
                    min_latitude=20.0, max_latitude=60.0,
                    min_longitude=-50.0, max_longitude=-20.0,
                    description="Central Atlantic Ocean"
                )
            ]


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_type: AnomalyType
    severity: SeverityLevel
    description: str
    field: str
    value: Any
    expected_range: Optional[Tuple[Any, Any]] = None
    confidence: float = 1.0  # 0-1 confidence in anomaly detection
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AnomalyDetector:
    """Advanced anomaly detection system for flight data."""
    
    def __init__(self, config: AnomalyConfig = None):
        """Initialize the anomaly detector."""
        self.config = config or AnomalyConfig()
        
        # Historical data storage (in production, this would be external)
        self.historical_data = {
            'altitudes': [],
            'velocities': [],
            'positions': {},  # keyed by icao24
            'timestamps': []
        }
        
        # Aircraft tracking for stuck detection
        self.aircraft_positions = {}  # icao24 -> list of (lat, lon, timestamp)
        
        logger.info("AnomalyDetector initialized")
    
    def detect_anomalies(self, record: Dict[str, Any], 
                        historical_records: List[Dict[str, Any]] = None) -> List[Anomaly]:
        """
        Detect anomalies in a flight data record.
        
        Args:
            record: Current flight data record
            historical_records: Historical records for statistical analysis
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        try:
            # Update historical data
            if historical_records:
                self._update_historical_data(historical_records)
            
            # 1. Physical impossibility detection
            anomalies.extend(self._detect_physical_impossibilities(record))
            
            # 2. Statistical anomaly detection
            anomalies.extend(self._detect_statistical_anomalies(record))
            
            # 3. Geographic boundary violations
            anomalies.extend(self._detect_geographic_anomalies(record))
            
            # 4. Position jump detection
            anomalies.extend(self._detect_position_jumps(record))
            
            # 5. Stuck aircraft detection
            anomalies.extend(self._detect_stuck_aircraft(record))
            
            # 6. Temporal anomalies
            anomalies.extend(self._detect_temporal_anomalies(record))
            
            # 7. Data corruption detection
            anomalies.extend(self._detect_data_corruption(record))
            
            # Update aircraft position tracking
            self._update_aircraft_tracking(record)
            
            logger.debug(f"Detected {len(anomalies)} anomalies in record")
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            # Return a data corruption anomaly if we can't process the record
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                severity=SeverityLevel.HIGH,
                description=f"Failed to process record for anomaly detection: {str(e)}",
                field="record",
                value=str(record)[:200]
            ))
        
        return anomalies
    
    def _detect_physical_impossibilities(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect physically impossible values."""
        anomalies = []
        
        # Impossible altitudes
        if 'baro_altitude' in record and record['baro_altitude'] is not None:
            altitude = record['baro_altitude']
            if altitude > self.config.max_altitude_feet:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.ALTITUDE_ANOMALY,
                    severity=SeverityLevel.CRITICAL,
                    description=f"Altitude {altitude} feet exceeds maximum possible",
                    field="baro_altitude",
                    value=altitude,
                    expected_range=(self.config.min_altitude_feet, self.config.max_altitude_feet),
                    confidence=1.0
                ))
            elif altitude < self.config.min_altitude_feet:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.ALTITUDE_ANOMALY,
                    severity=SeverityLevel.HIGH,
                    description=f"Altitude {altitude} feet below minimum possible",
                    field="baro_altitude", 
                    value=altitude,
                    expected_range=(self.config.min_altitude_feet, self.config.max_altitude_feet),
                    confidence=0.9  # Slightly lower confidence as some areas are below sea level
                ))
        
        # Impossible velocities
        if 'velocity' in record and record['velocity'] is not None:
            velocity = record['velocity']
            if velocity > self.config.max_velocity_knots:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.VELOCITY_ANOMALY,
                    severity=SeverityLevel.CRITICAL,
                    description=f"Velocity {velocity} knots exceeds maximum possible for aircraft",
                    field="velocity",
                    value=velocity,
                    expected_range=(self.config.min_velocity_knots, self.config.max_velocity_knots),
                    confidence=1.0
                ))
            elif velocity < self.config.min_velocity_knots:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.VELOCITY_ANOMALY,
                    severity=SeverityLevel.MEDIUM,
                    description=f"Negative velocity {velocity} knots is impossible",
                    field="velocity",
                    value=velocity,
                    expected_range=(self.config.min_velocity_knots, self.config.max_velocity_knots),
                    confidence=1.0
                ))
        
        # Impossible vertical rates
        if 'vertical_rate' in record and record['vertical_rate'] is not None:
            vertical_rate = abs(record['vertical_rate'])
            if vertical_rate > self.config.max_vertical_rate_fpm:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.IMPOSSIBLE_FLIGHT,
                    severity=SeverityLevel.HIGH,
                    description=f"Vertical rate {record['vertical_rate']} fpm exceeds aircraft capability",
                    field="vertical_rate",
                    value=record['vertical_rate'],
                    expected_range=(-self.config.max_vertical_rate_fpm, self.config.max_vertical_rate_fpm),
                    confidence=0.9
                ))
        
        return anomalies
    
    def _detect_statistical_anomalies(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect statistical anomalies based on historical data."""
        anomalies = []
        
        # Only perform statistical analysis if we have sufficient historical data
        if len(self.historical_data['altitudes']) < self.config.min_samples_for_stats:
            return anomalies
        
        # Altitude statistical anomaly
        if 'baro_altitude' in record and record['baro_altitude'] is not None:
            altitude = record['baro_altitude']
            anomaly = self._detect_statistical_outlier(
                altitude, 
                self.historical_data['altitudes'],
                "baro_altitude",
                "Altitude"
            )
            if anomaly:
                anomaly.anomaly_type = AnomalyType.ALTITUDE_ANOMALY
                anomalies.append(anomaly)
        
        # Velocity statistical anomaly
        if 'velocity' in record and record['velocity'] is not None:
            velocity = record['velocity']
            anomaly = self._detect_statistical_outlier(
                velocity,
                self.historical_data['velocities'],
                "velocity", 
                "Velocity"
            )
            if anomaly:
                anomaly.anomaly_type = AnomalyType.VELOCITY_ANOMALY
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_statistical_outlier(self, value: float, historical_values: List[float],
                                   field_name: str, description_prefix: str) -> Optional[Anomaly]:
        """Detect if a value is a statistical outlier."""
        if len(historical_values) < self.config.min_samples_for_stats:
            return None
        
        # Calculate Z-score
        mean_val = statistics.mean(historical_values)
        std_val = statistics.stdev(historical_values)
        
        if std_val > 0:
            z_score = abs(value - mean_val) / std_val
            if z_score > self.config.z_score_threshold:
                severity = SeverityLevel.HIGH if z_score > 4 else SeverityLevel.MEDIUM
                return Anomaly(
                    anomaly_type=AnomalyType.DATA_CORRUPTION,  # Will be overridden by caller
                    severity=severity,
                    description=f"{description_prefix} {value} is {z_score:.2f} standard deviations from mean ({mean_val:.2f})",
                    field=field_name,
                    value=value,
                    confidence=min(1.0, z_score / 5.0),  # Higher z-score = higher confidence
                    metadata={'z_score': z_score, 'mean': mean_val, 'std': std_val}
                )
        
        # Calculate IQR-based outlier detection
        sorted_values = sorted(historical_values)
        q1 = np.percentile(sorted_values, 25)
        q3 = np.percentile(sorted_values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - self.config.iqr_multiplier * iqr
        upper_bound = q3 + self.config.iqr_multiplier * iqr
        
        if value < lower_bound or value > upper_bound:
            return Anomaly(
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                severity=SeverityLevel.MEDIUM,
                description=f"{description_prefix} {value} is outside IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}]",
                field=field_name,
                value=value,
                confidence=0.7,
                metadata={'q1': q1, 'q3': q3, 'iqr': iqr}
            )
        
        return None
    
    def _detect_geographic_anomalies(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect geographic boundary violations."""
        anomalies = []
        
        if not ('latitude' in record and 'longitude' in record and
                record['latitude'] is not None and record['longitude'] is not None):
            return anomalies
        
        latitude = record['latitude']
        longitude = record['longitude']
        
        # Check forbidden zones
        for zone in self.config.forbidden_zones:
            if zone.contains_point(latitude, longitude):
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.GEOGRAPHIC_BOUNDARY,
                    severity=SeverityLevel.HIGH,
                    description=f"Aircraft in forbidden zone: {zone.name} - {zone.description}",
                    field="position",
                    value=(latitude, longitude),
                    confidence=0.9,
                    metadata={'zone_name': zone.name}
                ))
        
        # Check for aircraft stuck in ocean-only zones without appropriate flight phase
        on_ground = record.get('on_ground', False)
        if not on_ground:  # Only check airborne aircraft
            for zone in self.config.ocean_only_zones:
                if zone.contains_point(latitude, longitude):
                    # This is suspicious but not critical - might be oceanic flight
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.GEOGRAPHIC_BOUNDARY,
                        severity=SeverityLevel.LOW,
                        description=f"Aircraft in oceanic zone: {zone.name} - verify flight path",
                        field="position",
                        value=(latitude, longitude),
                        confidence=0.5,
                        metadata={'zone_name': zone.name, 'zone_type': 'oceanic'}
                    ))
        
        return anomalies
    
    def _detect_position_jumps(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect impossible position jumps."""
        anomalies = []
        
        icao24 = record.get('icao24')
        if not icao24 or not self._has_position(record):
            return anomalies
        
        current_lat = record['latitude']
        current_lon = record['longitude']
        current_time = record.get('last_contact') or record.get('time_position')
        
        if icao24 in self.aircraft_positions and self.aircraft_positions[icao24]:
            # Get the most recent position
            last_position = self.aircraft_positions[icao24][-1]
            last_lat, last_lon, last_time = last_position
            
            if current_time and last_time:
                time_diff = abs(current_time - last_time)
                
                if time_diff > 0:  # Avoid division by zero
                    distance = self._calculate_distance(last_lat, last_lon, current_lat, current_lon)
                    speed_miles_per_second = distance / time_diff
                    
                    # Check for teleportation (impossible speed)
                    if speed_miles_per_second > self.config.max_distance_per_second:
                        severity = (SeverityLevel.CRITICAL if distance > self.config.teleportation_threshold 
                                  else SeverityLevel.HIGH)
                        
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.POSITION_JUMP,
                            severity=severity,
                            description=f"Aircraft {icao24} teleported {distance:.1f} miles in {time_diff:.1f} seconds",
                            field="position",
                            value=(current_lat, current_lon),
                            confidence=1.0 if distance > 1000 else 0.8,
                            metadata={
                                'distance_miles': distance,
                                'time_diff_seconds': time_diff,
                                'speed_miles_per_second': speed_miles_per_second,
                                'previous_position': (last_lat, last_lon)
                            }
                        ))
        
        return anomalies
    
    def _detect_stuck_aircraft(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect aircraft that appear to be stuck in the same position."""
        anomalies = []
        
        icao24 = record.get('icao24')
        if not icao24 or not self._has_position(record) or record.get('on_ground', False):
            return anomalies
        
        current_lat = record['latitude']
        current_lon = record['longitude']
        current_time = record.get('last_contact') or record.get('time_position')
        current_velocity = record.get('velocity', 0)
        
        if icao24 in self.aircraft_positions and len(self.aircraft_positions[icao24]) >= 3:
            # Check if aircraft has been in essentially the same position
            positions = self.aircraft_positions[icao24][-3:]  # Last 3 positions
            
            # Calculate if all positions are within stuck radius
            all_stuck = True
            min_time = float('inf')
            max_time = 0
            
            for lat, lon, timestamp in positions:
                distance = self._calculate_distance(current_lat, current_lon, lat, lon)
                if distance > self.config.stuck_position_radius:
                    all_stuck = False
                    break
                
                if timestamp:
                    min_time = min(min_time, timestamp)
                    max_time = max(max_time, timestamp)
            
            if all_stuck and current_time:
                stuck_duration = max_time - min_time
                
                # Aircraft is stuck if it's been in same position for too long
                # and not moving (low velocity)
                if (stuck_duration > self.config.stuck_time_threshold and
                    current_velocity < self.config.stuck_velocity_threshold):
                    
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.STUCK_AIRCRAFT,
                        severity=SeverityLevel.MEDIUM,
                        description=f"Aircraft {icao24} stuck at position for {stuck_duration/60:.1f} minutes",
                        field="position",
                        value=(current_lat, current_lon),
                        confidence=0.8,
                        metadata={
                            'stuck_duration_seconds': stuck_duration,
                            'velocity': current_velocity,
                            'position_count': len(positions) + 1
                        }
                    ))
        
        return anomalies
    
    def _detect_temporal_anomalies(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect temporal anomalies in timestamps."""
        anomalies = []
        
        current_time = datetime.utcnow().timestamp()
        
        # Check for future timestamps
        for time_field in ['last_contact', 'time_position']:
            if time_field in record and record[time_field] is not None:
                record_time = record[time_field]
                
                if record_time > current_time + self.config.future_data_threshold:
                    future_minutes = (record_time - current_time) / 60
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                        severity=SeverityLevel.HIGH,
                        description=f"Timestamp {time_field} is {future_minutes:.1f} minutes in the future",
                        field=time_field,
                        value=record_time,
                        confidence=1.0,
                        metadata={'future_offset_minutes': future_minutes}
                    ))
        
        # Check for very old timestamps (beyond reasonable data retention)
        old_threshold = current_time - (7 * 24 * 3600)  # 7 days old
        for time_field in ['last_contact', 'time_position']:
            if time_field in record and record[time_field] is not None:
                record_time = record[time_field]
                
                if record_time < old_threshold:
                    age_days = (current_time - record_time) / (24 * 3600)
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                        severity=SeverityLevel.MEDIUM,
                        description=f"Timestamp {time_field} is {age_days:.1f} days old",
                        field=time_field,
                        value=record_time,
                        confidence=0.7,
                        metadata={'age_days': age_days}
                    ))
        
        return anomalies
    
    def _detect_data_corruption(self, record: Dict[str, Any]) -> List[Anomaly]:
        """Detect signs of data corruption."""
        anomalies = []
        
        # Check for NaN, infinity, or extremely large values
        numeric_fields = ['baro_altitude', 'velocity', 'vertical_rate', 'latitude', 'longitude']
        
        for field in numeric_fields:
            if field in record and record[field] is not None:
                value = record[field]
                
                try:
                    # Check for NaN
                    if math.isnan(value):
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.DATA_CORRUPTION,
                            severity=SeverityLevel.HIGH,
                            description=f"Field {field} contains NaN value",
                            field=field,
                            value=value,
                            confidence=1.0
                        ))
                    
                    # Check for infinity
                    elif math.isinf(value):
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.DATA_CORRUPTION,
                            severity=SeverityLevel.HIGH,
                            description=f"Field {field} contains infinite value",
                            field=field,
                            value=value,
                            confidence=1.0
                        ))
                    
                    # Check for extremely large values that suggest corruption
                    elif abs(value) > 1e10:
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.DATA_CORRUPTION,
                            severity=SeverityLevel.MEDIUM,
                            description=f"Field {field} has suspiciously large value: {value}",
                            field=field,
                            value=value,
                            confidence=0.8
                        ))
                        
                except (TypeError, ValueError):
                    # Value is not numeric when it should be
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        severity=SeverityLevel.HIGH,
                        description=f"Field {field} contains non-numeric value: {value}",
                        field=field,
                        value=value,
                        confidence=1.0
                    ))
        
        return anomalies
    
    def _has_position(self, record: Dict[str, Any]) -> bool:
        """Check if record has valid position data."""
        return (record.get('latitude') is not None and 
                record.get('longitude') is not None)
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in miles using Haversine formula."""
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 3959  # Radius of Earth in miles
        
        return c * r
    
    def _update_historical_data(self, historical_records: List[Dict[str, Any]]) -> None:
        """Update historical data for statistical analysis."""
        for record in historical_records[-self.config.min_samples_for_stats:]:
            if 'baro_altitude' in record and record['baro_altitude'] is not None:
                self.historical_data['altitudes'].append(record['baro_altitude'])
            
            if 'velocity' in record and record['velocity'] is not None:
                self.historical_data['velocities'].append(record['velocity'])
        
        # Keep only recent data
        max_samples = self.config.min_samples_for_stats * 2
        self.historical_data['altitudes'] = self.historical_data['altitudes'][-max_samples:]
        self.historical_data['velocities'] = self.historical_data['velocities'][-max_samples:]
    
    def _update_aircraft_tracking(self, record: Dict[str, Any]) -> None:
        """Update aircraft position tracking for stuck detection."""
        icao24 = record.get('icao24')
        if not icao24 or not self._has_position(record):
            return
        
        current_lat = record['latitude']
        current_lon = record['longitude']
        current_time = record.get('last_contact') or record.get('time_position') or datetime.utcnow().timestamp()
        
        if icao24 not in self.aircraft_positions:
            self.aircraft_positions[icao24] = []
        
        # Add current position
        self.aircraft_positions[icao24].append((current_lat, current_lon, current_time))
        
        # Keep only recent positions (last hour)
        cutoff_time = current_time - 3600  # 1 hour ago
        self.aircraft_positions[icao24] = [
            pos for pos in self.aircraft_positions[icao24] 
            if pos[2] > cutoff_time
        ]
        
        # Limit number of positions per aircraft to prevent memory issues
        if len(self.aircraft_positions[icao24]) > 100:
            self.aircraft_positions[icao24] = self.aircraft_positions[icao24][-50:]