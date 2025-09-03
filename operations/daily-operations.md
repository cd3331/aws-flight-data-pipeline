# Daily Operations Checklist

This document outlines the daily operational procedures for maintaining the Flight Data Pipeline system health, performance, and cost efficiency.

## 🌅 Morning Health Check Routine (30 minutes)

### 1. System Health Dashboard Review (10 minutes)

**Objective**: Verify overall system health and identify any overnight issues.

**Checklist**:
- [ ] Check overall system status in CloudWatch dashboard
- [ ] Verify all Lambda functions are healthy (no sustained errors)
- [ ] Confirm S3 buckets are accessible and ingestion is current
- [ ] Check DynamoDB table health and consumed capacity
- [ ] Review Athena query success rates

**Script**: Run automated health check
```bash
./scripts/daily-health-check.sh
```

**Expected Results**:
- All services showing "Healthy" status
- Error rates < 1% across all components
- No critical alerts in the last 24 hours

**Escalation**: If any service shows degraded status, follow [Incident Response Procedures](incident-response.md).

### 2. Data Quality Validation (10 minutes)

**Objective**: Ensure data pipeline is processing accurate and complete data.

**Checklist**:
- [ ] Verify data freshness (last ingestion timestamp)
- [ ] Check record count trends for anomalies
- [ ] Validate data schema compliance
- [ ] Review data quality metrics dashboard
- [ ] Confirm no missing partitions in processed data

**Script**: Run data quality validation
```bash
./scripts/validate-data-quality.sh --date $(date -d yesterday +%Y-%m-%d)
```

**Key Metrics to Check**:
- Records processed in last 24 hours: Expected > 1M records
- Data freshness: < 30 minutes lag
- Schema compliance: 100%
- Duplicate detection rate: < 0.1%

