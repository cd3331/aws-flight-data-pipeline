-- Flight Data Pipeline - Query Optimization and Cost-Saving Guide
-- Advanced techniques for maximizing Athena performance and minimizing costs

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- PARTITION PROJECTION OPTIMIZATION EXAMPLES
-- =============================================================================

-- Example 1: Efficient time-based queries using partition projection
-- ✅ GOOD: Uses partition columns for filtering
SELECT 
    COUNT(*) as flight_count,
    AVG(baro_altitude_ft) as avg_altitude
FROM processed_flight_data
WHERE 
    year = '2024'           -- Partition pruning
    AND month = '01'        -- Partition pruning  
    AND day BETWEEN '15' AND '21'  -- Week range
    AND hour BETWEEN '08' AND '18' -- Business hours
    AND data_quality_score > 0.8;  -- Quality filter

-- ❌ BAD: Does not use partition columns effectively
-- SELECT COUNT(*) FROM processed_flight_data 
-- WHERE collection_datetime >= '2024-01-15 08:00:00'
-- AND collection_datetime <= '2024-01-21 18:00:00';

-- Example 2: Multi-level partition optimization
-- ✅ GOOD: Hierarchical partition filtering
WITH daily_summaries AS (
    SELECT 
        year, month, day,
        COUNT(*) as daily_flights,
        AVG(data_quality_score) as daily_quality
    FROM processed_flight_data
    WHERE 
        year = year(current_date)     -- Current year only
        AND month = month(current_date)   -- Current month only
        AND day >= day(current_date) - 7  -- Last 7 days
        AND NOT on_ground                 -- Exclude ground traffic
    GROUP BY year, month, day
)
SELECT 
    year || '-' || LPAD(month, 2, '0') || '-' || LPAD(day, 2, '0') as date_str,
    daily_flights,
    ROUND(daily_quality, 3) as quality_score
FROM daily_summaries
ORDER BY year, month, day;

-- =============================================================================
-- COLUMN PRUNING AND PROJECTION
-- =============================================================================

-- Example 3: Efficient column selection for large queries
-- ✅ GOOD: Only select needed columns
CREATE OR REPLACE VIEW efficient_flight_overview AS
SELECT 
    icao24,                    -- Aircraft identifier
    collection_datetime,       -- Timestamp
    longitude, latitude,       -- Position (essential)
    baro_altitude_ft,         -- Altitude in feet
    velocity_knots,           -- Speed in knots  
    flight_phase,             -- Current phase
    data_quality_score,       -- Quality indicator
    year, month, day, hour    -- Partition columns
FROM processed_flight_data
WHERE 
    data_quality_score > 0.7  -- Pre-filter for quality
    AND NOT on_ground;        -- Active flights only

-- ❌ BAD: Selecting all columns increases I/O costs
-- SELECT * FROM processed_flight_data WHERE ...

-- Example 4: Aggregation-friendly projections
-- ✅ GOOD: Pre-aggregate at source for reporting
CREATE OR REPLACE VIEW regional_traffic_summary AS
SELECT 
    -- Time dimensions  
    year, month, day,
    
    -- Geographic regions (simplified)
    CASE 
        WHEN latitude BETWEEN 25 AND 70 AND longitude BETWEEN -125 AND -60 THEN 'North_America'
        WHEN latitude BETWEEN 35 AND 75 AND longitude BETWEEN -15 AND 50 THEN 'Europe'  
        WHEN latitude BETWEEN 10 AND 50 AND longitude BETWEEN 95 AND 145 THEN 'East_Asia'
        WHEN latitude BETWEEN -45 AND 5 AND longitude BETWEEN 105 AND 180 THEN 'Oceania'
        ELSE 'Other'
    END as region,
    
    -- Aggregated metrics (computed once, reused many times)
    COUNT(*) as flight_count,
    COUNT(DISTINCT icao24) as unique_aircraft,
    AVG(baro_altitude_ft) as avg_altitude_ft,
    AVG(velocity_knots) as avg_speed_knots,
    AVG(data_quality_score) as avg_quality
    
FROM processed_flight_data
WHERE 
    NOT on_ground
    AND data_quality_score > 0.7
    
GROUP BY 
    year, month, day,
    CASE 
        WHEN latitude BETWEEN 25 AND 70 AND longitude BETWEEN -125 AND -60 THEN 'North_America'
        WHEN latitude BETWEEN 35 AND 75 AND longitude BETWEEN -15 AND 50 THEN 'Europe'
        WHEN latitude BETWEEN 10 AND 50 AND longitude BETWEEN 95 AND 145 THEN 'East_Asia'
        WHEN latitude BETWEEN -45 AND 5 AND longitude BETWEEN 105 AND 180 THEN 'Oceania'
        ELSE 'Other'
    END;

