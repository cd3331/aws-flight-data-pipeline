# Incident Response Procedures

This document outlines the incident response procedures for the Flight Data Pipeline system, including escalation paths, troubleshooting steps, and resolution procedures for common incident types.

## 🚨 Incident Classification

### Severity Levels

| Severity | Impact | Response Time | Examples |
|----------|--------|---------------|----------|
| **P0 - Critical** | Complete system outage or data loss | 15 minutes | API completely down, data corruption |
| **P1 - High** | Major functionality impaired | 1 hour | High error rates (>5%), significant performance degradation |
| **P2 - Medium** | Minor functionality impaired | 4 hours | Moderate performance issues, non-critical feature failures |
| **P3 - Low** | Minimal impact | 24 hours | Cost anomalies, capacity warnings, minor bugs |

### Incident Types

1. **Service Availability** - API or core services unavailable
2. **Performance Degradation** - System response times or throughput issues
3. **Data Quality** - Incorrect, missing, or corrupted data
4. **Cost Anomalies** - Unexpected cost spikes or resource consumption
5. **Security** - Unauthorized access attempts or security breaches

## 🔥 Critical Incident Response (P0)

### Immediate Actions (0-5 minutes)

1. **Acknowledge the incident** in monitoring system
2. **Page the on-call engineer** immediately
3. **Create incident channel**: `#incident-YYYYMMDD-HHMM`
4. **Start incident bridge** and invite key stakeholders
5. **Begin incident documentation** in shared document

### Initial Assessment (5-15 minutes)

**Incident Commander Tasks**:
- [ ] Assess scope of impact (users affected, services down)
- [ ] Determine if this is a complete outage or partial degradation
- [ ] Check for any recent deployments or changes
- [ ] Review monitoring dashboards for root cause indicators
- [ ] Initiate customer communication if user-facing impact

**Technical Lead Tasks**:
- [ ] Check overall system status
- [ ] Review error logs for the last 30 minutes
- [ ] Verify database connectivity and health
- [ ] Check external service dependencies
- [ ] Assess if rollback is possible/needed

### Investigation and Resolution (15+ minutes)

Follow the appropriate runbook based on symptoms:

#### Complete System Outage
```bash
# Quick diagnosis script
./scripts/emergency-diagnosis.sh

# Check critical services
aws lambda invoke --function-name flightdata-health-check /tmp/health-response.json
aws dynamodb describe-table --table-name flightdata-main --query 'Table.TableStatus'
aws s3 ls s3://flightdata-processed/ --recursive | tail -5
```

**Common Causes & Solutions**:

1. **Lambda Function Errors**
   - Check CloudWatch logs: `/aws/lambda/flightdata-*`
   - Look for timeout, memory, or permission errors
   - Consider increasing memory/timeout if resource-related
   - Rollback to previous version if deployment-related

2. **Database Issues**
   - Check DynamoDB throttling metrics
   - Verify table status and provisioned capacity
   - Check for hot partition issues
   - Scale read/write capacity if needed

3. **External API Dependencies**
   - Verify OpenSky Network API availability
   - Check API rate limits and quotas
   - Implement fallback or circuit breaker if needed
   - Contact external service provider if outage confirmed

#### API Gateway Issues
```bash
# Check API Gateway health
aws apigateway get-rest-apis
aws logs filter-log-events --log-group-name API-Gateway-Execution-Logs_* --start-time $(date -d '1 hour ago' +%s)000

# Check for throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name 4XXError,5XXError \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

## ⚠️ High Priority Incident Response (P1)

### High Error Rate Response

**Symptoms**: Error rate > 5% sustained for > 5 minutes

**Investigation Steps**:

1. **Identify Error Patterns**
```bash
# Get recent errors by service
./scripts/analyze-error-patterns.sh --since "1 hour ago"

# Check Lambda function errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/flightdata-processor \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern 'ERROR' \
  --query 'events[*].[eventTime,message]' \
  --output table
```

2. **Check Resource Utilization**
```bash
# Check Lambda concurrency
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=flightdata-processor \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Maximum
```

**Common Resolutions**:
- **Memory/Timeout Issues**: Increase Lambda memory or timeout
- **Throttling**: Increase concurrency limits or implement backoff
- **Dependency Failures**: Enable circuit breaker or fallback mechanisms
- **Code Issues**: Rollback to previous stable version

### Performance Degradation Response

**Symptoms**: Response time > 5 seconds (95th percentile) or throughput < 50% normal

**Investigation Steps**:

1. **Performance Analysis**
```bash
# Generate performance breakdown
./scripts/performance-analysis.sh --period "last 2 hours"

