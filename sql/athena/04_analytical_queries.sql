-- Flight Data Pipeline - Optimized Analytical Queries
-- Collection of 10 optimized queries for flight data analytics

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- QUERY 1: CURRENT FLIGHT STATUS OVERVIEW
-- =============================================================================

-- Real-time flight status dashboard with key metrics
-- Cost optimization: Uses partition pruning and selective columns
WITH current_flights AS (
    SELECT 
        icao24,
        callsign,
        origin_country,
        longitude,
        latitude,
        baro_altitude_ft,
        velocity_knots,
        on_ground,
        altitude_category,
        speed_category,
        flight_phase,
        data_quality_score
    FROM processed_flight_data
    WHERE 
        -- Partition pruning: only current hour
        year = year(current_date)
        AND month = month(current_date)
        AND day = day(current_date)
        AND hour = hour(current_timestamp)
        -- Quality filter to reduce data volume
        AND data_quality_score > 0.7
        AND NOT on_ground  -- Active flights only
)
SELECT 
    'Flight Status Overview' as report_type,
    current_timestamp as report_time,
    
    -- Summary statistics
    COUNT(*) as total_active_flights,
    COUNT(DISTINCT origin_country) as countries_active,
    
    -- Altitude distribution
    SUM(CASE WHEN altitude_category = 'Low' THEN 1 ELSE 0 END) as low_altitude_flights,
    SUM(CASE WHEN altitude_category = 'Medium' THEN 1 ELSE 0 END) as medium_altitude_flights,
    SUM(CASE WHEN altitude_category = 'High' THEN 1 ELSE 0 END) as high_altitude_flights,
    SUM(CASE WHEN altitude_category = 'Very High' THEN 1 ELSE 0 END) as very_high_altitude_flights,
    
    -- Speed distribution
    SUM(CASE WHEN speed_category = 'Slow' THEN 1 ELSE 0 END) as slow_flights,
    SUM(CASE WHEN speed_category = 'Normal' THEN 1 ELSE 0 END) as normal_speed_flights,
    SUM(CASE WHEN speed_category = 'Fast' THEN 1 ELSE 0 END) as fast_flights,
    SUM(CASE WHEN speed_category = 'Very Fast' THEN 1 ELSE 0 END) as very_fast_flights,
    
    -- Flight phase distribution
    SUM(CASE WHEN flight_phase = 'Takeoff' THEN 1 ELSE 0 END) as takeoff_flights,
    SUM(CASE WHEN flight_phase = 'Climb' THEN 1 ELSE 0 END) as climb_flights,
    SUM(CASE WHEN flight_phase = 'Cruise' THEN 1 ELSE 0 END) as cruise_flights,
    SUM(CASE WHEN flight_phase = 'Descent' THEN 1 ELSE 0 END) as descent_flights,
    SUM(CASE WHEN flight_phase = 'Approach' THEN 1 ELSE 0 END) as approach_flights,
    
    -- Quality metrics
    AVG(data_quality_score) as avg_quality_score,
    MIN(data_quality_score) as min_quality_score,
    
    -- Performance metrics
    AVG(baro_altitude_ft) as avg_altitude_ft,
    MAX(baro_altitude_ft) as max_altitude_ft,
    AVG(velocity_knots) as avg_speed_knots,
    MAX(velocity_knots) as max_speed_knots
FROM current_flights;

-- =============================================================================
-- QUERY 2: FLIGHT DISTRIBUTION BY ALTITUDE BANDS
-- =============================================================================

