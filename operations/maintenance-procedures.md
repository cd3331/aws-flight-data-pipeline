# Maintenance Procedures

This document outlines scheduled maintenance procedures for the Flight Data Pipeline system, including Lambda function updates, dependency management, security patching, and performance tuning.

## 📅 Maintenance Schedule

### Weekly Maintenance (Sundays, 02:00 UTC)
- [ ] Dependency vulnerability scan
- [ ] Performance metrics review
- [ ] Log rotation and cleanup
- [ ] Cost optimization analysis
- [ ] Capacity planning review

### Monthly Maintenance (First Sunday, 01:00 UTC)
- [ ] Lambda function updates
- [ ] Security patches
- [ ] Infrastructure configuration review
- [ ] Disaster recovery testing
- [ ] Documentation updates

### Quarterly Maintenance (Seasonal)
- [ ] Major version upgrades
- [ ] Architecture review
- [ ] Security audit
- [ ] Performance load testing
- [ ] Cost optimization implementation

## 🔄 Lambda Function Updates

### Pre-Update Checklist

Before updating any Lambda function:

- [ ] Review current function performance metrics
- [ ] Check for any active incidents or issues
- [ ] Verify staging environment is ready
- [ ] Ensure rollback plan is prepared
- [ ] Notify stakeholders of maintenance window
- [ ] Create backup of current function version

### Update Procedure

#### 1. Staging Environment Testing

```bash
# Deploy to staging environment first
./scripts/deploy-to-staging.sh --function flightdata-processor --version latest

# Run automated tests against staging
./scripts/run-integration-tests.sh --environment staging

# Perform manual smoke testing
./scripts/staging-smoke-test.sh
```

#### 2. Production Deployment

```bash
# Create backup of current version
aws lambda publish-version --function-name flightdata-processor --description "Backup before update $(date)"

# Deploy new version with gradual rollout
./scripts/deploy-with-canary.sh --function flightdata-processor --traffic-percentage 10

# Monitor deployment
./scripts/monitor-deployment.sh --function flightdata-processor --duration 30m

# Complete rollout if successful
aws lambda update-alias \
  --function-name flightdata-processor \
  --name production \
  --function-version '$LATEST'
```

#### 3. Post-Deployment Verification

```bash
# Verify function health
./scripts/verify-lambda-health.sh --function flightdata-processor

# Check metrics for anomalies
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors,Duration \
  --dimensions Name=FunctionName,Value=flightdata-processor \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum,Average

# Run end-to-end tests
./scripts/e2e-tests.sh --environment production
```

### Rollback Procedure

If issues are detected during or after deployment:

```bash
# Immediate rollback to previous version
aws lambda update-alias \
  --function-name flightdata-processor \
  --name production \
  --function-version [PREVIOUS_VERSION]

# Verify rollback success
./scripts/verify-lambda-health.sh --function flightdata-processor

# Document rollback reason and follow up with investigation
```

## 📦 Dependency Updates

### Python Dependencies

#### Weekly Dependency Scan

```bash
#!/bin/bash
# weekly-dependency-scan.sh

echo "=== Weekly Dependency Vulnerability Scan ==="
echo "Date: $(date)"

# Scan for vulnerabilities in each function
for function_dir in lambda/*/; do
    if [ -f "$function_dir/requirements.txt" ]; then
        echo "Scanning dependencies in $function_dir..."
        
        # Create virtual environment for scanning
        python3 -m venv /tmp/scan_env
        source /tmp/scan_env/bin/activate
        
        # Install dependencies
        pip install -r "$function_dir/requirements.txt"
        
        # Run security scan
        pip install safety
        safety check --json > "/tmp/scan_results_$(basename $function_dir).json"
        
        # Check for outdated packages
        pip list --outdated --format=json > "/tmp/outdated_$(basename $function_dir).json"
        
        # Clean up
        deactivate
        rm -rf /tmp/scan_env
        
        echo "Scan complete for $function_dir"
    fi
done

echo "Generating consolidated report..."
python3 ./scripts/generate-dependency-report.py

echo "Dependency scan complete."
```

#### Monthly Dependency Updates

