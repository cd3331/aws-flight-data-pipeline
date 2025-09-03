"""
Comprehensive unit tests for Data Transformer.

Tests JSON to Parquet conversion, calculated fields, data categorization,
and duplicate removal functionality.
"""
import pytest
import pandas as pd
import pyarrow as pa
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import importlib
lambda_module = importlib.import_module('lambda.etl.data_transformer')
FlightDataTransformer = lambda_module.FlightDataTransformer
TransformationConfig = lambda_module.TransformationConfig
TransformationStats = lambda_module.TransformationStats
FlightPhase = lambda_module.FlightPhase
SpeedCategory = lambda_module.SpeedCategory


class TestTransformationConfig:
    """Test TransformationConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TransformationConfig()
        
        assert config.enable_altitude_ft == True
        assert config.enable_speed_knots == True
        assert config.enable_distance_calculations == True
        assert config.enable_rate_calculations == True
        assert config.enable_flight_phase_detection == True
        assert config.enable_speed_categorization == True
        assert config.duplicate_detection_enabled == True
        
        assert config.ground_altitude_threshold_ft == 100.0
        assert config.taxi_speed_threshold_knots == 30.0
        assert config.cruise_altitude_threshold_ft == 10000.0
        
        assert 'stationary' in config.speed_thresholds
        assert 'taxi_speed' in config.speed_thresholds
        assert 'supersonic' in config.speed_thresholds
        
        assert 'icao24' in config.duplicate_key_fields
        assert 'timestamp' in config.duplicate_key_fields
        
        assert 'altitude' in config.missing_value_strategy
        assert 'latitude' in config.missing_value_strategy
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = TransformationConfig(
            enable_altitude_ft=False,
            ground_altitude_threshold_ft=200.0,
            duplicate_detection_enabled=False,
            chunk_size=5000
        )
        
        assert config.enable_altitude_ft == False
        assert config.ground_altitude_threshold_ft == 200.0
        assert config.duplicate_detection_enabled == False
        assert config.chunk_size == 5000


class TestTransformationStats:
    """Test TransformationStats class."""
    
    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = TransformationStats()
        
        assert stats.records_input == 0
        assert stats.records_output == 0
        assert stats.records_dropped == 0
        assert stats.duplicates_removed == 0
        assert stats.missing_values_imputed == 0
        assert stats.calculated_fields_added == 0
        assert stats.processing_time_ms == 0.0
        assert stats.memory_usage_mb == 0.0
        assert isinstance(stats.transformation_details, dict)


class TestFlightDataTransformer:
    """Test FlightDataTransformer class."""
    
    @pytest.fixture
    def transformer(self, transformation_config_basic):
        """Create transformer instance."""
        return FlightDataTransformer(config=transformation_config_basic)
    
    @pytest.fixture
    def full_transformer(self, transformation_config_full):
        """Create transformer with all features enabled."""
        return FlightDataTransformer(config=transformation_config_full)
    
    @pytest.fixture
    def sample_df_with_timestamp(self, sample_dataframe):
        """Sample DataFrame with proper timestamp column."""
        df = sample_dataframe.copy()
        df['timestamp'] = pd.to_datetime(df['time_position'], unit='s')
        return df
    
    def test_transformer_initialization(self, transformer):
        """Test transformer initialization."""
        assert transformer is not None
        assert transformer.config is not None
        assert isinstance(transformer.stats, TransformationStats)
        assert isinstance(transformer._calculation_cache, dict)
        assert isinstance(transformer._aircraft_history_cache, dict)
    
    def test_validate_and_prepare_dataframe_success(self, transformer, sample_df_with_timestamp):
        """Test successful DataFrame validation and preparation."""
        df = transformer._validate_and_prepare_dataframe(sample_df_with_timestamp)
        
        assert 'icao24' in df.columns
        assert 'timestamp' in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])
        
        # Check sorting
        assert df['icao24'].tolist() == sorted(df['icao24'].tolist())
    
    def test_validate_and_prepare_dataframe_missing_columns(self, transformer):
        """Test DataFrame validation with missing required columns."""
        df = pd.DataFrame({'some_column': [1, 2, 3]})
        
        with pytest.raises(ValueError, match="Missing required columns"):
            transformer._validate_and_prepare_dataframe(df)
    
    def test_validate_and_prepare_dataframe_timestamp_conversion(self, transformer, sample_dataframe):
        """Test timestamp conversion during DataFrame preparation."""
        df = sample_dataframe.copy()
        df['timestamp'] = df['time_position']  # Unix timestamp
        
        prepared_df = transformer._validate_and_prepare_dataframe(df)
        
        assert pd.api.types.is_datetime64_any_dtype(prepared_df['timestamp'])
    
    def test_memory_optimization(self, transformer, sample_df_with_timestamp):
        """Test DataFrame memory optimization."""
        df = sample_df_with_timestamp.copy()
        
        # Add some numeric columns that can be optimized
        df['test_int'] = 100
        df['test_float'] = 1.5
        df['test_category'] = 'category_a'
        
        original_memory = df.memory_usage(deep=True).sum()
        optimized_df = transformer._optimize_dataframe_memory(df)
        optimized_memory = optimized_df.memory_usage(deep=True).sum()
        
        # Memory usage should be reduced or at least not increased significantly
        assert optimized_memory <= original_memory * 1.1  # Allow 10% increase due to overhead
    
    @pytest.mark.parametrize("strategy,column", [
        ('drop', 'latitude'),
        ('interpolate', 'baro_altitude'),
        ('forward_fill', 'callsign'),
        ('backward_fill', 'squawk'),
        ('mode', 'origin_country'),
        ('mean', 'velocity')
    ])
    def test_missing_value_strategies(self, transformer, strategy, column):
        """Test different missing value handling strategies."""
        # Create DataFrame with missing values
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30 12:00:00'), column: 100.0},
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30 12:01:00'), column: None},
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30 12:02:00'), column: 200.0}
        ])
        
        # Configure strategy
        transformer.config.missing_value_strategy = {column: strategy}
        
        initial_missing = df[column].isna().sum()
        processed_df = transformer._handle_missing_values(df)
        
        if strategy == 'drop':
            # Should drop rows with missing values
            assert len(processed_df) < len(df)
        else:
            # Should attempt to fill missing values
            final_missing = processed_df[column].isna().sum()
            assert final_missing <= initial_missing
    
    def test_add_altitude_ft_conversion(self, transformer):
        """Test altitude conversion to feet."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'altitude': 3048.0},  # 10000 ft in meters
            {'icao24': '123456', 'timestamp': pd.Timestamp('2023-08-30'), 'altitude': 1524.0}   # 5000 ft in meters
        ])
        
        result_df = transformer._add_altitude_ft(df)
        
        assert 'altitude_ft' in result_df.columns
        assert abs(result_df.iloc[0]['altitude_ft'] - 10000) < 10  # Within 10 feet
        assert abs(result_df.iloc[1]['altitude_ft'] - 5000) < 10
        assert result_df['altitude_ft'].dtype == 'int32'
    
    def test_add_speed_knots_conversion(self, transformer):
        """Test speed conversion to knots."""
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'timestamp': pd.Timestamp('2023-08-30'), 'velocity': 128.6},  # ~250 knots
            {'icao24': '123456', 'timestamp': pd.Timestamp('2023-08-30'), 'velocity': 231.5}   # ~450 knots
        ])
        
        result_df = transformer._add_speed_knots(df)
        
        assert 'speed_knots' in result_df.columns
        assert abs(result_df.iloc[0]['speed_knots'] - 250) < 5  # Within 5 knots
        assert abs(result_df.iloc[1]['speed_knots'] - 450) < 5
        assert result_df['speed_knots'].dtype == 'float32'
    
    def test_add_distance_calculations(self, transformer):
        """Test distance calculations between points."""
        # Create data with two points for same aircraft
        df = pd.DataFrame([
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),
                'latitude': 40.7128,
                'longitude': -74.0060  # NYC
            },
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:01:00'),
                'latitude': 40.7580,
                'longitude': -73.9855  # Near NYC
            }
        ])
        
        result_df = transformer._add_distance_calculations(df)
        
        assert 'distance_km' in result_df.columns
        assert 'cumulative_distance_km' in result_df.columns
        
        # First point should have 0 distance
        assert result_df.iloc[0]['distance_km'] == 0.0
        
        # Second point should have non-zero distance
        assert result_df.iloc[1]['distance_km'] > 0.0
        assert result_df.iloc[1]['cumulative_distance_km'] > 0.0
        
        # Data types should be float32
        assert result_df['distance_km'].dtype == 'float32'
        assert result_df['cumulative_distance_km'].dtype == 'float32'
    
    def test_add_rate_calculations(self, transformer):
        """Test rate calculations (climb rate and acceleration)."""
        # Create data with altitude and speed changes
        df = pd.DataFrame([
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),
                'altitude_ft': 10000.0,
                'speed_knots': 250.0
            },
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:01:00'),
                'altitude_ft': 11000.0,  # Climbed 1000 ft in 1 min
                'speed_knots': 280.0     # Accelerated 30 knots in 1 min
            }
        ])
        
        result_df = transformer._add_rate_calculations(df)
        
        assert 'climb_rate_fpm' in result_df.columns
        assert 'acceleration_kts_min' in result_df.columns
        
        # First point should have 0 rates
        assert result_df.iloc[0]['climb_rate_fpm'] == 0
        assert result_df.iloc[0]['acceleration_kts_min'] == 0
        
        # Second point should have calculated rates
        assert result_df.iloc[1]['climb_rate_fpm'] == 1000  # 1000 ft/min climb
        assert result_df.iloc[1]['acceleration_kts_min'] == 30  # 30 kts/min acceleration
    
    @pytest.mark.parametrize("altitude,speed,climb_rate,expected_phase", [
        (50, 5, 0, FlightPhase.GROUND),
        (50, 20, 0, FlightPhase.TAXI),
        (50, 80, 600, FlightPhase.TAKEOFF),
        (2000, 200, 800, FlightPhase.TAKEOFF),
        (5000, 250, 600, FlightPhase.CLIMB),
        (35000, 450, 0, FlightPhase.CRUISE),
        (25000, 400, -400, FlightPhase.DESCENT),
        (2000, 180, -500, FlightPhase.APPROACH),
    ])
    def test_flight_phase_detection(self, transformer, altitude, speed, climb_rate, expected_phase):
        """Test flight phase detection logic."""
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'timestamp': pd.Timestamp('2023-08-30'),
            'altitude_ft': altitude,
            'speed_knots': speed,
            'climb_rate_fpm': climb_rate
        }])
        
        result_df = transformer._detect_flight_phases(df)
        
        assert 'flight_phase' in result_df.columns
        assert result_df.iloc[0]['flight_phase'] == expected_phase.value
        assert result_df['flight_phase'].dtype.name == 'category'
    
    @pytest.mark.parametrize("speed,expected_category", [
        (2, SpeedCategory.STATIONARY),
        (15, SpeedCategory.TAXI_SPEED),
        (100, SpeedCategory.LOW_SPEED),
        (250, SpeedCategory.MEDIUM_SPEED),
        (500, SpeedCategory.HIGH_SPEED),
        (700, SpeedCategory.SUPERSONIC),
    ])
    def test_speed_categorization(self, transformer, speed, expected_category):
        """Test speed categorization logic."""
        df = pd.DataFrame([{
            'icao24': 'abcdef',
            'timestamp': pd.Timestamp('2023-08-30'),
            'speed_knots': speed
        }])
        
        result_df = transformer._categorize_speed(df)
        
        assert 'speed_category' in result_df.columns
        assert result_df.iloc[0]['speed_category'] == expected_category.value
        assert result_df['speed_category'].dtype.name == 'category'
    
    @pytest.mark.parametrize("keep_strategy", ['first', 'last', 'best_quality'])
    def test_remove_duplicates(self, transformer, keep_strategy):
        """Test duplicate removal with different strategies."""
        # Create DataFrame with duplicates
        df = pd.DataFrame([
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),
                'latitude': 40.7128,
                'longitude': -74.0060,
                'altitude_ft': 10000,
                'speed_knots': 250
            },
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),  # Same timestamp - duplicate
                'latitude': 40.7128,
                'longitude': -74.0060,
                'altitude_ft': None,      # Missing data - lower quality
                'speed_knots': None
            },
            {
                'icao24': '123456',
                'timestamp': pd.Timestamp('2023-08-30 12:00:00'),
                'latitude': 51.4700,
                'longitude': -0.4543,
                'altitude_ft': 35000,
                'speed_knots': 450
            }
        ])
        
        transformer.config.keep_duplicate_strategy = keep_strategy
        transformer.config.duplicate_key_fields = ['icao24', 'timestamp']
        
        result_df = transformer._remove_duplicates(df)
        
        # Should have 2 records (one duplicate removed)
        assert len(result_df) == 2
        assert transformer.stats.duplicates_removed == 1
        
        # Check that we kept the right record based on strategy
        if keep_strategy == 'best_quality':
            # Should keep the record with complete data
            abcdef_record = result_df[result_df['icao24'] == 'abcdef'].iloc[0]
            assert pd.notna(abcdef_record['altitude_ft'])
            assert pd.notna(abcdef_record['speed_knots'])
    
    def test_remove_duplicates_by_quality(self, transformer):
        """Test duplicate removal by quality score."""
        df = pd.DataFrame([
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30'),
                'latitude': 40.7128,
                'longitude': -74.0060,
                'altitude_ft': 10000,
                'speed_knots': 250,
                'callsign': 'UAL123'
            },
            {
                'icao24': 'abcdef',
                'timestamp': pd.Timestamp('2023-08-30'),  # Same key - duplicate
                'latitude': None,      # Missing critical data
                'longitude': None,
                'altitude_ft': None,
                'speed_knots': None,
                'callsign': None
            }
        ])
        
        result_df = transformer._remove_duplicates_by_quality(df)
        
        assert len(result_df) == 1
        
        # Should keep the record with better quality (complete data)
        kept_record = result_df.iloc[0]
        assert pd.notna(kept_record['latitude'])
        assert pd.notna(kept_record['longitude'])
        assert pd.notna(kept_record['altitude_ft'])
        assert pd.notna(kept_record['speed_knots'])
        assert pd.notna(kept_record['callsign'])
    
    def test_final_cleanup(self, transformer):
        """Test final cleanup operations."""
        # Create DataFrame with empty rows
        df = pd.DataFrame([
            {'icao24': 'abcdef', 'latitude': 40.7128, 'longitude': -74.0060},
            {'icao24': None, 'latitude': None, 'longitude': None},  # Empty row
            {'icao24': '123456', 'latitude': 51.4700, 'longitude': -0.4543}
        ])
        
        result_df = transformer._final_cleanup(df)
        
        # Should remove empty row
        assert len(result_df) == 2
        
        # Index should be reset
        assert result_df.index.tolist() == [0, 1]
    
    def test_transform_dataframe_complete_workflow(self, full_transformer, sample_df_with_timestamp):
        """Test complete DataFrame transformation workflow."""
        df = sample_df_with_timestamp.copy()
        
        # Add some missing values to test imputation
        df.loc[0, 'baro_altitude'] = None
        df.loc[1, 'velocity'] = None
        
        transformed_df, stats = full_transformer.transform_dataframe(df)
        
        # Check that transformation completed
        assert transformed_df is not None
        assert isinstance(stats, TransformationStats)
        
        # Check that calculated fields were added
        if full_transformer.config.enable_altitude_ft:
            assert 'altitude_ft' in transformed_df.columns or df['baro_altitude'].isna().all()
        
        if full_transformer.config.enable_speed_knots:
            assert 'speed_knots' in transformed_df.columns or df['velocity'].isna().all()
        
        if full_transformer.config.enable_flight_phase_detection:
            expected_columns = ['altitude_ft', 'speed_knots']
            if all(col in transformed_df.columns for col in expected_columns):
                assert 'flight_phase' in transformed_df.columns
        
        if full_transformer.config.enable_speed_categorization:
            if 'speed_knots' in transformed_df.columns:
                assert 'speed_category' in transformed_df.columns
        
        # Check stats
        assert stats.records_input == len(df)
        assert stats.records_output <= stats.records_input
        assert stats.processing_time_ms > 0
    
    def test_transform_arrow_table(self, full_transformer, sample_arrow_table):
        """Test PyArrow Table transformation."""
        transformed_table, stats = full_transformer.transform_arrow_table(sample_arrow_table)
        
        assert transformed_table is not None
        assert isinstance(transformed_table, pa.Table)
        assert isinstance(stats, TransformationStats)
        assert stats.records_input > 0
        assert stats.processing_time_ms > 0
    
    def test_get_transformation_summary(self, transformer, sample_df_with_timestamp):
        """Test transformation summary generation."""
        # Run a transformation to populate stats
        transformed_df, stats = transformer.transform_dataframe(sample_df_with_timestamp)
        
        summary = transformer.get_transformation_summary()
        
        assert 'statistics' in summary
        assert 'configuration' in summary
        assert 'cache_stats' in summary
        
        # Check statistics
        stats_section = summary['statistics']
        assert 'records_input' in stats_section
        assert 'records_output' in stats_section
        assert 'processing_time_ms' in stats_section
        assert 'records_per_second' in stats_section
        
        # Check configuration
        config_section = summary['configuration']
        assert 'chunk_size' in config_section
        assert 'enabled_transformations' in config_section
        
        # Check cache stats
        cache_section = summary['cache_stats']
        assert 'calculation_cache_size' in cache_section
        assert 'aircraft_history_cache_size' in cache_section
    
    def test_error_handling_invalid_data_types(self, transformer):
        """Test error handling with invalid data types."""
        # Create DataFrame with problematic data types
        df = pd.DataFrame([
            {
                'icao24': 'abcdef',
                'timestamp': 'invalid_timestamp',  # This should cause issues
                'latitude': 'not_a_number',
                'longitude': 'also_not_a_number'
            }
        ])
        
        # Should handle errors gracefully
        try:
            transformed_df, stats = transformer.transform_dataframe(df)
            # If it completes, that's fine too
            assert transformed_df is not None
        except Exception as e:
            # Should be a meaningful error
            assert isinstance(e, (ValueError, TypeError, pd.errors.ParserError))
    
    def test_edge_case_empty_dataframe(self, transformer):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame(columns=['icao24', 'timestamp'])
        
        transformed_df, stats = transformer.transform_dataframe(df)
        
        assert len(transformed_df) == 0
        assert stats.records_input == 0
        assert stats.records_output == 0
    
    def test_edge_case_single_row(self, transformer, sample_df_with_timestamp):
        """Test handling of single-row DataFrame."""
        df = sample_df_with_timestamp.head(1)
        
        transformed_df, stats = transformer.transform_dataframe(df)
        
        assert len(transformed_df) == 1
        assert stats.records_input == 1
        assert stats.records_output <= 1
    
    @pytest.mark.slow
    def test_performance_large_dataset(self, transformer, large_dataframe, performance_timer):
        """Test performance with large dataset."""
        # Add timestamp column
        large_df = large_dataframe.head(10000).copy()
        large_df['timestamp'] = pd.to_datetime(large_df['time_position'], unit='s')
        
        performance_timer.start()
        transformed_df, stats = transformer.transform_dataframe(large_df)
        performance_timer.stop()
        
        assert transformed_df is not None
        assert len(transformed_df) <= len(large_df)
        assert stats.records_input == len(large_df)
        assert performance_timer.elapsed_seconds < 120  # Should complete in under 2 minutes
        assert stats.processing_time_ms > 0
        
        # Check performance metrics
        records_per_second = stats.records_output / (stats.processing_time_ms / 1000)
        assert records_per_second > 10  # Should process at least 10 records per second
    
    def test_concurrent_transformations(self, transformer, sample_df_with_timestamp):
        """Test concurrent transformations don't interfere."""
        import concurrent.futures
        
        def transform_df(df_copy):
            return transformer.transform_dataframe(df_copy)
        
        # Create multiple DataFrame copies
        dfs = [sample_df_with_timestamp.copy() for _ in range(3)]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(transform_df, df) for df in dfs]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        assert len(results) == 3
        for transformed_df, stats in results:
            assert transformed_df is not None
            assert stats.records_input > 0