-- Detailed altitude analysis with statistical insights
-- Cost optimization: Aggregates data at source, uses approximate functions
SELECT 
    'Altitude Distribution Analysis' as report_type,
    
    -- Altitude bands (more granular than categories)
    CASE 
        WHEN baro_altitude_ft < 1000 THEN 'Surface (0-1K ft)'
        WHEN baro_altitude_ft < 5000 THEN 'Low (1-5K ft)'  
        WHEN baro_altitude_ft < 10000 THEN 'Medium-Low (5-10K ft)'
        WHEN baro_altitude_ft < 20000 THEN 'Medium (10-20K ft)'
        WHEN baro_altitude_ft < 30000 THEN 'Medium-High (20-30K ft)'
        WHEN baro_altitude_ft < 40000 THEN 'High (30-40K ft)'
        WHEN baro_altitude_ft < 50000 THEN 'Very High (40-50K ft)'
        ELSE 'Extreme (50K+ ft)'
    END as altitude_band,
    
    -- Flight counts
    COUNT(*) as flight_count,
    COUNT(DISTINCT icao24) as unique_aircraft,
    
    -- Percentage of total
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage_of_total,
    
    -- Speed characteristics by altitude
    AVG(velocity_knots) as avg_speed_knots,
    STDDEV(velocity_knots) as speed_stddev,
    
    -- Flight phase distribution
    SUM(CASE WHEN flight_phase = 'Cruise' THEN 1 ELSE 0 END) as cruise_count,
    SUM(CASE WHEN flight_phase = 'Climb' THEN 1 ELSE 0 END) as climb_count,
    SUM(CASE WHEN flight_phase = 'Descent' THEN 1 ELSE 0 END) as descent_count,
    
    -- Data quality by altitude
    AVG(data_quality_score) as avg_quality_score,
    
    -- Statistical measures
    MIN(baro_altitude_ft) as min_altitude_ft,
    MAX(baro_altitude_ft) as max_altitude_ft,
    APPROX_PERCENTILE(baro_altitude_ft, 0.5) as median_altitude_ft,
    APPROX_PERCENTILE(baro_altitude_ft, 0.95) as p95_altitude_ft
    
FROM processed_flight_data
WHERE 
    -- Last 24 hours with partition pruning
    year = year(current_date)
    AND month = month(current_date)
    AND day >= day(current_date) - 1
    AND NOT on_ground
    AND baro_altitude_ft IS NOT NULL
    AND baro_altitude_ft > 0
    AND data_quality_score > 0.6
    
GROUP BY 
    CASE 
        WHEN baro_altitude_ft < 1000 THEN 'Surface (0-1K ft)'
        WHEN baro_altitude_ft < 5000 THEN 'Low (1-5K ft)'
        WHEN baro_altitude_ft < 10000 THEN 'Medium-Low (5-10K ft)'
        WHEN baro_altitude_ft < 20000 THEN 'Medium (10-20K ft)'
        WHEN baro_altitude_ft < 30000 THEN 'Medium-High (20-30K ft)'
        WHEN baro_altitude_ft < 40000 THEN 'High (30-40K ft)'
        WHEN baro_altitude_ft < 50000 THEN 'Very High (40-50K ft)'
        ELSE 'Extreme (50K+ ft)'
    END
    
ORDER BY 
    MIN(baro_altitude_ft);

-- =============================================================================
-- QUERY 3: DATA QUALITY METRICS BY HOUR
-- =============================================================================

-- Hourly data quality trend analysis for monitoring and alerting
-- Cost optimization: Pre-aggregated quality metrics table, time-based partitioning
SELECT 
    'Hourly Data Quality Report' as report_type,
    year,
    month, 
    day,
    LPAD(CAST(hour AS varchar), 2, '0') as hour_padded,
    year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') || ' ' || LPAD(CAST(hour AS varchar), 2, '0') || ':00:00' as datetime_hour,
    
    -- Volume metrics
    SUM(total_records) as total_records_processed,
    SUM(valid_records) as total_valid_records,
    SUM(invalid_records) as total_invalid_records,
    
    -- Quality percentages
    ROUND(100.0 * SUM(valid_records) / NULLIF(SUM(total_records), 0), 2) as valid_record_percentage,
    ROUND(100.0 * SUM(invalid_records) / NULLIF(SUM(total_records), 0), 2) as invalid_record_percentage,
    
    -- Average quality scores
    AVG(overall_quality_score) as avg_overall_quality,
    AVG(completeness_score) as avg_completeness,
    AVG(validity_score) as avg_validity,
    AVG(consistency_score) as avg_consistency,
    AVG(timeliness_score) as avg_timeliness,
    
    -- Quality score distribution
    APPROX_PERCENTILE(overall_quality_score, 0.5) as median_quality_score,
    APPROX_PERCENTILE(overall_quality_score, 0.25) as q25_quality_score,
    APPROX_PERCENTILE(overall_quality_score, 0.75) as q75_quality_score,
    MIN(overall_quality_score) as min_quality_score,
    
    -- Issue counts
    SUM(missing_icao24_count) as total_missing_icao24,
    SUM(missing_position_count) as total_missing_position,
    SUM(invalid_coordinate_count) as total_invalid_coordinates,
    
    -- Anomaly detection summary
    SUM(altitude_anomaly_count) as total_altitude_anomalies,
    SUM(velocity_anomaly_count) as total_velocity_anomalies,
    SUM(position_anomaly_count) as total_position_anomalies,
    
    -- Performance metrics
    AVG(processing_duration_ms) as avg_processing_time_ms,
    AVG(api_response_time_ms) as avg_api_response_time_ms,
    AVG(compression_ratio) as avg_compression_ratio,
    
    -- Quality flags
    CASE 
        WHEN AVG(overall_quality_score) >= 0.9 THEN 'Excellent'
        WHEN AVG(overall_quality_score) >= 0.8 THEN 'Good'  
        WHEN AVG(overall_quality_score) >= 0.7 THEN 'Fair'
        WHEN AVG(overall_quality_score) >= 0.6 THEN 'Poor'
        ELSE 'Critical'
    END as quality_grade
    