-- =============================================================================
-- APPROXIMATE FUNCTIONS FOR COST REDUCTION
-- =============================================================================

-- Example 5: Using approximate functions for large datasets
-- ✅ GOOD: Approximate functions reduce computation costs
SELECT 
    altitude_category,
    
    -- Exact counts (expensive for large data)
    COUNT(*) as exact_count,
    
    -- Approximate percentiles (much faster and cheaper)
    APPROX_PERCENTILE(baro_altitude_ft, 0.25) as altitude_p25,
    APPROX_PERCENTILE(baro_altitude_ft, 0.5) as altitude_median,
    APPROX_PERCENTILE(baro_altitude_ft, 0.75) as altitude_p75,
    APPROX_PERCENTILE(baro_altitude_ft, 0.95) as altitude_p95,
    
    -- Approximate distinct counts (faster than exact)
    APPROX_COUNT_DISTINCT(icao24) as approx_unique_aircraft,
    APPROX_COUNT_DISTINCT(origin_country) as approx_countries,
    
    -- Standard aggregations (always efficient)
    AVG(velocity_knots) as avg_speed,
    MAX(velocity_knots) as max_speed,
    STDDEV(velocity_knots) as speed_variance
    
FROM processed_flight_data
WHERE 
    year = year(current_date)
    AND month = month(current_date)
    AND day >= day(current_date) - 7
    AND data_quality_score > 0.8
    
GROUP BY altitude_category
ORDER BY exact_count DESC;

-- Example 6: Approximate functions in time-series analysis
-- ✅ GOOD: Fast approximations for trending
WITH hourly_approximations AS (
    SELECT 
        year, month, day, hour,
        
        -- Fast approximate metrics
        APPROX_COUNT_DISTINCT(icao24) as approx_aircraft_count,
        COUNT(*) as observation_count,
        APPROX_PERCENTILE(baro_altitude_ft, 0.5) as median_altitude,
        AVG(velocity_knots) as avg_speed,
        
        -- Approximate histogram data
        histogram(baro_altitude_ft, 10) as altitude_histogram,
        histogram(velocity_knots, 8) as speed_histogram
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 3  -- 3 days for trending
        AND NOT on_ground
        AND data_quality_score > 0.7
        
    GROUP BY year, month, day, hour
)
SELECT 
    hour,
    AVG(approx_aircraft_count) as avg_hourly_aircraft,
    AVG(observation_count) as avg_hourly_observations,
    AVG(median_altitude) as avg_median_altitude,
    AVG(avg_speed) as avg_hourly_speed
    
FROM hourly_approximations
GROUP BY hour
ORDER BY hour;

-- =============================================================================
-- EFFICIENT JOIN PATTERNS
-- =============================================================================

-- Example 7: Optimized joins with partition-aware patterns
-- ✅ GOOD: Join with proper filtering and partition awareness
SELECT 
    p.icao24,
    p.callsign,
    a.model as aircraft_model,
    a.manufacturername as manufacturer,
    
    -- Flight metrics
    COUNT(*) as flight_observations,
    AVG(p.baro_altitude_ft) as avg_altitude,
    AVG(p.velocity_knots) as avg_speed,
    AVG(p.data_quality_score) as avg_quality
    
FROM processed_flight_data p
JOIN aircraft_reference a ON p.icao24 = a.icao24
WHERE 
    -- Partition pruning first (most important)
    p.year = year(current_date)
    AND p.month = month(current_date) 
    AND p.day >= day(current_date) - 1  -- Yesterday and today
    
    -- Quality filters  
    AND p.data_quality_score > 0.8
    AND NOT p.on_ground
    
    -- Reference data filters
    AND a.model IS NOT NULL
    AND a.manufacturername IS NOT NULL
    
GROUP BY p.icao24, p.callsign, a.model, a.manufacturername
HAVING COUNT(*) >= 10  -- Minimum observations threshold
ORDER BY flight_observations DESC
LIMIT 100;