```bash
#!/bin/bash
# monthly-dependency-update.sh

FUNCTION_NAME=${1:-"all"}

echo "=== Monthly Dependency Update ==="

update_function_dependencies() {
    local func_dir=$1
    local func_name=$(basename $func_dir)
    
    echo "Updating dependencies for $func_name..."
    
    # Create backup of current requirements
    cp "$func_dir/requirements.txt" "$func_dir/requirements.txt.backup.$(date +%Y%m%d)"
    
    # Create virtual environment
    python3 -m venv /tmp/update_env
    source /tmp/update_env/bin/activate
    
    # Install current dependencies
    pip install -r "$func_dir/requirements.txt"
    
    # Upgrade packages (excluding major version bumps)
    pip list --outdated --format=json | jq -r '.[] | select(.latest_version) | .name' | while read package; do
        echo "Updating $package..."
        pip install --upgrade "$package"
    done
    
    # Generate new requirements file
    pip freeze > "$func_dir/requirements.txt.new"
    
    # Test with new dependencies
    echo "Testing $func_name with updated dependencies..."
    ./scripts/test-function-locally.sh --function "$func_name" --requirements "$func_dir/requirements.txt.new"
    
    if [ $? -eq 0 ]; then
        mv "$func_dir/requirements.txt.new" "$func_dir/requirements.txt"
        echo "Dependencies updated successfully for $func_name"
    else
        echo "Tests failed for $func_name, keeping old dependencies"
        rm "$func_dir/requirements.txt.new"
    fi
    
    # Clean up
    deactivate
    rm -rf /tmp/update_env
}

# Update specified function or all functions
if [ "$FUNCTION_NAME" == "all" ]; then
    for function_dir in lambda/*/; do
        if [ -f "$function_dir/requirements.txt" ]; then
            update_function_dependencies "$function_dir"
        fi
    done
else
    update_function_dependencies "lambda/$FUNCTION_NAME"
fi

echo "Dependency update complete."
```

## 🔒 Security Patching

### Operating System Updates

Lambda functions use AWS-managed runtimes, but we need to monitor for runtime updates:

```bash
#!/bin/bash
# check-runtime-updates.sh

echo "=== Lambda Runtime Update Check ==="

# Get current runtime versions for all functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`flightdata`)].{Name:FunctionName,Runtime:Runtime}' --output table

# Check for deprecated runtimes
echo "Checking for deprecated runtimes..."
aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`flightdata`) && (Runtime==`python3.7` || Runtime==`python3.6` || Runtime==`nodejs12.x`)].{Name:FunctionName,Runtime:Runtime}' --output table

# Get latest recommended runtime versions
echo "Latest recommended runtime versions:"
echo "Python: python3.11"
echo "Node.js: nodejs18.x"
echo "Java: java11"

echo "Runtime check complete."
```

### Container Image Updates

For functions using container images:

```bash
#!/bin/bash
# update-container-images.sh

FUNCTION_NAME=$1

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name>"
    exit 1
fi

echo "=== Container Image Update for $FUNCTION_NAME ==="

# Get current image URI
CURRENT_IMAGE=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Code.ImageUri' --output text)
echo "Current image: $CURRENT_IMAGE"

# Build new image with latest base image
echo "Building updated container image..."
cd lambda/$FUNCTION_NAME

# Update Dockerfile base image
sed -i 's/FROM public\.ecr\.aws\/lambda\/python:[0-9]\+\.[0-9]\+/FROM public.ecr.aws\/lambda\/python:3.11/' Dockerfile

# Build and tag new image
REPO_URI=$(echo $CURRENT_IMAGE | cut -d':' -f1)
NEW_TAG="$(date +%Y%m%d%H%M%S)"

docker build -t "$REPO_URI:$NEW_TAG" .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(echo $REPO_URI | cut -d'/' -f1)
docker push "$REPO_URI:$NEW_TAG"

# Update Lambda function
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri "$REPO_URI:$NEW_TAG"

echo "Container image update complete for $FUNCTION_NAME"
```

## ⚡ Performance Tuning

### Weekly Performance Analysis