FROM data_quality_metrics
WHERE 
    -- Last 7 days for trending
    year = year(current_date)
    AND month = month(current_date)
    AND day >= day(current_date) - 7
    
GROUP BY year, month, day, hour
ORDER BY year DESC, month DESC, day DESC, hour DESC
LIMIT 168; -- 7 days * 24 hours

-- =============================================================================
-- QUERY 4: PEAK TRAFFIC ANALYSIS
-- =============================================================================

-- Identify peak traffic patterns and congestion hotspots
-- Cost optimization: Uses windowing functions efficiently, limited time range
WITH hourly_traffic AS (
    SELECT 
        year,
        month,
        day,
        hour,
        COUNT(*) as flight_count,
        COUNT(DISTINCT icao24) as unique_aircraft,
        AVG(velocity_knots) as avg_speed,
        COUNT(CASE WHEN flight_phase = 'Takeoff' THEN 1 END) as takeoff_count,
        COUNT(CASE WHEN flight_phase = 'Approach' THEN 1 END) as approach_count,
        -- Geographic concentration 
        COUNT(CASE WHEN ABS(latitude) BETWEEN 40 AND 50 AND ABS(longitude) BETWEEN 70 AND 130 THEN 1 END) as europe_na_corridor
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date) 
        AND day >= day(current_date) - 7  -- Last 7 days
        AND NOT on_ground
        AND data_quality_score > 0.7
    GROUP BY year, month, day, hour
),
traffic_with_ranking AS (
    SELECT 
        *,
        -- Ranking by traffic volume
        RANK() OVER (ORDER BY flight_count DESC) as traffic_rank,
        -- Moving average for trend analysis
        AVG(flight_count) OVER (
            ORDER BY year, month, day, hour 
            ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
        ) as moving_avg_traffic,
        -- Hour of day pattern
        hour as hour_of_day,
        -- Day of week calculation (approximate)
        ((day - 1) % 7) + 1 as day_of_week_approx
    FROM hourly_traffic
)
SELECT 
    'Peak Traffic Analysis' as report_type,
    
    -- Time identification
    year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') || ' ' || LPAD(CAST(hour AS varchar), 2, '0') || ':00' as peak_datetime,
    
    traffic_rank,
    flight_count as peak_flight_count,
    unique_aircraft as peak_unique_aircraft,
    
    -- Traffic intensity
    ROUND(flight_count / 60.0, 1) as flights_per_minute,
    CASE 
        WHEN flight_count > 5000 THEN 'Extreme'
        WHEN flight_count > 3000 THEN 'Very High'
        WHEN flight_count > 2000 THEN 'High'
        WHEN flight_count > 1000 THEN 'Moderate'
        ELSE 'Low'
    END as traffic_intensity,
    
    -- Speed analysis during peak
    ROUND(avg_speed, 1) as avg_speed_knots,
    CASE 
        WHEN avg_speed < 400 THEN 'Congested'
        WHEN avg_speed < 450 THEN 'Normal'
        ELSE 'Free Flow'
    END as traffic_flow_status,
    
    -- Airport activity indicators  
    takeoff_count,
    approach_count,
    takeoff_count + approach_count as total_airport_activity,
    
    -- Geographic concentration
    europe_na_corridor as high_traffic_corridor_flights,
    ROUND(100.0 * europe_na_corridor / flight_count, 1) as corridor_concentration_pct,
    
    -- Trend information
    ROUND(moving_avg_traffic, 0) as moving_avg_traffic,
    ROUND(flight_count - moving_avg_traffic, 0) as deviation_from_avg,
    
    -- Time pattern analysis
    hour_of_day,
    CASE 
        WHEN hour_of_day BETWEEN 6 AND 10 THEN 'Morning Peak'
        WHEN hour_of_day BETWEEN 11 AND 15 THEN 'Midday'  
        WHEN hour_of_day BETWEEN 16 AND 20 THEN 'Evening Peak'
        WHEN hour_of_day BETWEEN 21 AND 23 THEN 'Night'
        ELSE 'Late Night/Early Morning'
    END as time_period,
    
    day_of_week_approx,
    CASE 
        WHEN day_of_week_approx IN (1, 7) THEN 'Weekend'
        ELSE 'Weekday'
    END as day_type
    