-- Example 8: Broadcast join optimization for small reference tables
-- ✅ GOOD: Small dimension table joins are automatically optimized
WITH top_airports AS (
    -- Small lookup table (broadcast join candidate)
    SELECT icao_code, airport_name, city, country, 
           latitude as airport_lat, longitude as airport_lon
    FROM airport_reference
    WHERE airport_type = 'large_airport'
),
airport_proximity AS (
    SELECT 
        f.icao24,
        f.callsign,  
        f.latitude,
        f.longitude,
        f.baro_altitude_ft,
        
        -- Find closest airport using cross join (broadcast)
        a.icao_code as nearest_airport,
        a.airport_name,
        
        -- Approximate distance calculation  
        SQRT(
            POW(69.1 * (f.latitude - a.airport_lat), 2) + 
            POW(69.1 * (f.longitude - a.airport_lon) * COS(RADIANS(f.latitude)), 2)
        ) as distance_miles
        
    FROM processed_flight_data f
    CROSS JOIN top_airports a
    WHERE 
        f.year = year(current_date)
        AND f.month = month(current_date)
        AND f.day = day(current_date)
        AND f.hour = hour(current_timestamp)  -- Current hour only
        AND f.data_quality_score > 0.8
        
        -- Pre-filter for proximity (performance optimization)
        AND f.latitude BETWEEN a.airport_lat - 1 AND a.airport_lat + 1
        AND f.longitude BETWEEN a.airport_lon - 1 AND a.airport_lon + 1
        
    QUALIFY ROW_NUMBER() OVER (PARTITION BY f.icao24 ORDER BY distance_miles) = 1
)
SELECT 
    nearest_airport,
    airport_name,
    COUNT(*) as nearby_flights,
    AVG(distance_miles) as avg_distance_miles,
    AVG(baro_altitude_ft) as avg_altitude_ft
    
FROM airport_proximity
WHERE distance_miles <= 50  -- Within 50 miles
GROUP BY nearest_airport, airport_name
ORDER BY nearby_flights DESC;

-- =============================================================================
-- WINDOW FUNCTIONS OPTIMIZATION
-- =============================================================================

-- Example 9: Efficient window function usage
-- ✅ GOOD: Window functions with proper partitioning
WITH flight_rankings AS (
    SELECT 
        icao24,
        callsign,
        collection_datetime,
        baro_altitude_ft,
        velocity_knots,
        data_quality_score,
        
        -- Efficient window functions with appropriate partitioning
        ROW_NUMBER() OVER (
            PARTITION BY icao24, DATE(from_unixtime(collection_time))
            ORDER BY collection_time DESC
        ) as daily_observation_rank,
        
        -- Moving averages for trend analysis
        AVG(baro_altitude_ft) OVER (
            PARTITION BY icao24 
            ORDER BY collection_time
            ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
        ) as altitude_moving_avg,
        
        -- Lag functions for change detection
        LAG(baro_altitude_ft, 1) OVER (
            PARTITION BY icao24 
            ORDER BY collection_time
        ) as prev_altitude_ft,
        
        -- Ranking within time windows
        RANK() OVER (
            PARTITION BY DATE(from_unixtime(collection_time)), HOUR(from_unixtime(collection_time))
            ORDER BY velocity_knots DESC
        ) as hourly_speed_rank
        
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 1
        AND data_quality_score > 0.8
        AND NOT on_ground
)
SELECT 
    icao24,
    callsign,
    collection_datetime,
    baro_altitude_ft,
    velocity_knots,
    
    -- Derived metrics from window functions
    ROUND(altitude_moving_avg, 0) as altitude_trend,
    baro_altitude_ft - prev_altitude_ft as altitude_change_ft,
    hourly_speed_rank,
    
    CASE 
        WHEN hourly_speed_rank <= 10 THEN 'Top Speed'
        WHEN hourly_speed_rank <= 50 THEN 'High Speed'  
        ELSE 'Normal Speed'
    END as speed_category
    
FROM flight_rankings
WHERE 
    daily_observation_rank <= 5  -- Latest 5 observations per aircraft per day
    AND hourly_speed_rank <= 100  -- Top 100 fastest per hour
    
ORDER BY icao24, collection_datetime DESC;

-- =============================================================================
-- SUBQUERY AND CTE OPTIMIZATION
-- =============================================================================

-- Example 10: Efficient CTE usage for complex analytics
-- ✅ GOOD: Well-structured CTEs with appropriate filtering
WITH 
-- Base data with quality filtering
quality_flights AS (
    SELECT 
        icao24, callsign, origin_country,
        collection_time, baro_altitude_ft, velocity_knots,
        flight_phase, data_quality_score,
        year, month, day, hour
    FROM processed_flight_data
    WHERE 
        year = year(current_date)
        AND month = month(current_date)
        AND day >= day(current_date) - 7  -- One week
        AND data_quality_score > 0.8
        AND NOT on_ground
),

