#!/bin/bash

# Daily Health Check Script for Flight Data Pipeline
# This script performs comprehensive health checks across all system components

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/health-check-$(date +%Y%m%d).log"
ALERT_THRESHOLD_ERROR_RATE=5
ALERT_THRESHOLD_LATENCY_MS=5000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Status tracking
OVERALL_STATUS="HEALTHY"
FAILED_CHECKS=()

# Print header
print_header() {
    echo -e "${GREEN}=================================================================${NC}"
    echo -e "${GREEN}       Flight Data Pipeline - Daily Health Check${NC}"
    echo -e "${GREEN}=================================================================${NC}"
    echo "Start Time: $(date)"
    echo "Log File: $LOG_FILE"
    echo ""
}

# Check if AWS CLI is configured
check_aws_cli() {
    log "Checking AWS CLI configuration..."
    
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo -e "${RED}✗ AWS CLI not configured or credentials invalid${NC}"
        OVERALL_STATUS="CRITICAL"
        FAILED_CHECKS+=("AWS CLI Configuration")
        return 1
    fi
    
    echo -e "${GREEN}✓ AWS CLI configured and working${NC}"
    return 0
}

# Check Lambda functions health
check_lambda_functions() {
    log "Checking Lambda functions..."
    
    local functions=("flightdata-processor" "flightdata-api-handler" "flightdata-aggregator" "flightdata-scheduler")
    local failed_functions=()
    
    for func in "${functions[@]}"; do
        # Check if function exists and get its state
        if ! function_info=$(aws lambda get-function --function-name "$func" 2>/dev/null); then
            echo -e "${RED}✗ Function $func not found${NC}"
            failed_functions+=("$func (not found)")
            continue
        fi
        
        # Check function state
        state=$(echo "$function_info" | jq -r '.Configuration.State')
        if [ "$state" != "Active" ]; then
            echo -e "${RED}✗ Function $func is in state: $state${NC}"
            failed_functions+=("$func ($state)")
            continue
        fi
        
        # Check for recent errors (last 1 hour)
        error_count=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/Lambda \
            --metric-name Errors \
            --dimensions Name=FunctionName,Value="$func" \
            --start-time "$(date -d '1 hour ago' --iso-8601)" \
            --end-time "$(date --iso-8601)" \
            --period 3600 \
            --statistics Sum \
            --query 'Datapoints[0].Sum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$error_count" != "None" ] && [ "$error_count" -gt 0 ]; then
            echo -e "${YELLOW}⚠ Function $func has $error_count errors in the last hour${NC}"
        else
            echo -e "${GREEN}✓ Function $func is healthy${NC}"
        fi
    done
    
    if [ ${#failed_functions[@]} -gt 0 ]; then
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("Lambda Functions: ${failed_functions[*]}")
        return 1
    fi
    
    return 0
}

# Check DynamoDB tables
check_dynamodb_tables() {
    log "Checking DynamoDB tables..."
    
    local tables=("flightdata-main" "flightdata-metrics" "flightdata-config")
    local failed_tables=()
    
    for table in "${tables[@]}"; do
        # Check table status
        if ! table_info=$(aws dynamodb describe-table --table-name "$table" 2>/dev/null); then
            echo -e "${RED}✗ Table $table not found${NC}"
            failed_tables+=("$table (not found)")
            continue
        fi
        
        # Check table status
        status=$(echo "$table_info" | jq -r '.Table.TableStatus')
        if [ "$status" != "ACTIVE" ]; then
            echo -e "${RED}✗ Table $table status: $status${NC}"
            failed_tables+=("$table ($status)")
            continue
        fi
        
        # Check for throttling in the last hour
        throttle_count=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/DynamoDB \
            --metric-name ThrottledRequests \
            --dimensions Name=TableName,Value="$table" \
            --start-time "$(date -d '1 hour ago' --iso-8601)" \
            --end-time "$(date --iso-8601)" \
            --period 3600 \
            --statistics Sum \
            --query 'Datapoints[0].Sum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$throttle_count" != "None" ] && [ "$throttle_count" -gt 0 ]; then
            echo -e "${YELLOW}⚠ Table $table has $throttle_count throttled requests${NC}"
        else
            echo -e "${GREEN}✓ Table $table is healthy${NC}"
        fi
    done
    
    if [ ${#failed_tables[@]} -gt 0 ]; then
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("DynamoDB Tables: ${failed_tables[*]}")
        return 1
    fi
    
    return 0
}

# Check S3 buckets
check_s3_buckets() {
    log "Checking S3 buckets..."
    
    local buckets=("flightdata-raw" "flightdata-processed" "flightdata-analytics" "flightdata-backups")
    local failed_buckets=()
    
    for bucket in "${buckets[@]}"; do
        # Check bucket accessibility
        if ! aws s3 ls "s3://$bucket/" >/dev/null 2>&1; then
            echo -e "${RED}✗ Bucket $bucket not accessible${NC}"
            failed_buckets+=("$bucket")
            continue
        fi
        
        # Check recent object count (as a proxy for activity)
        recent_objects=$(aws s3 ls "s3://$bucket/" --recursive | wc -l)
        if [ "$recent_objects" -eq 0 ]; then
            echo -e "${YELLOW}⚠ Bucket $bucket appears empty${NC}"
        else
            echo -e "${GREEN}✓ Bucket $bucket is accessible ($recent_objects objects)${NC}"
        fi
    done
    
    if [ ${#failed_buckets[@]} -gt 0 ]; then
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("S3 Buckets: ${failed_buckets[*]}")
        return 1
    fi
    
    return 0
}

# Check API Gateway health
check_api_gateway() {
    log "Checking API Gateway..."
    
    # Get API Gateway endpoint (this would be your actual endpoint)
    API_ENDPOINT="https://api.flightdata-pipeline.com"
    
    # Test health endpoint
    if ! response=$(curl -s -w "%{http_code}" -o /tmp/api_response "$API_ENDPOINT/health" 2>/dev/null); then
        echo -e "${RED}✗ API Gateway not responding${NC}"
        OVERALL_STATUS="CRITICAL"
        FAILED_CHECKS+=("API Gateway (not responding)")
        return 1
    fi
    
    http_code=$(tail -c 3 <<< "$response")
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✓ API Gateway is healthy (HTTP $http_code)${NC}"
    else
        echo -e "${RED}✗ API Gateway returned HTTP $http_code${NC}"
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("API Gateway (HTTP $http_code)")
        return 1
    fi
    
    return 0
}

# Check data freshness
check_data_freshness() {
    log "Checking data freshness..."
    
    # Check latest data in processed bucket
    latest_processed=$(aws s3 ls s3://flightdata-processed/ --recursive | tail -1 | awk '{print $1 " " $2}')
    
    if [ -z "$latest_processed" ]; then
        echo -e "${RED}✗ No processed data found${NC}"
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("Data Freshness (no data)")
        return 1
    fi
    
    # Convert to timestamp and check if older than 1 hour
    latest_timestamp=$(date -d "$latest_processed" +%s 2>/dev/null || echo "0")
    current_timestamp=$(date +%s)
    age_minutes=$(( (current_timestamp - latest_timestamp) / 60 ))
    
    if [ "$age_minutes" -gt 60 ]; then
        echo -e "${YELLOW}⚠ Latest processed data is $age_minutes minutes old${NC}"
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("Data Freshness ($age_minutes minutes old)")
    else
        echo -e "${GREEN}✓ Data is fresh (last processed: $age_minutes minutes ago)${NC}"
    fi
    
    return 0
}

# Check external dependencies
check_external_dependencies() {
    log "Checking external dependencies..."
    
    # Check OpenSky Network API
    if ! response=$(curl -s -w "%{http_code}" -o /dev/null "https://opensky-network.org/api/states/all?lamin=45.8389&lomin=5.9962&lamax=47.8229&lomax=10.5226" 2>/dev/null); then
        echo -e "${YELLOW}⚠ OpenSky Network API not responding${NC}"
    elif [ "$response" -eq 200 ]; then
        echo -e "${GREEN}✓ OpenSky Network API is accessible${NC}"
    else
        echo -e "${YELLOW}⚠ OpenSky Network API returned HTTP $response${NC}"
    fi
    
    # Check other external services as needed
    return 0
}

# Check system metrics and alerts
check_system_metrics() {
    log "Checking system metrics..."
    
    # Check for any active CloudWatch alarms
    active_alarms=$(aws cloudwatch describe-alarms \
        --state-value ALARM \
        --query 'MetricAlarms[?starts_with(AlarmName, `flightdata`)].AlarmName' \
        --output text)
    
    if [ -n "$active_alarms" ]; then
        echo -e "${RED}✗ Active CloudWatch alarms: $active_alarms${NC}"
        OVERALL_STATUS="DEGRADED"
        FAILED_CHECKS+=("CloudWatch Alarms: $active_alarms")
    else
        echo -e "${GREEN}✓ No active CloudWatch alarms${NC}"
    fi
    
    # Check error rates across services
    overall_error_rate=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --start-time "$(date -d '1 hour ago' --iso-8601)" \
        --end-time "$(date --iso-8601)" \
        --period 3600 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$overall_error_rate" != "None" ] && [ "$overall_error_rate" -gt $ALERT_THRESHOLD_ERROR_RATE ]; then
        echo -e "${YELLOW}⚠ Overall error rate: $overall_error_rate errors in last hour${NC}"
    else
        echo -e "${GREEN}✓ Error rates within normal limits${NC}"
    fi
    
    return 0
}

# Generate health report summary
generate_summary() {
    echo ""
    echo -e "${GREEN}=================================================================${NC}"
    echo -e "${GREEN}                    HEALTH CHECK SUMMARY${NC}"
    echo -e "${GREEN}=================================================================${NC}"
    echo "Completion Time: $(date)"
    echo "Overall Status: $OVERALL_STATUS"
    
    if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed successfully${NC}"
        echo "System is operating normally."
    else
        echo -e "${RED}✗ Failed Checks:${NC}"
        for check in "${FAILED_CHECKS[@]}"; do
            echo "  - $check"
        done
        echo ""
        echo "Recommended Actions:"
        echo "1. Review failed components immediately"
        echo "2. Check CloudWatch logs for detailed error information"
        echo "3. Consider triggering incident response if critical services affected"
        echo "4. Update monitoring team with current status"
    fi
    
    echo ""
    echo "Log file: $LOG_FILE"
    echo -e "${GREEN}=================================================================${NC}"
}

# Send alerts if needed
send_alerts() {
    if [ "$OVERALL_STATUS" = "CRITICAL" ] || [ "$OVERALL_STATUS" = "DEGRADED" ]; then
        # Send SNS notification (configure your SNS topic ARN)
        SNS_TOPIC="arn:aws:sns:us-east-1:ACCOUNT:flightdata-alerts"
        
        MESSAGE="Flight Data Pipeline Health Check Alert
Status: $OVERALL_STATUS
Failed Checks: ${#FAILED_CHECKS[@]}
Time: $(date)

Failed Components:
$(printf '%s\n' "${FAILED_CHECKS[@]}")

Review system status immediately.
"
        
        if aws sns publish --topic-arn "$SNS_TOPIC" --message "$MESSAGE" --subject "Health Check Alert - $OVERALL_STATUS" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Alert sent via SNS${NC}"
        else
            echo -e "${YELLOW}⚠ Failed to send SNS alert${NC}"
        fi
    fi
}

# Main execution
main() {
    print_header
    
    # Run all health checks
    check_aws_cli
    check_lambda_functions
    check_dynamodb_tables
    check_s3_buckets
    check_api_gateway
    check_data_freshness
    check_external_dependencies
    check_system_metrics
    
    # Generate summary
    generate_summary
    
    # Send alerts if needed
    send_alerts
    
    # Exit with appropriate code
    case "$OVERALL_STATUS" in
        "HEALTHY")
            exit 0
            ;;
        "DEGRADED")
            exit 1
            ;;
        "CRITICAL")
            exit 2
            ;;
        *)
            exit 1
            ;;
    esac
}

# Handle script interruption
trap 'echo "Health check interrupted"; exit 130' INT TERM

# Run main function
main "$@"