FROM traffic_with_ranking
WHERE traffic_rank <= 20  -- Top 20 peak traffic hours
ORDER BY traffic_rank;

-- =============================================================================
-- QUERY 5: ROUTE CORRIDOR IDENTIFICATION
-- =============================================================================

-- Identify major flight corridors and route patterns
-- Cost optimization: Geographic clustering, limited precision for performance
WITH geographic_grid AS (
    SELECT 
        icao24,
        callsign,
        -- Grid cell approach for route corridor identification
        ROUND(latitude / 2.0) * 2 as lat_grid,  -- 2-degree grid cells
        ROUND(longitude / 2.0) * 2 as lon_grid,
        baro_altitude_ft,
        velocity_knots,
        true_track,
        flight_phase,
        year, month, day, hour
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 3  -- 3 days for route pattern analysis
        AND NOT on_ground
        AND latitude IS NOT NULL 
        AND longitude IS NOT NULL
        AND data_quality_score > 0.8
        -- Focus on cruise altitude for clearer route patterns
        AND flight_phase = 'Cruise'
        AND baro_altitude_ft > 20000
),
corridor_analysis AS (
    SELECT 
        lat_grid,
        lon_grid,
        -- Geographic center of grid cell
        lat_grid as corridor_lat,
        lon_grid as corridor_lon,
        
        -- Traffic metrics
        COUNT(*) as total_flights,
        COUNT(DISTINCT icao24) as unique_aircraft,
        COUNT(DISTINCT callsign) as unique_flights,
        
        -- Directional analysis
        AVG(true_track) as avg_heading_degrees,
        STDDEV(true_track) as heading_variance,
        
        -- Altitude characteristics
        AVG(baro_altitude_ft) as avg_cruise_altitude,
        STDDEV(baro_altitude_ft) as altitude_variance,
        MIN(baro_altitude_ft) as min_altitude,
        MAX(baro_altitude_ft) as max_altitude,
        
        -- Speed characteristics  
        AVG(velocity_knots) as avg_speed_knots,
        STDDEV(velocity_knots) as speed_variance,
        
        -- Traffic density (flights per hour)
        COUNT(*) / (3.0 * 24.0) as flights_per_hour,
        
        -- Route consistency score (lower variance = more consistent route)
        (1.0 / (1.0 + COALESCE(STDDEV(true_track), 0) / 180.0)) as route_consistency_score
        
    FROM geographic_grid
    GROUP BY lat_grid, lon_grid
    HAVING COUNT(*) >= 50  -- Minimum flight threshold for corridor identification
),
major_corridors AS (
    SELECT 
        *,
        -- Corridor importance ranking
        RANK() OVER (ORDER BY total_flights DESC) as corridor_rank,
        
        -- Geographic region identification
        CASE 
            WHEN corridor_lat BETWEEN 30 AND 60 AND corridor_lon BETWEEN -130 AND -60 THEN 'North America'
            WHEN corridor_lat BETWEEN 40 AND 70 AND corridor_lon BETWEEN -10 AND 40 THEN 'Europe'
            WHEN corridor_lat BETWEEN 20 AND 50 AND corridor_lon BETWEEN 100 AND 140 THEN 'East Asia'
            WHEN corridor_lat BETWEEN 30 AND 50 AND corridor_lon BETWEEN 40 AND 80 THEN 'Central Asia/Middle East'
            WHEN corridor_lat BETWEEN -40 AND -10 AND corridor_lon BETWEEN 110 AND 160 THEN 'Australia/Oceania'
            WHEN corridor_lat BETWEEN -40 AND 10 AND corridor_lon BETWEEN -80 AND -30 THEN 'South America'
            WHEN corridor_lat BETWEEN -40 AND 40 AND corridor_lon BETWEEN -20 AND 60 THEN 'Africa'
            ELSE 'Other/Oceanic'
        END as geographic_region,
        
        -- Traffic classification
        CASE 
            WHEN total_flights > 1000 THEN 'Major International Corridor'
            WHEN total_flights > 500 THEN 'Regional Corridor'  
            WHEN total_flights > 200 THEN 'Secondary Route'
            ELSE 'Local Route'
        END as corridor_type
        
    FROM corridor_analysis
)
SELECT 
    'Route Corridor Analysis' as report_type,
    corridor_rank,
    
    -- Geographic identification
    ROUND(corridor_lat, 1) as corridor_center_lat,
    ROUND(corridor_lon, 1) as corridor_center_lon,
    geographic_region,
    corridor_type,
    
    -- Traffic characteristics
    total_flights,
    unique_aircraft,
    unique_flights,
    ROUND(flights_per_hour, 1) as avg_flights_per_hour,
    
    -- Route characteristics
    ROUND(avg_heading_degrees, 0) as avg_heading_deg,
    ROUND(heading_variance, 1) as heading_variance_deg,
    ROUND(route_consistency_score, 3) as route_consistency,
    
    -- Cardinal direction
    CASE 
        WHEN avg_heading_degrees BETWEEN 315 OR avg_heading_degrees <= 45 THEN 'North'
        WHEN avg_heading_degrees BETWEEN 45 AND 135 THEN 'East'
        WHEN avg_heading_degrees BETWEEN 135 AND 225 THEN 'South'
        WHEN avg_heading_degrees BETWEEN 225 AND 315 THEN 'West'
    END as primary_direction,
    
    -- Altitude profile
    ROUND(avg_cruise_altitude / 1000, 0) as avg_altitude_1000ft,
    ROUND(altitude_variance / 1000, 1) as altitude_spread_1000ft,
    
    -- Speed profile
    ROUND(avg_speed_knots, 0) as avg_speed_kts,
    ROUND(speed_variance, 1) as speed_variance_kts,
    
    -- Efficiency indicators
    CASE 
        WHEN route_consistency_score > 0.8 THEN 'Highly Structured'
        WHEN route_consistency_score > 0.6 THEN 'Well Defined'
        WHEN route_consistency_score > 0.4 THEN 'Moderately Defined'
        ELSE 'Dispersed'
    END as route_structure,
    
    -- Congestion indicator
    CASE 
        WHEN flights_per_hour > 20 THEN 'High Density'
        WHEN flights_per_hour > 10 THEN 'Medium Density'
        WHEN flights_per_hour > 5 THEN 'Low Density'  
        ELSE 'Very Low Density'
    END as traffic_density
    
