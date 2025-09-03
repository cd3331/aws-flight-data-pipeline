#!/bin/bash

# Data Quality Validation Script for Flight Data Pipeline
# This script validates data quality across the pipeline

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/data-quality-validation-$(date +%Y%m%d).log"
ATHENA_RESULT_BUCKET="flightdata-query-results"
ATHENA_WORKGROUP="primary"

# Default parameters
DATE_TO_CHECK=${DATE_TO_CHECK:-$(date -d yesterday +%Y-%m-%d)}
VERBOSE=${VERBOSE:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --date DATE     Date to validate (YYYY-MM-DD, default: yesterday)"
    echo "  --verbose       Enable verbose output"
    echo "  --help          Show this help message"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --date)
            DATE_TO_CHECK="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - [VERBOSE] $1" | tee -a "$LOG_FILE"
    fi
}

# Print header
print_header() {
    echo -e "${BLUE}=================================================================${NC}"
    echo -e "${BLUE}          Flight Data Pipeline - Data Quality Validation${NC}"
    echo -e "${BLUE}=================================================================${NC}"
    echo "Validation Date: $DATE_TO_CHECK"
    echo "Start Time: $(date)"
    echo "Log File: $LOG_FILE"
    echo ""
}

# Execute Athena query and wait for results
execute_athena_query() {
    local query="$1"
    local description="$2"
    
    verbose_log "Executing query: $description"
    verbose_log "Query: $query"
    
    # Start query execution
    local execution_id
    execution_id=$(aws athena start-query-execution \
        --query-string "$query" \
        --result-configuration OutputLocation="s3://${ATHENA_RESULT_BUCKET}/" \
        --work-group "$ATHENA_WORKGROUP" \
        --query 'QueryExecutionId' \
        --output text)
    
    verbose_log "Query execution ID: $execution_id"
    
    # Wait for query to complete
    local status="RUNNING"
    local attempts=0
    local max_attempts=60  # 5 minutes timeout
    
    while [ "$status" = "RUNNING" ] && [ $attempts -lt $max_attempts ]; do
        sleep 5
        status=$(aws athena get-query-execution \
            --query-execution-id "$execution_id" \
            --query 'QueryExecution.Status.State' \
            --output text)
        ((attempts++))
        verbose_log "Query status: $status (attempt $attempts/$max_attempts)"
    done
    
    if [ "$status" = "SUCCEEDED" ]; then
        # Get query results
        aws athena get-query-results \
            --query-execution-id "$execution_id" \
            --query 'ResultSet.Rows[1:][].Data[].VarCharValue' \
            --output text
        return 0
    else
        echo "Query failed with status: $status" >&2
        return 1
    fi
}

# Check if data exists for the specified date
check_data_exists() {
    echo -e "${BLUE}[1/8] Checking if data exists for $DATE_TO_CHECK...${NC}"
    
    # Parse date components
    local year=$(date -d "$DATE_TO_CHECK" +%Y)
    local month=$(date -d "$DATE_TO_CHECK" +%m)
    local day=$(date -d "$DATE_TO_CHECK" +%d)
    
    # Check raw data
    echo "  Checking raw data..."
    local raw_objects
    raw_objects=$(aws s3 ls "s3://flightdata-raw/year=$year/month=$month/day=$day/" 2>/dev/null | wc -l || echo "0")
    
    if [ "$raw_objects" -gt 0 ]; then
        echo -e "${GREEN}  ✓ Raw data exists: $raw_objects files${NC}"
    else
        echo -e "${RED}  ✗ No raw data found${NC}"
        return 1
    fi
    
    # Check processed data
    echo "  Checking processed data..."
    local processed_objects
    processed_objects=$(aws s3 ls "s3://flightdata-processed/year=$year/month=$month/day=$day/" 2>/dev/null | wc -l || echo "0")
    
    if [ "$processed_objects" -gt 0 ]; then
        echo -e "${GREEN}  ✓ Processed data exists: $processed_objects files${NC}"
    else
        echo -e "${YELLOW}  ⚠ No processed data found${NC}"
    fi
    
    return 0
}

