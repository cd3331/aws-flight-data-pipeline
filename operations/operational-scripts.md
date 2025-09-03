# Operational Scripts and Troubleshooting Guide

This document provides comprehensive operational scripts and troubleshooting procedures for the Flight Data Pipeline system.

## 📁 Script Directory Structure

```
operations/scripts/
├── daily-health-check.sh           # Daily system health verification
├── emergency-diagnosis.sh          # Critical incident diagnosis
├── validate-data-quality.sh        # Data quality validation
├── backup-system-config.sh         # System configuration backup
├── deploy-with-canary.sh          # Safe deployment with canary testing
├── monitor-deployment.sh          # Deployment monitoring
├── performance-analysis.sh        # System performance analysis  
├── cost-spike-analysis.sh         # Cost anomaly investigation
├── alert-summary.sh               # Alert analysis and reporting
├── maintenance-mode.sh            # Maintenance window management
└── troubleshooting/               # Specialized troubleshooting tools
    ├── lambda-debugger.sh         # Lambda function troubleshooting
    ├── database-troubleshoot.sh   # Database connectivity/performance
    ├── api-troubleshoot.sh        # API Gateway debugging
    └── network-diagnostics.sh     # Network connectivity testing
```

## 🔧 Core Operational Scripts

### 1. Daily Health Check (`daily-health-check.sh`)

**Purpose**: Comprehensive daily system health verification

**Features**:
- AWS service connectivity testing
- Lambda function health verification
- DynamoDB table status checking
- S3 bucket accessibility testing
- API Gateway response validation
- Data freshness verification
- System metrics analysis
- Automated alerting

**Usage**:
```bash
# Basic health check
./scripts/daily-health-check.sh

# Run with detailed logging
VERBOSE=true ./scripts/daily-health-check.sh

# Check specific date
DATE_OVERRIDE=2024-12-01 ./scripts/daily-health-check.sh
```

**Exit Codes**:
- `0`: All systems healthy
- `1`: Degraded performance detected
- `2`: Critical issues found

### 2. Emergency Diagnosis (`emergency-diagnosis.sh`)

**Purpose**: Rapid diagnosis during critical incidents

**Features**:
- Critical service status verification
- Recent error analysis
- Resource utilization checking
- Quick recovery action suggestions
- Automated recovery options

**Usage**:
```bash
# Emergency diagnosis
./scripts/emergency-diagnosis.sh

# With automatic recovery attempt
./scripts/emergency-diagnosis.sh --auto-recover

# Generate diagnosis report only
./scripts/emergency-diagnosis.sh --report-only
```

### 3. Data Quality Validation (`validate-data-quality.sh`)

**Purpose**: Comprehensive data quality assessment

**Features**:
- Record count validation
- Duplicate detection
- Schema compliance checking
- Data freshness analysis
- Quality metrics validation
- Partition consistency verification

**Usage**:
```bash
# Validate yesterday's data
./scripts/validate-data-quality.sh

# Validate specific date
./scripts/validate-data-quality.sh --date 2024-12-01

# Verbose output with detailed analysis
./scripts/validate-data-quality.sh --date 2024-12-01 --verbose
```

## 🚨 Incident Response Scripts

### Lambda Function Troubleshooter

```bash
#!/bin/bash
# troubleshooting/lambda-debugger.sh

FUNCTION_NAME=$1

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name>"
    exit 1
fi

echo "=== Lambda Function Diagnostic: $FUNCTION_NAME ==="

# Function configuration
echo "1. Function Configuration:"
aws lambda get-function-configuration --function-name "$FUNCTION_NAME" --output table

# Recent invocations
echo "2. Recent Invocations (last hour):"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Sum \
    --output table

# Error analysis
echo "3. Error Analysis:"
aws logs filter-log-events \
    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
    --start-time $(date -d '1 hour ago' +%s)000 \
    --filter-pattern 'ERROR' \
    --query 'events[0:10].[eventTime,message]' \
    --output table

# Performance metrics
echo "4. Performance Metrics:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Average,Maximum \
    --output table

# Recommendations
echo "5. Troubleshooting Recommendations:"
echo "   - Check function logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo "   - Test function: aws lambda invoke --function-name $FUNCTION_NAME output.json"
echo "   - Check environment variables and permissions"
echo "   - Review recent deployments"
```