-- Hourly aggregations
hourly_stats AS (
    SELECT 
        year, month, day, hour,
        COUNT(*) as hourly_flights,
        COUNT(DISTINCT icao24) as hourly_aircraft,
        AVG(baro_altitude_ft) as avg_altitude,
        AVG(velocity_knots) as avg_speed,
        STDDEV(velocity_knots) as speed_variance
    FROM quality_flights
    GROUP BY year, month, day, hour
),

-- Daily aggregations built on hourly
daily_stats AS (
    SELECT 
        year, month, day,
        SUM(hourly_flights) as daily_flights,
        AVG(hourly_aircraft) as avg_hourly_aircraft,
        AVG(avg_altitude) as daily_avg_altitude,
        AVG(avg_speed) as daily_avg_speed,
        MAX(hourly_flights) as peak_hour_flights,
        MIN(hourly_flights) as min_hour_flights
    FROM hourly_stats
    GROUP BY year, month, day
),

-- Performance classification
classified_days AS (
    SELECT 
        *,
        CASE 
            WHEN daily_flights > 50000 THEN 'Very High Volume'
            WHEN daily_flights > 25000 THEN 'High Volume'
            WHEN daily_flights > 12500 THEN 'Medium Volume'  
            ELSE 'Low Volume'
        END as volume_class,
        
        CASE 
            WHEN (peak_hour_flights - min_hour_flights) / peak_hour_flights > 0.8 THEN 'Highly Variable'
            WHEN (peak_hour_flights - min_hour_flights) / peak_hour_flights > 0.6 THEN 'Variable'
            ELSE 'Consistent'
        END as variability_class
        
    FROM daily_stats
)

-- Final result with all derived metrics
SELECT 
    year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') as analysis_date,
    volume_class,
    variability_class,
    
    -- Volume metrics
    daily_flights,
    ROUND(avg_hourly_aircraft, 1) as avg_aircraft_per_hour,
    
    -- Performance metrics
    ROUND(daily_avg_altitude, 0) as avg_altitude_ft,
    ROUND(daily_avg_speed, 0) as avg_speed_knots,
    
    -- Variability metrics
    peak_hour_flights,
    min_hour_flights,
    ROUND(100.0 * (peak_hour_flights - min_hour_flights) / peak_hour_flights, 1) as traffic_variability_pct
    
FROM classified_days
ORDER BY year DESC, month DESC, day DESC;

-- =============================================================================
-- COST MONITORING QUERIES
-- =============================================================================

-- Example 11: Query to monitor your Athena costs and data scanning
-- Use this to identify expensive queries and optimize them
SELECT 
    query_id,
    query,
    state,
    submission_time,
    completion_time,
    
    -- Cost-related metrics  
    data_scanned_in_bytes,
    ROUND(data_scanned_in_bytes / 1024.0 / 1024.0 / 1024.0, 2) as data_scanned_gb,
    ROUND((data_scanned_in_bytes / 1024.0 / 1024.0 / 1024.0) * 5.00, 2) as estimated_cost_usd,  -- $5/TB
    
    -- Performance metrics
    execution_time_in_millis,
    ROUND(execution_time_in_millis / 1000.0, 2) as execution_time_seconds,
    
    -- Efficiency metrics
    ROUND(
        (data_scanned_in_bytes / 1024.0 / 1024.0) / 
        NULLIF(execution_time_in_millis / 1000.0, 0), 2
    ) as mb_per_second_throughput
    
FROM information_schema.query_history
WHERE 
    submission_time >= current_timestamp - INTERVAL '7' DAY
    AND state = 'SUCCEEDED'
    AND data_scanned_in_bytes > 0
    
ORDER BY data_scanned_in_bytes DESC
LIMIT 25;

-- =============================================================================  
-- PERFORMANCE BENCHMARKING QUERIES
-- =============================================================================

-- Example 12: Benchmark different query patterns for performance comparison
-- Run these queries to compare performance of different approaches

-- Approach A: Direct aggregation (baseline)
SELECT 'Direct Aggregation' as approach, current_timestamp as start_time;
SELECT 
    COUNT(*) as total_flights,
    AVG(baro_altitude_ft) as avg_altitude,
    AVG(velocity_knots) as avg_speed
FROM processed_flight_data
WHERE 
    year = year(current_date) AND month = month(current_date) 
    AND day = day(current_date) AND data_quality_score > 0.8;
SELECT 'Direct Aggregation Complete' as approach, current_timestamp as end_time;