class TestFlightPhaseEnum:
    """Test FlightPhase enum."""
    
    def test_flight_phase_values(self):
        """Test FlightPhase enum values."""
        assert FlightPhase.GROUND.value == "ground"
        assert FlightPhase.TAXI.value == "taxi"
        assert FlightPhase.TAKEOFF.value == "takeoff"
        assert FlightPhase.CLIMB.value == "climb"
        assert FlightPhase.CRUISE.value == "cruise"
        assert FlightPhase.DESCENT.value == "descent"
        assert FlightPhase.APPROACH.value == "approach"
        assert FlightPhase.LANDING.value == "landing"
        assert FlightPhase.UNKNOWN.value == "unknown"


class TestSpeedCategoryEnum:
    """Test SpeedCategory enum."""
    
    def test_speed_category_values(self):
        """Test SpeedCategory enum values."""
        assert SpeedCategory.STATIONARY.value == "stationary"
        assert SpeedCategory.TAXI_SPEED.value == "taxi_speed"
        assert SpeedCategory.LOW_SPEED.value == "low_speed"
        assert SpeedCategory.MEDIUM_SPEED.value == "medium_speed"
        assert SpeedCategory.HIGH_SPEED.value == "high_speed"
        assert SpeedCategory.SUPERSONIC.value == "supersonic"