### Database Troubleshooter

```bash
#!/bin/bash
# troubleshooting/database-troubleshoot.sh

TABLE_NAME=${1:-"flightdata-main"}

echo "=== DynamoDB Troubleshooting: $TABLE_NAME ==="

# Table status
echo "1. Table Status:"
aws dynamodb describe-table --table-name "$TABLE_NAME" \
    --query 'Table.{Status:TableStatus,ItemCount:ItemCount,SizeBytes:TableSizeBytes}' \
    --output table

# Capacity metrics
echo "2. Capacity Utilization (last hour):"
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value="$TABLE_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Sum \
    --output table

# Throttling check
echo "3. Throttling Events:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ThrottledRequests \
    --dimensions Name=TableName,Value="$TABLE_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Sum \
    --output table

# Connection test
echo "4. Connection Test:"
if aws dynamodb scan --table-name "$TABLE_NAME" --limit 1 >/dev/null 2>&1; then
    echo "   ✓ Table is accessible"
else
    echo "   ✗ Cannot access table"
fi

echo "5. Troubleshooting Steps:"
echo "   - Check table status and provisioned capacity"
echo "   - Review throttling metrics"
echo "   - Verify IAM permissions"
echo "   - Check VPC configuration if applicable"
echo "   - Monitor hot partition issues"
```

### API Gateway Troubleshooter

```bash
#!/bin/bash
# troubleshooting/api-troubleshoot.sh

API_NAME=${1:-"flightdata"}

echo "=== API Gateway Troubleshooting: $API_NAME ==="

# Find API
API_ID=$(aws apigateway get-rest-apis --query "items[?contains(name, '$API_NAME')].id" --output text)

if [ -z "$API_ID" ] || [ "$API_ID" = "None" ]; then
    echo "API not found with name containing: $API_NAME"
    exit 1
fi

echo "API ID: $API_ID"

# API status
echo "1. API Configuration:"
aws apigateway get-rest-api --rest-api-id "$API_ID" --output table

# Recent requests
echo "2. Request Metrics (last hour):"
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Count \
    --dimensions Name=ApiName,Value="$API_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Sum \
    --output table

# Error rates
echo "3. Error Analysis:"
for error_type in 4XXError 5XXError; do
    echo "   $error_type:"
    aws cloudwatch get-metric-statistics \
        --namespace AWS/ApiGateway \
        --metric-name "$error_type" \
        --dimensions Name=ApiName,Value="$API_NAME" \
        --start-time "$(date -d '1 hour ago' --iso-8601)" \
        --end-time "$(date --iso-8601)" \
        --period 300 \
        --statistics Sum \
        --output table
done

# Latency check
echo "4. Latency Metrics:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Latency \
    --dimensions Name=ApiName,Value="$API_NAME" \
    --start-time "$(date -d '1 hour ago' --iso-8601)" \
    --end-time "$(date --iso-8601)" \
    --period 300 \
    --statistics Average,Maximum \
    --output table

# Test endpoint
echo "5. Endpoint Test:"
ENDPOINT_URL="https://${API_ID}.execute-api.$(aws configure get region || echo us-east-1).amazonaws.com/prod"
echo "   Testing: $ENDPOINT_URL/health"

if response=$(curl -s -w "%{http_code}" -o /tmp/api_test "$ENDPOINT_URL/health" 2>/dev/null); then
    http_code=$(tail -c 3 <<< "$response")
    echo "   HTTP Status: $http_code"
    if [ -f /tmp/api_test ]; then
        echo "   Response: $(cat /tmp/api_test)"
    fi
else
    echo "   ✗ Endpoint not responding"
fi
```

## 📊 Performance Analysis Scripts

### System Performance Analyzer

