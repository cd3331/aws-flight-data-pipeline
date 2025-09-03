#!/bin/bash

# =============================================================================
# Flight Data Pipeline Demo Script
# =============================================================================
# This script demonstrates the complete flight data pipeline in action:
# 1. Triggers data ingestion
# 2. Shows data in S3 
# 3. Displays CloudWatch metrics
# 4. Runs sample Athena queries
# 5. Shows data quality scores
# 6. Displays cost estimates
# =============================================================================

set -euo pipefail

# Color codes for output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="flight-data-pipeline"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Derived resource names
RAW_DATA_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-raw-data"
PROCESSED_DATA_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-processed-data"
INGESTION_LAMBDA="${PROJECT_NAME}-${ENVIRONMENT}-flight-ingestion"
PROCESSING_LAMBDA="${PROJECT_NAME}-${ENVIRONMENT}-flight-processing"
VALIDATION_LAMBDA="${PROJECT_NAME}-${ENVIRONMENT}-data-validation"
DDB_TABLE="${PROJECT_NAME}-${ENVIRONMENT}-execution-tracking"
QUALITY_TABLE="${PROJECT_NAME}-${ENVIRONMENT}-data-quality-metrics"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo -e "${WHITE}$1${NC}"
    echo -e "${WHITE}$(printf '=%.0s' {1..80})${NC}"
}

print_step() {
    echo -e "${CYAN}➤ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_dependencies() {
    local deps=("aws" "jq" "date")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing[*]}"
        print_info "Please install the missing dependencies and try again."
        exit 1
    fi
}

wait_for_execution() {
    local max_wait=${1:-300}  # Default 5 minutes
    local check_interval=10
    local elapsed=0
    
    print_step "Waiting for pipeline execution to complete..."
    
    while [ $elapsed -lt $max_wait ]; do
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        
        # Check if recent execution completed successfully
        local recent_executions
        recent_executions=$(aws dynamodb scan \
            --table-name "$DDB_TABLE" \
            --filter-expression "#status = :status AND #timestamp > :timestamp" \
            --expression-attribute-names '{"#status": "status", "#timestamp": "timestamp"}' \
            --expression-attribute-values "{\":status\": {\"S\": \"COMPLETED\"}, \":timestamp\": {\"S\": \"$(date -d '5 minutes ago' -Iso)\"}}" \
            --region "$AWS_REGION" \
            --output json 2>/dev/null || echo '{"Items": []}')
        
        local count
        count=$(echo "$recent_executions" | jq '.Items | length')
        
        if [ "$count" -gt 0 ]; then
            print_success "Pipeline execution completed!"
            return 0
        fi
        
        printf "."
    done
    
    echo ""
    print_warning "Execution still in progress after ${max_wait}s. Continuing with demo..."
}

# =============================================================================
# MAIN DEMO FUNCTIONS
# =============================================================================

show_pipeline_info() {
    print_header "Flight Data Pipeline Demo - Environment: $ENVIRONMENT"
    print_info "AWS Region: $AWS_REGION"
    print_info "Project: $PROJECT_NAME"
    print_info "Timestamp: $(date)"
    echo ""
}

trigger_data_ingestion() {
    print_header "1. TRIGGERING DATA INGESTION"
    
    print_step "Invoking flight data ingestion Lambda..."
    
    # Prepare payload for Lambda
    local payload
    payload=$(cat <<EOF
{
    "demo": true,
    "source": "manual_trigger",
    "timestamp": "$(date -Iso)"
}
EOF
)
    
    # Invoke the ingestion Lambda
    local response
    response=$(aws lambda invoke \
        --function-name "$INGESTION_LAMBDA" \
        --payload "$payload" \
        --region "$AWS_REGION" \
        /tmp/lambda_response.json 2>&1) || {
        print_error "Failed to invoke ingestion Lambda"
        print_info "Error: $response"
        return 1
    }
    
    # Parse response
    local status_code
    status_code=$(echo "$response" | jq -r '.StatusCode // empty')
    
    if [ "$status_code" = "200" ]; then
        print_success "Ingestion Lambda invoked successfully"
        local execution_result
        execution_result=$(cat /tmp/lambda_response.json | jq -r '.body // .message // "Success"')
        print_info "Response: $execution_result"
    else
        print_error "Lambda invocation failed with status: $status_code"
        cat /tmp/lambda_response.json | jq . || cat /tmp/lambda_response.json
    fi
    
    # Wait for execution to complete
    wait_for_execution 180
    
    echo ""
}

