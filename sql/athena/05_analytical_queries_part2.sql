-- Flight Data Pipeline - Optimized Analytical Queries (Part 2)
-- Additional analytical queries 7-10 for comprehensive flight data analysis

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- QUERY 7: AIRCRAFT PERFORMANCE ANALYSIS
-- =============================================================================

-- Analyze aircraft performance characteristics and efficiency metrics
-- Cost optimization: Focuses on recent data, uses efficient aggregations
WITH aircraft_performance AS (
    SELECT 
        p.icao24,
        a.model as aircraft_model,
        a.manufacturername as manufacturer,
        a.icaoaircrafttype as aircraft_type,
        
        -- Flight count and activity
        COUNT(*) as total_observations,
        COUNT(DISTINCT DATE(from_unixtime(p.collection_time))) as active_days,
        
        -- Performance metrics
        AVG(p.baro_altitude_ft) as avg_cruise_altitude_ft,
        MAX(p.baro_altitude_ft) as max_altitude_ft,
        AVG(p.velocity_knots) as avg_speed_knots,
        MAX(p.velocity_knots) as max_speed_knots,
        STDDEV(p.velocity_knots) as speed_consistency,
        
        -- Operational characteristics
        AVG(CASE WHEN p.flight_phase = 'Cruise' THEN p.velocity_knots END) as avg_cruise_speed,
        AVG(CASE WHEN p.flight_phase = 'Climb' THEN p.vertical_rate_fpm END) as avg_climb_rate_fpm,
        AVG(CASE WHEN p.flight_phase = 'Descent' THEN ABS(p.vertical_rate_fpm) END) as avg_descent_rate_fpm,
        
        -- Efficiency indicators
        AVG(p.velocity_knots) / NULLIF(AVG(p.baro_altitude_ft), 0) * 1000 as speed_to_altitude_ratio,
        COUNT(CASE WHEN p.flight_phase = 'Cruise' THEN 1 END) / NULLIF(COUNT(*), 0) as cruise_time_ratio,
        
        -- Data quality for this aircraft
        AVG(p.data_quality_score) as avg_data_quality,
        MIN(p.data_quality_score) as min_data_quality,
        
        -- Geographic activity
        COUNT(DISTINCT p.origin_country) as countries_visited,
        STDDEV(p.latitude) + STDDEV(p.longitude) as geographic_spread
        
    FROM processed_flight_data p
    LEFT JOIN aircraft_reference a ON p.icao24 = a.icao24
    WHERE 
        p.year = year(current_date)
        AND p.month = month(current_date) 
        AND p.day >= day(current_date) - 7  -- Last week
        AND NOT p.on_ground
        AND p.data_quality_score > 0.7
        AND p.baro_altitude_ft > 1000  -- Exclude ground operations
        
    GROUP BY 
        p.icao24, a.model, a.manufacturername, a.icaoaircrafttype
        
    HAVING 
        COUNT(*) >= 20  -- Minimum observations for statistical validity
),
performance_rankings AS (
    SELECT 
        *,
        -- Performance rankings
        RANK() OVER (ORDER BY avg_cruise_speed DESC) as speed_rank,
        RANK() OVER (ORDER BY max_altitude_ft DESC) as altitude_rank,
        RANK() OVER (ORDER BY avg_climb_rate_fpm DESC) as climb_rank,
        RANK() OVER (ORDER BY speed_consistency ASC) as consistency_rank,
        
        -- Aircraft class based on performance
        CASE 
            WHEN avg_cruise_speed > 500 AND max_altitude_ft > 40000 THEN 'High Performance Jet'
            WHEN avg_cruise_speed > 400 AND max_altitude_ft > 30000 THEN 'Commercial Airliner'
            WHEN avg_cruise_speed > 300 AND max_altitude_ft > 20000 THEN 'Regional Aircraft'
            WHEN avg_cruise_speed > 200 THEN 'Light Aircraft'
            ELSE 'Low Performance'
        END as performance_class,
        
        -- Efficiency score (normalized combination of metrics)
        (COALESCE(avg_cruise_speed, 0) / 600.0 + 
         COALESCE(max_altitude_ft, 0) / 50000.0 + 
         COALESCE(avg_climb_rate_fpm, 0) / 3000.0 +
         (1 - COALESCE(speed_consistency, 100) / 100.0)) / 4.0 as efficiency_score
         
    FROM aircraft_performance
)
SELECT 
    'Aircraft Performance Analysis' as report_type,
    
    -- Aircraft identification
    icao24,
    COALESCE(aircraft_model, 'Unknown Model') as aircraft_model,
    COALESCE(manufacturer, 'Unknown Manufacturer') as manufacturer,
    COALESCE(aircraft_type, 'Unknown Type') as aircraft_type,
    performance_class,
    
    -- Activity metrics  
    total_observations,
    active_days,
    ROUND(total_observations / NULLIF(active_days, 0), 1) as avg_observations_per_day,
    
    -- Performance metrics
    ROUND(avg_cruise_altitude_ft, 0) as avg_cruise_altitude_ft,
    ROUND(max_altitude_ft, 0) as max_altitude_ft,
    ROUND(avg_speed_knots, 0) as avg_speed_knots,
    ROUND(max_speed_knots, 0) as max_speed_knots,
    ROUND(COALESCE(avg_cruise_speed, 0), 0) as avg_cruise_speed_knots,
    
    -- Operational characteristics
    ROUND(COALESCE(avg_climb_rate_fpm, 0), 0) as avg_climb_rate_fpm,
    ROUND(COALESCE(avg_descent_rate_fpm, 0), 0) as avg_descent_rate_fpm,
    ROUND(cruise_time_ratio * 100, 1) as cruise_time_percentage,
    
    -- Performance rankings
    speed_rank,
    altitude_rank,
    climb_rank,
    consistency_rank,
    
    -- Efficiency metrics
    ROUND(efficiency_score, 3) as efficiency_score,
    ROUND(speed_consistency, 1) as speed_consistency_knots,
    
    -- Operational reach
    countries_visited,
    ROUND(geographic_spread, 2) as geographic_activity_spread,
    
    -- Data quality
    ROUND(avg_data_quality, 3) as avg_data_quality
    