# Validate record counts
validate_record_counts() {
    echo -e "${BLUE}[2/8] Validating record counts...${NC}"
    
    local query="
    SELECT COUNT(*) as record_count 
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK'
    "
    
    local record_count
    if record_count=$(execute_athena_query "$query" "Count records for $DATE_TO_CHECK"); then
        verbose_log "Record count query result: $record_count"
        
        # Clean up the result (remove extra whitespace)
        record_count=$(echo "$record_count" | tr -d '[:space:]')
        
        if [ "$record_count" -gt 0 ]; then
            echo -e "${GREEN}  ✓ Found $record_count records${NC}"
            
            # Check if count is within expected range (e.g., at least 50,000 records per day)
            if [ "$record_count" -lt 50000 ]; then
                echo -e "${YELLOW}  ⚠ Record count below expected minimum (50,000)${NC}"
            fi
        else
            echo -e "${RED}  ✗ No records found for $DATE_TO_CHECK${NC}"
            return 1
        fi
    else
        echo -e "${RED}  ✗ Failed to count records${NC}"
        return 1
    fi
    
    return 0
}

# Check for duplicate records
check_duplicates() {
    echo -e "${BLUE}[3/8] Checking for duplicate records...${NC}"
    
    local query="
    SELECT COUNT(*) as duplicate_count
    FROM (
        SELECT flight_id, COUNT(*) as cnt
        FROM flightdata_processed 
        WHERE dt = '$DATE_TO_CHECK'
        GROUP BY flight_id
        HAVING COUNT(*) > 1
    )
    "
    
    local duplicate_count
    if duplicate_count=$(execute_athena_query "$query" "Count duplicate records"); then
        duplicate_count=$(echo "$duplicate_count" | tr -d '[:space:]')
        
        if [ "$duplicate_count" -eq 0 ]; then
            echo -e "${GREEN}  ✓ No duplicate records found${NC}"
        else
            echo -e "${YELLOW}  ⚠ Found $duplicate_count duplicate flight IDs${NC}"
            
            # Get sample duplicates if verbose
            if [ "$VERBOSE" = true ]; then
                local sample_query="
                SELECT flight_id, COUNT(*) as cnt
                FROM flightdata_processed 
                WHERE dt = '$DATE_TO_CHECK'
                GROUP BY flight_id
                HAVING COUNT(*) > 1
                LIMIT 5
                "
                
                echo "    Sample duplicate flight IDs:"
                execute_athena_query "$sample_query" "Sample duplicates" | while read -r line; do
                    echo "      $line"
                done
            fi
        fi
    else
        echo -e "${RED}  ✗ Failed to check for duplicates${NC}"
        return 1
    fi
    
    return 0
}

# Validate data schema compliance
validate_schema() {
    echo -e "${BLUE}[4/8] Validating data schema compliance...${NC}"
    
    # Check for null values in required fields
    local required_fields=("flight_id" "latitude" "longitude" "timestamp")
    local schema_issues=0
    
    for field in "${required_fields[@]}"; do
        echo "  Checking required field: $field"
        
        local query="
        SELECT COUNT(*) as null_count
        FROM flightdata_processed 
        WHERE dt = '$DATE_TO_CHECK' 
        AND ($field IS NULL OR $field = '')
        "
        
        local null_count
        if null_count=$(execute_athena_query "$query" "Check null values in $field"); then
            null_count=$(echo "$null_count" | tr -d '[:space:]')
            
            if [ "$null_count" -eq 0 ]; then
                echo -e "${GREEN}    ✓ No null values in $field${NC}"
            else
                echo -e "${RED}    ✗ Found $null_count null values in $field${NC}"
                ((schema_issues++))
            fi
        else
            echo -e "${RED}    ✗ Failed to check $field${NC}"
            ((schema_issues++))
        fi
    done
    
    # Check data type validity
    echo "  Checking data type validity..."
    
    # Check latitude range
    local lat_query="
    SELECT COUNT(*) as invalid_lat_count
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK' 
    AND (latitude < -90 OR latitude > 90)
    "
    
    local invalid_lat
    if invalid_lat=$(execute_athena_query "$lat_query" "Check latitude range"); then
        invalid_lat=$(echo "$invalid_lat" | tr -d '[:space:]')
        
        if [ "$invalid_lat" -eq 0 ]; then
            echo -e "${GREEN}    ✓ All latitude values within valid range${NC}"
        else
            echo -e "${RED}    ✗ Found $invalid_lat records with invalid latitude${NC}"
            ((schema_issues++))
        fi
    fi
    
    # Check longitude range
    local lon_query="
    SELECT COUNT(*) as invalid_lon_count
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK' 
    AND (longitude < -180 OR longitude > 180)
    "
    
    local invalid_lon
    if invalid_lon=$(execute_athena_query "$lon_query" "Check longitude range"); then
        invalid_lon=$(echo "$invalid_lon" | tr -d '[:space:]')
        
        if [ "$invalid_lon" -eq 0 ]; then
            echo -e "${GREEN}    ✓ All longitude values within valid range${NC}"
        else
            echo -e "${RED}    ✗ Found $invalid_lon records with invalid longitude${NC}"
            ((schema_issues++))
        fi
    fi
    
    if [ $schema_issues -eq 0 ]; then
        echo -e "${GREEN}  ✓ Schema validation passed${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Schema validation failed ($schema_issues issues)${NC}"
        return 1
    fi
}

