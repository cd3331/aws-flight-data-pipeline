-- Flight Data Pipeline - Processed Data Tables
-- External tables for processed Parquet data with optimized schema and partitioning

-- Set the database context
USE flight_data_analytics;

-- =============================================================================
-- PROCESSED FLIGHT DATA TABLE (PARQUET FORMAT)
-- =============================================================================

-- Drop table if exists for clean recreation
DROP TABLE IF EXISTS processed_flight_data;

-- Create external table for processed Parquet data
CREATE EXTERNAL TABLE processed_flight_data (
    -- Core flight identification
    icao24 string COMMENT 'ICAO 24-bit address (aircraft identifier)',
    callsign string COMMENT 'Flight call sign (trimmed and cleaned)',
    origin_country string COMMENT 'Country of aircraft registration',
    
    -- Temporal information
    collection_time bigint COMMENT 'Unix timestamp of data collection',
    position_time bigint COMMENT 'Unix timestamp of position report',
    last_contact bigint COMMENT 'Unix timestamp of last contact',
    collection_datetime string COMMENT 'ISO datetime of collection (derived)',
    
    -- Position data
    longitude double COMMENT 'WGS-84 longitude in decimal degrees',
    latitude double COMMENT 'WGS-84 latitude in decimal degrees', 
    baro_altitude_m double COMMENT 'Barometric altitude in meters',
    geo_altitude_m double COMMENT 'Geometric altitude in meters',
    baro_altitude_ft int COMMENT 'Barometric altitude in feet (derived)',
    geo_altitude_ft int COMMENT 'Geometric altitude in feet (derived)',
    
    -- Movement and status
    on_ground boolean COMMENT 'Aircraft on ground status',
    velocity_ms double COMMENT 'Velocity over ground in m/s',
    velocity_knots double COMMENT 'Velocity in knots (derived)',
    velocity_kmh double COMMENT 'Velocity in km/h (derived)',
    true_track double COMMENT 'True track in degrees (0-360)',
    vertical_rate_ms double COMMENT 'Vertical rate in m/s (negative = descending)',
    vertical_rate_fpm int COMMENT 'Vertical rate in feet per minute (derived)',
    
    -- Technical data
    squawk string COMMENT 'Transponder squawk code',
    spi boolean COMMENT 'Special purpose indicator',
    position_source int COMMENT 'Position source (0=ADS-B, 1=ASTERIX, 2=MLAT)',
    sensor_count int COMMENT 'Number of contributing sensors (derived)',
    
    -- Derived analytics fields
    altitude_category string COMMENT 'Altitude category (Low/Medium/High/Very High)',
    speed_category string COMMENT 'Speed category (Slow/Normal/Fast/Very Fast)', 
    flight_phase string COMMENT 'Estimated flight phase (Ground/Takeoff/Climb/Cruise/Descent/Approach)',
    region_code string COMMENT 'Geographic region code (derived from coordinates)',
    
    -- Data quality metrics
    data_quality_score double COMMENT 'Overall data quality score (0-1)',
    completeness_score double COMMENT 'Data completeness score (0-1)',
    validity_score double COMMENT 'Data validity score (0-1)',
    consistency_score double COMMENT 'Data consistency score (0-1)',
    
    -- Processing metadata
    processing_timestamp bigint COMMENT 'Unix timestamp when record was processed',
    processing_duration_ms bigint COMMENT 'Processing time in milliseconds',
    pipeline_version string COMMENT 'Version of processing pipeline',
    quality_flags array<string> COMMENT 'Data quality issue flags'
)
COMMENT 'Processed and enriched flight data in optimized Parquet format'
PARTITIONED BY (
    year string COMMENT 'Partition by year (YYYY)',
    month string COMMENT 'Partition by month (MM)',
    day string COMMENT 'Partition by day (DD)',
    hour string COMMENT 'Partition by hour (HH)'
)
STORED AS PARQUET
LOCATION 's3://flight-data-processed-{environment}-{random_suffix}/flight-data/'
TBLPROPERTIES (
    -- Enable partition projection
    'projection.enabled' = 'true',
    
    -- Year projection
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2034',
    'projection.year.format' = 'yyyy',
    'projection.year.interval' = '1',
    'projection.year.interval.unit' = 'YEARS',
    
    -- Month projection
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12', 
    'projection.month.format' = 'MM',
    'projection.month.interval' = '1',
    'projection.month.interval.unit' = 'MONTHS',
    
    -- Day projection
    'projection.day.type' = 'integer',
    'projection.day.range' = '1,31',
    'projection.day.format' = 'DD', 
    'projection.day.interval' = '1',
    'projection.day.interval.unit' = 'DAYS',
    
    -- Hour projection
    'projection.hour.type' = 'integer',
    'projection.hour.range' = '0,23',
    'projection.hour.format' = 'HH',
    'projection.hour.interval' = '1', 
    'projection.hour.interval.unit' = 'HOURS',
    
    -- S3 location template
    'storage.location.template' = 's3://flight-data-processed-{environment}-{random_suffix}/flight-data/year=${year}/month=${month}/day=${day}/hour=${hour}/',
    
    -- Parquet optimization
    'parquet.compression' = 'SNAPPY',
    'parquet.enable.dictionary' = 'true',
    'parquet.page.size' = '1048576', -- 1MB pages
    'parquet.block.size' = '134217728', -- 128MB blocks
    
    -- Query optimization  
    'classification' = 'parquet',
    'columnar.serde' = 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe',
    
    -- Schema evolution support
    'parquet.write.int96.as.timestamp' = 'true',
    'parquet.timestamp.skip.conversion' = 'true',
    
    -- Metadata
    'created_by' = 'flight-data-processing-pipeline',
    'version' = '1.0',
    'optimization_level' = 'high_performance'
);

