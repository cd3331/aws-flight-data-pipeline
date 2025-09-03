#!/bin/bash

# Smoke Test Runner for Flight Data Pipeline
# This script runs comprehensive smoke tests after deployment

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
API_BASE_URL=${API_BASE_URL:-""}
TIMEOUT=${SMOKE_TEST_TIMEOUT:-"300"}
OUTPUT_DIR=${OUTPUT_DIR:-"$PROJECT_ROOT/test-results/smoke"}
PARALLEL_TESTS=${PARALLEL_TESTS:-"false"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Print usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --environment ENV     Environment to test (dev, staging, production)"
    echo "  --region REGION       AWS region (default: us-east-1)"
    echo "  --api-url URL         API base URL to test"
    echo "  --timeout SECONDS     Test timeout in seconds (default: 300)"
    echo "  --output-dir DIR      Directory for test results"
    echo "  --parallel           Run tests in parallel"
    echo "  --api-only           Run only API tests"
    echo "  --lambda-only        Run only Lambda tests"
    echo "  --infrastructure-only Run only infrastructure tests"
    echo "  --help               Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  ENVIRONMENT          Environment name"
    echo "  AWS_REGION           AWS region"
    echo "  API_BASE_URL         API base URL"
    echo "  SMOKE_TEST_TIMEOUT   Test timeout"
}

# Parse command line arguments
TEST_TYPES=("api" "lambda" "infrastructure")

while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --api-url)
            API_BASE_URL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL_TESTS="true"
            shift
            ;;
        --api-only)
            TEST_TYPES=("api")
            shift
            ;;
        --lambda-only)
            TEST_TYPES=("lambda")
            shift
            ;;
        --infrastructure-only)
            TEST_TYPES=("infrastructure")
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

# Print header
print_header() {
    echo -e "${BLUE}=================================================================${NC}"
    echo -e "${BLUE}          Flight Data Pipeline - Smoke Tests${NC}"
    echo -e "${BLUE}=================================================================${NC}"
    echo "Environment: $ENVIRONMENT"
    echo "Region: $AWS_REGION"
    echo "API URL: ${API_BASE_URL:-'Auto-detect'}"
    echo "Timeout: ${TIMEOUT}s"
    echo "Output Directory: $OUTPUT_DIR"
    echo "Test Types: ${TEST_TYPES[*]}"
    echo "Parallel Execution: $PARALLEL_TESTS"
    echo "Start Time: $(date)"
    echo ""
}

# Setup test environment
setup_test_environment() {
    log "Setting up test environment..."
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Install Python dependencies if needed
    if ! python3 -c "import requests" 2>/dev/null; then
        log "Installing Python dependencies..."
        pip3 install requests boto3 pytest
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        exit 1
    fi
    
    # Auto-detect API URL if not provided
    if [ -z "$API_BASE_URL" ]; then
        log "Auto-detecting API Gateway URL..."
        
        # Try to get API Gateway URL from CloudFormation stack outputs
        STACK_NAME="flightdata-pipeline-$ENVIRONMENT"
        API_URL=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$AWS_REGION" \
            --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$API_URL" ] && [ "$API_URL" != "None" ]; then
            API_BASE_URL="$API_URL"
            log "Detected API URL: $API_BASE_URL"
        else
            # Try to find API Gateway by name
            API_ID=$(aws apigateway get-rest-apis \
                --region "$AWS_REGION" \
                --query "items[?contains(name, 'flightdata')].id" \
                --output text 2>/dev/null | head -1)
            
            if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
                API_BASE_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod"
                log "Constructed API URL: $API_BASE_URL"
            else
                log "Could not auto-detect API URL - API tests may fail"
                API_BASE_URL="https://api-${ENVIRONMENT}.flightdata-pipeline.com"
            fi
        fi
    fi
    
    # Export environment variables for test scripts
    export ENVIRONMENT
    export AWS_REGION
    export API_BASE_URL
    export SMOKE_TEST_TIMEOUT="$TIMEOUT"
    
    echo -e "${GREEN}✅ Test environment setup completed${NC}"
}