show_s3_data() {
    print_header "2. S3 DATA STORAGE"
    
    print_step "Checking raw data bucket: $RAW_DATA_BUCKET"
    
    # Check if raw data bucket exists and show contents
    if aws s3 ls "s3://$RAW_DATA_BUCKET" --region "$AWS_REGION" &>/dev/null; then
        local raw_objects
        raw_objects=$(aws s3api list-objects-v2 \
            --bucket "$RAW_DATA_BUCKET" \
            --max-items 10 \
            --region "$AWS_REGION" \
            --output json 2>/dev/null || echo '{"Contents": []}')
        
        local raw_count
        raw_count=$(echo "$raw_objects" | jq '.Contents | length')
        
        if [ "$raw_count" -gt 0 ]; then
            print_success "Found $raw_count objects in raw data bucket"
            
            echo -e "${BLUE}Recent raw data files:${NC}"
            echo "$raw_objects" | jq -r '.Contents[] | "  📁 \(.Key) (\(.Size | tonumber) bytes) - \(.LastModified)"' | head -5
            
            # Show total storage used
            local total_size
            total_size=$(echo "$raw_objects" | jq '[.Contents[].Size] | add // 0')
            print_info "Total raw data storage: $(numfmt --to=iec $total_size)"
        else
            print_warning "No objects found in raw data bucket"
        fi
    else
        print_error "Cannot access raw data bucket: $RAW_DATA_BUCKET"
    fi
    
    echo ""
    
    print_step "Checking processed data bucket: $PROCESSED_DATA_BUCKET"
    
    # Check processed data bucket
    if aws s3 ls "s3://$PROCESSED_DATA_BUCKET" --region "$AWS_REGION" &>/dev/null; then
        local processed_objects
        processed_objects=$(aws s3api list-objects-v2 \
            --bucket "$PROCESSED_DATA_BUCKET" \
            --max-items 10 \
            --region "$AWS_REGION" \
            --output json 2>/dev/null || echo '{"Contents": []}')
        
        local processed_count
        processed_count=$(echo "$processed_objects" | jq '.Contents | length')
        
        if [ "$processed_count" -gt 0 ]; then
            print_success "Found $processed_count objects in processed data bucket"
            
            echo -e "${BLUE}Recent processed data files:${NC}"
            echo "$processed_objects" | jq -r '.Contents[] | "  📊 \(.Key) (\(.Size | tonumber) bytes) - \(.LastModified)"' | head -5
            
            # Show partitioning structure
            local partitions
            partitions=$(echo "$processed_objects" | jq -r '.Contents[].Key' | cut -d'/' -f1-3 | sort | uniq | head -3)
            
            if [ -n "$partitions" ]; then
                echo -e "${BLUE}Data partitioning structure:${NC}"
                echo "$partitions" | while read -r partition; do
                    echo "  📂 $partition/"
                done
            fi
            
            # Show total processed storage
            local total_processed_size
            total_processed_size=$(echo "$processed_objects" | jq '[.Contents[].Size] | add // 0')
            print_info "Total processed data storage: $(numfmt --to=iec $total_processed_size)"
        else
            print_warning "No objects found in processed data bucket"
        fi
    else
        print_error "Cannot access processed data bucket: $PROCESSED_DATA_BUCKET"
    fi
    
    echo ""
}

