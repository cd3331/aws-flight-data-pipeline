-- Flight Data Pipeline - Raw Data Tables
-- External tables for raw JSON data with partition projection

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- RAW JSON DATA TABLE WITH PARTITION PROJECTION
-- =============================================================================

-- Drop table if exists for clean recreation
DROP TABLE IF EXISTS raw_flight_data;

-- Create external table for raw JSON data
CREATE EXTERNAL TABLE raw_flight_data (
    -- OpenSky Network API response structure
    time bigint COMMENT 'Unix timestamp of the data collection',
    states array<struct<
        icao24: string,           -- ICAO 24-bit address
        callsign: string,         -- Call sign of the vehicle
        origin_country: string,   -- Country name inferred from ICAO 24-bit address
        time_position: bigint,    -- Unix timestamp (seconds) for position
        last_contact: bigint,     -- Unix timestamp (seconds) for last contact
        longitude: double,        -- WGS-84 longitude in decimal degrees
        latitude: double,         -- WGS-84 latitude in decimal degrees
        baro_altitude: double,    -- Barometric altitude in meters
        on_ground: boolean,       -- Whether aircraft is on ground
        velocity: double,         -- Velocity over ground in m/s
        true_track: double,       -- True track in decimal degrees clockwise from north
        vertical_rate: double,    -- Vertical rate in m/s (negative means descending)
        sensors: array<int>,      -- IDs of sensors which contributed to this state vector
        geo_altitude: double,     -- Geometric altitude in meters
        squawk: string,           -- Transponder code
        spi: boolean,             -- Whether flight is in special purpose indicator
        position_source: int      -- Origin of this state's position (0=ADS-B, 1=ASTERIX, 2=MLAT)
    >> COMMENT 'Array of aircraft state vectors from OpenSky Network'
)
COMMENT 'Raw flight data from OpenSky Network API in JSON format'
PARTITIONED BY (
    year string COMMENT 'Partition by year (YYYY format)',
    month string COMMENT 'Partition by month (MM format)', 
    day string COMMENT 'Partition by day (DD format)',
    hour string COMMENT 'Partition by hour (HH format)'
)
STORED AS JSON
LOCATION 's3://flight-data-raw-{environment}-{random_suffix}/flight-data/'
TBLPROPERTIES (
    -- Enable partition projection for automatic partition discovery
    'projection.enabled' = 'true',
    
    -- Year projection (2024 onwards for 10 years)
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2034',
    'projection.year.format' = 'yyyy',
    'projection.year.interval' = '1',
    'projection.year.interval.unit' = 'YEARS',
    
    -- Month projection (01-12)
    'projection.month.type' = 'integer', 
    'projection.month.range' = '1,12',
    'projection.month.format' = 'MM',
    'projection.month.interval' = '1',
    'projection.month.interval.unit' = 'MONTHS',
    
    -- Day projection (01-31)
    'projection.day.type' = 'integer',
    'projection.day.range' = '1,31', 
    'projection.day.format' = 'DD',
    'projection.day.interval' = '1',
    'projection.day.interval.unit' = 'DAYS',
    
    -- Hour projection (00-23)
    'projection.hour.type' = 'integer',
    'projection.hour.range' = '0,23',
    'projection.hour.format' = 'HH', 
    'projection.hour.interval' = '1',
    'projection.hour.interval.unit' = 'HOURS',
    
    -- S3 location template with partition structure
    'storage.location.template' = 's3://flight-data-raw-{environment}-{random_suffix}/flight-data/year=${year}/month=${month}/day=${day}/hour=${hour}/',
    
    -- Optimize for analytical queries
    'skip.header.line.count' = '0',
    'serialization.format' = '1',
    'classification' = 'json',
    
    -- Cost optimization
    'compressionType' = 'gzip',
    
    -- Data lifecycle
    'last_modified_time' = '1704067200', -- 2024-01-01 00:00:00 UTC
    'created_by' = 'flight-data-pipeline',
    'version' = '1.0'
);

-- =============================================================================
-- RAW DATA INGESTION LOG TABLE
-- =============================================================================

-- Drop table if exists
DROP TABLE IF EXISTS raw_ingestion_log;