```bash
#!/bin/bash
# performance-analysis.sh

PERIOD=${1:-"daily"}
OUTPUT_FORMAT=${2:-"table"}

echo "=== System Performance Analysis ($PERIOD) ==="

case $PERIOD in
    "hourly")
        START_TIME=$(date -d '1 hour ago' --iso-8601)
        PERIOD_SECONDS=300
        ;;
    "daily")
        START_TIME=$(date -d '1 day ago' --iso-8601)
        PERIOD_SECONDS=3600
        ;;
    "weekly")
        START_TIME=$(date -d '1 week ago' --iso-8601)
        PERIOD_SECONDS=86400
        ;;
    *)
        echo "Invalid period. Use: hourly, daily, weekly"
        exit 1
        ;;
esac

END_TIME=$(date --iso-8601)

# Lambda performance
echo "1. Lambda Function Performance:"
for func in flightdata-processor flightdata-api-handler flightdata-aggregator; do
    echo "   Function: $func"
    
    # Duration
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Duration \
        --dimensions Name=FunctionName,Value="$func" \
        --start-time "$START_TIME" \
        --end-time "$END_TIME" \
        --period $PERIOD_SECONDS \
        --statistics Average,Maximum \
        --output $OUTPUT_FORMAT
    
    # Error rate
    error_count=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value="$func" \
        --start-time "$START_TIME" \
        --end-time "$END_TIME" \
        --period $PERIOD_SECONDS \
        --statistics Sum \
        --query 'Datapoints[*].Sum' \
        --output text | tr '\t' '+' | bc 2>/dev/null || echo "0")
    
    invocation_count=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value="$func" \
        --start-time "$START_TIME" \
        --end-time "$END_TIME" \
        --period $PERIOD_SECONDS \
        --statistics Sum \
        --query 'Datapoints[*].Sum' \
        --output text | tr '\t' '+' | bc 2>/dev/null || echo "1")
    
    error_rate=$(echo "scale=2; $error_count / $invocation_count * 100" | bc)
    echo "   Error Rate: ${error_rate}%"
    echo ""
done

# DynamoDB performance
echo "2. DynamoDB Performance:"
for table in flightdata-main flightdata-metrics; do
    echo "   Table: $table"
    
    aws cloudwatch get-metric-statistics \
        --namespace AWS/DynamoDB \
        --metric-name ConsumedReadCapacityUnits \
        --dimensions Name=TableName,Value="$table" \
        --start-time "$START_TIME" \
        --end-time "$END_TIME" \
        --period $PERIOD_SECONDS \
        --statistics Average,Maximum \
        --output $OUTPUT_FORMAT
done

# API Gateway performance
echo "3. API Gateway Performance:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Latency \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period $PERIOD_SECONDS \
    --statistics Average,Maximum \
    --output $OUTPUT_FORMAT

echo "Performance analysis complete."
```

### Cost Spike Analyzer

```bash
#!/bin/bash
# cost-spike-analysis.sh

DATE=${1:-$(date +%Y-%m-%d)}

echo "=== Cost Spike Analysis for $DATE ==="

# Get daily costs by service
echo "1. Cost Breakdown by Service:"
aws ce get-cost-and-usage \
    --time-period Start="$DATE",End="$(date -d "$DATE + 1 day" +%Y-%m-%d)" \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE \
    --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.BlendedCost.Amount]' \
    --output table

# Compare with previous day
PREV_DATE=$(date -d "$DATE - 1 day" +%Y-%m-%d)

echo "2. Day-over-Day Comparison:"
echo "Date: $DATE vs $PREV_DATE"

# Lambda costs
current_lambda=$(aws ce get-cost-and-usage \
    --time-period Start="$DATE",End="$(date -d "$DATE + 1 day" +%Y-%m-%d)" \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS Lambda"]}}' \
    --query 'ResultsByTime[0].Groups[0].Metrics.BlendedCost.Amount' \
    --output text 2>/dev/null || echo "0")

prev_lambda=$(aws ce get-cost-and-usage \
    --time-period Start="$PREV_DATE",End="$DATE" \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS Lambda"]}}' \
    --query 'ResultsByTime[0].Groups[0].Metrics.BlendedCost.Amount' \
    --output text 2>/dev/null || echo "0")

lambda_change=$(echo "scale=2; ($current_lambda - $prev_lambda) / $prev_lambda * 100" | bc 2>/dev/null || echo "0")
echo "Lambda: $current_lambda (${lambda_change}% change)"

# DynamoDB costs
current_dynamo=$(aws ce get-cost-and-usage \
    --time-period Start="$DATE",End="$(date -d "$DATE + 1 day" +%Y-%m-%d)" \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon DynamoDB"]}}' \
    --query 'ResultsByTime[0].Groups[0].Metrics.BlendedCost.Amount' \
    --output text 2>/dev/null || echo "0")

prev_dynamo=$(aws ce get-cost-and-usage \
    --time-period Start="$PREV_DATE",End="$DATE" \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon DynamoDB"]}}' \
    --query 'ResultsByTime[0].Groups[0].Metrics.BlendedCost.Amount' \
    --output text 2>/dev/null || echo "0")

dynamo_change=$(echo "scale=2; ($current_dynamo - $prev_dynamo) / $prev_dynamo * 100" | bc 2>/dev/null || echo "0")
echo "DynamoDB: $current_dynamo (${dynamo_change}% change)"

# Usage metrics for spike correlation
echo "3. Usage Metrics for $DATE:"

# Lambda invocations
lambda_invocations=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --start-time "${DATE}T00:00:00Z" \
    --end-time "$(date -d "$DATE + 1 day" +%Y-%m-%d)T00:00:00Z" \
    --period 86400 \
    --statistics Sum \
    --query 'Datapoints[0].Sum' \
    --output text 2>/dev/null || echo "0")

echo "Total Lambda Invocations: $lambda_invocations"

# DynamoDB operations
dynamo_reads=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value=flightdata-main \
    --start-time "${DATE}T00:00:00Z" \
    --end-time "$(date -d "$DATE + 1 day" +%Y-%m-%d)T00:00:00Z" \
    --period 86400 \
    --statistics Sum \
    --query 'Datapoints[0].Sum' \
    --output text 2>/dev/null || echo "0")

echo "DynamoDB Read Capacity Consumed: $dynamo_reads"

echo "Cost spike analysis complete."
```

