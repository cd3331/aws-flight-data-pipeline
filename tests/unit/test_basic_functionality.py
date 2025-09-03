"""
Basic functionality tests to verify test setup works.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone


class TestBasicSetup:
    """Test basic setup and dependencies."""
    
    def test_pandas_available(self):
        """Test that pandas is available."""
        assert pd is not None
        
    def test_sample_data_fixture(self, sample_flight_data):
        """Test that sample data fixture works."""
        assert isinstance(sample_flight_data, list)
        assert len(sample_flight_data) > 0
        assert 'icao24' in sample_flight_data[0]
        
    def test_sample_dataframe_fixture(self, sample_dataframe):
        """Test that sample dataframe fixture works."""
        assert isinstance(sample_dataframe, pd.DataFrame)
        assert len(sample_dataframe) > 0
        assert 'icao24' in sample_dataframe.columns
        
    def test_invalid_dataframe_fixture(self, invalid_dataframe):
        """Test that invalid dataframe fixture works."""
        assert isinstance(invalid_dataframe, pd.DataFrame)
        assert len(invalid_dataframe) > 0
        
    def test_large_dataframe_fixture(self, large_dataframe):
        """Test that large dataframe fixture works."""
        assert isinstance(large_dataframe, pd.DataFrame)
        assert len(large_dataframe) >= 1000
        
    def test_coordinate_test_cases(self, coordinate_test_case):
        """Test coordinate test case parameterization."""
        assert 'lat' in coordinate_test_case
        assert 'lon' in coordinate_test_case
        assert 'expected' in coordinate_test_case
        
    def test_icao24_test_cases(self, icao24_test_case):
        """Test ICAO24 test case parameterization."""
        assert 'icao24' in icao24_test_case
        assert 'expected' in icao24_test_case
        
    def test_performance_timer_fixture(self, performance_timer):
        """Test performance timer fixture."""
        performance_timer.start()
        performance_timer.stop()
        
        assert performance_timer.elapsed_ms >= 0
        assert performance_timer.elapsed_seconds >= 0


class TestDataValidation:
    """Test basic data validation functions."""
    
    def test_data_completeness_basic(self, sample_dataframe):
        """Test basic data completeness check."""
        # Test that required fields are present
        required_fields = ['icao24', 'latitude', 'longitude']
        
        for field in required_fields:
            assert field in sample_dataframe.columns
            
        # Test that data is not all null
        for field in required_fields:
            assert not sample_dataframe[field].isna().all()
    
    def test_data_validity_basic(self, sample_dataframe):
        """Test basic data validity checks."""
        # Test latitude range
        if 'latitude' in sample_dataframe.columns:
            valid_lat = sample_dataframe['latitude'].between(-90, 90)
            assert valid_lat.all() or sample_dataframe['latitude'].isna().all()
            
        # Test longitude range  
        if 'longitude' in sample_dataframe.columns:
            valid_lon = sample_dataframe['longitude'].between(-180, 180)
            assert valid_lon.all() or sample_dataframe['longitude'].isna().all()
    
    def test_data_types(self, sample_dataframe):
        """Test basic data types."""
        # Test ICAO24 is string-like
        if 'icao24' in sample_dataframe.columns:
            non_null_icao = sample_dataframe['icao24'].dropna()
            if not non_null_icao.empty:
                assert non_null_icao.astype(str).str.len().min() > 0
                
        # Test coordinates are numeric
        if 'latitude' in sample_dataframe.columns:
            non_null_lat = sample_dataframe['latitude'].dropna()
            if not non_null_lat.empty:
                assert pd.api.types.is_numeric_dtype(non_null_lat) or non_null_lat.empty
                
        if 'longitude' in sample_dataframe.columns:
            non_null_lon = sample_dataframe['longitude'].dropna()
            if not non_null_lon.empty:
                assert pd.api.types.is_numeric_dtype(non_null_lon) or non_null_lon.empty


class TestUtilityFunctions:
    """Test utility functions used across the codebase."""
    
    def test_haversine_distance_calculation(self):
        """Test haversine distance calculation."""
        import math
        
        def calculate_haversine_distance(lat1, lon1, lat2, lon2):
            """Calculate haversine distance between two points."""
            R = 6371  # Earth's radius in km
            
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            return R * c
        
        # Test known distances
        # NYC to Los Angeles (approximate)
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        
        distance = calculate_haversine_distance(nyc_lat, nyc_lon, la_lat, la_lon)
        
        # Should be approximately 3944 km
        assert 3900 < distance < 4000
        
        # Test same point (should be 0)
        same_point_distance = calculate_haversine_distance(nyc_lat, nyc_lon, nyc_lat, nyc_lon)
        assert same_point_distance < 0.001  # Very close to 0
    
    def test_timestamp_handling(self):
        """Test timestamp handling utilities."""
        current_time = datetime.now(timezone.utc)
        unix_timestamp = current_time.timestamp()
        
        # Test conversion back
        converted_time = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        
        # Should be very close (within 1 second)
        time_diff = abs((current_time - converted_time).total_seconds())
        assert time_diff < 1.0
    
    def test_data_quality_score_calculation(self):
        """Test basic data quality score calculation."""
        # Simple completeness score
        total_fields = 5
        complete_fields = 4
        completeness_score = complete_fields / total_fields
        
        assert 0.0 <= completeness_score <= 1.0
        assert completeness_score == 0.8
        
        # Weighted score calculation
        scores = {'completeness': 0.8, 'validity': 0.9, 'consistency': 0.7}
        weights = {'completeness': 0.4, 'validity': 0.4, 'consistency': 0.2}
        
        weighted_score = sum(scores[dim] * weights[dim] for dim in scores)
        
        assert 0.0 <= weighted_score <= 1.0
        expected_score = (0.8 * 0.4) + (0.9 * 0.4) + (0.7 * 0.2)
        assert abs(weighted_score - expected_score) < 0.001


class TestErrorConditions:
    """Test handling of various error conditions."""
    
    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        empty_df = pd.DataFrame()
        
        # Should not crash when checking properties
        assert len(empty_df) == 0
        assert len(empty_df.columns) == 0
        
        # Should handle operations gracefully
        try:
            result = empty_df.describe()
            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            # Should not be unexpected errors
            assert not isinstance(e, (AttributeError, KeyError))
    
    def test_invalid_data_types(self):
        """Test handling of invalid data types."""
        mixed_df = pd.DataFrame([
            {'value': 1.0, 'text': 'valid'},
            {'value': 'invalid', 'text': 2},
            {'value': None, 'text': None}
        ])
        
        # Should not crash when accessing
        assert len(mixed_df) == 3
        
        # Test type checking
        numeric_mask = pd.to_numeric(mixed_df['value'], errors='coerce').notna()
        assert numeric_mask.sum() >= 1  # At least one valid number
    
    def test_extreme_values(self):
        """Test handling of extreme values."""
        extreme_df = pd.DataFrame([
            {'normal': 1.0, 'large': 1e10, 'small': 1e-10},
            {'normal': 2.0, 'large': float('inf'), 'small': float('-inf')},
            {'normal': 3.0, 'large': float('nan'), 'small': 0.0}
        ])
        
        # Should handle inf and nan gracefully
        assert not extreme_df['normal'].isin([float('inf'), float('-inf'), float('nan')]).any()
        assert extreme_df['large'].isin([float('inf'), float('nan')]).any()
        assert extreme_df['small'].isin([float('-inf')]).any()
        
        # Test filtering
        finite_values = extreme_df.select_dtypes(include=[np.number]).apply(lambda x: np.isfinite(x))
        assert finite_values.any().any()  # Should have some finite values