# Run API smoke tests
run_api_tests() {
    log "Running API smoke tests..."
    
    local output_file="$OUTPUT_DIR/api-smoke-test-results.json"
    local start_time=$(date +%s)
    
    export API_BASE_URL
    export SMOKE_TEST_OUTPUT_FILE="$output_file"
    
    if timeout "$TIMEOUT" python3 "$SCRIPT_DIR/test_api_endpoints.py"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${GREEN}✅ API smoke tests PASSED (${duration}s)${NC}"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${RED}❌ API smoke tests FAILED (${duration}s)${NC}"
        return 1
    fi
}

# Run Lambda smoke tests
run_lambda_tests() {
    log "Running Lambda function smoke tests..."
    
    local output_file="$OUTPUT_DIR/lambda-smoke-test-results.json"
    local start_time=$(date +%s)
    
    export LAMBDA_SMOKE_TEST_OUTPUT_FILE="$output_file"
    
    if timeout "$TIMEOUT" python3 "$SCRIPT_DIR/test_lambda_functions.py"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${GREEN}✅ Lambda smoke tests PASSED (${duration}s)${NC}"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo -e "${RED}❌ Lambda smoke tests FAILED (${duration}s)${NC}"
        return 1
    fi
}

# Run infrastructure smoke tests
run_infrastructure_tests() {
    log "Running infrastructure smoke tests..."
    
    local output_file="$OUTPUT_DIR/infrastructure-smoke-test-results.json"
    local start_time=$(date +%s)
    local test_results=()
    
    echo "{" > "$output_file"
    echo "  \"environment\": \"$ENVIRONMENT\"," >> "$output_file"
    echo "  \"region\": \"$AWS_REGION\"," >> "$output_file"
    echo "  \"timestamp\": $(date +%s)," >> "$output_file"
    echo "  \"tests\": {" >> "$output_file"
    
    local test_count=0
    local failed_tests=0
    
    # Test S3 buckets
    log "  Testing S3 buckets..."
    local s3_buckets=("flightdata-raw-$ENVIRONMENT" "flightdata-processed-$ENVIRONMENT")
    local s3_results=()
    
    for bucket in "${s3_buckets[@]}"; do
        if aws s3 ls "s3://$bucket/" >/dev/null 2>&1; then
            echo -e "${GREEN}    ✅ Bucket accessible: $bucket${NC}"
            s3_results+=("\"$bucket\": {\"status\": \"accessible\"}")
        else
            echo -e "${RED}    ❌ Bucket not accessible: $bucket${NC}"
            s3_results+=("\"$bucket\": {\"status\": \"not_accessible\"}")
            ((failed_tests++))
        fi
        ((test_count++))
    done
    
    echo "    \"s3_buckets\": {" >> "$output_file"
    echo "      $(IFS=','; echo "${s3_results[*]}")" >> "$output_file"
    echo "    }," >> "$output_file"
    
    # Test DynamoDB tables
    log "  Testing DynamoDB tables..."
    local dynamo_tables=("flightdata-main-$ENVIRONMENT" "flightdata-metrics-$ENVIRONMENT")
    local dynamo_results=()
    
    for table in "${dynamo_tables[@]}"; do
        if aws dynamodb describe-table --table-name "$table" --region "$AWS_REGION" >/dev/null 2>&1; then
            echo -e "${GREEN}    ✅ Table accessible: $table${NC}"
            dynamo_results+=("\"$table\": {\"status\": \"accessible\"}")
        else
            echo -e "${RED}    ❌ Table not accessible: $table${NC}"
            dynamo_results+=("\"$table\": {\"status\": \"not_accessible\"}")
            ((failed_tests++))
        fi
        ((test_count++))
    done
    
    echo "    \"dynamodb_tables\": {" >> "$output_file"
    echo "      $(IFS=','; echo "${dynamo_results[*]}")" >> "$output_file"
    echo "    }," >> "$output_file"
    
    # Test SNS topics
    log "  Testing SNS topics..."
    local sns_topics
    sns_topics=$(aws sns list-topics --region "$AWS_REGION" --query "Topics[?contains(TopicArn, 'flightdata') && contains(TopicArn, '$ENVIRONMENT')].TopicArn" --output text)
    
    if [ -n "$sns_topics" ]; then
        echo -e "${GREEN}    ✅ SNS topics found${NC}"
        echo "    \"sns_topics\": {\"status\": \"found\", \"count\": $(echo "$sns_topics" | wc -w)}," >> "$output_file"
    else
        echo -e "${YELLOW}    ⚠️  No SNS topics found${NC}"
        echo "    \"sns_topics\": {\"status\": \"not_found\"}," >> "$output_file"
    fi
    ((test_count++))
    
    # Test CloudWatch Log Groups
    log "  Testing CloudWatch Log Groups..."
    local log_groups
    log_groups=$(aws logs describe-log-groups --region "$AWS_REGION" --log-group-name-prefix "/aws/lambda/flightdata-" --query "logGroups[?contains(logGroupName, '$ENVIRONMENT')].logGroupName" --output text | wc -w)
    
    if [ "$log_groups" -gt 0 ]; then
        echo -e "${GREEN}    ✅ CloudWatch log groups found: $log_groups${NC}"
        echo "    \"cloudwatch_logs\": {\"status\": \"found\", \"count\": $log_groups}" >> "$output_file"
    else
        echo -e "${RED}    ❌ No CloudWatch log groups found${NC}"
        echo "    \"cloudwatch_logs\": {\"status\": \"not_found\"}" >> "$output_file"
        ((failed_tests++))
    fi
    ((test_count++))
    
    echo "  }," >> "$output_file"
    echo "  \"summary\": {" >> "$output_file"
    echo "    \"total_tests\": $test_count," >> "$output_file"
    echo "    \"failed_tests\": $failed_tests," >> "$output_file"
    echo "    \"success_rate\": $(echo "scale=2; ($test_count - $failed_tests) / $test_count * 100" | bc)" >> "$output_file"
    echo "  }" >> "$output_file"
    echo "}" >> "$output_file"
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $failed_tests -eq 0 ]; then
        echo -e "${GREEN}✅ Infrastructure smoke tests PASSED (${duration}s)${NC}"
        return 0
    else
        echo -e "${RED}❌ Infrastructure smoke tests FAILED ($failed_tests/$test_count tests failed, ${duration}s)${NC}"
        return 1
    fi
}

