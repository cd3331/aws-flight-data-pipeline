"""
Advanced Data Transformation Pipeline for Flight Data.

This module provides comprehensive data transformation capabilities including
calculated fields, flight phase categorization, duplicate handling, and
missing value imputation with optimized performance.

Author: Flight Data Pipeline Team
Version: 1.0
"""

import logging
import numpy as np
import time
import gc
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# Lazy imports
pandas = None
pyarrow = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _lazy_import_pandas():
    """Lazy import pandas with optimizations."""
    global pandas
    if pandas is None:
        import pandas as pd
        # Optimize pandas settings for performance
        pd.options.mode.chained_assignment = None
        pd.options.compute.use_bottleneck = True
        pd.options.compute.use_numexpr = True
        pandas = pd
    return pandas


def _lazy_import_pyarrow():
    """Lazy import PyArrow."""
    global pyarrow
    if pyarrow is None:
        import pyarrow as pa
        import pyarrow.compute as pc
        pyarrow = pa
        pyarrow.compute = pc
    return pyarrow


class FlightPhase(Enum):
    """Flight phase categories."""
    GROUND = "ground"
    TAXI = "taxi"
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    LANDING = "landing"
    UNKNOWN = "unknown"


class SpeedCategory(Enum):
    """Speed-based flight categories."""
    STATIONARY = "stationary"      # 0-5 knots
    TAXI_SPEED = "taxi_speed"      # 5-30 knots
    LOW_SPEED = "low_speed"        # 30-150 knots
    MEDIUM_SPEED = "medium_speed"   # 150-350 knots
    HIGH_SPEED = "high_speed"      # 350-600 knots
    SUPERSONIC = "supersonic"      # 600+ knots
    UNKNOWN = "unknown"            # Fallback for unmatchable speeds


@dataclass
class TransformationConfig:
    """Configuration for data transformation pipeline."""
    
    # Calculated fields configuration
    enable_altitude_ft: bool = True
    enable_speed_knots: bool = True
    enable_distance_calculations: bool = True
    enable_rate_calculations: bool = True
    
    # Flight phase detection
    enable_flight_phase_detection: bool = True
    ground_altitude_threshold_ft: float = 100.0
    taxi_speed_threshold_knots: float = 30.0
    takeoff_climb_rate_threshold: float = 500.0  # ft/min
    cruise_altitude_threshold_ft: float = 10000.0
    approach_descent_rate_threshold: float = -300.0  # ft/min
    
    # Speed categorization
    enable_speed_categorization: bool = True
    speed_thresholds: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        'stationary': (0.0, 5.0),
        'taxi_speed': (5.0, 30.0),
        'low_speed': (30.0, 150.0),
        'medium_speed': (150.0, 350.0),
        'high_speed': (350.0, 600.0),
        'supersonic': (600.0, float('inf'))
    })
    
    # Duplicate handling
    duplicate_detection_enabled: bool = True
    duplicate_key_fields: List[str] = field(default_factory=lambda: [
        'icao24', 'timestamp'
    ])
    duplicate_tolerance_seconds: int = 5
    keep_duplicate_strategy: str = 'last'  # 'first', 'last', 'best_quality'
    
    # Missing value handling
    missing_value_strategy: Dict[str, str] = field(default_factory=lambda: {
        'altitude': 'interpolate',
        'latitude': 'drop',
        'longitude': 'drop',
        'velocity': 'interpolate',
        'heading': 'forward_fill',
        'vertical_rate': 'interpolate',
        'squawk': 'mode',
        'callsign': 'forward_fill'
    })
    
    # Performance settings
    chunk_size: int = 10000
    use_vectorized_operations: bool = True
    parallel_processing: bool = True
    max_workers: int = 4
    
    # Memory optimization
    enable_memory_optimization: bool = True
    gc_frequency: int = 5  # Force GC every N chunks