-- Create table for ingestion metadata and quality tracking
CREATE EXTERNAL TABLE raw_ingestion_log (
    ingestion_id string COMMENT 'Unique identifier for ingestion batch',
    timestamp string COMMENT 'ISO timestamp of ingestion start', 
    execution_time_ms bigint COMMENT 'Total execution time in milliseconds',
    records_fetched int COMMENT 'Number of records fetched from API',
    records_stored int COMMENT 'Number of records stored in S3',
    api_response_time_ms bigint COMMENT 'OpenSky API response time',
    data_size_bytes bigint COMMENT 'Size of raw data in bytes',
    quality_score double COMMENT 'Initial data quality score (0-1)',
    error_count int COMMENT 'Number of errors encountered',
    status string COMMENT 'Ingestion status: success, partial, failed',
    opensky_api_version string COMMENT 'OpenSky API version used',
    pipeline_version string COMMENT 'Flight data pipeline version'
)
COMMENT 'Ingestion execution log and metadata'
PARTITIONED BY (
    year string COMMENT 'Partition by year (YYYY)',
    month string COMMENT 'Partition by month (MM)', 
    day string COMMENT 'Partition by day (DD)'
)
STORED AS JSON
LOCATION 's3://flight-data-raw-{environment}-{random_suffix}/ingestion-logs/'
TBLPROPERTIES (
    -- Partition projection for ingestion logs
    'projection.enabled' = 'true',
    
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2034', 
    'projection.year.format' = 'yyyy',
    
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12',
    'projection.month.format' = 'MM',
    
    'projection.day.type' = 'integer', 
    'projection.day.range' = '1,31',
    'projection.day.format' = 'DD',
    
    'storage.location.template' = 's3://flight-data-raw-{environment}-{random_suffix}/ingestion-logs/year=${year}/month=${month}/day=${day}/',
    
    'classification' = 'json',
    'compressionType' = 'gzip'
);

-- =============================================================================
-- CREATE INDEXES FOR QUERY PERFORMANCE (SIMULATED WITH VIEWS)
-- =============================================================================

-- Note: Athena doesn't support traditional indexes, but we can create optimized views
-- that act as materialized query patterns for common access patterns

-- View for recent data (last 24 hours) - frequently accessed
CREATE OR REPLACE VIEW recent_raw_flight_data AS
SELECT 
    time,
    states,
    year,
    month, 
    day,
    hour,
    -- Add computed columns for common queries
    from_unixtime(time) as collection_timestamp,
    cardinality(states) as aircraft_count
FROM raw_flight_data
WHERE 
    -- Optimize for recent data queries (last 24 hours)
    year = year(current_date) 
    AND month = month(current_date)
    AND (
        (day = day(current_date) AND hour >= hour(current_timestamp) - 24) 
        OR 
        (day = day(current_date) - 1 AND hour >= hour(current_timestamp) + 24 - 24)
    )
    AND time >= unix_timestamp(current_timestamp) - 86400; -- 24 hours

-- View for current day data - high frequency access
CREATE OR REPLACE VIEW today_raw_flight_data AS  
SELECT
    time,
    states,
    hour,
    from_unixtime(time) as collection_timestamp,
    cardinality(states) as aircraft_count
FROM raw_flight_data
WHERE 
    year = year(current_date)
    AND month = month(current_date) 
    AND day = day(current_date);

-- =============================================================================
-- TABLE STATISTICS AND OPTIMIZATION
-- =============================================================================

-- Analyze tables to update statistics (run after data ingestion)
-- Note: These would typically be run via scheduled maintenance

/*
-- Example maintenance commands to run periodically:

-- Update table statistics
ANALYZE TABLE raw_flight_data COMPUTE STATISTICS;
ANALYZE TABLE raw_ingestion_log COMPUTE STATISTICS; 

-- Repair partitions (if needed for manual partition management)
MSCK REPAIR TABLE raw_flight_data;
MSCK REPAIR TABLE raw_ingestion_log;

-- Show partitions to verify projection is working
SHOW PARTITIONS raw_flight_data;

-- Sample partition pruning test query
SELECT COUNT(*) 
FROM raw_flight_data 
WHERE year = '2024' AND month = '01' AND day = '15' AND hour = '10';
*/