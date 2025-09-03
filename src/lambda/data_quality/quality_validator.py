"""
Comprehensive Data Quality Validation System for Flight Data Pipeline.

This module provides a complete data quality validation framework with:
- Multi-dimensional quality scoring (completeness, validity, consistency, timeliness)
- Weighted scoring algorithm (0-1 scale)
- Anomaly detection for flight data
- CloudWatch metrics publishing
- Automated data quarantine
- Configurable thresholds and alerting

Author: Flight Data Pipeline Team
Version: 1.0
"""

import json
import math
import statistics
import boto3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class QualityDimension(Enum):
    """Quality dimensions for assessment."""
    COMPLETENESS = "completeness"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"


class SeverityLevel(Enum):
    """Severity levels for quality issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class QualityConfig:
    """Configuration for quality validation thresholds and weights."""
    
    # Dimension weights (must sum to 1.0)
    completeness_weight: float = 0.30
    validity_weight: float = 0.30
    consistency_weight: float = 0.25
    timeliness_weight: float = 0.15
    
    # Completeness thresholds
    critical_fields_required: List[str] = None
    important_fields_optional: List[str] = None
    missing_critical_penalty: float = 0.8  # Severe penalty for missing critical fields
    missing_important_penalty: float = 0.2  # Moderate penalty for missing important fields
    
    # Validity thresholds
    altitude_min: float = -1000.0  # feet (Death Valley level)
    altitude_max: float = 60000.0  # feet (commercial aviation ceiling)
    velocity_min: float = 0.0      # knots
    velocity_max: float = 800.0    # knots (military aircraft)
    latitude_min: float = -90.0    # degrees
    latitude_max: float = 90.0     # degrees
    longitude_min: float = -180.0  # degrees
    longitude_max: float = 180.0   # degrees
    vertical_rate_max: float = 8000.0  # feet per minute (emergency descent)
    
    # Consistency thresholds
    speed_altitude_ratio_max: float = 2.0      # knots per 1000 feet
    position_jump_threshold: float = 500.0     # miles (teleportation detection)
    time_between_updates_max: float = 3600.0   # seconds (1 hour)
    stuck_position_threshold: float = 0.1      # miles (essentially not moving)
    stuck_time_threshold: float = 1800.0       # seconds (30 minutes)
    
    # Timeliness thresholds
    data_freshness_threshold: float = 300.0    # seconds (5 minutes)
    optimal_freshness: float = 60.0            # seconds (1 minute)
    stale_data_threshold: float = 1800.0       # seconds (30 minutes)
    
    # Overall quality thresholds
    excellent_quality_threshold: float = 0.95
    good_quality_threshold: float = 0.85
    acceptable_quality_threshold: float = 0.70
    poor_quality_threshold: float = 0.50
    
    # Quarantine thresholds
    quarantine_threshold: float = 0.30         # Below this score, quarantine the data
    critical_issue_quarantine: bool = True     # Quarantine on any critical issue
    
    def __post_init__(self):
        """Initialize default field lists and validate configuration."""
        if self.critical_fields_required is None:
            self.critical_fields_required = [
                'icao24', 'latitude', 'longitude', 'time_position', 'last_contact'
            ]
        
        if self.important_fields_optional is None:
            self.important_fields_optional = [
                'baro_altitude', 'velocity', 'callsign', 'origin_country'
            ]
        
        # Validate weights sum to 1.0
        total_weight = (self.completeness_weight + self.validity_weight + 
                       self.consistency_weight + self.timeliness_weight)
        if not math.isclose(total_weight, 1.0, abs_tol=0.01):
            raise ValueError(f"Quality dimension weights must sum to 1.0, got {total_weight}")


@dataclass
class QualityIssue:
    """Represents a data quality issue."""
    dimension: QualityDimension
    severity: SeverityLevel
    field: str
    issue_type: str
    description: str
    value: Any = None
    expected_range: Tuple[Any, Any] = None


@dataclass
class QualityScore:
    """Comprehensive quality score with dimensional breakdown."""
    overall_score: float
    completeness_score: float
    validity_score: float
    consistency_score: float
    timeliness_score: float
    
    total_fields_checked: int
    issues_found: List[QualityIssue]
    
    grade: str
    recommendations: List[str]
    should_quarantine: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quality score to dictionary for serialization."""
        return {
            'overall_score': round(self.overall_score, 4),
            'completeness_score': round(self.completeness_score, 4),
            'validity_score': round(self.validity_score, 4),
            'consistency_score': round(self.consistency_score, 4),
            'timeliness_score': round(self.timeliness_score, 4),
            'total_fields_checked': self.total_fields_checked,
            'issues_count': len(self.issues_found),
            'grade': self.grade,
            'should_quarantine': self.should_quarantine,
            'issues': [
                {
                    'dimension': issue.dimension.value,
                    'severity': issue.severity.value,
                    'field': issue.field,
                    'issue_type': issue.issue_type,
                    'description': issue.description,
                    'value': issue.value
                }
                for issue in self.issues_found
            ],
            'recommendations': self.recommendations
        }


