-- Flight Data Pipeline - Analytics Views
-- Common analytics views for hourly, daily, and real-time metrics

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- HOURLY SUMMARY STATISTICS VIEW
-- =============================================================================

-- Comprehensive hourly metrics aggregation for dashboard consumption
CREATE OR REPLACE VIEW hourly_flight_summary AS
WITH hourly_metrics AS (
    SELECT 
        year,
        month,
        day,
        hour,
        
        -- Create standardized datetime
        year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') || ' ' || LPAD(CAST(hour AS varchar), 2, '0') || ':00:00' as hour_datetime,
        from_unixtime(unix_timestamp(year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') || ' ' || LPAD(CAST(hour AS varchar), 2, '0') || ':00:00')) as hour_timestamp,
        
        -- Volume metrics
        COUNT(*) as total_flights,
        COUNT(DISTINCT icao24) as unique_aircraft,
        COUNT(DISTINCT callsign) as unique_callsigns,
        COUNT(DISTINCT origin_country) as countries_active,
        
        -- Flight status distribution
        COUNT(CASE WHEN on_ground = true THEN 1 END) as grounded_aircraft,
        COUNT(CASE WHEN on_ground = false THEN 1 END) as airborne_aircraft,
        
        -- Altitude statistics
        AVG(baro_altitude_ft) as avg_altitude_ft,
        MIN(baro_altitude_ft) as min_altitude_ft,
        MAX(baro_altitude_ft) as max_altitude_ft,
        STDDEV(baro_altitude_ft) as altitude_stddev_ft,
        APPROX_PERCENTILE(baro_altitude_ft, 0.5) as median_altitude_ft,
        APPROX_PERCENTILE(baro_altitude_ft, 0.95) as p95_altitude_ft,
        
        -- Speed statistics  
        AVG(velocity_knots) as avg_speed_knots,
        MIN(velocity_knots) as min_speed_knots,
        MAX(velocity_knots) as max_speed_knots,
        STDDEV(velocity_knots) as speed_stddev_knots,
        APPROX_PERCENTILE(velocity_knots, 0.5) as median_speed_knots,
        APPROX_PERCENTILE(velocity_knots, 0.95) as p95_speed_knots,
        
        -- Altitude category distribution
        COUNT(CASE WHEN altitude_category = 'Low' THEN 1 END) as low_altitude_count,
        COUNT(CASE WHEN altitude_category = 'Medium' THEN 1 END) as medium_altitude_count,
        COUNT(CASE WHEN altitude_category = 'High' THEN 1 END) as high_altitude_count,
        COUNT(CASE WHEN altitude_category = 'Very High' THEN 1 END) as very_high_altitude_count,
        
        -- Speed category distribution
        COUNT(CASE WHEN speed_category = 'Slow' THEN 1 END) as slow_speed_count,
        COUNT(CASE WHEN speed_category = 'Normal' THEN 1 END) as normal_speed_count,
        COUNT(CASE WHEN speed_category = 'Fast' THEN 1 END) as fast_speed_count,
        COUNT(CASE WHEN speed_category = 'Very Fast' THEN 1 END) as very_fast_speed_count,
        
        -- Flight phase distribution
        COUNT(CASE WHEN flight_phase = 'Ground' THEN 1 END) as ground_phase_count,
        COUNT(CASE WHEN flight_phase = 'Takeoff' THEN 1 END) as takeoff_phase_count,
        COUNT(CASE WHEN flight_phase = 'Climb' THEN 1 END) as climb_phase_count,
        COUNT(CASE WHEN flight_phase = 'Cruise' THEN 1 END) as cruise_phase_count,
        COUNT(CASE WHEN flight_phase = 'Descent' THEN 1 END) as descent_phase_count,
        COUNT(CASE WHEN flight_phase = 'Approach' THEN 1 END) as approach_phase_count,
        
        -- Geographic distribution (simplified regions)
        COUNT(CASE WHEN latitude BETWEEN 30 AND 70 AND longitude BETWEEN -130 AND -60 THEN 1 END) as north_america_flights,
        COUNT(CASE WHEN latitude BETWEEN 35 AND 70 AND longitude BETWEEN -15 AND 45 THEN 1 END) as europe_flights,
        COUNT(CASE WHEN latitude BETWEEN 20 AND 50 AND longitude BETWEEN 100 AND 150 THEN 1 END) as east_asia_flights,
        COUNT(CASE WHEN latitude BETWEEN -45 AND -10 AND longitude BETWEEN 110 AND 180 THEN 1 END) as oceania_flights,
        
        -- Data quality metrics
        AVG(data_quality_score) as avg_data_quality_score,
        MIN(data_quality_score) as min_data_quality_score,
        COUNT(CASE WHEN data_quality_score >= 0.9 THEN 1 END) as excellent_quality_count,
        COUNT(CASE WHEN data_quality_score >= 0.8 THEN 1 END) as good_quality_count,
        COUNT(CASE WHEN data_quality_score < 0.7 THEN 1 END) as poor_quality_count,
        
        AVG(completeness_score) as avg_completeness_score,
        AVG(validity_score) as avg_validity_score,
        AVG(consistency_score) as avg_consistency_score
        
    FROM processed_flight_data
    WHERE 
        -- Optimized for recent data queries (configurable range)
        data_quality_score > 0.5  -- Basic quality filter
        
    GROUP BY year, month, day, hour
)
SELECT 
    year,
    month,
    day,
    hour,
    hour_datetime,
    hour_timestamp,
    
    -- Volume and activity metrics
    total_flights,
    unique_aircraft,
    unique_callsigns,
    countries_active,
    grounded_aircraft,
    airborne_aircraft,
    
    -- Activity rates
    ROUND(total_flights / 60.0, 2) as flights_per_minute,
    ROUND(100.0 * airborne_aircraft / NULLIF(total_flights, 0), 1) as airborne_percentage,
    
    -- Altitude metrics
    ROUND(avg_altitude_ft, 0) as avg_altitude_ft,
    min_altitude_ft,
    max_altitude_ft,
    ROUND(altitude_stddev_ft, 0) as altitude_stddev_ft,
    ROUND(median_altitude_ft, 0) as median_altitude_ft,
    ROUND(p95_altitude_ft, 0) as p95_altitude_ft,
    
    -- Speed metrics
    ROUND(avg_speed_knots, 0) as avg_speed_knots,
    min_speed_knots,
    max_speed_knots,
    ROUND(speed_stddev_knots, 0) as speed_stddev_knots,
    ROUND(median_speed_knots, 0) as median_speed_knots,
    ROUND(p95_speed_knots, 0) as p95_speed_knots,
    
    -- Distribution percentages - altitude
    ROUND(100.0 * low_altitude_count / NULLIF(total_flights, 0), 1) as low_altitude_pct,
    ROUND(100.0 * medium_altitude_count / NULLIF(total_flights, 0), 1) as medium_altitude_pct,
    ROUND(100.0 * high_altitude_count / NULLIF(total_flights, 0), 1) as high_altitude_pct,
    ROUND(100.0 * very_high_altitude_count / NULLIF(total_flights, 0), 1) as very_high_altitude_pct,
    
    -- Distribution percentages - speed
    ROUND(100.0 * slow_speed_count / NULLIF(total_flights, 0), 1) as slow_speed_pct,
    ROUND(100.0 * normal_speed_count / NULLIF(total_flights, 0), 1) as normal_speed_pct,
    ROUND(100.0 * fast_speed_count / NULLIF(total_flights, 0), 1) as fast_speed_pct,
    ROUND(100.0 * very_fast_speed_count / NULLIF(total_flights, 0), 1) as very_fast_speed_pct,
    
    -- Distribution percentages - flight phase
    ROUND(100.0 * ground_phase_count / NULLIF(total_flights, 0), 1) as ground_phase_pct,
    ROUND(100.0 * takeoff_phase_count / NULLIF(total_flights, 0), 1) as takeoff_phase_pct,
    ROUND(100.0 * climb_phase_count / NULLIF(total_flights, 0), 1) as climb_phase_pct,
    ROUND(100.0 * cruise_phase_count / NULLIF(total_flights, 0), 1) as cruise_phase_pct,
    ROUND(100.0 * descent_phase_count / NULLIF(total_flights, 0), 1) as descent_phase_pct,
    ROUND(100.0 * approach_phase_count / NULLIF(total_flights, 0), 1) as approach_phase_pct,
    
    -- Geographic distribution
    north_america_flights,
    europe_flights,
    east_asia_flights,
    oceania_flights,
    ROUND(100.0 * (north_america_flights + europe_flights + east_asia_flights + oceania_flights) / NULLIF(total_flights, 0), 1) as major_regions_pct,
    
    -- Data quality metrics
    ROUND(avg_data_quality_score, 3) as avg_data_quality_score,
    ROUND(min_data_quality_score, 3) as min_data_quality_score,
    ROUND(100.0 * excellent_quality_count / NULLIF(total_flights, 0), 1) as excellent_quality_pct,
    ROUND(100.0 * good_quality_count / NULLIF(total_flights, 0), 1) as good_quality_pct,
    ROUND(100.0 * poor_quality_count / NULLIF(total_flights, 0), 1) as poor_quality_pct,
    
    ROUND(avg_completeness_score, 3) as avg_completeness_score,
    ROUND(avg_validity_score, 3) as avg_validity_score,
    ROUND(avg_consistency_score, 3) as avg_consistency_score,
    
    -- Traffic classification
    CASE 
        WHEN total_flights > 5000 THEN 'Peak Traffic'
        WHEN total_flights > 3000 THEN 'High Traffic'
        WHEN total_flights > 1500 THEN 'Moderate Traffic'
        WHEN total_flights > 500 THEN 'Low Traffic'
        ELSE 'Minimal Traffic'
    END as traffic_level;

-- =============================================================================
-- DAILY AGGREGATIONS VIEW
-- =============================================================================

-- Daily summary metrics for trend analysis and reporting
CREATE OR REPLACE VIEW daily_flight_summary AS
WITH daily_metrics AS (
    SELECT 
        year,
        month,
        day,
        
        -- Create standardized date
        year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') as summary_date,
        
        -- Day of week calculation (simplified)
        ((day - 1) % 7) + 1 as day_of_week_num,
        
        -- Volume metrics
        COUNT(*) as total_flights,
        COUNT(DISTINCT icao24) as unique_aircraft,
        COUNT(DISTINCT callsign) as unique_callsigns,
        COUNT(DISTINCT origin_country) as countries_active,
        
        -- Hourly distribution analysis
        COUNT(DISTINCT hour) as hours_with_data,
        MAX(COUNT(*)) OVER (PARTITION BY year, month, day, hour) as peak_hour_flights,
        MIN(COUNT(*)) OVER (PARTITION BY year, month, day, hour) as min_hour_flights,
        
        -- Performance metrics
        AVG(baro_altitude_ft) as avg_altitude_ft,
        STDDEV(baro_altitude_ft) as altitude_variance,
        AVG(velocity_knots) as avg_speed_knots,
        STDDEV(velocity_knots) as speed_variance,
        
        -- Operational metrics
        COUNT(CASE WHEN NOT on_ground THEN 1 END) as airborne_observations,
        COUNT(CASE WHEN flight_phase IN ('Takeoff', 'Approach') THEN 1 END) as airport_operations,
        COUNT(CASE WHEN flight_phase = 'Cruise' THEN 1 END) as cruise_observations,
        
        -- Geographic coverage
        MAX(latitude) - MIN(latitude) as latitude_span,
        MAX(longitude) - MIN(longitude) as longitude_span,
        COUNT(DISTINCT CONCAT(CAST(ROUND(latitude) AS varchar), ',', CAST(ROUND(longitude) AS varchar))) as geographic_cells_covered,
        
        -- Data quality aggregation
        AVG(data_quality_score) as avg_data_quality,
        MIN(data_quality_score) as min_data_quality,
        STDDEV(data_quality_score) as quality_variance,
        COUNT(CASE WHEN data_quality_score >= 0.9 THEN 1 END) as high_quality_observations,
        
        -- Processing efficiency (if available from processing metadata)
        AVG(processing_duration_ms) as avg_processing_time_ms
        
    FROM processed_flight_data
    WHERE data_quality_score > 0.5
    GROUP BY year, month, day
)
SELECT 
    year,
    month,
    day,
    summary_date,
    
    -- Day classification
    day_of_week_num,
    CASE 
        WHEN day_of_week_num = 1 THEN 'Sunday'
        WHEN day_of_week_num = 2 THEN 'Monday' 
        WHEN day_of_week_num = 3 THEN 'Tuesday'
        WHEN day_of_week_num = 4 THEN 'Wednesday'
        WHEN day_of_week_num = 5 THEN 'Thursday'
        WHEN day_of_week_num = 6 THEN 'Friday'
        WHEN day_of_week_num = 7 THEN 'Saturday'
    END as day_of_week,
    
    CASE 
        WHEN day_of_week_num IN (1, 7) THEN 'Weekend'
        ELSE 'Weekday'
    END as day_type,
    
    -- Volume metrics
    total_flights,
    unique_aircraft,
    unique_callsigns,
    countries_active,
    hours_with_data,
    
    -- Activity rates
    ROUND(total_flights / 24.0, 1) as avg_flights_per_hour,
    ROUND(total_flights / 1440.0, 2) as avg_flights_per_minute,
    peak_hour_flights,
    min_hour_flights,
    peak_hour_flights - min_hour_flights as hourly_traffic_range,
    
    -- Coverage metrics
    airborne_observations,
    airport_operations,
    cruise_observations,
    ROUND(100.0 * airborne_observations / NULLIF(total_flights, 0), 1) as airborne_percentage,
    ROUND(100.0 * airport_operations / NULLIF(total_flights, 0), 1) as airport_ops_percentage,
    ROUND(100.0 * cruise_observations / NULLIF(total_flights, 0), 1) as cruise_percentage,
    
    -- Performance metrics
    ROUND(avg_altitude_ft, 0) as avg_altitude_ft,
    ROUND(altitude_variance, 0) as altitude_variance,
    ROUND(avg_speed_knots, 0) as avg_speed_knots,
    ROUND(speed_variance, 0) as speed_variance,
    
    -- Geographic metrics
    ROUND(latitude_span, 2) as latitude_coverage_degrees,
    ROUND(longitude_span, 2) as longitude_coverage_degrees,
    geographic_cells_covered,
    ROUND(geographic_cells_covered / NULLIF(total_flights / 1000.0, 0), 1) as geographic_density_score,
    
    -- Data quality metrics
    ROUND(avg_data_quality, 4) as avg_data_quality_score,
    ROUND(min_data_quality, 4) as min_data_quality_score,
    ROUND(quality_variance, 4) as quality_variance,
    ROUND(100.0 * high_quality_observations / NULLIF(total_flights, 0), 1) as high_quality_percentage,
    
    -- Quality grade
    CASE 
        WHEN avg_data_quality >= 0.9 THEN 'Excellent'
        WHEN avg_data_quality >= 0.8 THEN 'Good'
        WHEN avg_data_quality >= 0.7 THEN 'Fair' 
        WHEN avg_data_quality >= 0.6 THEN 'Poor'
        ELSE 'Critical'
    END as daily_quality_grade,
    
    -- Traffic pattern classification
    CASE 
        WHEN total_flights > 100000 THEN 'Very High Volume'
        WHEN total_flights > 50000 THEN 'High Volume'
        WHEN total_flights > 25000 THEN 'Moderate Volume'
        WHEN total_flights > 10000 THEN 'Low Volume'
        ELSE 'Very Low Volume'  
    END as volume_classification,
    
    -- Variability assessment
    CASE 
        WHEN (peak_hour_flights - min_hour_flights) / NULLIF(peak_hour_flights, 0) > 0.8 THEN 'Highly Variable'
        WHEN (peak_hour_flights - min_hour_flights) / NULLIF(peak_hour_flights, 0) > 0.6 THEN 'Variable'
        WHEN (peak_hour_flights - min_hour_flights) / NULLIF(peak_hour_flights, 0) > 0.4 THEN 'Moderately Consistent'
        ELSE 'Highly Consistent'
    END as traffic_pattern_consistency,
    
    -- Processing performance
    ROUND(COALESCE(avg_processing_time_ms, 0), 0) as avg_processing_time_ms;

-- =============================================================================
-- REAL-TIME METRICS VIEW
-- =============================================================================

-- Real-time dashboard view for current operational status
CREATE OR REPLACE VIEW realtime_flight_metrics AS
WITH current_status AS (
    SELECT 
        -- Current time context
        current_timestamp as report_timestamp,
        year(current_date) as current_year,
        month(current_date) as current_month,
        day(current_date) as current_day,
        hour(current_timestamp) as current_hour,
        
        -- Live flight metrics (last hour)
        COUNT(*) as current_hour_flights,
        COUNT(DISTINCT icao24) as current_hour_aircraft,
        COUNT(CASE WHEN NOT on_ground THEN 1 END) as currently_airborne,
        COUNT(CASE WHEN on_ground THEN 1 END) as currently_grounded,
        
        -- Real-time performance metrics
        AVG(baro_altitude_ft) as current_avg_altitude,
        MAX(baro_altitude_ft) as current_max_altitude,
        AVG(velocity_knots) as current_avg_speed,
        MAX(velocity_knots) as current_max_speed,
        
        -- Flight phase distribution (current activity)
        COUNT(CASE WHEN flight_phase = 'Takeoff' THEN 1 END) as active_takeoffs,
        COUNT(CASE WHEN flight_phase = 'Climb' THEN 1 END) as active_climbs,
        COUNT(CASE WHEN flight_phase = 'Cruise' THEN 1 END) as active_cruise,
        COUNT(CASE WHEN flight_phase = 'Descent' THEN 1 END) as active_descents,
        COUNT(CASE WHEN flight_phase = 'Approach' THEN 1 END) as active_approaches,
        
        -- Geographic distribution
        COUNT(DISTINCT origin_country) as countries_represented,
        
        -- Data freshness and quality
        AVG(data_quality_score) as current_data_quality,
        MAX(collection_time) as latest_data_timestamp,
        COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 300 THEN 1 END) as fresh_data_points,
        
        -- High-level activity indicators
        COUNT(CASE WHEN baro_altitude_ft > 30000 THEN 1 END) as high_altitude_traffic,
        COUNT(CASE WHEN velocity_knots > 400 THEN 1 END) as high_speed_traffic,
        COUNT(CASE WHEN ABS(vertical_rate_fpm) > 1000 THEN 1 END) as active_climbers_descenders
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day = day(current_date)
        AND hour = hour(current_timestamp)
        AND data_quality_score > 0.7
),
recent_trend AS (
    -- Compare with previous hour for trend analysis
    SELECT 
        COUNT(*) as prev_hour_flights,
        AVG(baro_altitude_ft) as prev_avg_altitude,
        AVG(velocity_knots) as prev_avg_speed,
        COUNT(CASE WHEN NOT on_ground THEN 1 END) as prev_airborne
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day = day(current_date)
        AND hour = CASE 
            WHEN hour(current_timestamp) = 0 THEN 23
            ELSE hour(current_timestamp) - 1
        END
        AND data_quality_score > 0.7
),
daily_context AS (
    -- Today's cumulative statistics
    SELECT 
        COUNT(*) as today_total_flights,
        COUNT(DISTINCT icao24) as today_unique_aircraft,
        AVG(data_quality_score) as today_avg_quality,
        MAX(baro_altitude_ft) as today_max_altitude,
        MAX(velocity_knots) as today_max_speed
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day = day(current_date)
        AND data_quality_score > 0.7
)
SELECT 
    -- Timestamp and context
    cs.report_timestamp,
    cs.current_year || '-' || LPAD(CAST(cs.current_month AS varchar), 2, '0') || '-' || LPAD(CAST(cs.current_day AS varchar), 2, '0') || ' ' || LPAD(CAST(cs.current_hour AS varchar), 2, '0') || ':00' as current_hour_label,
    
    -- Current activity level
    cs.current_hour_flights,
    cs.current_hour_aircraft,
    cs.currently_airborne,
    cs.currently_grounded,
    
    -- Activity rates
    ROUND(cs.current_hour_flights / 60.0, 2) as current_flights_per_minute,
    ROUND(100.0 * cs.currently_airborne / NULLIF(cs.current_hour_flights, 0), 1) as current_airborne_percentage,
    
    -- Performance indicators
    ROUND(cs.current_avg_altitude, 0) as current_avg_altitude_ft,
    cs.current_max_altitude as current_max_altitude_ft,
    ROUND(cs.current_avg_speed, 0) as current_avg_speed_knots,
    cs.current_max_speed as current_max_speed_knots,
    
    -- Activity distribution
    cs.active_takeoffs,
    cs.active_climbs,
    cs.active_cruise,
    cs.active_descents,  
    cs.active_approaches,
    cs.active_takeoffs + cs.active_approaches as current_airport_activity,
    
    -- Geographic and operational scope
    cs.countries_represented,
    cs.high_altitude_traffic,
    cs.high_speed_traffic,
    cs.active_climbers_descenders,
    
    -- Data quality and freshness
    ROUND(cs.current_data_quality, 3) as current_data_quality_score,
    from_unixtime(cs.latest_data_timestamp) as latest_data_time,
    cs.fresh_data_points,
    ROUND(100.0 * cs.fresh_data_points / NULLIF(cs.current_hour_flights, 0), 1) as data_freshness_percentage,
    
    -- Trend analysis (vs previous hour)
    COALESCE(rt.prev_hour_flights, 0) as prev_hour_flights,
    cs.current_hour_flights - COALESCE(rt.prev_hour_flights, 0) as hourly_flight_change,
    CASE 
        WHEN cs.current_hour_flights > COALESCE(rt.prev_hour_flights, 0) * 1.1 THEN 'Increasing'
        WHEN cs.current_hour_flights < COALESCE(rt.prev_hour_flights, 0) * 0.9 THEN 'Decreasing'
        ELSE 'Stable'
    END as traffic_trend,
    
    cs.currently_airborne - COALESCE(rt.prev_airborne, 0) as airborne_change,
    
    -- Daily context
    dc.today_total_flights,
    dc.today_unique_aircraft,
    ROUND(dc.today_avg_quality, 3) as today_avg_data_quality,
    dc.today_max_altitude as today_peak_altitude_ft,
    dc.today_max_speed as today_peak_speed_knots,
    
    -- Daily progress
    ROUND(100.0 * cs.current_hour_flights / NULLIF(dc.today_total_flights, 0), 1) as current_hour_share_of_day,
    
    -- System status assessment
    CASE 
        WHEN cs.current_data_quality >= 0.9 AND cs.fresh_data_points / NULLIF(cs.current_hour_flights, 0) > 0.8 THEN 'Excellent'
        WHEN cs.current_data_quality >= 0.8 AND cs.fresh_data_points / NULLIF(cs.current_hour_flights, 0) > 0.6 THEN 'Good'
        WHEN cs.current_data_quality >= 0.7 AND cs.fresh_data_points / NULLIF(cs.current_hour_flights, 0) > 0.5 THEN 'Fair'
        ELSE 'Poor'
    END as system_health_status,
    
    -- Traffic intensity classification
    CASE 
        WHEN cs.current_hour_flights > 5000 THEN 'Peak Traffic'
        WHEN cs.current_hour_flights > 3000 THEN 'High Traffic'
        WHEN cs.current_hour_flights > 1500 THEN 'Moderate Traffic' 
        WHEN cs.current_hour_flights > 500 THEN 'Light Traffic'
        ELSE 'Minimal Traffic'
    END as current_traffic_intensity
    
FROM current_status cs
LEFT JOIN recent_trend rt ON 1=1  -- Cross join since both are single-row results
LEFT JOIN daily_context dc ON 1=1;

-- =============================================================================
-- DATA QUALITY DASHBOARD VIEW
-- =============================================================================

-- Specialized view for data quality monitoring and alerting
CREATE OR REPLACE VIEW data_quality_dashboard AS
SELECT 
    -- Time context
    current_timestamp as dashboard_timestamp,
    year(current_date) || '-' || LPAD(CAST(month(current_date) AS varchar), 2, '0') || '-' || LPAD(CAST(day(current_date) AS varchar), 2, '0') as dashboard_date,
    
    -- Recent quality metrics (last 4 hours rolling window)
    AVG(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) as last_4h_avg_quality,
    MIN(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) as last_4h_min_quality,
    COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 AND data_quality_score < 0.7 THEN 1 END) as last_4h_poor_quality_count,
    COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN 1 END) as last_4h_total_records,
    
    -- Current hour quality snapshot  
    AVG(CASE WHEN year = year(current_date) AND month = month(current_date) AND day = day(current_date) AND hour = hour(current_timestamp) THEN data_quality_score END) as current_hour_avg_quality,
    COUNT(CASE WHEN year = year(current_date) AND month = month(current_date) AND day = day(current_date) AND hour = hour(current_timestamp) AND data_quality_score >= 0.9 THEN 1 END) as current_hour_excellent_quality,
    COUNT(CASE WHEN year = year(current_date) AND month = month(current_date) AND day = day(current_date) AND hour = hour(current_timestamp) THEN 1 END) as current_hour_total_records,
    
    -- Data completeness indicators
    COUNT(CASE WHEN icao24 IS NULL OR icao24 = '' THEN 1 END) as missing_aircraft_id_count,
    COUNT(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 END) as missing_position_count,
    COUNT(CASE WHEN baro_altitude_ft IS NULL THEN 1 END) as missing_altitude_count,
    COUNT(CASE WHEN velocity_knots IS NULL THEN 1 END) as missing_velocity_count,
    
    -- Data validity indicators
    COUNT(CASE WHEN ABS(latitude) > 90 OR ABS(longitude) > 180 THEN 1 END) as invalid_coordinates_count,
    COUNT(CASE WHEN baro_altitude_ft < -1000 OR baro_altitude_ft > 60000 THEN 1 END) as invalid_altitude_count,
    COUNT(CASE WHEN velocity_knots < 0 OR velocity_knots > 1000 THEN 1 END) as invalid_velocity_count,
    
    -- Total record context
    COUNT(*) as total_dashboard_records,
    
    -- Calculated quality percentages
    ROUND(100.0 * COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 AND data_quality_score < 0.7 THEN 1 END) / NULLIF(COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN 1 END), 0), 2) as last_4h_poor_quality_percentage,
    
    ROUND(100.0 * COUNT(CASE WHEN year = year(current_date) AND month = month(current_date) AND day = day(current_date) AND hour = hour(current_timestamp) AND data_quality_score >= 0.9 THEN 1 END) / NULLIF(COUNT(CASE WHEN year = year(current_date) AND month = month(current_date) AND day = day(current_date) AND hour = hour(current_timestamp) THEN 1 END), 0), 2) as current_hour_excellent_percentage,
    
    -- Data issue percentages
    ROUND(100.0 * COUNT(CASE WHEN icao24 IS NULL OR icao24 = '' THEN 1 END) / NULLIF(COUNT(*), 0), 3) as missing_aircraft_id_percentage,
    ROUND(100.0 * COUNT(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 END) / NULLIF(COUNT(*), 0), 3) as missing_position_percentage,
    
    -- Quality status flags
    CASE 
        WHEN AVG(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) >= 0.9 THEN 'EXCELLENT'
        WHEN AVG(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) >= 0.8 THEN 'GOOD'
        WHEN AVG(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) >= 0.7 THEN 'FAIR'
        WHEN AVG(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN data_quality_score END) >= 0.6 THEN 'POOR' 
        ELSE 'CRITICAL'
    END as quality_status_flag,
    
    -- Alert conditions
    CASE 
        WHEN COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 AND data_quality_score < 0.7 THEN 1 END) / NULLIF(COUNT(CASE WHEN collection_time >= unix_timestamp(current_timestamp) - 14400 THEN 1 END), 0) > 0.1 THEN true
        ELSE false
    END as quality_alert_triggered,
    
    CASE 
        WHEN COUNT(CASE WHEN icao24 IS NULL OR icao24 = '' THEN 1 END) / NULLIF(COUNT(*), 0) > 0.02 THEN true
        ELSE false  
    END as missing_data_alert_triggered
    
FROM processed_flight_data
WHERE 
    -- Focus on recent data for dashboard relevance
    collection_time >= unix_timestamp(current_timestamp) - 86400  -- Last 24 hours
    AND year = year(current_date)
    AND month = month(current_date)
    AND day >= day(current_date) - 1;