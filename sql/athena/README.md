# Flight Data Pipeline - Athena Analytics Setup

This directory contains comprehensive SQL scripts for setting up Amazon Athena analytics on flight data with optimized performance and cost-efficiency.

## 🚀 Quick Start

### 1. Execute Scripts in Order
```bash
# Run scripts in sequence
aws athena start-query-execution --query-string "$(cat 01_create_database.sql)" --work-group primary
aws athena start-query-execution --query-string "$(cat 02_create_raw_tables.sql)" --work-group primary  
aws athena start-query-execution --query-string "$(cat 03_create_processed_tables.sql)" --work-group primary
aws athena start-query-execution --query-string "$(cat 06_analytics_views.sql)" --work-group primary
```

### 2. Replace Template Variables
Before execution, replace these placeholders in SQL files:
- `{environment}` → `prod`, `staging`, or `dev`
- `{random_suffix}` → your S3 bucket suffix (e.g., `abc123def456`)

## 📁 File Structure

| File | Purpose | Tables/Views Created |
|------|---------|----------------------|
| `01_create_database.sql` | Database setup | `flight_data_analytics` |
| `02_create_raw_tables.sql` | Raw JSON data tables | `raw_flight_data`, `raw_ingestion_log` |
| `03_create_processed_tables.sql` | Processed Parquet tables | `processed_flight_data`, `data_quality_metrics`, `aircraft_reference`, `airport_reference` |
| `04_analytical_queries.sql` | 10 optimized analytical queries | Query examples |
| `05_analytical_queries_part2.sql` | Additional analytical queries | Query examples |
| `06_analytics_views.sql` | Common analytics views | `hourly_flight_summary`, `daily_flight_summary`, `realtime_flight_metrics`, `data_quality_dashboard` |

## 📊 Table Architecture

### Raw Data Tables (JSON Format)

#### `raw_flight_data`
- **Format**: JSON with GZIP compression
- **Partitioning**: `year/month/day/hour` 
- **Partition Projection**: Automatic discovery (2024-2034)
- **Data Source**: OpenSky Network API responses
- **Usage**: Source data ingestion and historical analysis

```sql
-- Example query with partition pruning
SELECT COUNT(*) 
FROM raw_flight_data 
WHERE year = '2024' AND month = '01' AND day = '15' 
  AND hour BETWEEN '08' AND '18';
```

#### `raw_ingestion_log`
- **Format**: JSON metadata and execution logs  
- **Partitioning**: `year/month/day`
- **Purpose**: Pipeline monitoring and troubleshooting

### Processed Data Tables (Parquet Format)

#### `processed_flight_data` 
- **Format**: Parquet with Snappy compression
- **Partitioning**: `year/month/day/hour`
- **Schema**: 40+ enriched columns with derived analytics fields
- **Optimization**: Columnar storage, dictionary encoding, 128MB blocks

**Key Features:**
- ✅ **Enriched Data**: Altitude/speed categories, flight phases, geographic regions
- ✅ **Quality Scoring**: Data quality, completeness, validity, consistency scores
- ✅ **Unit Conversions**: Altitude (ft), velocity (knots/kmh), vertical rate (fpm)
- ✅ **Analytics Fields**: Region codes, performance classifications

#### `data_quality_metrics`
- **Format**: Parquet with quality metrics per processing batch
- **Partitioning**: `year/month/day`
- **Purpose**: Quality monitoring, anomaly detection, performance tracking

#### `aircraft_reference` & `airport_reference`
- **Format**: Parquet reference data
- **Update Frequency**: Weekly (aircraft), Monthly (airports)
- **Purpose**: Enrichment lookups and geographic analysis

## 🔍 Analytical Query Collection

### Query Categories

**Operational Monitoring (Queries 1-3)**
1. **Current Flight Status Overview** - Real-time dashboard metrics
2. **Flight Distribution by Altitude** - Traffic pattern analysis  
3. **Data Quality Metrics by Hour** - Quality trend monitoring