class DataQualityValidator:
    """Comprehensive data quality validator for flight data."""
    
    def __init__(self, config: QualityConfig = None, environment: str = 'dev'):
        """Initialize the quality validator."""
        self.config = config or QualityConfig()
        self.environment = environment
        
        # AWS clients
        self.cloudwatch = boto3.client('cloudwatch')
        self.s3 = boto3.client('s3')
        
        # Historical data for consistency checks (in-memory cache)
        self.aircraft_history = {}
        self.validation_metrics = {
            'total_records_processed': 0,
            'total_quarantined': 0,
            'quality_score_sum': 0.0,
            'issues_by_type': {},
            'issues_by_severity': {}
        }
        
        logger.info(f"DataQualityValidator initialized for environment: {environment}")
    
    def validate_record(self, record: Dict[str, Any], 
                       previous_record: Optional[Dict[str, Any]] = None) -> QualityScore:
        """
        Validate a single flight data record across all quality dimensions.
        
        Args:
            record: Current flight data record
            previous_record: Previous record for same aircraft (for consistency checks)
            
        Returns:
            QualityScore: Comprehensive quality assessment
        """
        # Handle None input
        if record is None:
            return QualityScore(
                overall_score=0.0,
                completeness_score=0.0,
                validity_score=0.0,
                consistency_score=0.0,
                timeliness_score=0.0,
                total_fields_checked=0,
                issues_found=[QualityIssue(
                    dimension=QualityDimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                    field="record",
                    issue_type="null_record",
                    description="Record is null or missing",
                    value=None
                )],
                grade='F',
                recommendations=['Provide a valid data record'],
                should_quarantine=True
            )
            
        issues = []
        
        # 1. Completeness Assessment
        completeness_score, completeness_issues = self._assess_completeness(record)
        issues.extend(completeness_issues)
        
        # 2. Validity Assessment
        validity_score, validity_issues = self._assess_validity(record)
        issues.extend(validity_issues)
        
        # 3. Consistency Assessment
        consistency_score, consistency_issues = self._assess_consistency(record, previous_record)
        issues.extend(consistency_issues)
        
        # 4. Timeliness Assessment
        timeliness_score, timeliness_issues = self._assess_timeliness(record)
        issues.extend(timeliness_issues)
        
        # 5. Calculate weighted overall score
        overall_score = (
            completeness_score * self.config.completeness_weight +
            validity_score * self.config.validity_weight +
            consistency_score * self.config.consistency_weight +
            timeliness_score * self.config.timeliness_weight
        )
        
        # 6. Determine quality grade
        grade = self._calculate_quality_grade(overall_score)
        
        # 7. Generate recommendations
        recommendations = self._generate_recommendations(issues)
        
        # 8. Determine if quarantine is needed
        should_quarantine = self._should_quarantine(overall_score, issues)
        
        # 9. Create quality score object
        quality_score = QualityScore(
            overall_score=overall_score,
            completeness_score=completeness_score,
            validity_score=validity_score,
            consistency_score=consistency_score,
            timeliness_score=timeliness_score,
            total_fields_checked=len(record),
            issues_found=issues,
            grade=grade,
            recommendations=recommendations,
            should_quarantine=should_quarantine
        )
        
        # 10. Update metrics
        self._update_validation_metrics(quality_score)
        
        return quality_score
    
    def _assess_completeness(self, record: Dict[str, Any]) -> Tuple[float, List[QualityIssue]]:
        """Assess data completeness."""
        issues = []
        score = 1.0
        
        # Check critical fields
        missing_critical = 0
        for field in self.config.critical_fields_required:
            if not self._is_field_present(record, field):
                issues.append(QualityIssue(
                    dimension=QualityDimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                    field=field,
                    issue_type="missing_critical_field",
                    description=f"Critical field '{field}' is missing or null"
                ))
                missing_critical += 1
        
        # Check important fields
        missing_important = 0
        for field in self.config.important_fields_optional:
            if not self._is_field_present(record, field):
                issues.append(QualityIssue(
                    dimension=QualityDimension.COMPLETENESS,
                    severity=SeverityLevel.MEDIUM,
                    field=field,
                    issue_type="missing_important_field",
                    description=f"Important field '{field}' is missing or null"
                ))
                missing_important += 1
        
        # Calculate completeness score
        critical_penalty = missing_critical * self.config.missing_critical_penalty
        important_penalty = missing_important * self.config.missing_important_penalty
        
        # Apply penalties
        score = max(0.0, score - critical_penalty - important_penalty)
        
        # Additional completeness checks
        total_fields = len(self.config.critical_fields_required) + len(self.config.important_fields_optional)
        if total_fields > 0:
            completeness_ratio = (
                (len(self.config.critical_fields_required) - missing_critical) +
                (len(self.config.important_fields_optional) - missing_important)
            ) / total_fields
            score = min(score, completeness_ratio)
        
        logger.debug(f"Completeness assessment: score={score:.3f}, issues={len(issues)}")
        return score, issues
    
    def _assess_validity(self, record: Dict[str, Any]) -> Tuple[float, List[QualityIssue]]:
        """Assess data validity against business rules."""
        issues = []
        score = 1.0
        checks_performed = 0
        failed_checks = 0
        
        # Altitude validation
        if 'baro_altitude' in record and record['baro_altitude'] is not None:
            checks_performed += 1
            altitude = record['baro_altitude']
            
            try:
                altitude_val = float(altitude)
                if altitude_val < self.config.altitude_min or altitude_val > self.config.altitude_max:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.HIGH,
                        field="baro_altitude",
                        issue_type="invalid_altitude",
                        description=f"Altitude {altitude_val} feet is outside valid range",
                        value=altitude_val,
                        expected_range=(self.config.altitude_min, self.config.altitude_max)
                    ))
                    failed_checks += 1
            except (ValueError, TypeError):
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.HIGH,
                    field="baro_altitude",
                    issue_type="invalid_altitude_type",
                    description=f"Altitude '{record['baro_altitude']}' is not a valid numeric value",
                    value=record['baro_altitude']
                ))
                failed_checks += 1
        
        # Velocity validation
        if 'velocity' in record and record['velocity'] is not None:
            checks_performed += 1
            velocity = record['velocity']
            
            try:
                velocity_val = float(velocity)
                if velocity_val < self.config.velocity_min or velocity_val > self.config.velocity_max:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.HIGH,
                        field="velocity",
                        issue_type="invalid_velocity",
                        description=f"Velocity {velocity_val} knots is outside valid range",
                        value=velocity_val,
                        expected_range=(self.config.velocity_min, self.config.velocity_max)
                    ))
                    failed_checks += 1
            except (ValueError, TypeError):
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.HIGH,
                    field="velocity",
                    issue_type="invalid_velocity_type",
                    description=f"Velocity '{record['velocity']}' is not a valid numeric value",
                    value=record['velocity']
                ))
                failed_checks += 1
        
        # Geographic coordinates validation
        if 'latitude' in record and record['latitude'] is not None:
            checks_performed += 1
            latitude = record['latitude']
            
            # Check if latitude is numeric
            try:
                latitude = float(latitude)
                if latitude < self.config.latitude_min or latitude > self.config.latitude_max:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.CRITICAL,
                        field="latitude",
                        issue_type="invalid_latitude",
                        description=f"Latitude {latitude}° is outside valid range",
                        value=latitude,
                        expected_range=(self.config.latitude_min, self.config.latitude_max)
                    ))
                    failed_checks += 1
            except (ValueError, TypeError):
                # Handle non-numeric values
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.CRITICAL,
                    field="latitude",
                    issue_type="invalid_latitude_type",
                    description=f"Latitude '{record['latitude']}' is not a valid numeric value",
                    value=record['latitude']
                ))
                failed_checks += 1
        
        if 'longitude' in record and record['longitude'] is not None:
            checks_performed += 1
            longitude = record['longitude']
            
            # Check if longitude is numeric
            try:
                longitude_val = float(longitude)
                # Check for infinity or NaN
                if not math.isfinite(longitude_val):
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.CRITICAL,
                        field="longitude",
                        issue_type="invalid_longitude_type",
                        description=f"Longitude '{record['longitude']}' is not a finite numeric value",
                        value=record['longitude']
                    ))
                    failed_checks += 1
                elif longitude_val < self.config.longitude_min or longitude_val > self.config.longitude_max:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.CRITICAL,
                        field="longitude",
                        issue_type="invalid_longitude",
                        description=f"Longitude {longitude_val}° is outside valid range",
                        value=longitude_val,
                        expected_range=(self.config.longitude_min, self.config.longitude_max)
                    ))
                    failed_checks += 1
            except (ValueError, TypeError):
                # Handle non-numeric values
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.CRITICAL,
                    field="longitude",
                    issue_type="invalid_longitude_type",
                    description=f"Longitude '{record['longitude']}' is not a valid numeric value",
                    value=record['longitude']
                ))
                failed_checks += 1
        
        # Vertical rate validation
        if 'vertical_rate' in record and record['vertical_rate'] is not None:
            checks_performed += 1
            vertical_rate = abs(record['vertical_rate'])
            if vertical_rate > self.config.vertical_rate_max:
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.MEDIUM,
                    field="vertical_rate",
                    issue_type="excessive_vertical_rate",
                    description=f"Vertical rate {record['vertical_rate']} fpm exceeds maximum",
                    value=record['vertical_rate'],
                    expected_range=(-self.config.vertical_rate_max, self.config.vertical_rate_max)
                ))
                failed_checks += 1
        
        # ICAO24 format validation
        if 'icao24' in record:
            checks_performed += 1
            icao24_value = record['icao24']
            
            # Check for None or empty values
            if icao24_value is None or (isinstance(icao24_value, str) and not icao24_value.strip()):
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    severity=SeverityLevel.HIGH,
                    field="icao24",
                    issue_type="invalid_icao24_format",
                    description=f"ICAO24 '{icao24_value}' has invalid format",
                    value=icao24_value
                ))
                failed_checks += 1
            else:
                # Validate format for non-None values
                icao24 = str(icao24_value).strip().lower()
                if len(icao24) != 6 or not all(c in '0123456789abcdef' for c in icao24):
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        severity=SeverityLevel.HIGH,
                        field="icao24",
                        issue_type="invalid_icao24_format",
                        description=f"ICAO24 '{record['icao24']}' has invalid format",
                        value=record['icao24']
                    ))
                    failed_checks += 1
        
        # Calculate validity score
        if checks_performed > 0:
            score = 1.0 - (failed_checks / checks_performed)
        
        logger.debug(f"Validity assessment: score={score:.3f}, checks={checks_performed}, failed={failed_checks}")
        return score, issues
    
    def _assess_consistency(self, record: Dict[str, Any], 
                          previous_record: Optional[Dict[str, Any]] = None) -> Tuple[float, List[QualityIssue]]:
        """Assess data consistency and logical relationships."""
        issues = []
        score = 1.0
        checks_performed = 0
        failed_checks = 0
        
        # Speed-altitude relationship check
        try:
            if (record.get('velocity') is not None and 
                record.get('baro_altitude') is not None):
                
                altitude_val = float(record['baro_altitude'])
                velocity_val = float(record['velocity'])
                
                if altitude_val > 1000:  # Only for airborne aircraft
                    checks_performed += 1
                    speed_altitude_ratio = velocity_val / (altitude_val / 1000)
                    if speed_altitude_ratio > self.config.speed_altitude_ratio_max:
                        issues.append(QualityIssue(
                            dimension=QualityDimension.CONSISTENCY,
                            severity=SeverityLevel.MEDIUM,
                            field="velocity_altitude_ratio",
                            issue_type="inconsistent_speed_altitude",
                            description=f"Speed-altitude ratio {speed_altitude_ratio:.2f} is unusually high",
                            value=speed_altitude_ratio
                        ))
                        failed_checks += 1
        except (ValueError, TypeError, ZeroDivisionError):
            # Skip consistency check if values are not numeric or cause division errors
            pass
        
        # Temporal consistency (if previous record available)
        if previous_record:
            icao24 = record.get('icao24')
            if icao24:
                # Position jump detection
                if (self._has_coordinates(record) and self._has_coordinates(previous_record)):
                    checks_performed += 1
                    distance = self._calculate_distance(
                        previous_record['latitude'], previous_record['longitude'],
                        record['latitude'], record['longitude']
                    )
                    
                    time_diff = self._get_time_difference(previous_record, record)
                    if time_diff > 0:
                        # Calculate maximum possible distance based on time and reasonable speed
                        max_reasonable_distance = (self.config.velocity_max * 1.15078) * (time_diff / 3600)  # Convert knots to mph
                        
                        if distance > max_reasonable_distance and distance > self.config.position_jump_threshold:
                            issues.append(QualityIssue(
                                dimension=QualityDimension.CONSISTENCY,
                                severity=SeverityLevel.HIGH,
                                field="position",
                                issue_type="position_teleportation",
                                description=f"Aircraft moved {distance:.1f} miles in {time_diff:.1f} seconds (impossible)",
                                value=distance
                            ))
                            failed_checks += 1
                
                # Stuck aircraft detection
                if self._detect_stuck_aircraft(record, previous_record, icao24):
                    checks_performed += 1
                    issues.append(QualityIssue(
                        dimension=QualityDimension.CONSISTENCY,
                        severity=SeverityLevel.MEDIUM,
                        field="position",
                        issue_type="stuck_aircraft",
                        description=f"Aircraft {icao24} appears to be stuck in same position",
                        value=icao24
                    ))
                    failed_checks += 1
        
        # On-ground consistency
        if record.get('on_ground') is not None:
            checks_performed += 1
            on_ground = record['on_ground']
            altitude = record.get('baro_altitude', 0)
            velocity = record.get('velocity', 0)
            
            # Aircraft on ground should have low altitude and reasonable speed
            if on_ground and altitude > 1000:
                issues.append(QualityIssue(
                    dimension=QualityDimension.CONSISTENCY,
                    severity=SeverityLevel.HIGH,
                    field="on_ground",
                    issue_type="inconsistent_ground_status",
                    description=f"Aircraft marked as on-ground but at {altitude} feet altitude",
                    value=altitude
                ))
                failed_checks += 1
            
            # Aircraft in air should not be on ground
            elif not on_ground and altitude < 100 and velocity < 50:
                issues.append(QualityIssue(
                    dimension=QualityDimension.CONSISTENCY,
                    severity=SeverityLevel.MEDIUM,
                    field="on_ground",
                    issue_type="inconsistent_airborne_status",
                    description=f"Aircraft marked as airborne but low altitude ({altitude}ft) and speed ({velocity}kts)",
                    value={'altitude': altitude, 'velocity': velocity}
                ))
                failed_checks += 1
        
        # Calculate consistency score
        if checks_performed > 0:
            score = 1.0 - (failed_checks / checks_performed)
        
        logger.debug(f"Consistency assessment: score={score:.3f}, checks={checks_performed}, failed={failed_checks}")
        return score, issues
    
    def _assess_timeliness(self, record: Dict[str, Any]) -> Tuple[float, List[QualityIssue]]:
        """Assess data timeliness and freshness."""
        issues = []
        score = 1.0
        
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Check last_contact freshness
        if 'last_contact' in record and record['last_contact'] is not None:
            last_contact = record['last_contact']
            
            try:
                last_contact_val = float(last_contact)
                freshness = current_time - last_contact_val
                
                if freshness > self.config.stale_data_threshold:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.TIMELINESS,
                        severity=SeverityLevel.HIGH,
                        field="last_contact",
                        issue_type="stale_data",
                        description=f"Data is {freshness/60:.1f} minutes old",
                        value=freshness
                    ))
                    score = 0.2  # Very poor score for stale data
                    
                elif freshness > self.config.data_freshness_threshold:
                    issues.append(QualityIssue(
                        dimension=QualityDimension.TIMELINESS,
                        severity=SeverityLevel.MEDIUM,
                        field="last_contact",
                        issue_type="aged_data",
                        description=f"Data is {freshness/60:.1f} minutes old",
                        value=freshness
                    ))
                    # Linear degradation from perfect to poor
                    score = max(0.5, 1.0 - (freshness - self.config.optimal_freshness) / 
                               (self.config.data_freshness_threshold - self.config.optimal_freshness))
                
                elif freshness <= self.config.optimal_freshness:
                    score = 1.0  # Perfect freshness
                else:
                    # Linear degradation within acceptable range
                    score = 1.0 - (freshness - self.config.optimal_freshness) / \
                           (self.config.data_freshness_threshold - self.config.optimal_freshness) * 0.2
            except (ValueError, TypeError):
                # Handle non-numeric timestamp values
                issues.append(QualityIssue(
                    dimension=QualityDimension.TIMELINESS,
                    severity=SeverityLevel.HIGH,
                    field="last_contact",
                    issue_type="invalid_timestamp",
                    description=f"Invalid timestamp value: '{record['last_contact']}'",
                    value=record['last_contact']
                ))
                score = 0.0
        
        # Check time_position freshness
        if 'time_position' in record and record['time_position'] is not None:
            time_position = record['time_position']
            position_freshness = current_time - time_position
            
            if position_freshness > self.config.stale_data_threshold:
                issues.append(QualityIssue(
                    dimension=QualityDimension.TIMELINESS,
                    severity=SeverityLevel.MEDIUM,
                    field="time_position",
                    issue_type="stale_position_data",
                    description=f"Position data is {position_freshness/60:.1f} minutes old",
                    value=position_freshness
                ))
                score = min(score, 0.5)  # Cap score for stale position
        
        logger.debug(f"Timeliness assessment: score={score:.3f}, issues={len(issues)}")
        return score, issues
    
    def _is_field_present(self, record: Dict[str, Any], field: str) -> bool:
        """Check if a field is present and not null/empty."""
        if field not in record:
            return False
        
        value = record[field]
        if value is None:
            return False
        
        # Check for empty strings
        if isinstance(value, str) and value.strip() == '':
            return False
        
        return True
    
    def _has_coordinates(self, record: Dict[str, Any]) -> bool:
        """Check if record has valid coordinates."""
        return (self._is_field_present(record, 'latitude') and 
                self._is_field_present(record, 'longitude'))
    
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
    
    def _get_time_difference(self, record1: Dict[str, Any], record2: Dict[str, Any]) -> float:
        """Get time difference between two records in seconds."""
        time1 = record1.get('last_contact') or record1.get('time_position', 0)
        time2 = record2.get('last_contact') or record2.get('time_position', 0)
        return abs(time2 - time1)
    
    def _detect_stuck_aircraft(self, current_record: Dict[str, Any], 
                             previous_record: Dict[str, Any], icao24: str) -> bool:
        """Detect if aircraft appears to be stuck in same position."""
        if not (self._has_coordinates(current_record) and self._has_coordinates(previous_record)):
            return False
        
        distance = self._calculate_distance(
            previous_record['latitude'], previous_record['longitude'],
            current_record['latitude'], current_record['longitude']
        )
        
        time_diff = self._get_time_difference(previous_record, current_record)
        
        # Aircraft is considered stuck if it hasn't moved significantly over a long period
        return (distance < self.config.stuck_position_threshold and 
                time_diff > self.config.stuck_time_threshold and
                not current_record.get('on_ground', False))  # Exclude aircraft on ground
    
    def _calculate_quality_grade(self, score: float) -> str:
        """Calculate quality grade based on score."""
        if score >= self.config.excellent_quality_threshold:
            return "A"
        elif score >= self.config.good_quality_threshold:
            return "B"
        elif score >= self.config.acceptable_quality_threshold:
            return "C"
        elif score >= self.config.poor_quality_threshold:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(self, issues: List[QualityIssue]) -> List[str]:
        """Generate recommendations based on identified issues."""
        recommendations = []
        issue_types = set(issue.issue_type for issue in issues)
        
        if "missing_critical_field" in issue_types:
            recommendations.append("Verify data source completeness and API response integrity")
        
        if "invalid_altitude" in issue_types or "invalid_velocity" in issue_types:
            recommendations.append("Review sensor calibration and data transformation logic")
        
        if "position_teleportation" in issue_types:
            recommendations.append("Investigate data source timing and aircraft identification accuracy")
        
        if "stuck_aircraft" in issue_types:
            recommendations.append("Check for duplicate or cached data in processing pipeline")
        
        if "stale_data" in issue_types:
            recommendations.append("Review data ingestion frequency and source availability")
        
        if "inconsistent_ground_status" in issue_types:
            recommendations.append("Validate ground detection logic and altitude sensor accuracy")
        
        return recommendations
    
    def _should_quarantine(self, overall_score: float, issues: List[QualityIssue]) -> bool:
        """Determine if data should be quarantined."""
        # Quarantine if overall score is too low
        if overall_score < self.config.quarantine_threshold:
            return True
        
        # Quarantine if critical issues are present and configured to do so
        if self.config.critical_issue_quarantine:
            critical_issues = [issue for issue in issues if issue.severity == SeverityLevel.CRITICAL]
            if critical_issues:
                return True
        
        return False
    
    def _update_validation_metrics(self, quality_score: QualityScore) -> None:
        """Update internal validation metrics."""
        self.validation_metrics['total_records_processed'] += 1
        self.validation_metrics['quality_score_sum'] += quality_score.overall_score
        
        if quality_score.should_quarantine:
            self.validation_metrics['total_quarantined'] += 1
        
        # Count issues by type and severity
        for issue in quality_score.issues_found:
            issue_type = issue.issue_type
            severity = issue.severity.value
            
            self.validation_metrics['issues_by_type'][issue_type] = \
                self.validation_metrics['issues_by_type'].get(issue_type, 0) + 1
            
            self.validation_metrics['issues_by_severity'][severity] = \
                self.validation_metrics['issues_by_severity'].get(severity, 0) + 1