```bash
#!/bin/bash
# weekly-performance-analysis.sh

echo "=== Weekly Performance Analysis ==="
echo "Analysis Period: $(date -d '7 days ago' +%Y-%m-%d) to $(date +%Y-%m-%d)"

# Analyze Lambda function performance
echo "Analyzing Lambda function performance..."

for function in flightdata-processor flightdata-api-handler flightdata-aggregator; do
    echo "Function: $function"
    
    # Get duration statistics
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Duration \
        --dimensions Name=FunctionName,Value=$function \
        --start-time $(date -d '7 days ago' --iso-8601) \
        --end-time $(date --iso-8601) \
        --period 86400 \
        --statistics Average,Maximum \
        --query 'Datapoints[*].[Timestamp,Average,Maximum]' \
        --output table
    
    # Get memory utilization (if available)
    echo "Memory utilization analysis for $function:"
    ./scripts/analyze-memory-usage.sh --function $function --days 7
    
    # Get error rates
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value=$function \
        --start-time $(date -d '7 days ago' --iso-8601) \
        --end-time $(date --iso-8601) \
        --period 86400 \
        --statistics Sum \
        --query 'Datapoints[*].[Timestamp,Sum]' \
        --output table
    
    echo "---"
done

# Database performance analysis
echo "Analyzing DynamoDB performance..."
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value=flightdata-main \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Average,Maximum \
    --output table

# API Gateway performance
echo "Analyzing API Gateway performance..."
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Latency \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Average \
    --output table

echo "Performance analysis complete."
```

### Performance Optimization Implementation

```bash
#!/bin/bash
# implement-performance-optimizations.sh

echo "=== Implementing Performance Optimizations ==="

# Memory optimization based on usage patterns
optimize_lambda_memory() {
    local function_name=$1
    
    echo "Optimizing memory for $function_name..."
    
    # Get current memory setting
    current_memory=$(aws lambda get-function-configuration --function-name $function_name --query 'MemorySize' --output text)
    echo "Current memory: ${current_memory}MB"
    
    # Analyze memory usage from logs
    avg_memory_used=$(./scripts/get-avg-memory-usage.sh --function $function_name --days 7)
    
    if [ -n "$avg_memory_used" ]; then
        # Calculate optimal memory (add 20% buffer)
        optimal_memory=$(echo "$avg_memory_used * 1.2" | bc | cut -d'.' -f1)
        
        # Round to nearest power of 2 (Lambda requirement)
        optimal_memory=$(python3 -c "import math; print(2**math.ceil(math.log2($optimal_memory)))")
        
        # Ensure minimum 128MB
        if [ $optimal_memory -lt 128 ]; then
            optimal_memory=128
        fi
        
        echo "Recommended memory: ${optimal_memory}MB"
        
        # Update if significantly different
        memory_diff=$(echo "$optimal_memory - $current_memory" | bc)
        if [ ${memory_diff#-} -gt 64 ]; then  # More than 64MB difference
            echo "Updating memory allocation..."
            aws lambda update-function-configuration \
                --function-name $function_name \
                --memory-size $optimal_memory
            
            # Monitor after change
            echo "Monitoring performance after memory update..."
            sleep 300  # Wait 5 minutes
            ./scripts/verify-performance.sh --function $function_name
        else
            echo "Memory allocation is already optimal"
        fi
    else
        echo "Could not determine average memory usage"
    fi
}

# Optimize each Lambda function
for function in flightdata-processor flightdata-api-handler flightdata-aggregator; do
    optimize_lambda_memory $function
done

# Database optimization
echo "Checking DynamoDB optimization opportunities..."

# Check for hot partitions
python3 << EOF
import boto3
import json

cloudwatch = boto3.client('cloudwatch')
dynamodb = boto3.client('dynamodb')

# Check for throttling events
response = cloudwatch.get_metric_statistics(
    Namespace='AWS/DynamoDB',
    MetricName='ThrottledRequests',
    Dimensions=[
        {'Name': 'TableName', 'Value': 'flightdata-main'}
    ],
    StartTime='2024-01-01T00:00:00Z',
    EndTime='2024-12-31T23:59:59Z',
    Period=86400,
    Statistics=['Sum']
)

if response['Datapoints']:
    total_throttles = sum(point['Sum'] for point in response['Datapoints'])
    if total_throttles > 0:
        print(f"Found {total_throttles} throttling events - consider increasing capacity")
    else:
        print("No throttling detected")
else:
    print("No throttling data available")
EOF

echo "Performance optimization complete."
```

## 🧹 System Cleanup and Maintenance