**Traffic Analysis (Queries 4-6)**
4. **Peak Traffic Analysis** - Congestion identification and patterns
5. **Route Corridor Identification** - Major flight path analysis
6. **Anomaly Detection** - Unusual flight pattern identification

**Performance Analysis (Queries 7-10)**
7. **Aircraft Performance Analysis** - Efficiency and capability metrics
8. **Airport Proximity Analysis** - Terminal area traffic patterns
9. **Temporal Flight Patterns** - Time-based activity analysis
10. **Data Quality Assessment** - Comprehensive quality reporting

### Query Optimization Features

**Partition Pruning**
```sql
-- Efficient: Uses partition projection
WHERE year = '2024' AND month = '01' AND day = '15'

-- Inefficient: Scans all partitions  
WHERE collection_time >= '2024-01-15 00:00:00'
```

**Column Selection**
```sql
-- Efficient: Only required columns
SELECT icao24, latitude, longitude, baro_altitude_ft
FROM processed_flight_data

-- Inefficient: SELECT *
SELECT * FROM processed_flight_data
```

**Approximate Functions**
```sql
-- Cost-effective for large datasets
APPROX_PERCENTILE(altitude, 0.95) as p95_altitude
APPROX_COUNT_DISTINCT(icao24) as unique_aircraft
```

## 📈 Analytics Views

### Hourly Summary Statistics (`hourly_flight_summary`)

**Purpose**: Dashboard consumption and trend analysis
**Refresh**: Real-time (view-based)
**Aggregation Level**: Per hour

**Key Metrics:**
- Volume: flights, aircraft, countries
- Performance: altitude/speed statistics  
- Distribution: altitude/speed/phase categories
- Geography: major region activity
- Quality: data quality scores and grades

```sql
-- Usage example
SELECT hour_datetime, total_flights, traffic_level,
       avg_altitude_ft, avg_data_quality_score
FROM hourly_flight_summary  
WHERE year = '2024' AND month = '01' AND day = '15'
ORDER BY hour_datetime;
```

### Daily Aggregations (`daily_flight_summary`)

**Purpose**: Historical analysis and reporting
**Aggregation Level**: Per day
**Features**: Day-of-week analysis, traffic patterns, quality trends

**Key Metrics:**
- Volume classification (Very High/High/Moderate/Low/Very Low)
- Traffic consistency assessment
- Geographic coverage analysis
- Processing performance tracking

### Real-time Metrics (`realtime_flight_metrics`)

**Purpose**: Live operational dashboard
**Update Frequency**: Current hour data
**Features**: Trend comparison, system health status

**Key Metrics:**
- Current activity: flights per minute, airborne percentage
- Real-time performance: altitude/speed distributions
- System health: data quality, freshness indicators
- Traffic intensity classification

### Data Quality Dashboard (`data_quality_dashboard`)

**Purpose**: Quality monitoring and alerting
**Focus**: Last 4 hours rolling window + current hour
**Features**: Alert triggering, quality status flags

**Quality Indicators:**
- Overall quality scores and trends
- Missing data percentages  
- Invalid data detection
- Quality alert thresholds

## 💰 Cost Optimization Strategies

### 1. Partition Projection Benefits

**Cost Savings**: Eliminates S3 LIST operations
```sql
-- Automatic partition discovery
'projection.enabled' = 'true'
'projection.year.type' = 'integer'
'projection.year.range' = '2024,2034'
```

**Cost Impact**: 
- Reduces query planning time by 80%
- Eliminates metadata storage costs
- Prevents accidental full-table scans

### 2. Parquet Optimization

**Storage Efficiency**:
```sql
-- Optimized Parquet configuration
'parquet.compression' = 'SNAPPY'
'parquet.page.size' = '1048576'      -- 1MB pages
'parquet.block.size' = '134217728'   -- 128MB blocks
'parquet.enable.dictionary' = 'true'
```