show_cloudwatch_metrics() {
    print_header "3. CLOUDWATCH METRICS"
    
    local end_time
    local start_time
    end_time=$(date -Iso)
    start_time=$(date -d '1 hour ago' -Iso)
    
    print_step "Retrieving Lambda function metrics..."
    
    # Lambda invocation metrics
    local lambda_metrics
    lambda_metrics=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value="$INGESTION_LAMBDA" \
        --statistics Sum \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --period 3600 \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Datapoints": []}')
    
    local invocation_count
    invocation_count=$(echo "$lambda_metrics" | jq '[.Datapoints[].Sum] | add // 0')
    print_info "Lambda invocations (last hour): $invocation_count"
    
    # Lambda error metrics
    local error_metrics
    error_metrics=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value="$INGESTION_LAMBDA" \
        --statistics Sum \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --period 3600 \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Datapoints": []}')
    
    local error_count
    error_count=$(echo "$error_metrics" | jq '[.Datapoints[].Sum] | add // 0')
    
    if [ "$error_count" -eq 0 ]; then
        print_success "Lambda errors (last hour): $error_count"
    else
        print_warning "Lambda errors (last hour): $error_count"
    fi
    
    # Lambda duration metrics
    local duration_metrics
    duration_metrics=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Duration \
        --dimensions Name=FunctionName,Value="$INGESTION_LAMBDA" \
        --statistics Average,Maximum \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --period 3600 \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Datapoints": []}')
    
    if [ "$(echo "$duration_metrics" | jq '.Datapoints | length')" -gt 0 ]; then
        local avg_duration
        local max_duration
        avg_duration=$(echo "$duration_metrics" | jq '[.Datapoints[].Average] | add / length | floor')
        max_duration=$(echo "$duration_metrics" | jq '[.Datapoints[].Maximum] | max | floor')
        
        print_info "Lambda avg duration (last hour): ${avg_duration}ms"
        print_info "Lambda max duration (last hour): ${max_duration}ms"
    fi
    
    echo ""
    
    print_step "Retrieving S3 metrics..."
    
    # S3 storage metrics
    local s3_storage_metrics
    s3_storage_metrics=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/S3 \
        --metric-name BucketSizeBytes \
        --dimensions Name=BucketName,Value="$RAW_DATA_BUCKET" Name=StorageType,Value=StandardStorage \
        --statistics Maximum \
        --start-time "$(date -d '1 day ago' -Iso)" \
        --end-time "$end_time" \
        --period 86400 \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Datapoints": []}')
    
    if [ "$(echo "$s3_storage_metrics" | jq '.Datapoints | length')" -gt 0 ]; then
        local storage_bytes
        storage_bytes=$(echo "$s3_storage_metrics" | jq '.Datapoints[-1].Maximum // 0')
        print_info "S3 storage size: $(numfmt --to=iec $storage_bytes)"
    else
        print_info "S3 storage metrics: Not available yet"
    fi
    
    # Custom metrics (if available)
    print_step "Checking custom pipeline metrics..."
    
    local custom_metrics
    custom_metrics=$(aws logs filter-log-events \
        --log-group-name "/aws/lambda/$INGESTION_LAMBDA" \
        --start-time "$(date -d '1 hour ago' +%s)000" \
        --filter-pattern "METRICS" \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"events": []}')
    
    local metric_events
    metric_events=$(echo "$custom_metrics" | jq '.events | length')
    
    if [ "$metric_events" -gt 0 ]; then
        print_success "Found $metric_events custom metric events"
        echo -e "${BLUE}Recent metric samples:${NC}"
        echo "$custom_metrics" | jq -r '.events[0:3][] | "  📊 \(.message)"' 2>/dev/null || true
    else
        print_info "No custom metrics found in recent logs"
    fi
    
    echo ""
}