### Log Cleanup

```bash
#!/bin/bash
# cleanup-logs.sh

echo "=== Log Cleanup ==="

# Set retention policy for CloudWatch log groups
for log_group in $(aws logs describe-log-groups --query 'logGroups[?starts_with(logGroupName, `/aws/lambda/flightdata`)].logGroupName' --output text); do
    echo "Setting retention policy for $log_group..."
    aws logs put-retention-policy \
        --log-group-name "$log_group" \
        --retention-in-days 30
done

# Clean up old S3 access logs
echo "Cleaning up old S3 access logs..."
aws s3 rm s3://flightdata-access-logs/ --recursive --exclude "*" --include "*/$(date -d '90 days ago' +%Y/%m/%d)/*"

# Clean up old query result files in Athena
echo "Cleaning up old Athena query results..."
aws s3 rm s3://flightdata-query-results/ --recursive --exclude "*" --include "*/$(date -d '30 days ago' +%Y/%m/%d)/*"

echo "Log cleanup complete."
```

### Database Maintenance

```bash
#!/bin/bash
# database-maintenance.sh

echo "=== Database Maintenance ==="

# Analyze table utilization
echo "Analyzing DynamoDB table utilization..."

# Get table metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits,ConsumedWriteCapacityUnits \
    --dimensions Name=TableName,Value=flightdata-main \
    --start-time $(date -d '7 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Average,Maximum \
    --output table

# Check table size and item count
aws dynamodb describe-table \
    --table-name flightdata-main \
    --query 'Table.{ItemCount:ItemCount,TableSizeBytes:TableSizeBytes}' \
    --output table

# Archive old data if needed
echo "Checking for archival candidates..."
python3 << EOF
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('flightdata-main')

# Find items older than 1 year
cutoff_date = (datetime.now() - timedelta(days=365)).isoformat()

# Note: This is a simplified example. In practice, you'd want to
# use a more efficient method like scanning with pagination
print(f"Items older than {cutoff_date} should be archived")
EOF

echo "Database maintenance complete."
```

## 📊 Capacity Planning

### Monthly Capacity Review

```bash
#!/bin/bash
# monthly-capacity-review.sh

echo "=== Monthly Capacity Planning Review ==="
echo "Review Date: $(date)"

# Lambda concurrency analysis
echo "Lambda Concurrency Analysis:"
for function in flightdata-processor flightdata-api-handler flightdata-aggregator; do
    echo "Function: $function"
    
    # Get concurrent executions
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name ConcurrentExecutions \
        --dimensions Name=FunctionName,Value=$function \
        --start-time $(date -d '30 days ago' --iso-8601) \
        --end-time $(date --iso-8601) \
        --period 86400 \
        --statistics Average,Maximum \
        --query 'Datapoints[*].[Timestamp,Average,Maximum]' \
        --output table
    
    # Check for throttling
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Throttles \
        --dimensions Name=FunctionName,Value=$function \
        --start-time $(date -d '30 days ago' --iso-8601) \
        --end-time $(date --iso-8601) \
        --period 86400 \
        --statistics Sum \
        --query 'Datapoints[*].[Timestamp,Sum]' \
        --output table
done

# DynamoDB capacity analysis
echo "DynamoDB Capacity Analysis:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits,ConsumedWriteCapacityUnits \
    --dimensions Name=TableName,Value=flightdata-main \
    --start-time $(date -d '30 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Average,Maximum \
    --output table

# S3 storage growth analysis
echo "S3 Storage Growth Analysis:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/S3 \
    --metric-name BucketSizeBytes \
    --dimensions Name=BucketName,Value=flightdata-processed Name=StorageType,Value=StandardStorage \
    --start-time $(date -d '30 days ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 86400 \
    --statistics Average \
    --output table

# Generate capacity recommendations
echo "Generating capacity recommendations..."
python3 ./scripts/generate-capacity-recommendations.py --period 30

echo "Capacity review complete."
```

## 🔧 Automation Scripts

### Deploy with Canary Release