**Benefits**:
- 5-10x compression vs JSON
- Column pruning reduces I/O
- Predicate pushdown minimizes data scanned

### 3. Query Patterns for Cost Control

**Time-bound Queries**:
```sql
-- Limit time range for cost control
WHERE year = year(current_date)
  AND month = month(current_date)
  AND day >= day(current_date) - 7  -- Last 7 days only
```

**Selective Column Access**:
```sql
-- Only query needed columns
SELECT icao24, baro_altitude_ft, velocity_knots
FROM processed_flight_data
WHERE -- conditions
```

**Approximate Aggregations**:
```sql
-- Use approximate functions for large datasets
APPROX_PERCENTILE(altitude, 0.95)  -- vs exact PERCENTILE
APPROX_COUNT_DISTINCT(icao24)      -- vs exact COUNT DISTINCT
```

### 4. Data Lifecycle Management

**Table Lifecycle**:
- **Raw Data**: 90 days → Glacier → Deep Archive
- **Processed Data**: 365 days → IA → Glacier  
- **Quality Metrics**: 180 days → IA → Delete
- **Reference Data**: Update cycles only

## ⚡ Performance Optimization

### 1. Query Performance Best Practices

**Partition Pruning**:
```sql
-- Always include partition columns in WHERE clause
WHERE year = '2024' 
  AND month = '01' 
  AND day BETWEEN '01' AND '07'
  AND hour BETWEEN '08' AND '18'
```

**Filter Early**:
```sql
-- Apply filters before joins and aggregations
WHERE data_quality_score > 0.7
  AND NOT on_ground
  AND baro_altitude_ft > 1000
```

**Efficient Joins**:
```sql
-- Join on partitioned columns when possible
FROM processed_flight_data p
JOIN aircraft_reference a ON p.icao24 = a.icao24
WHERE p.year = '2024' AND p.month = '01'  -- Partition pruning
```

### 2. View Optimization

**Materialized Query Patterns**:
- Pre-aggregated hourly summaries
- Common filter combinations
- Geographic region groupings
- Quality score classifications

**Index Simulation**:
```sql
-- Views act as "indexes" for common patterns
CREATE VIEW recent_high_quality_flights AS
SELECT * FROM processed_flight_data
WHERE data_quality_score > 0.8
  AND collection_time >= unix_timestamp() - 86400;
```

### 3. Workload Management

**Query Prioritization**:
- Real-time dashboard: Small time windows, frequent execution
- Historical analysis: Larger time windows, scheduled execution  
- Ad-hoc exploration: Interactive, user-driven

**Resource Allocation**:
- Separate workgroups for different query types
- Query result caching for repeated patterns
- Concurrent query limits

## 🔒 Security and Access Control

### Table-Level Security