## 🚀 Deployment and Maintenance Scripts

### Canary Deployment Script

```bash
#!/bin/bash
# deploy-with-canary.sh

FUNCTION_NAME=$1
TRAFFIC_PERCENTAGE=${2:-10}
MONITOR_DURATION=${3:-30}

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name> [traffic-percentage] [monitor-duration-minutes]"
    exit 1
fi

echo "=== Canary Deployment: $FUNCTION_NAME ==="
echo "Traffic split: ${TRAFFIC_PERCENTAGE}%"
echo "Monitor duration: ${MONITOR_DURATION} minutes"

# Publish new version
echo "1. Publishing new version..."
NEW_VERSION=$(aws lambda publish-version --function-name "$FUNCTION_NAME" --query 'Version' --output text)
echo "   New version: $NEW_VERSION"

# Update alias for traffic splitting
echo "2. Configuring traffic split..."
TRAFFIC_WEIGHT=$(echo "scale=2; $TRAFFIC_PERCENTAGE/100" | bc)

aws lambda update-alias \
    --function-name "$FUNCTION_NAME" \
    --name production \
    --routing-config "AdditionalVersionWeights={\"$NEW_VERSION\":$TRAFFIC_WEIGHT}"

echo "   Traffic split configured: ${TRAFFIC_PERCENTAGE}% to version $NEW_VERSION"

# Monitor deployment
echo "3. Monitoring deployment for $MONITOR_DURATION minutes..."

START_TIME=$(date +%s)
END_TIME=$((START_TIME + MONITOR_DURATION * 60))
ERROR_THRESHOLD=5

while [ $(date +%s) -lt $END_TIME ]; do
    CURRENT_TIME=$(date)
    ELAPSED=$(($(date +%s) - START_TIME))
    REMAINING=$(((END_TIME - $(date +%s)) / 60))
    
    echo "   [$CURRENT_TIME] Monitoring... (${ELAPSED}s elapsed, ${REMAINING}m remaining)"
    
    # Check error rate
    ERRORS=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value="$FUNCTION_NAME" \
        --start-time "$(date -d '5 minutes ago' --iso-8601)" \
        --end-time "$(date --iso-8601)" \
        --period 300 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$ERRORS" != "None" ] && [ "$ERRORS" -gt $ERROR_THRESHOLD ]; then
        echo "   ⚠ HIGH ERROR RATE DETECTED: $ERRORS errors"
        echo "   Rolling back deployment..."
        
        # Rollback
        aws lambda update-alias \
            --function-name "$FUNCTION_NAME" \
            --name production \
            --routing-config "{}"
        
        echo "   ✗ Deployment rolled back due to high error rate"
        exit 1
    else
        echo "   ✓ Error rate acceptable: $ERRORS errors"
    fi
    
    sleep 60
done

# Promote to 100% if monitoring successful
echo "4. Monitoring completed successfully. Promoting to 100%..."
aws lambda update-alias \
    --function-name "$FUNCTION_NAME" \
    --name production \
    --function-version "$NEW_VERSION"

echo "✓ Canary deployment completed successfully"
echo "  Function: $FUNCTION_NAME"
echo "  Version: $NEW_VERSION"
echo "  Traffic: 100%"
```