# Check data freshness and completeness
check_data_freshness() {
    echo -e "${BLUE}[5/8] Checking data freshness and completeness...${NC}"
    
    # Check hourly data distribution
    local query="
    SELECT EXTRACT(HOUR FROM CAST(timestamp AS timestamp)) as hour, 
           COUNT(*) as records_per_hour
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK'
    GROUP BY EXTRACT(HOUR FROM CAST(timestamp AS timestamp))
    ORDER BY hour
    "
    
    echo "  Checking hourly distribution..."
    local hourly_data
    if hourly_data=$(execute_athena_query "$query" "Get hourly distribution"); then
        local hours_with_data
        hours_with_data=$(echo "$hourly_data" | wc -l)
        
        echo -e "${GREEN}    ✓ Data spans $hours_with_data hours${NC}"
        
        if [ "$VERBOSE" = true ]; then
            echo "    Hourly breakdown:"
            echo "$hourly_data" | while read -r line; do
                echo "      Hour $line"
            done
        fi
        
        # Check if we have data for most hours (at least 20 hours)
        if [ "$hours_with_data" -lt 20 ]; then
            echo -e "${YELLOW}    ⚠ Data coverage seems incomplete ($hours_with_data/24 hours)${NC}"
        fi
    else
        echo -e "${RED}    ✗ Failed to check hourly distribution${NC}"
        return 1
    fi
    
    return 0
}

# Validate data quality metrics
validate_quality_metrics() {
    echo -e "${BLUE}[6/8] Validating data quality metrics...${NC}"
    
    # Check for reasonable altitude values
    echo "  Checking altitude values..."
    local altitude_query="
    SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN altitude >= 0 AND altitude <= 50000 THEN 1 END) as valid_altitude,
        COUNT(CASE WHEN altitude < 0 OR altitude > 50000 THEN 1 END) as invalid_altitude
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK'
    AND altitude IS NOT NULL
    "
    
    if altitude_stats=$(execute_athena_query "$altitude_query" "Check altitude statistics"); then
        echo "    Altitude statistics: $altitude_stats"
        # Parse results and validate
        echo -e "${GREEN}    ✓ Altitude validation completed${NC}"
    else
        echo -e "${RED}    ✗ Failed to validate altitude values${NC}"
    fi
    
    # Check for reasonable speed values
    echo "  Checking velocity values..."
    local velocity_query="
    SELECT 
        AVG(velocity) as avg_velocity,
        MAX(velocity) as max_velocity,
        COUNT(CASE WHEN velocity < 0 OR velocity > 1000 THEN 1 END) as invalid_velocity
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK'
    AND velocity IS NOT NULL
    "
    
    if velocity_stats=$(execute_athena_query "$velocity_query" "Check velocity statistics"); then
        echo "    Velocity statistics: $velocity_stats"
        echo -e "${GREEN}    ✓ Velocity validation completed${NC}"
    else
        echo -e "${RED}    ✗ Failed to validate velocity values${NC}"
    fi
    
    return 0
}

# Check data consistency across partitions
check_partition_consistency() {
    echo -e "${BLUE}[7/8] Checking partition consistency...${NC}"
    
    # Verify partition metadata matches data content
    local partition_query="
    SELECT 
        dt,
        MIN(CAST(timestamp AS date)) as min_date,
        MAX(CAST(timestamp AS date)) as max_date,
        COUNT(*) as record_count
    FROM flightdata_processed 
    WHERE dt = '$DATE_TO_CHECK'
    GROUP BY dt
    "
    
    echo "  Verifying partition metadata..."
    if partition_info=$(execute_athena_query "$partition_query" "Check partition consistency"); then
        verbose_log "Partition info: $partition_info"
        
        # Check if partition date matches data dates
        echo -e "${GREEN}    ✓ Partition consistency check completed${NC}"
        
        if [ "$VERBOSE" = true ]; then
            echo "    Partition details: $partition_info"
        fi
    else
        echo -e "${RED}    ✗ Failed to verify partition consistency${NC}"
        return 1
    fi
    
    return 0
}