**IAM Policies**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow", 
      "Action": ["athena:GetQueryExecution", "athena:GetQueryResults"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::flight-data-*/*"]
    }
  ]
}
```

**Column-Level Security**:
```sql
-- Sensitive data views
CREATE VIEW public_flight_data AS
SELECT icao24, longitude, latitude, baro_altitude_ft, velocity_knots
FROM processed_flight_data
-- Exclude: callsign, origin_country, detailed quality metrics
```

### Data Privacy

**Anonymization Options**:
```sql
-- Geographic fuzzing for privacy
SELECT 
  ROUND(latitude, 2) as fuzzy_latitude,    -- ~1km precision
  ROUND(longitude, 2) as fuzzy_longitude,
  -- Other fields...
FROM processed_flight_data
```

## 📝 Maintenance Procedures

### Daily Tasks

**Quality Monitoring**:
```sql
-- Check data quality dashboard  
SELECT * FROM data_quality_dashboard;

-- Verify partition creation
SHOW PARTITIONS processed_flight_data;
```

**Performance Monitoring**:
```sql
-- Query execution times
SELECT query_id, query, execution_time_in_millis
FROM information_schema.query_history
WHERE creation_time >= current_date - 1;
```

### Weekly Tasks

**Table Statistics**:
```sql
-- Update table statistics for query optimization
ANALYZE TABLE processed_flight_data COMPUTE STATISTICS;
ANALYZE TABLE data_quality_metrics COMPUTE STATISTICS;
```

**Reference Data Updates**:
```sql
-- Refresh aircraft reference data (weekly)
-- Refresh airport reference data (monthly)
```

### Monthly Tasks

**Cost Analysis**:
```sql
-- Data scanned analysis
SELECT 
  query_id,
  data_scanned_in_bytes / 1024 / 1024 / 1024 as gb_scanned,
  execution_time_in_millis / 1000 as execution_seconds
FROM information_schema.query_history
WHERE creation_time >= current_date - 30
ORDER BY data_scanned_in_bytes DESC
LIMIT 50;
```

**Performance Tuning**:
- Review slow queries and optimize
- Update partition projection ranges
- Refresh query result cache policies

## 🚨 Troubleshooting Guide

### Common Issues

**Query Timeout**:
```sql
-- Reduce time range or add more filters
WHERE year = '2024' AND month = '01' AND day = '15'  -- Single day
  AND data_quality_score > 0.8                      -- Filter early
```

**High Data Scan Costs**:
```sql
-- Use partition projection effectively
WHERE year = year(current_date)                     -- Partition pruning
  AND month = month(current_date)
LIMIT 1000;                                         -- Add LIMIT
```

**Missing Data**:
```sql
-- Verify partition existence
SHOW PARTITIONS raw_flight_data;

-- Check data freshness
SELECT MAX(collection_time), COUNT(*)
FROM processed_flight_data
WHERE year = year(current_date);
```

**Quality Issues**:
```sql
-- Investigate quality problems
SELECT quality_alerts, overall_assessment
FROM data_quality_dashboard;

-- Check specific quality metrics
SELECT * FROM data_quality_metrics
WHERE overall_quality_score < 0.7
ORDER BY processing_timestamp DESC
LIMIT 20;
```

## 📚 Usage Examples

### Dashboard Queries

**Real-time Status**:
```sql
SELECT report_timestamp, current_hour_flights, currently_airborne,
       current_traffic_intensity, system_health_status
FROM realtime_flight_metrics;
```

**Hourly Trends**:
```sql
SELECT hour_datetime, total_flights, avg_altitude_ft,
       traffic_level, avg_data_quality_score
FROM hourly_flight_summary
WHERE year = year(current_date) AND month = month(current_date)
  AND day = day(current_date)
ORDER BY hour_datetime DESC;
```

### Analytical Queries

**Performance Analysis**:
```sql
-- Top performing aircraft
SELECT icao24, aircraft_model, efficiency_score, 
       avg_cruise_speed_knots, performance_class
FROM processed_flight_data p
JOIN aircraft_reference a ON p.icao24 = a.icao24
WHERE collection_time >= unix_timestamp() - 86400
GROUP BY icao24, aircraft_model
ORDER BY efficiency_score DESC
LIMIT 20;
```

**Geographic Analysis**:
```sql
-- Regional traffic distribution
SELECT 
  CASE 
    WHEN latitude BETWEEN 30 AND 70 AND longitude BETWEEN -130 AND -60 THEN 'North America'
    WHEN latitude BETWEEN 35 AND 70 AND longitude BETWEEN -15 AND 45 THEN 'Europe'
    -- Other regions...
  END as region,
  COUNT(*) as flights,
  AVG(baro_altitude_ft) as avg_altitude,
  AVG(velocity_knots) as avg_speed
FROM processed_flight_data
WHERE year = year(current_date) AND NOT on_ground
GROUP BY 1
ORDER BY flights DESC;
```

This Athena analytics setup provides enterprise-grade flight data analysis capabilities with optimized performance, cost efficiency, and comprehensive monitoring features.