-- Approach B: Using pre-aggregated view
SELECT 'Pre-aggregated View' as approach, current_timestamp as start_time;
SELECT 
    SUM(total_flights) as total_flights,
    AVG(avg_altitude_ft) as avg_altitude, 
    AVG(avg_speed_knots) as avg_speed
FROM hourly_flight_summary
WHERE 
    year = year(current_date) AND month = month(current_date)
    AND day = day(current_date);
SELECT 'Pre-aggregated View Complete' as approach, current_timestamp as end_time;

-- Approach C: Approximate functions
SELECT 'Approximate Functions' as approach, current_timestamp as start_time;
SELECT 
    APPROX_COUNT_DISTINCT(icao24) as approx_flights,
    APPROX_PERCENTILE(baro_altitude_ft, 0.5) as median_altitude,
    APPROX_PERCENTILE(velocity_knots, 0.5) as median_speed  
FROM processed_flight_data
WHERE 
    year = year(current_date) AND month = month(current_date)
    AND day = day(current_date) AND data_quality_score > 0.8;
SELECT 'Approximate Functions Complete' as approach, current_timestamp as end_time;

-- =============================================================================
-- QUERY RESULT CACHING OPTIMIZATION
-- =============================================================================

-- Example 13: Queries designed for effective result caching
-- These queries are good candidates for caching due to stable results

-- Daily summary (stable after day completion)
CREATE OR REPLACE VIEW cacheable_daily_summary AS
SELECT 
    year || '-' || LPAD(CAST(month AS varchar), 2, '0') || '-' || LPAD(CAST(day AS varchar), 2, '0') as summary_date,
    COUNT(*) as total_flights,
    COUNT(DISTINCT icao24) as unique_aircraft, 
    AVG(baro_altitude_ft) as avg_altitude_ft,
    AVG(velocity_knots) as avg_speed_knots,
    AVG(data_quality_score) as avg_quality_score
FROM processed_flight_data
WHERE 
    data_quality_score > 0.7
    AND year = year(current_date) 
    AND month = month(current_date)
    AND day < day(current_date)  -- Only completed days (cacheable)
GROUP BY year, month, day
ORDER BY year DESC, month DESC, day DESC;

-- Aircraft performance summary (relatively stable)
CREATE OR REPLACE VIEW cacheable_aircraft_performance AS
SELECT 
    p.icao24,
    a.model,
    a.manufacturername,
    COUNT(*) as observation_count,
    AVG(p.baro_altitude_ft) as avg_cruise_altitude,
    AVG(p.velocity_knots) as avg_cruise_speed,
    STDDEV(p.velocity_knots) as speed_consistency,
    AVG(p.data_quality_score) as avg_data_quality
FROM processed_flight_data p
LEFT JOIN aircraft_reference a ON p.icao24 = a.icao24  
WHERE 
    p.year = year(current_date)
    AND p.month = month(current_date) 
    AND p.day BETWEEN day(current_date) - 7 AND day(current_date) - 1  -- Completed week
    AND p.flight_phase = 'Cruise'
    AND p.data_quality_score > 0.8
GROUP BY p.icao24, a.model, a.manufacturername
HAVING COUNT(*) >= 20
ORDER BY observation_count DESC;

/*
=============================================================================
COST OPTIMIZATION SUMMARY
=============================================================================

1. PARTITION PROJECTION
   - Always filter by year/month/day/hour
   - Use exact partition values when possible
   - Avoid timestamp comparisons across partitions

2. COLUMN PRUNING  
   - Select only required columns
   - Avoid SELECT * queries
   - Use views for common column combinations

3. APPROXIMATE FUNCTIONS
   - Use APPROX_PERCENTILE instead of exact percentiles
   - Use APPROX_COUNT_DISTINCT for large cardinality
   - Trade precision for performance when appropriate

4. EFFICIENT JOINS
   - Filter before joining
   - Join on partition columns when possible  
   - Use broadcast joins for small dimension tables

5. QUERY RESULT CACHING
   - Design queries for caching effectiveness
   - Use stable time ranges for cacheable results
   - Leverage view-based caching patterns

6. WORKLOAD MANAGEMENT
   - Separate workgroups by query type
   - Set appropriate data scan limits
   - Monitor and optimize expensive queries

Expected Cost Savings:
- Partition projection: 60-80% reduction in query planning time
- Column pruning: 70-90% reduction in data scanned  
- Approximate functions: 50-70% reduction in compute costs
- Effective caching: 90%+ cost reduction for repeated queries
- Combined optimizations: 80-95% total cost reduction vs unoptimized queries
=============================================================================
*/