run_athena_query() {
    print_header "4. ATHENA SAMPLE QUERIES"
    
    # Check if Glue catalog and table exist
    print_step "Checking Glue catalog setup..."
    
    local database_name="flight_data_db"
    local table_name="processed_flights"
    
    # Try to describe the database
    if aws glue get-database --name "$database_name" --region "$AWS_REGION" &>/dev/null; then
        print_success "Glue database '$database_name' exists"
        
        # Check if table exists
        if aws glue get-table --database-name "$database_name" --name "$table_name" --region "$AWS_REGION" &>/dev/null; then
            print_success "Glue table '$table_name' exists"
            
            # Run sample Athena query
            print_step "Running sample Athena query..."
            
            local query_string="SELECT 
    COUNT(*) as total_flights,
    AVG(altitude) as avg_altitude,
    COUNT(DISTINCT callsign) as unique_callsigns
FROM ${database_name}.${table_name} 
WHERE date >= current_date - interval '7' day
    AND altitude > 0
LIMIT 10;"
            
            # Start query execution
            local query_execution_id
            query_execution_id=$(aws athena start-query-execution \
                --query-string "$query_string" \
                --result-configuration "OutputLocation=s3://$PROCESSED_DATA_BUCKET/athena-results/" \
                --work-group "primary" \
                --region "$AWS_REGION" \
                --output text --query 'QueryExecutionId' 2>/dev/null) || {
                print_error "Failed to start Athena query"
                return 1
            }
            
            print_info "Query execution ID: $query_execution_id"
            
            # Wait for query to complete
            local max_wait=60
            local wait_time=0
            local status="RUNNING"
            
            while [ "$wait_time" -lt "$max_wait" ] && [ "$status" = "RUNNING" ] || [ "$status" = "QUEUED" ]; do
                sleep 5
                wait_time=$((wait_time + 5))
                
                status=$(aws athena get-query-execution \
                    --query-execution-id "$query_execution_id" \
                    --region "$AWS_REGION" \
                    --output text --query 'QueryExecution.Status.State' 2>/dev/null || echo "FAILED")
                
                printf "."
            done
            
            echo ""
            
            if [ "$status" = "SUCCEEDED" ]; then
                print_success "Query completed successfully"
                
                # Get query results
                local results
                results=$(aws athena get-query-results \
                    --query-execution-id "$query_execution_id" \
                    --region "$AWS_REGION" \
                    --output json 2>/dev/null) || {
                    print_warning "Could not retrieve query results"
                    return 0
                }
                
                echo -e "${BLUE}Query Results:${NC}"
                echo "$results" | jq -r '.ResultSet.Rows[] | .Data | map(.VarCharValue // "null") | join(" | ")' | head -5
                
            elif [ "$status" = "FAILED" ]; then
                print_error "Query failed"
                local error_message
                error_message=$(aws athena get-query-execution \
                    --query-execution-id "$query_execution_id" \
                    --region "$AWS_REGION" \
                    --output text --query 'QueryExecution.Status.StateChangeReason' 2>/dev/null || echo "Unknown error")
                print_info "Error: $error_message"
            else
                print_warning "Query timed out or status unknown: $status"
            fi
            
        else
            print_warning "Glue table '$table_name' not found"
            print_info "Table may not be created yet or catalog update is pending"
        fi
        
    else
        print_warning "Glue database '$database_name' not found"
        print_info "Running alternative query using S3 data directly..."
        
        # Alternative: Simple S3 object count query
        print_step "Running S3-based data analysis..."
        
        local s3_objects
        s3_objects=$(aws s3api list-objects-v2 \
            --bucket "$PROCESSED_DATA_BUCKET" \
            --region "$AWS_REGION" \
            --output json 2>/dev/null || echo '{"Contents": []}')
        
        local object_count
        local total_size
        object_count=$(echo "$s3_objects" | jq '.Contents | length')
        total_size=$(echo "$s3_objects" | jq '[.Contents[].Size] | add // 0')
        
        echo -e "${BLUE}S3 Data Analysis Results:${NC}"
        echo "  📊 Total processed files: $object_count"
        echo "  📊 Total data size: $(numfmt --to=iec $total_size)"
        
        if [ "$object_count" -gt 0 ]; then
            echo "  📊 Average file size: $(numfmt --to=iec $((total_size / object_count)))"
            
            # Show date partitions
            local date_partitions
            date_partitions=$(echo "$s3_objects" | jq -r '.Contents[].Key' | grep -o 'year=[0-9]*/month=[0-9]*/day=[0-9]*' | sort | uniq | wc -l)
            echo "  📊 Date partitions: $date_partitions"
        fi
    fi
    
    echo ""
}