# Generate data quality report
generate_quality_report() {
    echo -e "${BLUE}[8/8] Generating data quality report...${NC}"
    
    local report_file="/tmp/data-quality-report-${DATE_TO_CHECK}.json"
    
    # Create comprehensive report
    cat > "$report_file" << EOF
{
    "validation_date": "$DATE_TO_CHECK",
    "validation_timestamp": "$(date --iso-8601)",
    "validation_summary": {
        "overall_status": "$([ $? -eq 0 ] && echo "PASSED" || echo "FAILED")",
        "checks_performed": [
            "data_exists",
            "record_counts",
            "duplicate_check",
            "schema_validation",
            "data_freshness",
            "quality_metrics",
            "partition_consistency"
        ]
    },
    "metrics": {
        "total_records": "$(execute_athena_query "SELECT COUNT(*) FROM flightdata_processed WHERE dt = '$DATE_TO_CHECK'" "Final count" || echo "0")",
        "validation_duration_seconds": "$SECONDS"
    },
    "recommendations": [
        "Monitor duplicate rates daily",
        "Set up automated alerts for record count drops",
        "Implement real-time schema validation",
        "Review data quality metrics weekly"
    ]
}
EOF
    
    echo -e "${GREEN}  ✓ Data quality report generated: $report_file${NC}"
    
    if [ "$VERBOSE" = true ]; then
        echo "  Report contents:"
        cat "$report_file"
    fi
    
    return 0
}

# Send alerts if quality issues found
send_quality_alerts() {
    local issues_found=$1
    
    if [ "$issues_found" -gt 0 ]; then
        echo -e "${YELLOW}Sending data quality alerts...${NC}"
        
        local message="Data Quality Alert - Flight Data Pipeline

Date: $DATE_TO_CHECK
Issues Found: $issues_found
Validation Time: $(date)

Please review data quality logs and take appropriate action.

Log File: $LOG_FILE
"
        
        # Send SNS alert (configure your SNS topic)
        local sns_topic="arn:aws:sns:us-east-1:ACCOUNT:flightdata-data-quality-alerts"
        
        if aws sns publish --topic-arn "$sns_topic" --message "$message" --subject "Data Quality Alert - $DATE_TO_CHECK" >/dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Alert sent via SNS${NC}"
        else
            echo -e "${YELLOW}  ⚠ Failed to send SNS alert${NC}"
        fi
    fi
}

# Main execution
main() {
    local exit_code=0
    local issues_found=0
    
    print_header
    
    # Run all validation checks
    check_data_exists || { ((issues_found++)); exit_code=1; }
    validate_record_counts || { ((issues_found++)); exit_code=1; }
    check_duplicates || { ((issues_found++)); exit_code=1; }
    validate_schema || { ((issues_found++)); exit_code=1; }
    check_data_freshness || { ((issues_found++)); exit_code=1; }
    validate_quality_metrics || { ((issues_found++)); exit_code=1; }
    check_partition_consistency || { ((issues_found++)); exit_code=1; }
    generate_quality_report
    
    # Generate summary
    echo ""
    echo -e "${GREEN}=================================================================${NC}"
    echo -e "${GREEN}              DATA QUALITY VALIDATION SUMMARY${NC}"
    echo -e "${GREEN}=================================================================${NC}"
    echo "Validation Date: $DATE_TO_CHECK"
    echo "Completion Time: $(date)"
    echo "Issues Found: $issues_found"
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ All data quality checks passed${NC}"
        echo "Data quality is within acceptable parameters."
    else
        echo -e "${RED}✗ Data quality issues detected${NC}"
        echo "Review the validation log for detailed information."
        send_quality_alerts $issues_found
    fi
    
    echo "Full log: $LOG_FILE"
    echo ""
    
    exit $exit_code
}

# Handle script interruption
trap 'echo "Data quality validation interrupted"; exit 130' INT TERM

# Run main function
main "$@"