# Run tests in parallel
run_tests_parallel() {
    log "Running smoke tests in parallel..."
    
    local pids=()
    local results=()
    
    # Start tests in background
    for test_type in "${TEST_TYPES[@]}"; do
        case $test_type in
            "api")
                run_api_tests &
                pids+=($!)
                ;;
            "lambda")
                run_lambda_tests &
                pids+=($!)
                ;;
            "infrastructure")
                run_infrastructure_tests &
                pids+=($!)
                ;;
        esac
    done
    
    # Wait for all tests to complete
    local overall_result=0
    for i in "${!pids[@]}"; do
        local pid=${pids[$i]}
        local test_type=${TEST_TYPES[$i]}
        
        if wait $pid; then
            results+=("$test_type:PASSED")
        else
            results+=("$test_type:FAILED")
            overall_result=1
        fi
    done
    
    # Print results
    echo ""
    echo "Parallel Test Results:"
    for result in "${results[@]}"; do
        local test_name=${result%:*}
        local status=${result#*:}
        
        if [ "$status" = "PASSED" ]; then
            echo -e "  ${GREEN}✅ $test_name: $status${NC}"
        else
            echo -e "  ${RED}❌ $test_name: $status${NC}"
        fi
    done
    
    return $overall_result
}

# Run tests sequentially
run_tests_sequential() {
    log "Running smoke tests sequentially..."
    
    local overall_result=0
    local passed_tests=0
    local total_tests=${#TEST_TYPES[@]}
    
    for test_type in "${TEST_TYPES[@]}"; do
        echo ""
        case $test_type in
            "api")
                if run_api_tests; then
                    ((passed_tests++))
                else
                    overall_result=1
                fi
                ;;
            "lambda")
                if run_lambda_tests; then
                    ((passed_tests++))
                else
                    overall_result=1
                fi
                ;;
            "infrastructure")
                if run_infrastructure_tests; then
                    ((passed_tests++))
                else
                    overall_result=1
                fi
                ;;
        esac
    done
    
    echo ""
    echo "Sequential Test Results: $passed_tests/$total_tests tests passed"
    
    return $overall_result
}