show_data_quality_scores() {
    print_header "5. DATA QUALITY SCORES"
    
    print_step "Retrieving data quality metrics from DynamoDB..."
    
    # Check quality metrics table
    local quality_metrics
    quality_metrics=$(aws dynamodb scan \
        --table-name "$QUALITY_TABLE" \
        --filter-expression "#timestamp > :timestamp" \
        --expression-attribute-names '{"#timestamp": "timestamp"}' \
        --expression-attribute-values "{\":timestamp\": {\"S\": \"$(date -d '24 hours ago' -Iso)\"}}" \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"Items": []}')
    
    local metric_count
    metric_count=$(echo "$quality_metrics" | jq '.Items | length')
    
    if [ "$metric_count" -gt 0 ]; then
        print_success "Found $metric_count quality assessments in the last 24 hours"
        
        echo -e "${BLUE}Data Quality Dashboard:${NC}"
        
        # Calculate average scores
        local avg_completeness
        local avg_accuracy
        local avg_validity
        
        avg_completeness=$(echo "$quality_metrics" | jq '[.Items[].completeness_score.N | tonumber] | add / length * 100 | floor')
        avg_accuracy=$(echo "$quality_metrics" | jq '[.Items[].accuracy_score.N | tonumber] | add / length * 100 | floor')
        avg_validity=$(echo "$quality_metrics" | jq '[.Items[].validity_score.N | tonumber] | add / length * 100 | floor')
        
        # Color code based on score
        local completeness_color="$GREEN"
        local accuracy_color="$GREEN"
        local validity_color="$GREEN"
        
        [ "$avg_completeness" -lt 80 ] && completeness_color="$YELLOW"
        [ "$avg_completeness" -lt 60 ] && completeness_color="$RED"
        
        [ "$avg_accuracy" -lt 80 ] && accuracy_color="$YELLOW"
        [ "$avg_accuracy" -lt 60 ] && accuracy_color="$RED"
        
        [ "$avg_validity" -lt 80 ] && validity_color="$YELLOW"
        [ "$avg_validity" -lt 60 ] && validity_color="$RED"
        
        echo -e "  📊 Data Completeness: ${completeness_color}${avg_completeness}%${NC}"
        echo -e "  📊 Data Accuracy: ${accuracy_color}${avg_accuracy}%${NC}"
        echo -e "  📊 Data Validity: ${validity_color}${avg_validity}%${NC}"
        
        # Show recent quality trends
        echo -e "\n${BLUE}Recent Quality Assessments:${NC}"
        echo "$quality_metrics" | jq -r '.Items[0:3][] | 
            "  📅 \(.timestamp.S) - Completeness: \((.completeness_score.N | tonumber) * 100 | floor)% | Accuracy: \((.accuracy_score.N | tonumber) * 100 | floor)% | Validity: \((.validity_score.N | tonumber) * 100 | floor)%"' 2>/dev/null || echo "  No detailed metrics available"
        
        # Data quality alerts
        local low_quality_count
        low_quality_count=$(echo "$quality_metrics" | jq '[.Items[] | select((.completeness_score.N | tonumber) < 0.8 or (.accuracy_score.N | tonumber) < 0.8 or (.validity_score.N | tonumber) < 0.8)] | length')
        
        if [ "$low_quality_count" -gt 0 ]; then
            print_warning "Found $low_quality_count low-quality data batches"
        else
            print_success "All recent data batches meet quality thresholds"
        fi
        
    else
        print_warning "No quality metrics found in the last 24 hours"
        print_info "Quality assessment may be in progress or not yet configured"
        
        # Show alternative quality indicators from Lambda logs
        print_step "Checking processing logs for quality indicators..."
        
        local processing_logs
        processing_logs=$(aws logs filter-log-events \
            --log-group-name "/aws/lambda/$PROCESSING_LAMBDA" \
            --start-time "$(date -d '1 hour ago' +%s)000" \
            --filter-pattern "quality\|error\|validation" \
            --region "$AWS_REGION" \
            --output json 2>/dev/null || echo '{"events": []}')
        
        local log_events
        log_events=$(echo "$processing_logs" | jq '.events | length')
        
        if [ "$log_events" -gt 0 ]; then
            echo -e "${BLUE}Quality indicators from processing logs:${NC}"
            echo "$processing_logs" | jq -r '.events[0:3][] | "  📋 \(.message)"' 2>/dev/null || true
        else
            print_info "No quality-related log events found"
        fi
    fi
    
    # Check for data quality alarms
    print_step "Checking CloudWatch alarms for data quality..."
    
    local quality_alarms
    quality_alarms=$(aws cloudwatch describe-alarms \
        --alarm-name-prefix "$PROJECT_NAME-$ENVIRONMENT-quality" \
        --state-value ALARM \
        --region "$AWS_REGION" \
        --output json 2>/dev/null || echo '{"MetricAlarms": []}')
    
    local alarm_count
    alarm_count=$(echo "$quality_alarms" | jq '.MetricAlarms | length')
    
    if [ "$alarm_count" -gt 0 ]; then
        print_warning "Found $alarm_count active data quality alarms"
        echo "$quality_alarms" | jq -r '.MetricAlarms[] | "  🚨 \(.AlarmName): \(.StateReason)"'
    else
        print_success "No active data quality alarms"
    fi
    
    echo ""
}