-- =============================================================================
-- DATA QUALITY METRICS TABLE
-- =============================================================================

-- Drop table if exists
DROP TABLE IF EXISTS data_quality_metrics;

-- Create table for detailed quality metrics per processing batch
CREATE EXTERNAL TABLE data_quality_metrics (
    -- Batch identification
    batch_id string COMMENT 'Unique batch identifier',
    processing_timestamp bigint COMMENT 'Unix timestamp of processing',
    
    -- Volume metrics
    total_records bigint COMMENT 'Total records in batch',
    valid_records bigint COMMENT 'Records passing validation',
    invalid_records bigint COMMENT 'Records failing validation', 
    duplicate_records bigint COMMENT 'Duplicate records found',
    
    -- Quality scores (0-1 scale)
    overall_quality_score double COMMENT 'Overall quality score',
    completeness_score double COMMENT 'Data completeness score',
    validity_score double COMMENT 'Data validity score', 
    consistency_score double COMMENT 'Data consistency score',
    timeliness_score double COMMENT 'Data timeliness score',
    accuracy_score double COMMENT 'Data accuracy score',
    
    -- Field-level quality metrics
    missing_icao24_count bigint COMMENT 'Missing ICAO24 identifiers',
    missing_position_count bigint COMMENT 'Missing position data',
    missing_altitude_count bigint COMMENT 'Missing altitude data',
    missing_velocity_count bigint COMMENT 'Missing velocity data',
    invalid_coordinate_count bigint COMMENT 'Invalid coordinates', 
    invalid_altitude_count bigint COMMENT 'Invalid altitude values',
    invalid_velocity_count bigint COMMENT 'Invalid velocity values',
    
    -- Anomaly detection results
    altitude_anomaly_count bigint COMMENT 'Altitude anomalies detected',
    velocity_anomaly_count bigint COMMENT 'Velocity anomalies detected',
    position_anomaly_count bigint COMMENT 'Position anomalies detected',
    temporal_anomaly_count bigint COMMENT 'Temporal anomalies detected',
    
    -- Processing performance
    processing_duration_ms bigint COMMENT 'Total processing time',
    validation_duration_ms bigint COMMENT 'Validation processing time', 
    enrichment_duration_ms bigint COMMENT 'Enrichment processing time',
    storage_duration_ms bigint COMMENT 'Storage processing time',
    
    -- Source data characteristics
    api_response_time_ms bigint COMMENT 'Source API response time',
    source_data_size_bytes bigint COMMENT 'Source data size',
    processed_data_size_bytes bigint COMMENT 'Processed data size',
    compression_ratio double COMMENT 'Compression efficiency'
)
COMMENT 'Detailed data quality metrics and processing statistics'
PARTITIONED BY (
    year string COMMENT 'Processing year (YYYY)',
    month string COMMENT 'Processing month (MM)',
    day string COMMENT 'Processing day (DD)'
)
STORED AS PARQUET
LOCATION 's3://flight-data-processed-{environment}-{random_suffix}/quality-metrics/'
TBLPROPERTIES (
    -- Partition projection
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
    
    'storage.location.template' = 's3://flight-data-processed-{environment}-{random_suffix}/quality-metrics/year=${year}/month=${month}/day=${day}/',
    
    'parquet.compression' = 'SNAPPY',
    'classification' = 'parquet'
);

-- =============================================================================
-- AIRCRAFT REFERENCE DATA TABLE
-- =============================================================================

-- Drop table if exists  
DROP TABLE IF EXISTS aircraft_reference;