```bash
#!/bin/bash
# deploy-with-canary.sh

FUNCTION_NAME=$1
TRAFFIC_PERCENTAGE=${2:-10}

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name> [traffic-percentage]"
    exit 1
fi

echo "=== Canary Deployment for $FUNCTION_NAME ==="

# Publish new version
echo "Publishing new version..."
NEW_VERSION=$(aws lambda publish-version --function-name $FUNCTION_NAME --query 'Version' --output text)
echo "New version: $NEW_VERSION"

# Update alias to split traffic
echo "Configuring traffic split: ${TRAFFIC_PERCENTAGE}% to new version..."
aws lambda update-alias \
    --function-name $FUNCTION_NAME \
    --name production \
    --routing-config AdditionalVersionWeights="{\"$NEW_VERSION\":$(echo "scale=2; $TRAFFIC_PERCENTAGE/100" | bc)}"

echo "Canary deployment configured. Monitor metrics before full rollout."

# Monitor script
cat > /tmp/monitor-canary-$FUNCTION_NAME.sh << EOF
#!/bin/bash
echo "Monitoring canary deployment for $FUNCTION_NAME..."

# Monitor for 30 minutes
for i in {1..30}; do
    echo "Minute \$i of 30..."
    
    # Check error rate
    ERRORS=\$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
        --start-time \$(date -d '5 minutes ago' --iso-8601) \
        --end-time \$(date --iso-8601) \
        --period 300 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null)
    
    if [ "\$ERRORS" != "None" ] && [ "\$ERRORS" -gt 0 ]; then
        echo "WARNING: \$ERRORS errors detected in last 5 minutes"
    fi
    
    sleep 60
done

echo "Canary monitoring complete."
EOF

chmod +x /tmp/monitor-canary-$FUNCTION_NAME.sh
echo "Monitor script created: /tmp/monitor-canary-$FUNCTION_NAME.sh"
```

### Maintenance Window Manager

```bash
#!/bin/bash
# maintenance-window.sh

ACTION=$1
WINDOW_ID=${2:-"mw-flightdata-weekly"}

case $ACTION in
    "start")
        echo "Starting maintenance window: $WINDOW_ID"
        
        # Disable monitoring alerts
        aws sns set-topic-attributes \
            --topic-arn arn:aws:sns:us-east-1:ACCOUNT:flightdata-alerts \
            --attribute-name DeliveryPolicy \
            --attribute-value '{"healthyRetryPolicy":{"numRetries":0}}'
        
        # Set maintenance mode in status page
        curl -X POST "https://api.statuspage.io/v1/pages/PAGE_ID/incidents" \
            -H "Authorization: OAuth YOUR_TOKEN" \
            -d "incident[name]=Scheduled Maintenance" \
            -d "incident[status]=investigating" \
            -d "incident[impact_override]=maintenance"
        
        echo "Maintenance window started"
        ;;
        
    "end")
        echo "Ending maintenance window: $WINDOW_ID"
        
        # Re-enable monitoring alerts
        aws sns set-topic-attributes \
            --topic-arn arn:aws:sns:us-east-1:ACCOUNT:flightdata-alerts \
            --attribute-name DeliveryPolicy \
            --attribute-value '{"healthyRetryPolicy":{"numRetries":3}}'
        
        # Update status page
        curl -X PATCH "https://api.statuspage.io/v1/pages/PAGE_ID/incidents/INCIDENT_ID" \
            -H "Authorization: OAuth YOUR_TOKEN" \
            -d "incident[status]=resolved"
        
        # Run post-maintenance verification
        ./scripts/post-maintenance-verification.sh
        
        echo "Maintenance window ended"
        ;;
        
    *)
        echo "Usage: $0 {start|end} [window-id]"
        exit 1
        ;;
esac
```

## 📋 Maintenance Checklist Templates

### Pre-Maintenance Checklist
- [ ] Verify no active incidents
- [ ] Check system performance is stable
- [ ] Ensure backup procedures are current
- [ ] Notify stakeholders of maintenance window
- [ ] Prepare rollback procedures
- [ ] Set up monitoring during maintenance
- [ ] Start maintenance window notifications

### Post-Maintenance Checklist
- [ ] Verify all services are operational
- [ ] Check performance metrics for anomalies
- [ ] Run integration test suite
- [ ] Monitor error rates for 30 minutes
- [ ] Update maintenance logs
- [ ] End maintenance window notifications
- [ ] Document any issues encountered

---

**Next**: [Disaster Recovery Plan](disaster-recovery.md)