show_cost_estimates() {
    print_header "6. COST ESTIMATES"
    
    local end_date
    local start_date
    end_date=$(date +%Y-%m-%d)
    start_date=$(date -d '7 days ago' +%Y-%m-%d)
    
    print_step "Retrieving AWS cost data for the last 7 days..."
    
    # Get cost and usage data
    local cost_data
    cost_data=$(aws ce get-cost-and-usage \
        --time-period Start="$start_date",End="$end_date" \
        --granularity DAILY \
        --metrics BlendedCost \
        --group-by Type=DIMENSION,Key=SERVICE \
        --region us-east-1 \
        --output json 2>/dev/null) || {
        print_error "Unable to retrieve cost data"
        print_info "Cost Explorer may not be enabled or insufficient permissions"
        return 1
    }
    
    # Calculate total costs
    local total_cost
    total_cost=$(echo "$cost_data" | jq '[.ResultsByTime[].Groups[].Metrics.BlendedCost.Amount | tonumber] | add')
    
    if [ "$total_cost" != "null" ] && [ "$(echo "$total_cost > 0" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
        print_success "Retrieved cost data for the last 7 days"
        
        echo -e "${BLUE}Cost Breakdown (Last 7 Days):${NC}"
        printf "  💰 Total Cost: $%.2f USD\n" "$total_cost"
        
        # Daily average
        local daily_avg
        daily_avg=$(echo "scale=2; $total_cost / 7" | bc -l 2>/dev/null || echo "0")
        printf "  📊 Daily Average: $%.2f USD\n" "$daily_avg"
        
        # Monthly projection
        local monthly_projection
        monthly_projection=$(echo "scale=2; $daily_avg * 30" | bc -l 2>/dev/null || echo "0")
        printf "  📈 Monthly Projection: $%.2f USD\n" "$monthly_projection"
        
        # Service breakdown
        echo -e "\n${BLUE}Top Services by Cost:${NC}"
        echo "$cost_data" | jq -r '
            [.ResultsByTime[].Groups[] | {
                service: .Keys[0],
                cost: (.Metrics.BlendedCost.Amount | tonumber)
            }] |
            group_by(.service) |
            map({
                service: .[0].service,
                total_cost: (map(.cost) | add)
            }) |
            sort_by(.total_cost) |
            reverse |
            .[0:5][] |
            "  💳 \(.service): $\(.total_cost | . * 100 | floor / 100)"
        ' 2>/dev/null || echo "  Service breakdown not available"
        
    else
        print_warning "No cost data available for the specified period"
        print_info "This could be due to recent deployment or minimal usage"
        
        # Provide estimated costs based on usage patterns
        print_step "Providing estimated costs based on resource configuration..."
        
        echo -e "${BLUE}Estimated Monthly Costs (Based on Configuration):${NC}"
        
        # Lambda cost estimation
        local lambda_requests_per_month=100000  # Assumption
        local lambda_gb_seconds=50              # Assumption based on memory/execution time
        local lambda_cost
        lambda_cost=$(echo "scale=2; ($lambda_requests_per_month * 0.0000002) + ($lambda_gb_seconds * 0.0000166667)" | bc -l 2>/dev/null || echo "0")
        printf "  ⚡ Lambda (estimated): $%.2f USD\n" "$lambda_cost"
        
        # S3 cost estimation
        local s3_storage_gb=10                  # Assumption
        local s3_requests=10000                 # Assumption
        local s3_cost
        s3_cost=$(echo "scale=2; ($s3_storage_gb * 0.023) + ($s3_requests * 0.0004 / 1000)" | bc -l 2>/dev/null || echo "0")
        printf "  🗃️  S3 (estimated): $%.2f USD\n" "$s3_cost"
        
        # DynamoDB cost estimation
        local dynamodb_cost="5.00"  # Assumption for PAY_PER_REQUEST
        printf "  🗄️  DynamoDB (estimated): $%.2f USD\n" "$dynamodb_cost"
        
        # CloudWatch cost estimation
        local cloudwatch_cost="2.00"  # Assumption
        printf "  📊 CloudWatch (estimated): $%.2f USD\n" "$cloudwatch_cost"
        
        # Total estimated cost
        local total_estimated
        total_estimated=$(echo "scale=2; $lambda_cost + $s3_cost + $dynamodb_cost + $cloudwatch_cost" | bc -l 2>/dev/null || echo "15.00")
        printf "  💰 Total Estimated: $%.2f USD/month\n" "$total_estimated"
        
        print_info "These are rough estimates. Actual costs depend on usage patterns."
    fi
    
    # Cost optimization recommendations
    echo -e "\n${BLUE}Cost Optimization Recommendations:${NC}"
    
    # Check S3 storage classes
    local raw_bucket_size
    raw_bucket_size=$(aws s3api list-objects-v2 --bucket "$RAW_DATA_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null | jq '[.Contents[].Size] | add // 0')
    
    if [ "$raw_bucket_size" -gt 1073741824 ]; then  # > 1GB
        echo "  💡 Consider S3 Intelligent Tiering for raw data (potential 20-30% savings)"
    fi
    
    # Check Lambda memory settings
    echo "  💡 Review Lambda memory settings - current config may be over-provisioned"
    
    # Check log retention
    echo "  💡 Consider reducing CloudWatch log retention from 30 days to 14 days"
    
    # Environment-specific recommendations
    if [ "$ENVIRONMENT" = "dev" ]; then
        echo "  💡 Enable auto-shutdown for dev environment (potential 40-60% savings)"
    fi
    
    echo ""
}

cleanup() {
    print_step "Cleaning up temporary files..."
    rm -f /tmp/lambda_response.json
}

main() {
    # Trap cleanup on exit
    trap cleanup EXIT
    
    # Check dependencies
    check_dependencies
    
    # Show pipeline info
    show_pipeline_info
    
    # Run demo sections
    trigger_data_ingestion
    show_s3_data
    show_cloudwatch_metrics
    run_athena_query
    show_data_quality_scores
    show_cost_estimates
    
    # Final summary
    print_header "DEMO COMPLETE"
    print_success "Flight Data Pipeline demo completed successfully!"
    print_info "Check the AWS Console for detailed monitoring and additional metrics."
    
    if [ "$ENVIRONMENT" = "dev" ]; then
        print_warning "Remember: This is a development environment - production metrics may vary."
    fi
    
    echo ""
    print_info "For more detailed analysis, consider:"
    echo "  • Accessing the CloudWatch dashboard"
    echo "  • Running custom Athena queries"
    echo "  • Reviewing detailed cost reports in AWS Cost Explorer"
    echo ""
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi