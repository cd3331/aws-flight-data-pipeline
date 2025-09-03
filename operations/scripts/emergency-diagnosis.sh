#!/bin/bash

# Emergency Diagnosis Script for Flight Data Pipeline
# This script performs rapid diagnosis during system outages or critical incidents

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/emergency-diagnosis-$(date +%Y%m%d%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Print emergency header
print_header() {
    echo -e "${RED}=================================================================${NC}"
    echo -e "${RED}           EMERGENCY SYSTEM DIAGNOSIS - FLIGHT DATA${NC}"
    echo -e "${RED}=================================================================${NC}"
    echo "Diagnosis Time: $(date)"
    echo "Log File: $LOG_FILE"
    echo "Operator: $(whoami)"
    echo ""
}

# Quick AWS connectivity test
test_aws_connectivity() {
    echo -e "${BLUE}[1/8] Testing AWS connectivity...${NC}"
    
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo -e "${RED}CRITICAL: AWS CLI not working or credentials invalid${NC}"
        echo "  - Check AWS credentials"
        echo "  - Verify network connectivity"
        echo "  - Check IAM permissions"
        return 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    REGION=$(aws configure get region || echo "us-east-1")
    
    echo -e "${GREEN}✓ AWS connectivity OK${NC}"
    echo "  Account: $ACCOUNT_ID"
    echo "  Region: $REGION"
    return 0
}

# Lambda functions emergency check
check_lambda_emergency() {
    echo -e "${BLUE}[2/8] Emergency Lambda function check...${NC}"
    
    local critical_functions=("flightdata-processor" "flightdata-api-handler")
    local function_issues=()
    
    for func in "${critical_functions[@]}"; do
        echo "  Checking $func..."
        
        # Check if function exists
        if ! function_config=$(aws lambda get-function-configuration --function-name "$func" 2>/dev/null); then
            echo -e "${RED}    ✗ Function $func NOT FOUND${NC}"
            function_issues+=("$func: not found")
            continue
        fi
        
        # Check function state
        state=$(echo "$function_config" | jq -r '.State')
        last_update_status=$(echo "$function_config" | jq -r '.LastUpdateStatus')
        
        if [ "$state" != "Active" ] || [ "$last_update_status" != "Successful" ]; then
            echo -e "${RED}    ✗ Function $func in bad state: $state ($last_update_status)${NC}"
            function_issues+=("$func: $state/$last_update_status")
        else
            echo -e "${GREEN}    ✓ Function $func is active${NC}"
        fi
        
        # Quick test invoke for API handler
        if [ "$func" = "flightdata-api-handler" ]; then
            echo "    Testing API handler..."
            if aws lambda invoke \
                --function-name "$func" \
                --payload '{"httpMethod":"GET","path":"/health","headers":{},"queryStringParameters":null}' \
                /tmp/lambda-test-response.json >/dev/null 2>&1; then
                
                status_code=$(jq -r '.statusCode' /tmp/lambda-test-response.json 2>/dev/null || echo "unknown")
                if [ "$status_code" = "200" ]; then
                    echo -e "${GREEN}    ✓ API handler responding correctly${NC}"
                else
                    echo -e "${RED}    ✗ API handler returned status: $status_code${NC}"
                    function_issues+=("$func: bad response ($status_code)")
                fi
            else
                echo -e "${RED}    ✗ API handler invoke failed${NC}"
                function_issues+=("$func: invoke failed")
            fi
        fi
    done
    
    if [ ${#function_issues[@]} -gt 0 ]; then
        echo -e "${RED}LAMBDA ISSUES DETECTED:${NC}"
        for issue in "${function_issues[@]}"; do
            echo "  - $issue"
        done
        return 1
    fi
    
    echo -e "${GREEN}✓ Critical Lambda functions operational${NC}"
    return 0
}

# Database emergency check
check_database_emergency() {
    echo -e "${BLUE}[3/8] Emergency database check...${NC}"
    
    local critical_tables=("flightdata-main" "flightdata-config")
    local db_issues=()
    
    for table in "${critical_tables[@]}"; do
        echo "  Checking table $table..."
        
        if ! table_status=$(aws dynamodb describe-table --table-name "$table" --query 'Table.TableStatus' --output text 2>/dev/null); then
            echo -e "${RED}    ✗ Table $table NOT FOUND${NC}"
            db_issues+=("$table: not found")
            continue
        fi
        
        if [ "$table_status" != "ACTIVE" ]; then
            echo -e "${RED}    ✗ Table $table status: $table_status${NC}"
            db_issues+=("$table: $table_status")
        else
            echo -e "${GREEN}    ✓ Table $table is active${NC}"
        fi
        
        # Quick read test
        if aws dynamodb scan --table-name "$table" --limit 1 >/dev/null 2>&1; then
            echo -e "${GREEN}    ✓ Table $table is readable${NC}"
        else
            echo -e "${RED}    ✗ Table $table read failed${NC}"
            db_issues+=("$table: read failed")
        fi
    done
    
    if [ ${#db_issues[@]} -gt 0 ]; then
        echo -e "${RED}DATABASE ISSUES DETECTED:${NC}"
        for issue in "${db_issues[@]}"; do
            echo "  - $issue"
        done
        return 1
    fi
    
    echo -e "${GREEN}✓ Critical database tables operational${NC}"
    return 0
}

# S3 storage emergency check
check_s3_emergency() {
    echo -e "${BLUE}[4/8] Emergency S3 storage check...${NC}"
    
    local critical_buckets=("flightdata-raw" "flightdata-processed")
    local s3_issues=()
    
    for bucket in "${critical_buckets[@]}"; do
        echo "  Checking bucket $bucket..."
        
        if ! aws s3 ls "s3://$bucket/" >/dev/null 2>&1; then
            echo -e "${RED}    ✗ Bucket $bucket not accessible${NC}"
            s3_issues+=("$bucket: not accessible")
            continue
        fi
        
        # Check if we can write (test with small file)
        test_key="health-check/emergency-test-$(date +%s).txt"
        if echo "emergency test" | aws s3 cp - "s3://$bucket/$test_key" 2>/dev/null; then
            echo -e "${GREEN}    ✓ Bucket $bucket is writable${NC}"
            # Clean up test file
            aws s3 rm "s3://$bucket/$test_key" >/dev/null 2>&1 || true
        else
            echo -e "${RED}    ✗ Bucket $bucket write failed${NC}"
            s3_issues+=("$bucket: write failed")
        fi
    done
    
    if [ ${#s3_issues[@]} -gt 0 ]; then
        echo -e "${RED}S3 ISSUES DETECTED:${NC}"
        for issue in "${s3_issues[@]}"; do
            echo "  - $issue"
        done
        return 1
    fi
    
    echo -e "${GREEN}✓ Critical S3 buckets operational${NC}"
    return 0
}

# API Gateway emergency check
check_api_emergency() {
    echo -e "${BLUE}[5/8] Emergency API Gateway check...${NC}"
    
    # Try to find the API Gateway
    api_id=$(aws apigateway get-rest-apis --query 'items[?contains(name, `flightdata`)].id' --output text 2>/dev/null || echo "")
    
    if [ -z "$api_id" ]; then
        echo -e "${RED}    ✗ API Gateway not found${NC}"
        return 1
    fi
    
    echo "    API ID: $api_id"
    
    # Check deployment status
    deployments=$(aws apigateway get-deployments --rest-api-id "$api_id" --query 'items[0].id' --output text 2>/dev/null || echo "")
    
    if [ -z "$deployments" ] || [ "$deployments" = "None" ]; then
        echo -e "${RED}    ✗ No API deployments found${NC}"
        return 1
    fi
    
    echo -e "${GREEN}    ✓ API Gateway deployment exists${NC}"
    
    # Try to get the actual endpoint URL and test it
    # This would need to be configured with your actual API endpoint
    API_ENDPOINT="https://${api_id}.execute-api.$(aws configure get region || echo us-east-1).amazonaws.com/prod"
    
    echo "    Testing endpoint: $API_ENDPOINT/health"
    
    if response=$(curl -s -w "%{http_code}" -o /tmp/api_emergency_response "$API_ENDPOINT/health" 2>/dev/null); then
        http_code=$(tail -c 3 <<< "$response")
        if [ "$http_code" = "200" ]; then
            echo -e "${GREEN}    ✓ API endpoint responding (HTTP 200)${NC}"
        else
            echo -e "${YELLOW}    ⚠ API endpoint returned HTTP $http_code${NC}"
        fi
    else
        echo -e "${RED}    ✗ API endpoint not responding${NC}"
        return 1
    fi
    
    return 0
}

# Recent errors analysis
analyze_recent_errors() {
    echo -e "${BLUE}[6/8] Analyzing recent errors (last 30 minutes)...${NC}"
    
    local start_time=$(date -d '30 minutes ago' --iso-8601)
    local end_time=$(date --iso-8601)
    local error_found=false
    
    # Check Lambda errors
    echo "  Checking Lambda errors..."
    for func in flightdata-processor flightdata-api-handler flightdata-aggregator; do
        error_count=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/Lambda \
            --metric-name Errors \
            --dimensions Name=FunctionName,Value="$func" \
            --start-time "$start_time" \
            --end-time "$end_time" \
            --period 1800 \
            --statistics Sum \
            --query 'Datapoints[0].Sum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$error_count" != "None" ] && [ "$error_count" -gt 0 ]; then
            echo -e "${RED}    ✗ $func: $error_count errors${NC}"
            error_found=true
            
            # Get specific error messages
            echo "      Recent error messages:"
            aws logs filter-log-events \
                --log-group-name "/aws/lambda/$func" \
                --start-time $(date -d '30 minutes ago' +%s)000 \
                --filter-pattern 'ERROR' \
                --query 'events[0:3].[eventTime,message]' \
                --output table 2>/dev/null || echo "        Could not retrieve error details"
        fi
    done
    
    # Check DynamoDB errors
    echo "  Checking DynamoDB throttling..."
    for table in flightdata-main flightdata-metrics; do
        throttle_count=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/DynamoDB \
            --metric-name ThrottledRequests \
            --dimensions Name=TableName,Value="$table" \
            --start-time "$start_time" \
            --end-time "$end_time" \
            --period 1800 \
            --statistics Sum \
            --query 'Datapoints[0].Sum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$throttle_count" != "None" ] && [ "$throttle_count" -gt 0 ]; then
            echo -e "${RED}    ✗ $table: $throttle_count throttled requests${NC}"
            error_found=true
        fi
    done
    
    if [ "$error_found" = false ]; then
        echo -e "${GREEN}    ✓ No significant errors in last 30 minutes${NC}"
    fi
    
    return 0
}

# System resource check
check_system_resources() {
    echo -e "${BLUE}[7/8] Checking system resources...${NC}"
    
    # Check Lambda concurrent executions
    echo "  Checking Lambda concurrency..."
    current_time=$(date --iso-8601)
    start_time=$(date -d '5 minutes ago' --iso-8601)
    
    concurrent_executions=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name ConcurrentExecutions \
        --start-time "$start_time" \
        --end-time "$current_time" \
        --period 300 \
        --statistics Maximum \
        --query 'Datapoints[0].Maximum' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$concurrent_executions" != "None" ] && [ "$concurrent_executions" -gt 800 ]; then
        echo -e "${YELLOW}    ⚠ High concurrent executions: $concurrent_executions${NC}"
    else
        echo -e "${GREEN}    ✓ Lambda concurrency normal: $concurrent_executions${NC}"
    fi
    
    # Check DynamoDB capacity utilization
    echo "  Checking DynamoDB capacity..."
    for table in flightdata-main; do
        read_capacity=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/DynamoDB \
            --metric-name ConsumedReadCapacityUnits \
            --dimensions Name=TableName,Value="$table" \
            --start-time "$start_time" \
            --end-time "$current_time" \
            --period 300 \
            --statistics Maximum \
            --query 'Datapoints[0].Maximum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$read_capacity" != "None" ]; then
            echo -e "${GREEN}    ✓ $table read capacity: $read_capacity units${NC}"
        fi
    done
    
    return 0
}

# Generate emergency action recommendations
generate_emergency_recommendations() {
    echo -e "${BLUE}[8/8] Emergency action recommendations...${NC}"
    
    echo ""
    echo -e "${YELLOW}IMMEDIATE ACTIONS IF ISSUES FOUND:${NC}"
    echo ""
    
    echo "1. LAMBDA ISSUES:"
    echo "   - Restart failed functions: aws lambda update-function-configuration --function-name FUNCTION_NAME --timeout 900"
    echo "   - Check recent deployments: aws lambda list-versions-by-function --function-name FUNCTION_NAME"
    echo "   - Rollback if needed: aws lambda update-alias --function-name FUNCTION_NAME --name production --function-version PREVIOUS_VERSION"
    echo ""
    
    echo "2. DATABASE ISSUES:"
    echo "   - Check table status: aws dynamodb describe-table --table-name TABLE_NAME"
    echo "   - Scale capacity: aws dynamodb update-table --table-name TABLE_NAME --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=100"
    echo "   - Check CloudWatch logs for errors"
    echo ""
    
    echo "3. S3 ISSUES:"
    echo "   - Check bucket policies and permissions"
    echo "   - Verify VPC endpoints if using private subnets"
    echo "   - Test cross-region replication status"
    echo ""
    
    echo "4. API ISSUES:"
    echo "   - Redeploy API: aws apigateway create-deployment --rest-api-id API_ID --stage-name prod"
    echo "   - Check throttling settings"
    echo "   - Review custom domain configuration"
    echo ""
    
    echo "5. GENERAL RECOVERY:"
    echo "   - Check AWS service status: https://status.aws.amazon.com/"
    echo "   - Review recent changes in deployment history"
    echo "   - Consider activating disaster recovery procedures"
    echo "   - Contact AWS support if infrastructure issue suspected"
    echo ""
}

# Quick recovery actions
quick_recovery_actions() {
    echo -e "${BLUE}Quick Recovery Actions Available:${NC}"
    echo ""
    
    read -p "Do you want to attempt automatic recovery actions? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Performing quick recovery actions..."
        
        # Restart Lambda functions by updating configuration
        echo "  Restarting Lambda functions..."
        for func in flightdata-processor flightdata-api-handler; do
            if aws lambda update-function-configuration --function-name "$func" --timeout 900 >/dev/null 2>&1; then
                echo -e "${GREEN}    ✓ Restarted $func${NC}"
            else
                echo -e "${RED}    ✗ Failed to restart $func${NC}"
            fi
        done
        
        # Clear any dead SQS messages
        echo "  Clearing SQS queues..."
        sqs_queues=$(aws sqs list-queues --query 'QueueUrls[?contains(@, `flightdata`)]' --output text 2>/dev/null || echo "")
        for queue in $sqs_queues; do
            if aws sqs purge-queue --queue-url "$queue" >/dev/null 2>&1; then
                echo -e "${GREEN}    ✓ Purged queue $(basename "$queue")${NC}"
            fi
        done
        
        echo "  Quick recovery actions completed."
    fi
}

# Main execution
main() {
    print_header
    
    # Critical checks
    test_aws_connectivity || { echo "Cannot proceed without AWS connectivity"; exit 1; }
    
    echo ""
    echo -e "${YELLOW}Running emergency diagnosis checks...${NC}"
    echo ""
    
    # Run all emergency checks
    check_lambda_emergency
    check_database_emergency
    check_s3_emergency
    check_api_emergency
    analyze_recent_errors
    check_system_resources
    
    echo ""
    generate_emergency_recommendations
    
    echo ""
    echo -e "${GREEN}=================================================================${NC}"
    echo -e "${GREEN}              EMERGENCY DIAGNOSIS COMPLETE${NC}"
    echo -e "${GREEN}=================================================================${NC}"
    echo "Completion Time: $(date)"
    echo "Full log available at: $LOG_FILE"
    echo ""
    
    # Offer quick recovery options
    quick_recovery_actions
}

# Handle script interruption
trap 'echo "Emergency diagnosis interrupted"; exit 130' INT TERM

# Run main function
main "$@"