-- Create table for aircraft reference data (relatively static)
CREATE EXTERNAL TABLE aircraft_reference (
    icao24 string COMMENT 'ICAO 24-bit address',
    registration string COMMENT 'Aircraft registration/tail number',
    manufacturericao string COMMENT 'Manufacturer ICAO code',
    manufacturername string COMMENT 'Manufacturer name',
    model string COMMENT 'Aircraft model',
    typecode string COMMENT 'Aircraft type code', 
    serialnumber string COMMENT 'Aircraft serial number',
    linenumber string COMMENT 'Aircraft line number',
    icaoaircrafttype string COMMENT 'ICAO aircraft type designator',
    operator string COMMENT 'Aircraft operator',
    operatorcallsign string COMMENT 'Operator call sign',
    operatoricao string COMMENT 'Operator ICAO code',
    operatoriata string COMMENT 'Operator IATA code',
    owner string COMMENT 'Aircraft owner',
    testreg string COMMENT 'Test registration',
    registered string COMMENT 'Registration date',
    reguntil string COMMENT 'Registration valid until',
    status string COMMENT 'Aircraft status',
    built string COMMENT 'Manufacturing date',
    firstflightdate string COMMENT 'First flight date',
    seatconfiguration string COMMENT 'Seat configuration',
    engines string COMMENT 'Engine information',
    modes boolean COMMENT 'Mode S equipped',
    adsb boolean COMMENT 'ADS-B equipped', 
    acars boolean COMMENT 'ACARS equipped',
    notes string COMMENT 'Additional notes',
    categoryDescription string COMMENT 'Aircraft category description',
    last_updated string COMMENT 'Last update timestamp'
)
COMMENT 'Aircraft reference data and registration information'
STORED AS PARQUET
LOCATION 's3://flight-data-processed-{environment}-{random_suffix}/aircraft-reference/'
TBLPROPERTIES (
    'parquet.compression' = 'SNAPPY',
    'classification' = 'parquet',
    'data_source' = 'opensky_aircraft_database',
    'update_frequency' = 'weekly'
);

-- =============================================================================
-- AIRPORT REFERENCE DATA TABLE  
-- =============================================================================

-- Drop table if exists
DROP TABLE IF EXISTS airport_reference;

-- Create table for airport reference data
CREATE EXTERNAL TABLE airport_reference (
    icao_code string COMMENT 'ICAO airport code',
    iata_code string COMMENT 'IATA airport code', 
    airport_name string COMMENT 'Airport name',
    city string COMMENT 'Airport city',
    country string COMMENT 'Airport country',
    latitude double COMMENT 'Airport latitude',
    longitude double COMMENT 'Airport longitude',
    elevation_ft int COMMENT 'Airport elevation in feet',
    timezone string COMMENT 'Airport timezone',
    dst string COMMENT 'Daylight saving time info',
    tz_database_time_zone string COMMENT 'Timezone database name',
    airport_type string COMMENT 'Airport type (large/medium/small)',
    data_source string COMMENT 'Reference data source'
)
COMMENT 'Airport reference data for geographic analysis'
STORED AS PARQUET
LOCATION 's3://flight-data-processed-{environment}-{random_suffix}/airport-reference/'
TBLPROPERTIES (
    'parquet.compression' = 'SNAPPY',
    'classification' = 'parquet',
    'data_source' = 'ourairports_com',
    'update_frequency' = 'monthly'
);

-- =============================================================================
-- OPTIMIZED VIEWS FOR COMMON QUERY PATTERNS
-- =============================================================================

-- View for recent processed data (last 24 hours)
CREATE OR REPLACE VIEW recent_processed_flight_data AS
SELECT 
    icao24,
    callsign,
    origin_country,
    collection_datetime,
    longitude,
    latitude, 
    baro_altitude_ft,
    velocity_knots,
    altitude_category,
    speed_category,
    flight_phase,
    data_quality_score,
    year,
    month,
    day, 
    hour
FROM processed_flight_data
WHERE 
    year = year(current_date)
    AND month = month(current_date) 
    AND (
        (day = day(current_date)) 
        OR 
        (day = day(current_date) - 1 AND hour >= 18) -- Include evening of previous day
    )
    AND collection_time >= unix_timestamp(current_timestamp) - 86400;

-- View for high-quality data only (quality score > 0.8)
CREATE OR REPLACE VIEW high_quality_flight_data AS
SELECT 
    icao24,
    callsign,
    origin_country,
    collection_datetime,
    longitude,
    latitude,
    baro_altitude_ft,
    velocity_knots,
    true_track,
    altitude_category,
    speed_category,
    flight_phase,
    data_quality_score,
    year,
    month,
    day,
    hour
FROM processed_flight_data
WHERE data_quality_score > 0.8
    AND completeness_score > 0.7
    AND validity_score > 0.8;