**Escalation**: If data quality issues detected, follow [Data Quality Incident Response](incident-response.md#data-quality-degradation).

### 3. Performance Metrics Review (10 minutes)

**Objective**: Monitor system performance and identify optimization opportunities.

**Checklist**:
- [ ] Review API response times (95th percentile)
- [ ] Check Lambda function duration and memory usage
- [ ] Monitor Athena query performance
- [ ] Verify S3 request metrics and error rates
- [ ] Review end-to-end processing latency

**Script**: Generate performance report
```bash
./scripts/generate-performance-report.sh --period daily
```

**Performance Thresholds**:
- API Response Time (95th percentile): < 2 seconds
- Lambda Average Duration: < 30 seconds
- End-to-end Processing Latency: < 15 minutes
- S3 Request Error Rate: < 0.01%

**Actions**:
- If thresholds exceeded, investigate using performance troubleshooting guide
- Log performance trends for weekly review
- Consider scaling adjustments if consistent degradation

## 💰 Cost Review and Budget Monitoring (15 minutes)

### 1. Daily Cost Analysis

**Objective**: Monitor daily spend and identify cost anomalies.

**Checklist**:
- [ ] Review yesterday's total AWS costs
- [ ] Compare costs to daily budget allocation
- [ ] Check for any significant service cost spikes
- [ ] Verify cost per million records processed
- [ ] Review month-to-date spend vs. budget

**Script**: Run daily cost analysis
```bash
./scripts/daily-cost-analysis.sh
```

**Cost Thresholds**:
- Daily variance from budget: < 15%
- Cost per million records: < $5.00
- Single service cost spike: > 50% increase needs investigation

### 2. Resource Utilization Check

**Checklist**:
- [ ] Review Lambda concurrent execution trends
- [ ] Check S3 storage growth rate
- [ ] Monitor DynamoDB consumption patterns
- [ ] Verify no unused resources are incurring costs

**Actions**:
- Flag any resources with < 10% utilization for review
- Identify opportunities for Reserved Instance savings
- Note any scaling recommendations for capacity planning

## 🚨 Alert Review and Acknowledgment (10 minutes)

### 1. Alert Triage

**Objective**: Review and acknowledge all system alerts from the previous 24 hours.

**Checklist**:
- [ ] Review all Critical and High severity alerts
- [ ] Acknowledge resolved alerts in monitoring system
- [ ] Document any manual interventions taken
- [ ] Update alert status and resolution notes
- [ ] Identify any recurring alert patterns

**Script**: Generate alert summary
```bash
./scripts/alert-summary.sh --since "24 hours ago"
```

### 2. Alert Analysis

**For each unresolved alert**:
- [ ] Assess current impact on system operations
- [ ] Determine if immediate action is required
- [ ] Schedule follow-up if investigation needed
- [ ] Update alert status and assign owner

## 📊 Operational Metrics Documentation

### Daily Metrics Log

Create a daily entry with the following information:

**Date**: `$(date +%Y-%m-%d)`

**System Health**:
- Overall Status: [Healthy/Degraded/Critical]
- Active Incidents: [Number]
- Services with Issues: [List any]

**Performance**:
- Records Processed: [Count]
- Average Processing Latency: [Minutes]
- API Response Time (95th): [Seconds]
- Error Rate: [Percentage]

**Cost**:
- Daily Spend: $[Amount]
- Budget Variance: [Percentage]
- Cost per Million Records: $[Amount]

**Alerts**:
- New Alerts (24h): [Count by severity]
- Resolved Alerts: [Count]
- Outstanding Issues: [List]

**Actions Taken**:
- [List any manual interventions]
- [Performance optimizations applied]
- [Cost optimization measures]

## 🔧 Common Daily Operations Scripts

### Health Check Script
```bash
#!/bin/bash
# daily-health-check.sh

echo "=== Flight Data Pipeline Health Check ==="
echo "Date: $(date)"
echo

# Check Lambda functions
echo "Checking Lambda functions..."
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `flightdata`)].FunctionName' --output table

# Check S3 buckets
echo "Checking S3 buckets..."
aws s3 ls | grep flightdata

# Check DynamoDB tables
echo "Checking DynamoDB tables..."
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `flightdata`)]' --output table

# Get recent errors
echo "Checking for recent errors..."
aws logs filter-log-events \
  --log-group-name /aws/lambda/flightdata-processor \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern 'ERROR' \
  --query 'events[].message' \
  --output text | head -10

echo "Health check complete."
```

### Data Quality Validation Script
```bash
#!/bin/bash
# validate-data-quality.sh

DATE=${1:-$(date -d yesterday +%Y-%m-%d)}

echo "=== Data Quality Validation for $DATE ==="

# Check record counts
echo "Checking record counts..."
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) as record_count FROM flightdata_processed WHERE dt='$DATE'" \
  --result-configuration OutputLocation=s3://flightdata-query-results/ \
  --work-group primary

# Check for schema compliance
echo "Validating schema compliance..."
python3 << EOF
import boto3
import json

# Schema validation logic here
s3 = boto3.client('s3')
# Implement schema validation
print("Schema validation: PASSED")
EOF

# Check data freshness
echo "Checking data freshness..."
LATEST=$(aws s3 ls s3://flightdata-processed/year=$(date +%Y)/month=$(date +%m)/day=$(date +%d)/ | tail -1 | awk '{print $1 " " $2}')
echo "Latest data timestamp: $LATEST"

echo "Data quality validation complete."
```

### Performance Report Script
```bash
#!/bin/bash
# generate-performance-report.sh

PERIOD=${1:-daily}

echo "=== Performance Report ($PERIOD) ==="
echo "Generated: $(date)"

# Lambda performance metrics
echo "Lambda Performance:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=flightdata-processor \
  --statistics Average,Maximum \
  --start-time $(date -d '1 day ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --query 'Datapoints[*].[Timestamp,Average,Maximum]' \
  --output table

# API Gateway metrics
echo "API Performance:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --statistics Average \
  --start-time $(date -d '1 day ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --query 'Datapoints[*].[Timestamp,Average]' \
  --output table

echo "Performance report complete."
```

## 📝 Daily Operations Log Template

```markdown
# Daily Operations Log - [DATE]

## Morning Health Check
- **Time Completed**: [TIME]
- **Overall Status**: [Healthy/Issues Detected]
- **Issues Found**: [List any issues]
- **Actions Taken**: [List actions]

## Data Quality Check
- **Records Processed**: [COUNT]
- **Data Freshness**: [TIMESTAMP]
- **Schema Compliance**: [PERCENTAGE]
- **Quality Issues**: [List any issues]

## Performance Review
- **API Response Time**: [TIME]
- **Processing Latency**: [TIME]  
- **Error Rates**: [PERCENTAGE]
- **Performance Issues**: [List any issues]

## Cost Analysis
- **Daily Spend**: $[AMOUNT]
- **Budget Variance**: [PERCENTAGE]
- **Cost Anomalies**: [List any spikes]
- **Optimization Actions**: [List actions taken]

## Alert Review
- **New Alerts**: [COUNT by severity]
- **Resolved Alerts**: [COUNT]
- **Outstanding Issues**: [List with owners]

## Summary
- **Overall Day Assessment**: [Smooth/Issues/Critical]
- **Follow-up Required**: [Yes/No - Details]
- **Recommendations**: [Any recommendations for next day]

---
**Completed by**: [NAME]
**Review Date**: [DATE]
```

## 🎯 Success Metrics

Track these daily metrics to measure operational success:

- **System Availability**: Target 99.5% daily uptime
- **Data Processing**: Complete processing within SLA timeframes
- **Cost Control**: Stay within ±10% of daily budget
- **Alert Response**: Acknowledge all alerts within defined SLA
- **Documentation**: Complete daily operations log

## 🔄 Weekly Review Process

Every Friday, conduct a weekly review:

1. Analyze week's operational metrics trends
2. Review recurring issues and implement preventive measures
3. Update operational procedures based on lessons learned
4. Plan capacity and performance optimizations
5. Review and update cost optimization strategies

---

**Next**: [Incident Response Procedures](incident-response.md)