FROM major_corridors
WHERE corridor_rank <= 25  -- Top 25 corridors
ORDER BY corridor_rank;

-- =============================================================================  
-- QUERY 6: ANOMALY DETECTION - UNUSUAL FLIGHT PATTERNS
-- =============================================================================

-- Detect anomalous flight patterns using statistical methods
-- Cost optimization: Uses approximate percentiles, focuses on recent data
WITH flight_statistics AS (
    SELECT 
        -- Statistical baselines for anomaly detection
        APPROX_PERCENTILE(baro_altitude_ft, 0.05) as altitude_p05,
        APPROX_PERCENTILE(baro_altitude_ft, 0.95) as altitude_p95,
        APPROX_PERCENTILE(velocity_knots, 0.05) as speed_p05,
        APPROX_PERCENTILE(velocity_knots, 0.95) as speed_p95,
        AVG(baro_altitude_ft) as avg_altitude,
        AVG(velocity_knots) as avg_speed,
        STDDEV(baro_altitude_ft) as altitude_stddev,
        STDDEV(velocity_knots) as speed_stddev
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 1  -- 24 hour baseline
        AND NOT on_ground
        AND data_quality_score > 0.8
),
anomaly_candidates AS (
    SELECT 
        f.icao24,
        f.callsign,
        f.origin_country,
        f.collection_datetime,
        f.longitude,
        f.latitude,
        f.baro_altitude_ft,
        f.velocity_knots,
        f.vertical_rate_fpm,
        f.flight_phase,
        f.data_quality_score,
        
        -- Z-score calculations for anomaly detection
        ABS(f.baro_altitude_ft - s.avg_altitude) / s.altitude_stddev as altitude_zscore,
        ABS(f.velocity_knots - s.avg_speed) / s.speed_stddev as speed_zscore,
        
        -- Percentile-based anomaly flags
        CASE WHEN f.baro_altitude_ft < s.altitude_p05 OR f.baro_altitude_ft > s.altitude_p95 THEN 1 ELSE 0 END as altitude_outlier,
        CASE WHEN f.velocity_knots < s.speed_p05 OR f.velocity_knots > s.speed_p95 THEN 1 ELSE 0 END as speed_outlier,
        
        -- Extreme values
        CASE WHEN f.baro_altitude_ft > 50000 THEN 1 ELSE 0 END as extreme_altitude,
        CASE WHEN f.velocity_knots > 600 THEN 1 ELSE 0 END as extreme_speed,
        CASE WHEN ABS(f.vertical_rate_fpm) > 3000 THEN 1 ELSE 0 END as extreme_vertical_rate,
        
        -- Geographic anomalies (unusual positions)
        CASE WHEN ABS(f.latitude) > 80 THEN 1 ELSE 0 END as polar_flight,
        CASE WHEN f.longitude BETWEEN -180 AND 180 AND ABS(f.longitude) < 1 AND ABS(f.latitude) < 1 THEN 1 ELSE 0 END as zero_coordinate,
        
        s.avg_altitude,
        s.avg_speed
        
    FROM processed_flight_data f
    CROSS JOIN flight_statistics s
    WHERE 
        f.year = year(current_date)
        AND f.month = month(current_date)
        AND f.day = day(current_date)
        AND f.hour >= hour(current_timestamp) - 2  -- Last 2 hours for real-time anomaly detection  
        AND NOT f.on_ground
        AND f.data_quality_score > 0.7
)
SELECT 
    'Flight Anomaly Detection' as report_type,
    current_timestamp as analysis_time,
    
    icao24,
    callsign,
    origin_country,
    collection_datetime,
    
    -- Position information
    ROUND(latitude, 4) as latitude,
    ROUND(longitude, 4) as longitude,
    
    -- Anomalous values
    baro_altitude_ft,
    velocity_knots,  
    vertical_rate_fpm,
    flight_phase,
    
    -- Anomaly scores and flags
    ROUND(altitude_zscore, 2) as altitude_z_score,
    ROUND(speed_zscore, 2) as speed_z_score,
    
    -- Specific anomaly types
    CONCAT_WS(', ',
        CASE WHEN altitude_outlier = 1 THEN 'Altitude Outlier' END,
        CASE WHEN speed_outlier = 1 THEN 'Speed Outlier' END,
        CASE WHEN extreme_altitude = 1 THEN 'Extreme Altitude' END,
        CASE WHEN extreme_speed = 1 THEN 'Extreme Speed' END,
        CASE WHEN extreme_vertical_rate = 1 THEN 'Extreme Climb/Descent' END,
        CASE WHEN polar_flight = 1 THEN 'Polar Region Flight' END,
        CASE WHEN zero_coordinate = 1 THEN 'Zero Coordinate' END
    ) as anomaly_types,
    
    -- Risk assessment
    CASE 
        WHEN (altitude_zscore > 3 OR speed_zscore > 3) THEN 'High Risk'
        WHEN (altitude_outlier + speed_outlier + extreme_altitude + extreme_speed) >= 2 THEN 'Medium Risk'
        WHEN (altitude_outlier + speed_outlier) >= 1 THEN 'Low Risk'
        ELSE 'Monitoring'
    END as risk_level,
    
    -- Comparison with normal values
    ROUND((baro_altitude_ft - avg_altitude) / 1000.0, 1) as altitude_deviation_1000ft,
    ROUND(velocity_knots - avg_speed, 0) as speed_deviation_knots,
    
    data_quality_score
    
FROM anomaly_candidates
WHERE 
    -- Filter to significant anomalies only
    (altitude_zscore > 2 OR speed_zscore > 2 OR 
     extreme_altitude = 1 OR extreme_speed = 1 OR extreme_vertical_rate = 1 OR
     polar_flight = 1 OR zero_coordinate = 1)
    
ORDER BY 
    GREATEST(altitude_zscore, speed_zscore) DESC,
    extreme_altitude DESC,
    extreme_speed DESC
    
LIMIT 100;  -- Limit results for performance