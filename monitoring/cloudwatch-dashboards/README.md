# CloudWatch Dashboards

This directory contains pre-configured CloudWatch dashboard configurations for comprehensive monitoring of the Flight Data Pipeline system. Each dashboard is designed for specific stakeholder groups with tailored metrics and visualizations.

## 📊 Dashboard Overview

| Dashboard | Audience | Purpose | Refresh Rate |
|-----------|----------|---------|--------------|
| **Executive** | Leadership, Business | High-level KPIs, costs, business metrics | 5 minutes |
| **Technical** | Engineers, DevOps | System performance, errors, infrastructure | 1 minute |
| **Data Quality** | Data Engineers, Analysts | Data accuracy, validation, anomalies | 5 minutes |

## 🎯 Executive Dashboard

**File**: [`executive-dashboard.json`](executive-dashboard.json)

### Key Metrics Tracked
- **📊 API Request Volume**: Total requests across all environments
- **💰 Revenue Metrics**: MRR, new customer revenue, churn
- **👥 User Engagement**: Active users, customer satisfaction
- **💸 Cost Analysis**: AWS spend by service with budget tracking
- **📈 Data Volume**: Ingestion, processing, and serving metrics
- **⚡ Performance**: API response times and availability
- **🏆 Business KPIs**: Market share, feature adoption rates

### Widget Configuration
```json
{
  "type": "metric",
  "properties": {
    "title": "📊 API Request Volume",
    "period": 300,
    "stat": "Sum",
    "region": "us-east-1",
    "annotations": {
      "horizontal": [{
        "label": "Target: 10M requests/month",
        "value": 463
      }]
    }
  }
}
```

### Time Range & Auto-Refresh
- **Default Range**: Last 24 hours
- **Auto-Refresh**: Every 5 minutes
- **Live Data**: Enabled for real-time updates

## ⚙️ Technical Dashboard

**File**: [`technical-dashboard.json`](technical-dashboard.json)

### Key Metrics Tracked
- **🔄 Lambda Performance**: Invocations, duration, errors, throttling
- **📊 Error Analysis**: Error rates by function with SLA thresholds
- **📬 Queue Monitoring**: SQS message flow, depths, and age
- **🗄️ Database Performance**: DynamoDB capacity, latency, throttling
- **💾 Cache Performance**: ElastiCache hits/misses, CPU utilization
- **🌐 API Gateway**: Latency breakdown, caching performance
- **⏰ Event Processing**: EventBridge rule executions
- **⏱️ Processing Latency**: End-to-end pipeline performance

### Critical Thresholds
```yaml
Lambda Duration: 240 seconds (timeout warning)
Error Rate: 1% (SLA threshold)
Queue Age: 300 seconds (5 minute SLA)
API Latency: 500ms (SLA target)
```

### Time Range & Auto-Refresh
- **Default Range**: Last 3 hours
- **Auto-Refresh**: Every 1 minute
- **Live Data**: Enabled for immediate issue detection

## 📊 Data Quality Dashboard

**File**: [`data-quality-dashboard.json`](data-quality-dashboard.json)

### Key Metrics Tracked
- **📈 Quality Scores**: Overall and by data type (98% target)
- **✅ Data Completeness**: Field-level completeness tracking
- **🔍 Validation Failures**: By rule type with detailed breakdown
- **🚨 Anomaly Detection**: By type (altitude changes, velocity, etc.)
- **📊 Processing Funnel**: Records through each pipeline stage
- **⏱️ Data Freshness**: Age of data by type (30-second target)
- **🔗 Consistency Scores**: Temporal, spatial, referential integrity
- **🌍 Geographic Coverage**: Data availability by region

### Quality Thresholds
```yaml
Data Quality Score: 98% (target), 95% (warning), 90% (critical)
Data Freshness: 30 seconds (target)
Completeness: 95% minimum for core fields
Anomaly Rate: <0.1% of processed records
```

### Time Range & Auto-Refresh
- **Default Range**: Last 6 hours
- **Auto-Refresh**: Every 5 minutes
- **Live Data**: Enabled for quality monitoring

## 🚀 Deployment Instructions

### 1. Using AWS CLI
```bash
# Deploy Executive Dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "FlightData-Executive" \
  --dashboard-body file://executive-dashboard.json \
  --region us-east-1

# Deploy Technical Dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "FlightData-Technical" \
  --dashboard-body file://technical-dashboard.json \
  --region us-east-1

# Deploy Data Quality Dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "FlightData-DataQuality" \
  --dashboard-body file://data-quality-dashboard.json \
  --region us-east-1
```

### 2. Using AWS CDK
```typescript
import { Dashboard } from 'aws-cdk-lib/aws-cloudwatch';
import * as fs from 'fs';

// Read dashboard configuration
const executiveDashboard = JSON.parse(
  fs.readFileSync('monitoring/cloudwatch-dashboards/executive-dashboard.json', 'utf8')
);

// Create dashboard resource
new Dashboard(this, 'ExecutiveDashboard', {
  dashboardName: 'FlightData-Executive',
  widgets: executiveDashboard.widgets.map(widget => 
    // Convert JSON widget to CDK widget construct
    this.createWidgetFromJson(widget)
  ),
});
```