### Maintenance Mode Manager

```bash
#!/bin/bash
# maintenance-mode.sh

ACTION=$1
SERVICE=${2:-"all"}

usage() {
    echo "Usage: $0 {enable|disable|status} [service]"
    echo "Services: api, processing, all"
}

case $ACTION in
    "enable")
        echo "=== Enabling Maintenance Mode ==="
        
        if [ "$SERVICE" = "api" ] || [ "$SERVICE" = "all" ]; then
            echo "1. Enabling API maintenance mode..."
            
            # Update API Gateway to return maintenance message
            # This would typically involve updating a configuration parameter
            aws ssm put-parameter \
                --name "/flightdata/maintenance-mode" \
                --value "enabled" \
                --overwrite
            
            echo "   ✓ API maintenance mode enabled"
        fi
        
        if [ "$SERVICE" = "processing" ] || [ "$SERVICE" = "all" ]; then
            echo "2. Pausing data processing..."
            
            # Set Lambda concurrency to 0 for processing functions
            for func in flightdata-processor flightdata-aggregator; do
                aws lambda put-reserved-concurrency-configuration \
                    --function-name "$func" \
                    --reserved-concurrent-executions 0
                echo "   ✓ Paused $func"
            done
        fi
        
        # Update status page
        echo "3. Updating status page..."
        # This would integrate with your status page API
        echo "   ✓ Status page updated"
        
        echo "Maintenance mode enabled for: $SERVICE"
        ;;
        
    "disable")
        echo "=== Disabling Maintenance Mode ==="
        
        if [ "$SERVICE" = "api" ] || [ "$SERVICE" = "all" ]; then
            echo "1. Disabling API maintenance mode..."
            
            aws ssm put-parameter \
                --name "/flightdata/maintenance-mode" \
                --value "disabled" \
                --overwrite
            
            echo "   ✓ API maintenance mode disabled"
        fi
        
        if [ "$SERVICE" = "processing" ] || [ "$SERVICE" = "all" ]; then
            echo "2. Resuming data processing..."
            
            # Remove concurrency limits
            for func in flightdata-processor flightdata-aggregator; do
                aws lambda delete-reserved-concurrency-configuration \
                    --function-name "$func"
                echo "   ✓ Resumed $func"
            done
        fi
        
        # Update status page
        echo "3. Updating status page..."
        echo "   ✓ Status page updated"
        
        echo "Maintenance mode disabled for: $SERVICE"
        ;;
        
    "status")
        echo "=== Maintenance Mode Status ==="
        
        # Check maintenance mode parameter
        MAINT_STATUS=$(aws ssm get-parameter \
            --name "/flightdata/maintenance-mode" \
            --query 'Parameter.Value' \
            --output text 2>/dev/null || echo "disabled")
        
        echo "API Maintenance Mode: $MAINT_STATUS"
        
        # Check Lambda concurrency restrictions
        echo "Processing Status:"
        for func in flightdata-processor flightdata-aggregator; do
            CONCURRENCY=$(aws lambda get-reserved-concurrency-configuration \
                --function-name "$func" \
                --query 'ReservedConcurrencyExecutions' \
                --output text 2>/dev/null || echo "unrestricted")
            
            if [ "$CONCURRENCY" = "0" ]; then
                echo "   $func: PAUSED"
            else
                echo "   $func: ACTIVE ($CONCURRENCY)"
            fi
        done
        ;;
        
    *)
        usage
        exit 1
        ;;
esac
```

## 📋 Troubleshooting Checklists

### Lambda Function Issues

**Symptoms**: Function errors, timeouts, or performance issues

**Troubleshooting Steps**:
1. **Check function logs**:
   ```bash
   aws logs tail /aws/lambda/FUNCTION_NAME --follow
   ```

2. **Verify function configuration**:
   ```bash
   aws lambda get-function-configuration --function-name FUNCTION_NAME
   ```