# Generate summary report
generate_summary_report() {
    log "Generating summary report..."
    
    local summary_file="$OUTPUT_DIR/smoke-test-summary.json"
    local end_time=$(date +%s)
    
    cat > "$summary_file" << EOF
{
  "test_run": {
    "environment": "$ENVIRONMENT",
    "region": "$AWS_REGION",
    "api_base_url": "$API_BASE_URL",
    "start_time": "$START_TIME",
    "end_time": "$(date --iso-8601)",
    "duration_seconds": $((end_time - START_TIME_EPOCH)),
    "test_types": [$(printf '"%s",' "${TEST_TYPES[@]}" | sed 's/,$//')]
  },
  "results_files": {
    "api": "api-smoke-test-results.json",
    "lambda": "lambda-smoke-test-results.json", 
    "infrastructure": "infrastructure-smoke-test-results.json"
  },
  "overall_status": "$([ $1 -eq 0 ] && echo "PASSED" || echo "FAILED")"
}
EOF
    
    echo -e "${BLUE}📄 Summary report saved to: $summary_file${NC}"
}

# Clean up function
cleanup() {
    log "Cleaning up..."
    
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    
    # Clean up temporary files
    rm -f /tmp/smoke_test_* 2>/dev/null || true
}

# Main execution
main() {
    # Set up trap for cleanup
    trap cleanup EXIT INT TERM
    
    START_TIME=$(date --iso-8601)
    START_TIME_EPOCH=$(date +%s)
    
    print_header
    setup_test_environment
    
    local overall_result
    
    if [ "$PARALLEL_TESTS" = "true" ]; then
        run_tests_parallel
        overall_result=$?
    else
        run_tests_sequential
        overall_result=$?
    fi
    
    generate_summary_report $overall_result
    
    echo ""
    echo -e "${BLUE}=================================================================${NC}"
    echo -e "${BLUE}                    SMOKE TEST SUMMARY${NC}"
    echo -e "${BLUE}=================================================================${NC}"
    echo "Environment: $ENVIRONMENT"
    echo "Region: $AWS_REGION"
    echo "Test Types: ${TEST_TYPES[*]}"
    echo "Duration: $(($(date +%s) - START_TIME_EPOCH)) seconds"
    
    if [ $overall_result -eq 0 ]; then
        echo -e "${GREEN}✅ Overall Status: ALL TESTS PASSED${NC}"
        echo "Deployment appears to be successful and healthy!"
    else
        echo -e "${RED}❌ Overall Status: SOME TESTS FAILED${NC}"
        echo "Check the test results in: $OUTPUT_DIR"
        echo "Manual verification and/or rollback may be required."
    fi
    
    echo ""
    echo "Test Results Directory: $OUTPUT_DIR"
    echo "End Time: $(date)"
    echo -e "${BLUE}=================================================================${NC}"
    
    exit $overall_result
}

# Run main function
main "$@"