### 3. Using Terraform
```hcl
resource "aws_cloudwatch_dashboard" "executive" {
  dashboard_name = "FlightData-Executive"
  
  dashboard_body = file("${path.module}/monitoring/cloudwatch-dashboards/executive-dashboard.json")
}

resource "aws_cloudwatch_dashboard" "technical" {
  dashboard_name = "FlightData-Technical"
  
  dashboard_body = file("${path.module}/monitoring/cloudwatch-dashboards/technical-dashboard.json")
}

resource "aws_cloudwatch_dashboard" "data_quality" {
  dashboard_name = "FlightData-DataQuality"
  
  dashboard_body = file("${path.module}/monitoring/cloudwatch-dashboards/data-quality-dashboard.json")
}
```

## 🔧 Customization Guide

### Modifying Time Ranges
```json
{
  "start": "-PT24H",  // 24 hours ago
  "end": "PT0H",      // now
  "period": 300       // 5-minute intervals
}

// Common time ranges:
// -PT1H    : Last 1 hour
// -PT3H    : Last 3 hours  
// -PT24H   : Last 24 hours
// -P7D     : Last 7 days
// -P30D    : Last 30 days
```

### Adding Custom Metrics
```json
{
  "type": "metric",
  "properties": {
    "metrics": [
      ["YourNamespace", "YourMetric", "Dimension", "Value"]
    ],
    "title": "Your Custom Metric",
    "period": 300,
    "stat": "Average",
    "region": "us-east-1"
  }
}
```

### Environment-Specific Dashboards
```bash
# Create environment-specific versions
sed 's/-prod/-staging/g' technical-dashboard.json > technical-dashboard-staging.json
sed 's/-prod/-dev/g' technical-dashboard.json > technical-dashboard-dev.json

# Deploy environment-specific dashboards
aws cloudwatch put-dashboard \
  --dashboard-name "FlightData-Technical-Staging" \
  --dashboard-body file://technical-dashboard-staging.json
```

## 📱 Mobile and Responsive Considerations

### Widget Sizing
```json
{
  "x": 0,      // X position (0-23)
  "y": 0,      // Y position
  "width": 12, // Width (1-24)
  "height": 6  // Height (1-50)
}

// Recommended sizes:
// Small metrics: 6x6
// Charts: 12x6 or 8x6  
// Large charts: 24x6
// Tables: 24x6
```

### Responsive Layout
- **Full Screen (24 units)**: Executive dashboard layout
- **Half Screen (12 units)**: Technical dashboard widgets
- **Mobile (6-8 units)**: Critical metrics only

## 🚨 Alerting Integration

### CloudWatch Alarms
```json
{
  "type": "metric",
  "properties": {
    "annotations": {
      "horizontal": [
        {
          "label": "Critical Threshold",
          "value": 95,
          "fill": "above"
        },
        {
          "label": "Warning Threshold", 
          "value": 98,
          "fill": "above"
        }
      ]
    }
  }
}
```

### SNS Integration
Configure dashboards to link with SNS topics for automated alerting:
```bash
# Create SNS topic for dashboard alerts
aws sns create-topic --name flight-data-dashboard-alerts

# Subscribe email to topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:flight-data-dashboard-alerts \
  --protocol email \
  --notification-endpoint alerts@flightdata.com
```

## 📊 Widget Types Reference

### Metric Widgets
- **Line Charts**: Time series data
- **Stacked Area**: Cumulative metrics
- **Number**: Single value with sparkline
- **Gauge**: Progress indicators

### Log Widgets
- **Table View**: Structured log data
- **Bar Chart**: Log aggregations
- **Pie Chart**: Distribution analysis

### Custom Widgets
- **Text**: Markdown documentation
- **Image**: Architecture diagrams
- **External**: Third-party integrations

## 🔍 Best Practices

### Dashboard Design
```yaml
✅ Do:
  - Group related metrics together
  - Use consistent time periods
  - Include threshold annotations
  - Add meaningful titles and labels
  - Use appropriate chart types

❌ Don't:
  - Overcrowd dashboards with too many widgets
  - Mix different time ranges in same view
  - Use misleading scales or axes
  - Forget to document custom metrics
```

### Performance Optimization
```yaml
Reduce Load Times:
  - Use appropriate periods (300s for real-time, 3600s for trends)
  - Limit number of metrics per widget
  - Cache expensive queries
  - Use statistical aggregation

Cost Optimization:
  - Avoid unnecessary high-frequency polling
  - Use CloudWatch Insights sparingly
  - Aggregate metrics at source when possible
  - Monitor CloudWatch API costs
```

### Maintenance
```yaml
Regular Tasks:
  - Review dashboard relevance quarterly
  - Update thresholds based on SLA changes
  - Archive unused dashboards
  - Document custom metric meanings
  - Test dashboard functionality after deployments
```

## 📚 Additional Resources

### AWS Documentation
- [CloudWatch Dashboard Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html)
- [CloudWatch Metrics Reference](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/aws-services-cloudwatch-metrics.html)
- [Dashboard API Reference](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/)

### Monitoring Best Practices
- [AWS Well-Architected Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/monitor-workload-resources.html)
- [Observability Best Practices](https://aws.amazon.com/builders-library/implementing-health-checks/)
- [CloudWatch Best Practices](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practices_For_Alarms.html)

---

These dashboards provide comprehensive monitoring capabilities for the Flight Data Pipeline, enabling stakeholders at all levels to monitor system health, business metrics, and data quality effectively.