FROM performance_rankings
WHERE efficiency_score IS NOT NULL
ORDER BY efficiency_score DESC, speed_rank ASC
LIMIT 50;

-- =============================================================================
-- QUERY 8: AIRPORT PROXIMITY AND TRAFFIC ANALYSIS
-- =============================================================================

-- Analyze flight traffic near major airports and identify approach/departure patterns
-- Cost optimization: Uses spatial approximation, focuses on major airports
WITH airport_proximity AS (
    SELECT 
        f.icao24,
        f.callsign,
        f.collection_datetime,
        f.longitude,
        f.latitude,
        f.baro_altitude_ft,
        f.velocity_knots,
        f.flight_phase,
        
        -- Find nearest airport using approximate distance
        a.icao_code as nearest_airport_icao,
        a.airport_name as nearest_airport_name,
        a.city as airport_city,
        a.country as airport_country,
        a.latitude as airport_lat,
        a.longitude as airport_lon,
        
        -- Approximate distance calculation (faster than exact spherical distance)
        SQRT(
            POW(69.1 * (f.latitude - a.latitude), 2) + 
            POW(69.1 * (f.longitude - a.longitude) * COS(RADIANS(f.latitude)), 2)
        ) as distance_miles,
        
        -- Bearing from airport (simplified)
        CASE 
            WHEN (f.longitude - a.longitude) > 0 AND (f.latitude - a.latitude) > 0 THEN 'NE'
            WHEN (f.longitude - a.longitude) > 0 AND (f.latitude - a.latitude) < 0 THEN 'SE'  
            WHEN (f.longitude - a.longitude) < 0 AND (f.latitude - a.latitude) > 0 THEN 'NW'
            WHEN (f.longitude - a.longitude) < 0 AND (f.latitude - a.latitude) < 0 THEN 'SW'
            WHEN (f.longitude - a.longitude) = 0 AND (f.latitude - a.latitude) > 0 THEN 'N'
            WHEN (f.longitude - a.longitude) = 0 AND (f.latitude - a.latitude) < 0 THEN 'S'
            WHEN (f.latitude - a.latitude) = 0 AND (f.longitude - a.longitude) > 0 THEN 'E'
            WHEN (f.latitude - a.latitude) = 0 AND (f.longitude - a.longitude) < 0 THEN 'W'
            ELSE 'Unknown'
        END as bearing_from_airport
        
    FROM processed_flight_data f
    CROSS JOIN airport_reference a
    WHERE 
        f.year = year(current_date)
        AND f.month = month(current_date)
        AND f.day = day(current_date)  -- Today only for airport analysis
        AND f.data_quality_score > 0.8
        AND a.airport_type = 'large_airport'  -- Focus on major airports
        -- Pre-filter by approximate geographic bounds for performance
        AND f.latitude BETWEEN a.latitude - 1 AND a.latitude + 1
        AND f.longitude BETWEEN a.longitude - 1 AND a.longitude + 1
        
    HAVING distance_miles <= 50  -- Within 50 miles of airport
),
airport_activity AS (
    SELECT 
        nearest_airport_icao,
        nearest_airport_name,
        airport_city,
        airport_country,
        
        -- Overall activity
        COUNT(*) as total_flights_nearby,
        COUNT(DISTINCT icao24) as unique_aircraft,
        
        -- Distance distribution
        AVG(distance_miles) as avg_distance_miles,
        MIN(distance_miles) as min_distance_miles,
        APPROX_PERCENTILE(distance_miles, 0.25) as q25_distance,
        APPROX_PERCENTILE(distance_miles, 0.75) as q75_distance,
        
        -- Altitude analysis near airport
        AVG(baro_altitude_ft) as avg_altitude_ft,
        MIN(baro_altitude_ft) as min_altitude_ft,
        COUNT(CASE WHEN baro_altitude_ft < 5000 THEN 1 END) as low_altitude_flights,
        COUNT(CASE WHEN baro_altitude_ft < 2000 THEN 1 END) as very_low_altitude_flights,
        
        -- Flight phase distribution
        COUNT(CASE WHEN flight_phase = 'Takeoff' THEN 1 END) as takeoff_count,
        COUNT(CASE WHEN flight_phase = 'Climb' THEN 1 END) as climb_count,
        COUNT(CASE WHEN flight_phase = 'Approach' THEN 1 END) as approach_count,
        COUNT(CASE WHEN flight_phase = 'Descent' THEN 1 END) as descent_count,
        
        -- Directional traffic
        COUNT(CASE WHEN bearing_from_airport = 'N' THEN 1 END) as north_traffic,
        COUNT(CASE WHEN bearing_from_airport = 'S' THEN 1 END) as south_traffic,
        COUNT(CASE WHEN bearing_from_airport = 'E' THEN 1 END) as east_traffic,
        COUNT(CASE WHEN bearing_from_airport = 'W' THEN 1 END) as west_traffic,
        COUNT(CASE WHEN bearing_from_airport IN ('NE', 'NW') THEN 1 END) as north_diagonal_traffic,
        COUNT(CASE WHEN bearing_from_airport IN ('SE', 'SW') THEN 1 END) as south_diagonal_traffic,
        
        -- Speed characteristics near airport
        AVG(velocity_knots) as avg_speed_knots,
        AVG(CASE WHEN distance_miles < 10 THEN velocity_knots END) as avg_speed_close_knots,
        
        -- Airport activity intensity
        COUNT(*) / 24.0 as flights_per_hour,
        (COUNT(CASE WHEN flight_phase IN ('Takeoff', 'Approach') THEN 1 END)) / 24.0 as airport_ops_per_hour
        
    FROM airport_proximity
    GROUP BY 
        nearest_airport_icao, nearest_airport_name, airport_city, airport_country
        
    HAVING COUNT(*) >= 10  -- Minimum activity threshold
)
SELECT 
    'Airport Traffic Analysis' as report_type,
    
    -- Airport identification
    nearest_airport_icao as airport_code,
    nearest_airport_name as airport_name,
    airport_city || ', ' || airport_country as airport_location,
    
    -- Activity metrics
    total_flights_nearby,
    unique_aircraft,
    ROUND(flights_per_hour, 1) as avg_flights_per_hour,
    ROUND(airport_ops_per_hour, 1) as avg_airport_ops_per_hour,
    
    -- Traffic intensity classification
    CASE 
        WHEN flights_per_hour > 50 THEN 'Very High'
        WHEN flights_per_hour > 25 THEN 'High'
        WHEN flights_per_hour > 10 THEN 'Moderate'
        ELSE 'Low'
    END as traffic_intensity,
    
    -- Proximity analysis
    ROUND(avg_distance_miles, 1) as avg_distance_miles,
    ROUND(min_distance_miles, 1) as closest_approach_miles,
    
    -- Altitude profile
    ROUND(avg_altitude_ft, 0) as avg_altitude_ft,
    low_altitude_flights,
    very_low_altitude_flights,
    ROUND(100.0 * low_altitude_flights / total_flights_nearby, 1) as low_altitude_percentage,
    
    -- Airport operations
    takeoff_count,
    approach_count,
    takeoff_count + approach_count as total_airport_ops,
    ROUND(100.0 * (takeoff_count + approach_count) / total_flights_nearby, 1) as airport_ops_percentage,
    
    -- Traffic pattern analysis
    CASE 
        WHEN (north_traffic + north_diagonal_traffic) > (south_traffic + south_diagonal_traffic) THEN 'North Dominant'
        WHEN (south_traffic + south_diagonal_traffic) > (north_traffic + north_diagonal_traffic) THEN 'South Dominant'
        ELSE 'Balanced N-S'
    END as north_south_pattern,
    
    CASE 
        WHEN east_traffic > west_traffic THEN 'East Dominant'
        WHEN west_traffic > east_traffic THEN 'West Dominant' 
        ELSE 'Balanced E-W'
    END as east_west_pattern,
    
    -- Performance near airport
    ROUND(avg_speed_knots, 0) as avg_speed_knots,
    ROUND(COALESCE(avg_speed_close_knots, 0), 0) as avg_speed_close_knots,
    
    -- Airport efficiency indicator
    ROUND(unique_aircraft / NULLIF(flights_per_hour, 0), 1) as aircraft_turnover_ratio
    