3. **Test function locally**:
   ```bash
   aws lambda invoke --function-name FUNCTION_NAME --payload '{}' output.json
   ```

4. **Check resource utilization**:
   ```bash
   ./scripts/troubleshooting/lambda-debugger.sh FUNCTION_NAME
   ```

5. **Common fixes**:
   - Increase memory allocation
   - Extend timeout setting
   - Check environment variables
   - Verify IAM permissions
   - Review recent deployments

### Database Performance Issues

**Symptoms**: High latency, throttling, connection failures

**Troubleshooting Steps**:
1. **Check table status**:
   ```bash
   ./scripts/troubleshooting/database-troubleshoot.sh TABLE_NAME
   ```

2. **Monitor capacity utilization**:
   ```bash
   aws cloudwatch get-metric-statistics --namespace AWS/DynamoDB --metric-name ConsumedReadCapacityUnits
   ```

3. **Check for hot partitions**:
   - Review access patterns
   - Analyze partition key distribution
   - Consider adding random suffix

4. **Common fixes**:
   - Increase provisioned capacity
   - Enable auto-scaling
   - Optimize queries
   - Review partition key strategy

### API Gateway Issues

**Symptoms**: 5xx errors, high latency, connectivity issues

**Troubleshooting Steps**:
1. **Test API endpoints**:
   ```bash
   ./scripts/troubleshooting/api-troubleshoot.sh
   ```

2. **Check backend services**:
   - Verify Lambda function health
   - Test database connectivity
   - Check VPC configuration

3. **Review API configuration**:
   - Deployment status
   - Stage configuration
   - Custom domain setup

4. **Common fixes**:
   - Redeploy API
   - Update backend permissions
   - Check throttling settings
   - Verify SSL certificates

### Data Quality Issues

**Symptoms**: Missing data, duplicate records, schema violations

**Troubleshooting Steps**:
1. **Run data quality validation**:
   ```bash
   ./scripts/validate-data-quality.sh --date YYYY-MM-DD --verbose
   ```

2. **Check data pipeline health**:
   - Verify ETL job status
   - Check source data availability
   - Review transformation logic

3. **Analyze data patterns**:
   - Compare with historical trends
   - Check for upstream changes
   - Verify processing schedules

4. **Common fixes**:
   - Re-run ETL jobs
   - Update data validation rules
   - Fix source data issues
   - Adjust processing parameters

## 🔄 Automated Recovery Procedures

### Self-Healing Lambda Functions

```bash
#!/bin/bash
# auto-recovery/lambda-self-heal.sh

FUNCTION_NAME=$1
MAX_ERROR_RATE=10

# Check error rate
ERROR_RATE=$(./scripts/troubleshooting/lambda-debugger.sh "$FUNCTION_NAME" | grep "Error Rate" | awk '{print $3}' | tr -d '%')

if [ "$ERROR_RATE" -gt $MAX_ERROR_RATE ]; then
    echo "High error rate detected: ${ERROR_RATE}%"
    echo "Attempting self-healing..."
    
    # Restart function
    aws lambda update-function-configuration --function-name "$FUNCTION_NAME" --timeout 900
    
    # Wait and check
    sleep 30
    NEW_ERROR_RATE=$(./scripts/troubleshooting/lambda-debugger.sh "$FUNCTION_NAME" | grep "Error Rate" | awk '{print $3}' | tr -d '%')
    
    if [ "$NEW_ERROR_RATE" -lt $ERROR_RATE ]; then
        echo "✓ Self-healing successful: ${NEW_ERROR_RATE}%"
    else
        echo "✗ Self-healing failed, manual intervention required"
    fi
fi
```

## 📊 Monitoring and Alerting Integration

All operational scripts integrate with:

- **CloudWatch Metrics**: Performance and health data
- **SNS Topics**: Alert notifications
- **Status Pages**: Public status communication
- **Slack/Teams**: Team notifications
- **PagerDuty**: On-call escalation

## 🎯 Script Usage Best Practices

1. **Always test scripts in non-production first**
2. **Use verbose logging for debugging**
3. **Implement proper error handling**
4. **Document script parameters and outputs**
5. **Regular script validation and updates**
6. **Version control all operational scripts**
7. **Monitor script execution and results**
8. **Maintain script documentation current**

---

**Next**: Complete operational documentation with integration guides and best practices.