# Check database performance
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits,ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=flightdata-main \
  --start-time $(date -d '2 hours ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

2. **Bottleneck Identification**
- Check Lambda duration and memory usage trends
- Review database read/write capacity consumption
- Analyze S3 request patterns and errors
- Verify network latency to external services

**Common Resolutions**:
- **Database Bottleneck**: Scale DynamoDB read/write capacity
- **Lambda Performance**: Optimize code or increase resources
- **S3 Performance**: Implement request pattern optimization
- **Network Issues**: Check routing and DNS resolution

## 📊 Data Quality Degradation

### Symptoms
- Missing data partitions for current day
- Record count drops > 20% from normal
- Schema validation failures > 1%
- Data freshness lag > 60 minutes

### Investigation Procedure

1. **Data Pipeline Health Check**
```bash
# Check data ingestion status
./scripts/check-data-pipeline-health.sh

# Verify latest data timestamps
aws s3 ls s3://flightdata-raw/year=$(date +%Y)/month=$(date +%m)/day=$(date +%d)/ --recursive | tail -10

# Check processing job status
aws glue get-job-runs --job-name flightdata-etl --max-items 5
```

2. **Data Quality Analysis**
```bash
# Run data quality validation
./scripts/validate-data-quality.sh --date $(date +%Y-%m-%d) --verbose

# Check for duplicate records
aws athena start-query-execution \
  --query-string "
    SELECT COUNT(*) as duplicates 
    FROM (
      SELECT flight_id, COUNT(*) as cnt 
      FROM flightdata_processed 
      WHERE dt = '$(date +%Y-%m-%d)' 
      GROUP BY flight_id 
      HAVING COUNT(*) > 1
    )" \
  --result-configuration OutputLocation=s3://flightdata-query-results/ \
  --work-group primary
```

### Resolution Steps

1. **For Missing Data**:
   - Check upstream data source availability
   - Verify ingestion Lambda function execution
   - Re-run ETL job for missing partitions
   - Update data processing schedules if needed

2. **For Schema Issues**:
   - Identify schema evolution in source data
   - Update data transformation logic
   - Implement backward compatibility
   - Notify downstream consumers of changes

3. **For Data Quality Issues**:
   - Enable additional data validation rules
   - Implement data quality monitoring
   - Set up alerting for quality degradation
   - Review and update data cleansing logic

## 🌐 API Unavailability Response

### Symptoms
- API Gateway returning 5xx errors
- Complete API unresponsiveness
- Authentication/authorization failures
- Timeout errors from clients

### Diagnosis Steps

1. **API Health Assessment**
```bash
# Test API endpoints
./scripts/test-api-endpoints.sh

# Check API Gateway status
aws apigateway get-deployments --rest-api-id YOUR_API_ID

# Review API Gateway logs
aws logs tail API-Gateway-Execution-Logs_*/production --follow --since 1h
```

2. **Backend Service Check**
```bash
# Test Lambda functions directly
aws lambda invoke \
  --function-name flightdata-api-handler \
  --payload '{"httpMethod":"GET","path":"/health"}' \
  /tmp/api-test-response.json

# Check backend database connectivity
./scripts/test-database-connectivity.sh
```

### Resolution Actions

1. **API Gateway Issues**:
   - Check deployment status and redeploy if necessary
   - Verify API Gateway configuration and permissions
   - Check throttling settings and rate limits
   - Review custom domain and certificate status

2. **Lambda Function Issues**:
   - Check function configuration and permissions
   - Review environment variables and dependencies
   - Monitor concurrency and timeout settings
   - Rollback to previous version if recent deployment

3. **Database Connectivity**:
   - Verify VPC configuration and security groups
   - Check database credentials and connection strings
   - Monitor database capacity and performance
   - Implement connection pooling if needed

## 💸 Cost Spike Investigation

### Symptoms
- Daily cost increase > 50% from baseline
- Unexpected resource consumption spikes
- Budget alerts triggered
- Unusually high service usage

### Investigation Process

1. **Cost Analysis**
```bash
# Generate cost breakdown by service
./scripts/cost-spike-analysis.sh --date $(date +%Y-%m-%d)

# Check resource usage patterns
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --start-time $(date -d '1 day ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Sum
```

2. **Resource Usage Review**
```bash
# Check for runaway processes
aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`flightdata`)].{Name:FunctionName,LastModified:LastModified}'

# Review S3 usage patterns
aws s3api list-objects-v2 --bucket flightdata-processed --query 'Contents[?LastModified>=`2024-01-01`]' --output table
```

### Resolution Actions

1. **Immediate Cost Control**:
   - Implement cost controls and limits
   - Scale down non-essential resources
   - Enable cost anomaly detection
   - Set up budget alerts for proactive monitoring

2. **Root Cause Analysis**:
   - Identify service causing cost spike
   - Review recent configuration changes
   - Analyze usage patterns and trends
   - Implement cost optimization measures

## 📋 Incident Response Checklist

### During Incident
- [ ] Acknowledge incident in monitoring system
- [ ] Create incident response channel
- [ ] Assign incident commander
- [ ] Start incident timeline documentation
- [ ] Communicate with stakeholders
- [ ] Begin troubleshooting following appropriate runbook
- [ ] Escalate if not resolved within SLA timeframe
- [ ] Implement workaround if permanent fix takes time

### Post-Incident
- [ ] Verify full resolution and system stability
- [ ] Update incident status to resolved
- [ ] Document root cause analysis
- [ ] Identify prevention measures
- [ ] Schedule post-incident review meeting
- [ ] Update runbooks based on learnings
- [ ] Implement monitoring improvements
- [ ] Close incident channel after documentation

## 🔧 Emergency Scripts

### Emergency Diagnosis Script
```bash
#!/bin/bash
# emergency-diagnosis.sh

echo "=== EMERGENCY SYSTEM DIAGNOSIS ==="
echo "Timestamp: $(date)"
echo

echo "1. Checking critical Lambda functions..."
for func in flightdata-processor flightdata-api-handler flightdata-aggregator; do
    echo "  Checking $func..."
    aws lambda get-function --function-name $func --query 'Configuration.State' --output text 2>/dev/null || echo "  ERROR: Cannot access $func"
done

echo "2. Checking DynamoDB tables..."
for table in flightdata-main flightdata-metrics; do
    echo "  Checking $table..."
    aws dynamodb describe-table --table-name $table --query 'Table.TableStatus' --output text 2>/dev/null || echo "  ERROR: Cannot access $table"
done

echo "3. Checking S3 buckets..."
aws s3 ls | grep flightdata || echo "ERROR: Cannot list S3 buckets"

echo "4. Checking recent errors (last 15 minutes)..."
aws logs filter-log-events \
  --log-group-name /aws/lambda/flightdata-processor \
  --start-time $(date -d '15 minutes ago' +%s)000 \
  --filter-pattern 'ERROR' \
  --query 'events[*].message' \
  --output text | head -5

echo "5. Checking API Gateway..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}, Response Time: %{time_total}s\n" \
  https://api.flightdata-pipeline.com/health 2>/dev/null || echo "ERROR: Cannot reach API"

echo "Emergency diagnosis complete."
```

### System Recovery Script
```bash
#!/bin/bash
# emergency-recovery.sh

echo "=== EMERGENCY RECOVERY ACTIONS ==="

# Restart critical Lambda functions
echo "Restarting Lambda functions..."
aws lambda update-function-configuration --function-name flightdata-processor --timeout 900
aws lambda update-function-configuration --function-name flightdata-api-handler --timeout 30

# Check and fix DynamoDB capacity
echo "Checking DynamoDB capacity..."
aws dynamodb update-table \
  --table-name flightdata-main \
  --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=100

# Clear any stuck SQS messages
echo "Purging SQS queues..."
aws sqs purge-queue --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/flightdata-processing-queue

echo "Recovery actions complete. Monitor system for stability."
```

## 📞 Escalation Matrix

| Time | Severity P0 | Severity P1 | Severity P2 |
|------|-------------|-------------|-------------|
| 0-15 min | On-call engineer | On-call engineer | - |
| 15-30 min | + Senior engineer | On-call engineer | On-call engineer |
| 30-60 min | + Engineering manager | + Senior engineer | On-call engineer |
| 60+ min | + Director/VP | + Engineering manager | + Senior engineer |

## 📚 Post-Incident Review Process

1. **Schedule Review Meeting** (within 48 hours)
2. **Prepare Timeline** of incident events
3. **Conduct Blameless Post-mortem**
4. **Identify Root Cause** and contributing factors
5. **Document Action Items** with owners and due dates
6. **Update Runbooks** based on lessons learned
7. **Implement Preventive Measures**
8. **Share Learnings** with broader team

---

**Next**: [Maintenance Procedures](maintenance-procedures.md)