FROM airport_activity
ORDER BY flights_per_hour DESC, total_flights_nearby DESC
LIMIT 25;

-- =============================================================================
-- QUERY 9: TEMPORAL FLIGHT PATTERN ANALYSIS  
-- =============================================================================

-- Analyze flight patterns across different time periods
-- Cost optimization: Pre-aggregated time buckets, efficient time calculations
WITH time_buckets AS (
    SELECT 
        year,
        month,
        day,
        hour,
        
        -- Time categorizations
        CASE 
            WHEN hour BETWEEN 0 AND 5 THEN 'Late Night (00-05)'
            WHEN hour BETWEEN 6 AND 11 THEN 'Morning (06-11)'
            WHEN hour BETWEEN 12 AND 17 THEN 'Afternoon (12-17)'
            WHEN hour BETWEEN 18 AND 23 THEN 'Evening (18-23)'
        END as time_period,
        
        -- Day of week approximation (simplified)
        ((day - 1) % 7) + 1 as day_of_week_num,
        CASE 
            WHEN ((day - 1) % 7) + 1 IN (1, 7) THEN 'Weekend'
            ELSE 'Weekday'
        END as day_type,
        
        -- Flight metrics
        COUNT(*) as flight_count,
        COUNT(DISTINCT icao24) as unique_aircraft,
        AVG(baro_altitude_ft) as avg_altitude_ft,
        AVG(velocity_knots) as avg_speed_knots,
        
        -- Phase distribution
        COUNT(CASE WHEN flight_phase = 'Takeoff' THEN 1 END) as takeoff_count,
        COUNT(CASE WHEN flight_phase = 'Climb' THEN 1 END) as climb_count,
        COUNT(CASE WHEN flight_phase = 'Cruise' THEN 1 END) as cruise_count,
        COUNT(CASE WHEN flight_phase = 'Descent' THEN 1 END) as descent_count,
        COUNT(CASE WHEN flight_phase = 'Approach' THEN 1 END) as approach_count,
        
        -- Geographic distribution
        COUNT(CASE WHEN ABS(latitude) < 30 THEN 1 END) as tropical_flights,
        COUNT(CASE WHEN ABS(latitude) BETWEEN 30 AND 60 THEN 1 END) as temperate_flights,
        COUNT(CASE WHEN ABS(latitude) > 60 THEN 1 END) as polar_flights,
        
        -- Quality metrics
        AVG(data_quality_score) as avg_quality_score
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 14  -- Two weeks of data
        AND NOT on_ground
        AND data_quality_score > 0.7
        
    GROUP BY year, month, day, hour
),
temporal_patterns AS (
    SELECT 
        time_period,
        day_type,
        
        -- Aggregated metrics
        SUM(flight_count) as total_flights,
        AVG(flight_count) as avg_flights_per_hour,
        STDDEV(flight_count) as flight_count_variance,
        SUM(unique_aircraft) as total_unique_aircraft,
        
        -- Time-based performance  
        AVG(avg_altitude_ft) as avg_altitude_ft,
        AVG(avg_speed_knots) as avg_speed_knots,
        AVG(avg_quality_score) as avg_quality_score,
        
        -- Phase distribution percentages
        ROUND(100.0 * SUM(takeoff_count) / SUM(flight_count), 2) as takeoff_percentage,
        ROUND(100.0 * SUM(climb_count) / SUM(flight_count), 2) as climb_percentage,
        ROUND(100.0 * SUM(cruise_count) / SUM(flight_count), 2) as cruise_percentage,
        ROUND(100.0 * SUM(descent_count) / SUM(flight_count), 2) as descent_percentage,
        ROUND(100.0 * SUM(approach_count) / SUM(flight_count), 2) as approach_percentage,
        
        -- Geographic distribution
        ROUND(100.0 * SUM(tropical_flights) / SUM(flight_count), 2) as tropical_percentage,
        ROUND(100.0 * SUM(temperate_flights) / SUM(flight_count), 2) as temperate_percentage,
        ROUND(100.0 * SUM(polar_flights) / SUM(flight_count), 2) as polar_percentage,
        
        -- Traffic consistency
        CASE 
            WHEN STDDEV(flight_count) / AVG(flight_count) < 0.2 THEN 'Very Consistent'
            WHEN STDDEV(flight_count) / AVG(flight_count) < 0.4 THEN 'Consistent'
            WHEN STDDEV(flight_count) / AVG(flight_count) < 0.6 THEN 'Variable'
            ELSE 'Highly Variable'
        END as traffic_consistency,
        
        COUNT(*) as sample_hours
        
    FROM time_buckets
    GROUP BY time_period, day_type
),
ranked_patterns AS (
    SELECT 
        *,
        RANK() OVER (ORDER BY total_flights DESC) as traffic_volume_rank,
        RANK() OVER (ORDER BY avg_flights_per_hour DESC) as hourly_intensity_rank
    FROM temporal_patterns
)
SELECT 
    'Temporal Flight Pattern Analysis' as report_type,
    
    -- Time identification
    time_period,
    day_type,
    time_period || ' - ' || day_type as time_category,
    
    -- Traffic volume
    total_flights,
    ROUND(avg_flights_per_hour, 1) as avg_flights_per_hour,
    traffic_volume_rank,
    hourly_intensity_rank,
    
    -- Traffic characteristics
    total_unique_aircraft,
    ROUND(total_flights / NULLIF(total_unique_aircraft, 0), 2) as avg_observations_per_aircraft,
    traffic_consistency,
    ROUND(flight_count_variance, 1) as hourly_variance,
    
    -- Performance characteristics
    ROUND(avg_altitude_ft, 0) as avg_altitude_ft,
    ROUND(avg_speed_knots, 0) as avg_speed_knots,
    ROUND(avg_quality_score, 3) as avg_data_quality,
    
    -- Flight phase distribution
    takeoff_percentage,
    climb_percentage, 
    cruise_percentage,
    descent_percentage,
    approach_percentage,
    
    -- Geographic activity
    tropical_percentage,
    temperate_percentage,
    polar_percentage,
    
    -- Activity level classification
    CASE 
        WHEN avg_flights_per_hour > 2000 THEN 'Peak Hours'
        WHEN avg_flights_per_hour > 1500 THEN 'High Activity'
        WHEN avg_flights_per_hour > 1000 THEN 'Moderate Activity'
        WHEN avg_flights_per_hour > 500 THEN 'Low Activity'
        ELSE 'Minimal Activity'
    END as activity_level,
    
    sample_hours
    
