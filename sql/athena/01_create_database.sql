-- Flight Data Pipeline - Athena Database Setup
-- This script creates the database and sets up the foundation for analytics

-- =============================================================================
-- DATABASE CREATION
-- =============================================================================

-- Create the main database for flight data analytics
CREATE DATABASE IF NOT EXISTS flight_data_analytics
COMMENT 'Flight data pipeline analytics database with raw and processed tables'
LOCATION 's3://flight-data-athena-results-{environment}-{random_suffix}/database/';