@dataclass
class TransformationStats:
    """Statistics for transformation operations."""
    records_input: int = 0
    records_output: int = 0
    records_dropped: int = 0
    duplicates_removed: int = 0
    missing_values_imputed: int = 0
    calculated_fields_added: int = 0
    processing_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    transformation_details: Dict[str, Any] = field(default_factory=dict)


class FlightDataTransformer:
    """Advanced flight data transformation pipeline with optimizations."""
    
    def __init__(self, config: TransformationConfig = None):
        """Initialize the transformer with configuration."""
        self.config = config or TransformationConfig()
        self.stats = TransformationStats()
        
        # Caching for expensive calculations
        self._calculation_cache = {}
        self._aircraft_history_cache = {}
        
        # Pre-compiled calculation functions for performance
        self._compiled_functions = {}
        self._compile_calculation_functions()
        
        logger.info("FlightDataTransformer initialized with optimized configuration")
    
    def transform_dataframe(self, df: 'pandas.DataFrame') -> Tuple['pandas.DataFrame', TransformationStats]:
        """
        Transform a pandas DataFrame with all configured transformations.
        
        Args:
            df: Input DataFrame with flight data
            
        Returns:
            Tuple of (transformed_dataframe, transformation_stats)
        """
        start_time = time.time()
        pd = _lazy_import_pandas()
        
        logger.info(f"Starting transformation of {len(df)} records")
        self.stats = TransformationStats(records_input=len(df))
        
        try:
            # Ensure required columns exist
            df = self._validate_and_prepare_dataframe(df)
            
            # Memory optimization
            if self.config.enable_memory_optimization:
                df = self._optimize_dataframe_memory(df)
            
            # Handle missing values first
            df = self._handle_missing_values(df)
            
            # Add calculated fields
            if self.config.enable_altitude_ft:
                df = self._add_altitude_ft(df)
            
            if self.config.enable_speed_knots:
                df = self._add_speed_knots(df)
            
            if self.config.enable_distance_calculations:
                df = self._add_distance_calculations(df)
            
            if self.config.enable_rate_calculations:
                df = self._add_rate_calculations(df)
            
            # Flight phase detection
            if self.config.enable_flight_phase_detection:
                df = self._detect_flight_phases(df)
            
            # Speed categorization
            if self.config.enable_speed_categorization:
                df = self._categorize_speed(df)
            
            # Remove duplicates
            if self.config.duplicate_detection_enabled:
                df = self._remove_duplicates(df)
            
            # Final cleanup and validation
            df = self._final_cleanup(df)
            
            # Update final stats
            self.stats.records_output = len(df)
            self.stats.records_dropped = self.stats.records_input - self.stats.records_output
            self.stats.processing_time_ms = (time.time() - start_time) * 1000
            
            logger.info(f"Transformation completed: {self.stats.records_input} -> {self.stats.records_output} records "
                       f"({self.stats.processing_time_ms:.1f}ms)")
            
            return df, self.stats
            
        except Exception as e:
            logger.error(f"Transformation failed: {str(e)}")
            raise
    
    def transform_arrow_table(self, table: 'pyarrow.Table') -> Tuple['pyarrow.Table', TransformationStats]:
        """
        Transform PyArrow Table directly for better performance.
        
        Args:
            table: Input PyArrow Table
            
        Returns:
            Tuple of (transformed_table, transformation_stats)
        """
        pa = _lazy_import_pyarrow()
        pd = _lazy_import_pandas()
        
        # Convert to pandas for complex transformations
        df = table.to_pandas()
        
        # Apply transformations
        df, stats = self.transform_dataframe(df)
        
        # Convert back to Arrow with optimizations
        result_table = pa.Table.from_pandas(df, preserve_index=False)
        
        return result_table, stats
    
    def _validate_and_prepare_dataframe(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Validate and prepare DataFrame for transformation."""
        pd = _lazy_import_pandas()
        
        # Ensure required columns exist
        required_columns = ['icao24', 'timestamp']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Convert timestamp to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        
        # Sort by icao24 and timestamp for efficient processing
        df = df.sort_values(['icao24', 'timestamp']).reset_index(drop=True)
        
        return df
    
    def _optimize_dataframe_memory(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Optimize DataFrame memory usage."""
        pd = _lazy_import_pandas()
        
        # Optimize numeric columns
        for col in df.select_dtypes(include=[np.number]).columns:
            if col in df.columns:
                # Check if integer can be downcasted
                if df[col].dtype in ['int64', 'int32']:
                    df[col] = pd.to_numeric(df[col], downcast='integer')
                elif df[col].dtype in ['float64', 'float32']:
                    df[col] = pd.to_numeric(df[col], downcast='float')
        
        # Convert string columns to categories if cardinality is low
        if len(df) > 0:  # Avoid division by zero for empty DataFrames
            for col in df.select_dtypes(include=['object']).columns:
                if col in df.columns:
                    unique_ratio = df[col].nunique() / len(df)
                    if unique_ratio < 0.5:  # Convert to category if < 50% unique values
                        df[col] = df[col].astype('category')
        
        return df
    
    def _handle_missing_values(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Handle missing values according to configuration."""
        pd = _lazy_import_pandas()
        
        for column, strategy in self.config.missing_value_strategy.items():
            if column not in df.columns:
                continue
            
            missing_count = df[column].isna().sum()
            if missing_count == 0:
                continue
            
            if strategy == 'drop':
                initial_count = len(df)
                df = df.dropna(subset=[column])
                dropped = initial_count - len(df)
                logger.info(f"Dropped {dropped} records due to missing {column}")
                
            elif strategy == 'interpolate':
                if pd.api.types.is_numeric_dtype(df[column]):
                    # Group by aircraft for better interpolation
                    df[column] = df.groupby('icao24')[column].transform(
                        lambda x: x.interpolate(method='linear', limit_direction='both')
                    )
                
            elif strategy == 'forward_fill':
                df[column] = df.groupby('icao24')[column].ffill()
                
            elif strategy == 'backward_fill':
                df[column] = df.groupby('icao24')[column].bfill()
                
            elif strategy == 'mode':
                mode_value = df[column].mode()
                if len(mode_value) > 0:
                    df[column] = df[column].fillna(mode_value.iloc[0])
                    
            elif strategy == 'mean':
                if pd.api.types.is_numeric_dtype(df[column]):
                    mean_value = df[column].mean()
                    df[column] = df[column].fillna(mean_value)
            
            imputed_count = missing_count - df[column].isna().sum()
            self.stats.missing_values_imputed += imputed_count
        
        return df
    
    def _add_altitude_ft(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Add altitude in feet from various altitude columns."""
        # Check for different altitude column names
        altitude_columns = ['altitude', 'altitude_m', 'altitude_meters', 'geoaltitude', 'baro_altitude']
        altitude_col = None
        
        for col in altitude_columns:
            if col in df.columns:
                altitude_col = col
                break
        
        if altitude_col is None:
            logger.warning("No altitude column found for conversion")
            return df
        
        # Convert to feet (assuming input is in meters, except for baro_altitude which is already in feet)
        if 'altitude_ft' not in df.columns:
            if altitude_col == 'baro_altitude':
                # baro_altitude is typically already in feet
                df['altitude_ft'] = df[altitude_col].round(0)
                # Convert to nullable integer to handle NaN values
                df['altitude_ft'] = df['altitude_ft'].astype('Int32')
            else:
                # Other altitude columns assumed to be in meters
                df['altitude_ft'] = df[altitude_col] * 3.28084  # meters to feet
                df['altitude_ft'] = df['altitude_ft'].round(0)
                # Convert to nullable integer to handle NaN values
                df['altitude_ft'] = df['altitude_ft'].astype('Int32')
            self.stats.calculated_fields_added += 1
            logger.debug("Added altitude_ft column")
        
        return df
    
    def _add_speed_knots(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Add speed in knots from velocity or other speed columns."""
        # Check for speed/velocity columns
        speed_columns = ['velocity', 'speed', 'speed_ms', 'groundspeed']
        speed_col = None
        
        for col in speed_columns:
            if col in df.columns:
                speed_col = col
                break
        
        if speed_col is None:
            logger.warning("No speed column found for conversion")
            return df
        
        # Convert to knots (assuming input is in m/s)
        if 'speed_knots' not in df.columns:
            df['speed_knots'] = df[speed_col] * 1.94384  # m/s to knots
            df['speed_knots'] = df['speed_knots'].round(1).astype('float32')
            self.stats.calculated_fields_added += 1
            logger.debug("Added speed_knots column")
        
        return df
    
    def _add_distance_calculations(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Add distance and displacement calculations."""
        if not all(col in df.columns for col in ['latitude', 'longitude']):
            logger.warning("Latitude/longitude not available for distance calculations")
            return df
        
        # Calculate distance traveled between consecutive points for each aircraft
        def calculate_haversine_distance(lat1, lon1, lat2, lon2):
            """Calculate haversine distance between two points."""
            R = 6371  # Earth's radius in km
            
            # Check for NaN or invalid coordinates
            if np.any([np.isnan(x) or x is None for x in [lat1, lon1, lat2, lon2]]):
                return np.nan
                
            # Validate coordinate ranges
            if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and 
                    -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
                return np.nan
            
            lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))  # Clip to avoid numerical errors
            
            return R * c
        
        # Group by aircraft and calculate distances
        df['distance_km'] = 0.0
        df['cumulative_distance_km'] = 0.0
        
        for icao24 in df['icao24'].unique():
            mask = df['icao24'] == icao24
            aircraft_data = df[mask].copy()
            
            if len(aircraft_data) > 1:
                # Calculate distance between consecutive points
                distances = []
                for i in range(len(aircraft_data)):
                    if i == 0:
                        distances.append(0.0)
                    else:
                        dist = calculate_haversine_distance(
                            aircraft_data.iloc[i-1]['latitude'],
                            aircraft_data.iloc[i-1]['longitude'],
                            aircraft_data.iloc[i]['latitude'],
                            aircraft_data.iloc[i]['longitude']
                        )
                        distances.append(dist)
                
                # Update DataFrame
                df.loc[mask, 'distance_km'] = distances
                df.loc[mask, 'cumulative_distance_km'] = np.cumsum(distances)
        
        # Convert to appropriate dtypes
        df['distance_km'] = df['distance_km'].round(3).astype('float32')
        df['cumulative_distance_km'] = df['cumulative_distance_km'].round(3).astype('float32')
        
        self.stats.calculated_fields_added += 2
        logger.debug("Added distance calculations")
        
        return df
    
    def _add_rate_calculations(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Add rate calculations (climb rate, acceleration, etc.)."""
        # Vertical rate (climb/descent rate)
        if 'altitude_ft' in df.columns and 'timestamp' in df.columns:
            df['climb_rate_fpm'] = 0.0  # feet per minute
            
            for icao24 in df['icao24'].unique():
                mask = df['icao24'] == icao24
                aircraft_data = df[mask].copy()
                
                if len(aircraft_data) > 1:
                    # Calculate time differences in minutes
                    time_diff = aircraft_data['timestamp'].diff().dt.total_seconds() / 60.0
                    alt_diff = aircraft_data['altitude_ft'].diff()
                    
                    # Calculate climb rate (feet per minute)
                    climb_rate = alt_diff / time_diff
                    climb_rate = climb_rate.fillna(0)
                    
                    df.loc[mask, 'climb_rate_fpm'] = climb_rate
            
            df['climb_rate_fpm'] = df['climb_rate_fpm'].round(0).astype('int32')
            self.stats.calculated_fields_added += 1
        
        # Ground speed acceleration
        if 'speed_knots' in df.columns and 'timestamp' in df.columns:
            df['acceleration_kts_min'] = 0.0  # knots per minute
            
            for icao24 in df['icao24'].unique():
                mask = df['icao24'] == icao24
                aircraft_data = df[mask].copy()
                
                if len(aircraft_data) > 1:
                    # Calculate time differences in minutes
                    time_diff = aircraft_data['timestamp'].diff().dt.total_seconds() / 60.0
                    speed_diff = aircraft_data['speed_knots'].diff()
                    
                    # Calculate acceleration
                    acceleration = speed_diff / time_diff
                    acceleration = acceleration.fillna(0)
                    
                    df.loc[mask, 'acceleration_kts_min'] = acceleration
            
            df['acceleration_kts_min'] = df['acceleration_kts_min'].round(1).astype('float32')
            self.stats.calculated_fields_added += 1
        
        logger.debug("Added rate calculations")
        return df
    
    def _detect_flight_phases(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Detect flight phases based on altitude, speed, and rates."""
        if not all(col in df.columns for col in ['altitude_ft', 'speed_knots']):
            logger.warning("Required columns not available for flight phase detection")
            df['flight_phase'] = FlightPhase.UNKNOWN.value
            return df
        
        df['flight_phase'] = FlightPhase.UNKNOWN.value
        
        for icao24 in df['icao24'].unique():
            mask = df['icao24'] == icao24
            aircraft_data = df[mask].copy()
            
            phases = []
            for _, row in aircraft_data.iterrows():
                altitude = row.get('altitude_ft', 0)
                speed = row.get('speed_knots', 0)
                climb_rate = row.get('climb_rate_fpm', 0)
                
                # Handle NaN values
                import pandas as pd
                if pd.isna(altitude):
                    altitude = 0
                if pd.isna(speed):
                    speed = 0
                if pd.isna(climb_rate):
                    climb_rate = 0
                
                # Ground phase
                if altitude <= self.config.ground_altitude_threshold_ft:
                    if speed <= 5:
                        phase = FlightPhase.GROUND
                    elif speed <= self.config.taxi_speed_threshold_knots:
                        phase = FlightPhase.TAXI
                    else:
                        phase = FlightPhase.TAKEOFF
                
                # Airborne phases
                else:
                    if climb_rate >= self.config.takeoff_climb_rate_threshold:
                        if altitude < 3000:
                            phase = FlightPhase.TAKEOFF
                        else:
                            phase = FlightPhase.CLIMB
                    elif climb_rate <= self.config.approach_descent_rate_threshold:
                        if altitude < 3000:
                            phase = FlightPhase.APPROACH
                        else:
                            phase = FlightPhase.DESCENT
                    elif altitude >= self.config.cruise_altitude_threshold_ft:
                        phase = FlightPhase.CRUISE
                    elif speed < 150:
                        phase = FlightPhase.APPROACH
                    else:
                        phase = FlightPhase.CRUISE
                
                phases.append(phase.value)
            
            df.loc[mask, 'flight_phase'] = phases
        
        # Convert to category for memory efficiency
        df['flight_phase'] = df['flight_phase'].astype('category')
        self.stats.calculated_fields_added += 1
        logger.debug("Added flight phase detection")
        
        return df
    
    def _categorize_speed(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Categorize aircraft by speed ranges."""
        if 'speed_knots' not in df.columns:
            logger.warning("Speed column not available for categorization")
            df['speed_category'] = SpeedCategory.UNKNOWN.value
            return df
        
        def get_speed_category(speed):
            for category, (min_speed, max_speed) in self.config.speed_thresholds.items():
                if min_speed <= speed < max_speed:
                    return category
            return SpeedCategory.UNKNOWN.value
        
        # Vectorized speed categorization
        df['speed_category'] = df['speed_knots'].apply(get_speed_category)
        df['speed_category'] = df['speed_category'].astype('category')
        
        self.stats.calculated_fields_added += 1
        logger.debug("Added speed categorization")
        
        return df
    
    def _remove_duplicates(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Remove duplicate records based on configuration."""
        initial_count = len(df)
        
        if self.config.keep_duplicate_strategy == 'first':
            df = df.drop_duplicates(subset=self.config.duplicate_key_fields, keep='first')
        elif self.config.keep_duplicate_strategy == 'last':
            df = df.drop_duplicates(subset=self.config.duplicate_key_fields, keep='last')
        elif self.config.keep_duplicate_strategy == 'best_quality':
            # Keep record with most complete data
            df = self._remove_duplicates_by_quality(df)
        
        duplicates_removed = initial_count - len(df)
        self.stats.duplicates_removed = duplicates_removed
        
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate records")
        
        return df
    
    def _remove_duplicates_by_quality(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Remove duplicates keeping the record with best data quality."""
        pd = _lazy_import_pandas()
        
        # Calculate quality score for each record
        def calculate_quality_score(row):
            score = 0
            total_fields = len(row)
            
            # Count non-null values
            non_null_count = row.count()
            completeness_score = non_null_count / total_fields
            
            # Bonus for critical fields
            critical_fields = ['latitude', 'longitude', 'altitude_ft', 'speed_knots']
            critical_score = sum(1 for field in critical_fields if field in row and pd.notna(row[field]))
            critical_score /= len(critical_fields)
            
            return completeness_score * 0.7 + critical_score * 0.3
        
        df['quality_score'] = df.apply(calculate_quality_score, axis=1)
        
        # Keep record with highest quality score for each duplicate group
        df = df.sort_values('quality_score', ascending=False)
        df = df.drop_duplicates(subset=self.config.duplicate_key_fields, keep='first')
        df = df.drop('quality_score', axis=1)
        
        return df
    
    def _final_cleanup(self, df: 'pandas.DataFrame') -> 'pandas.DataFrame':
        """Final cleanup and validation of transformed data."""
        # Remove any completely empty rows
        initial_count = len(df)
        df = df.dropna(how='all')
        dropped_empty = initial_count - len(df)
        
        if dropped_empty > 0:
            logger.info(f"Dropped {dropped_empty} completely empty rows")
        
        # Reset index
        df = df.reset_index(drop=True)
        
        # Force garbage collection if enabled
        if self.config.enable_memory_optimization:
            gc.collect()
        
        return df
    
    def _compile_calculation_functions(self):
        """Pre-compile frequently used calculation functions."""
        # This could be extended with numba JIT compilation for even better performance
        pass
    
    def get_transformation_summary(self) -> Dict[str, Any]:
        """Get comprehensive transformation summary."""
        return {
            'statistics': {
                'records_input': self.stats.records_input,
                'records_output': self.stats.records_output,
                'records_dropped': self.stats.records_dropped,
                'duplicates_removed': self.stats.duplicates_removed,
                'missing_values_imputed': self.stats.missing_values_imputed,
                'calculated_fields_added': self.stats.calculated_fields_added,
                'processing_time_ms': self.stats.processing_time_ms,
                'records_per_second': (self.stats.records_output / (self.stats.processing_time_ms / 1000)) if self.stats.processing_time_ms > 0 else 0
            },
            'configuration': {
                'chunk_size': self.config.chunk_size,
                'parallel_processing': self.config.parallel_processing,
                'memory_optimization': self.config.enable_memory_optimization,
                'enabled_transformations': {
                    'altitude_ft': self.config.enable_altitude_ft,
                    'speed_knots': self.config.enable_speed_knots,
                    'distance_calculations': self.config.enable_distance_calculations,
                    'rate_calculations': self.config.enable_rate_calculations,
                    'flight_phase_detection': self.config.enable_flight_phase_detection,
                    'speed_categorization': self.config.enable_speed_categorization,
                    'duplicate_detection': self.config.duplicate_detection_enabled
                }
            },
            'cache_stats': {
                'calculation_cache_size': len(self._calculation_cache),
                'aircraft_history_cache_size': len(self._aircraft_history_cache)
            }
        }