FROM ranked_patterns
ORDER BY traffic_volume_rank;

-- =============================================================================
-- QUERY 10: COMPREHENSIVE FLIGHT DATA QUALITY ASSESSMENT
-- =============================================================================

-- Comprehensive quality assessment across all data dimensions
-- Cost optimization: Uses quality metrics table, focused time range
WITH quality_assessment AS (
    SELECT 
        -- Time dimensions
        year,
        month, 
        day,
        year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') as assessment_date,
        
        -- Volume assessment
        SUM(total_records) as daily_total_records,
        SUM(valid_records) as daily_valid_records,
        SUM(invalid_records) as daily_invalid_records,
        SUM(duplicate_records) as daily_duplicate_records,
        
        -- Quality scores
        AVG(overall_quality_score) as avg_overall_quality,
        MIN(overall_quality_score) as min_overall_quality,
        STDDEV(overall_quality_score) as quality_variance,
        
        -- Dimensional quality scores
        AVG(completeness_score) as avg_completeness,
        AVG(validity_score) as avg_validity,
        AVG(consistency_score) as avg_consistency,
        AVG(timeliness_score) as avg_timeliness,
        AVG(accuracy_score) as avg_accuracy,
        
        -- Issue counts
        SUM(missing_icao24_count) as total_missing_icao24,
        SUM(missing_position_count) as total_missing_position,
        SUM(missing_altitude_count) as total_missing_altitude,
        SUM(invalid_coordinate_count) as total_invalid_coordinates,
        SUM(invalid_altitude_count) as total_invalid_altitude,
        SUM(invalid_velocity_count) as total_invalid_velocity,
        
        -- Anomaly totals
        SUM(altitude_anomaly_count) as total_altitude_anomalies,
        SUM(velocity_anomaly_count) as total_velocity_anomalies,
        SUM(position_anomaly_count) as total_position_anomalies,
        SUM(temporal_anomaly_count) as total_temporal_anomalies,
        
        -- Performance metrics
        AVG(processing_duration_ms) as avg_processing_time_ms,
        AVG(api_response_time_ms) as avg_api_response_time_ms,
        AVG(compression_ratio) as avg_compression_ratio,
        
        COUNT(*) as batch_count
        
    FROM data_quality_metrics
    WHERE 
        year = year(current_date)
        AND month = month(current_date) 
        AND day >= day(current_date) - 30  -- Last 30 days
        
    GROUP BY year, month, day
),
quality_trends AS (
    SELECT 
        *,
        -- Quality trend indicators (comparison with previous day)
        LAG(avg_overall_quality) OVER (ORDER BY year, month, day) as prev_day_quality,
        avg_overall_quality - LAG(avg_overall_quality) OVER (ORDER BY year, month, day) as quality_change,
        
        -- Volume trends
        LAG(daily_total_records) OVER (ORDER BY year, month, day) as prev_day_records,
        
        -- Data health score (weighted composite)
        (avg_completeness * 0.25 + 
         avg_validity * 0.25 + 
         avg_consistency * 0.20 + 
         avg_timeliness * 0.15 + 
         avg_accuracy * 0.15) as data_health_score,
         
        -- Issue rate calculations
        ROUND(100.0 * daily_invalid_records / NULLIF(daily_total_records, 0), 2) as invalid_rate_pct,
        ROUND(100.0 * daily_duplicate_records / NULLIF(daily_total_records, 0), 2) as duplicate_rate_pct,
        
        -- Missing data rates
        ROUND(100.0 * total_missing_icao24 / NULLIF(daily_total_records, 0), 2) as missing_icao24_pct,
        ROUND(100.0 * total_missing_position / NULLIF(daily_total_records, 0), 2) as missing_position_pct
        
    FROM quality_assessment
),
quality_classification AS (
    SELECT 
        *,
        -- Overall quality grade
        CASE 
            WHEN avg_overall_quality >= 0.95 THEN 'A+ (Excellent)'
            WHEN avg_overall_quality >= 0.90 THEN 'A (Very Good)'
            WHEN avg_overall_quality >= 0.85 THEN 'B+ (Good)'
            WHEN avg_overall_quality >= 0.80 THEN 'B (Acceptable)'
            WHEN avg_overall_quality >= 0.75 THEN 'C+ (Fair)'
            WHEN avg_overall_quality >= 0.70 THEN 'C (Marginal)'
            WHEN avg_overall_quality >= 0.60 THEN 'D (Poor)'
            ELSE 'F (Critical)'
        END as quality_grade,
        
        -- Data health classification
        CASE 
            WHEN data_health_score >= 0.90 THEN 'Excellent Health'
            WHEN data_health_score >= 0.80 THEN 'Good Health'
            WHEN data_health_score >= 0.70 THEN 'Fair Health'
            WHEN data_health_score >= 0.60 THEN 'Poor Health'
            ELSE 'Critical Health'
        END as health_status,
        
        -- Trend classification
        CASE 
            WHEN quality_change > 0.05 THEN 'Improving'
            WHEN quality_change > 0.01 THEN 'Slightly Improving'
            WHEN quality_change >= -0.01 THEN 'Stable'
            WHEN quality_change >= -0.05 THEN 'Slightly Declining'
            ELSE 'Declining'
        END as quality_trend
        
    FROM quality_trends
)
SELECT 
    'Comprehensive Data Quality Assessment' as report_type,
    assessment_date,
    
    -- Volume metrics
    daily_total_records,
    daily_valid_records,
    daily_invalid_records,
    batch_count as processing_batches,
    
    -- Quality scores and grades
    ROUND(avg_overall_quality, 4) as overall_quality_score,
    quality_grade,
    ROUND(data_health_score, 4) as data_health_score,
    health_status,
    
    -- Quality dimensions
    ROUND(avg_completeness, 3) as completeness_score,
    ROUND(avg_validity, 3) as validity_score,
    ROUND(avg_consistency, 3) as consistency_score,
    ROUND(avg_timeliness, 3) as timeliness_score,
    ROUND(avg_accuracy, 3) as accuracy_score,
    
    -- Issue rates
    invalid_rate_pct as invalid_record_percentage,
    duplicate_rate_pct as duplicate_record_percentage,
    missing_icao24_pct as missing_aircraft_id_percentage,
    missing_position_pct as missing_position_percentage,
    
    -- Anomaly summary
    total_altitude_anomalies,
    total_velocity_anomalies,
    total_position_anomalies,
    total_temporal_anomalies,
    total_altitude_anomalies + total_velocity_anomalies + total_position_anomalies + total_temporal_anomalies as total_anomalies,
    
    -- Performance indicators
    ROUND(avg_processing_time_ms, 0) as avg_processing_time_ms,
    ROUND(avg_api_response_time_ms, 0) as avg_api_response_time_ms,
    ROUND(avg_compression_ratio, 2) as avg_compression_ratio,
    
    -- Trend analysis
    quality_trend,
    ROUND(COALESCE(quality_change, 0), 4) as quality_score_change,
    
    -- Quality flags and recommendations
    CONCAT_WS('; ',
        CASE WHEN invalid_rate_pct > 10 THEN 'High Invalid Rate' END,
        CASE WHEN duplicate_rate_pct > 5 THEN 'High Duplicate Rate' END,
        CASE WHEN missing_icao24_pct > 2 THEN 'Missing Aircraft IDs' END,
        CASE WHEN missing_position_pct > 5 THEN 'Missing Position Data' END,
        CASE WHEN avg_processing_time_ms > 10000 THEN 'Slow Processing' END,
        CASE WHEN total_anomalies > 1000 THEN 'High Anomaly Rate' END
    ) as quality_alerts,
    
    -- Overall assessment
    CASE 
        WHEN avg_overall_quality >= 0.85 AND quality_trend IN ('Improving', 'Stable') THEN 'System Performing Well'
        WHEN avg_overall_quality >= 0.75 AND quality_trend != 'Declining' THEN 'Acceptable Performance'
        WHEN avg_overall_quality >= 0.65 THEN 'Needs Attention'
        ELSE 'Critical Issues - Immediate Action Required'
    END as overall_assessment
    
FROM quality_classification
WHERE assessment_date IS NOT NULL
ORDER BY assessment_date DESC
LIMIT 30;