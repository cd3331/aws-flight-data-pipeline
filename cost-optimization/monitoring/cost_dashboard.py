#!/usr/bin/env python3

import json
import boto3
import time
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import logging
import argparse
from decimal import Decimal, ROUND_HALF_UP
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DailyCostMetrics:
    date: str
    total_cost: float
    service_costs: Dict[str, float]
    records_processed: int
    cost_per_million_records: float
    cost_change_percent: float

@dataclass
class ServiceCostBreakdown:
    service_name: str
    current_cost: float
    previous_cost: float
    change_percent: float
    cost_drivers: List[str]
    optimization_potential: float

@dataclass
class BudgetAlert:
    alert_id: str
    budget_name: str
    alert_type: str
    threshold_percent: float
    current_percent: float
    forecasted_cost: float
    budget_limit: float
    severity: str
    recommended_actions: List[str]

@dataclass
class SavingsRecommendation:
    recommendation_id: str
    service: str
    opportunity_type: str
    estimated_monthly_savings: float
    confidence_score: float
    implementation_effort: str
    description: str
    next_steps: List[str]

@dataclass
class CostDashboardData:
    dashboard_id: str
    timestamp: str
    date_range: str
    daily_metrics: List[DailyCostMetrics]
    service_breakdown: List[ServiceCostBreakdown]
    budget_alerts: List[BudgetAlert]
    savings_recommendations: List[SavingsRecommendation]
    summary: Dict[str, Any]
    forecasts: Dict[str, Any]

class CostMonitoringDashboard:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.ce_client = boto3.client('ce', region_name='us-east-1')  # Cost Explorer is only in us-east-1
        self.budgets_client = boto3.client('budgets', region_name='us-east-1')
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.pricing_client = boto3.client('pricing', region_name='us-east-1')
        
        # Application-specific metrics
        self.app_name = 'flightdata-pipeline'
        self.key_services = [
            'Amazon Simple Storage Service',
            'AWS Lambda',
            'Amazon Athena',
            'Amazon DynamoDB',
            'AWS Glue',
            'Amazon CloudWatch',
            'Amazon Simple Notification Service'
        ]

    def get_daily_cost_metrics(self, days: int = 30) -> List[DailyCostMetrics]:
        """Get daily cost metrics for the specified period."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        daily_metrics = []
        
        try:
            # Get daily costs by service
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': self.key_services
                    }
                }
            )
            
            # Process daily data
            daily_data = {}
            for result in response['ResultsByTime']:
                result_date = result['TimePeriod']['Start']
                
                service_costs = {}
                total_cost = 0.0
                
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    service_costs[service] = cost
                    total_cost += cost
                
                # Get records processed for this date (if available)
                records_processed = self._get_records_processed(result_date)
                
                # Calculate cost per million records
                cost_per_million = (total_cost / records_processed * 1000000) if records_processed > 0 else 0.0
                
                daily_data[result_date] = {
                    'total_cost': total_cost,
                    'service_costs': service_costs,
                    'records_processed': records_processed,
                    'cost_per_million_records': cost_per_million
                }
            
            # Calculate day-over-day changes and create metrics
            sorted_dates = sorted(daily_data.keys())
            for i, date_str in enumerate(sorted_dates):
                data = daily_data[date_str]
                
                # Calculate change percentage
                if i > 0:
                    prev_cost = daily_data[sorted_dates[i-1]]['total_cost']
                    change_percent = ((data['total_cost'] - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0.0
                else:
                    change_percent = 0.0
                
                daily_metrics.append(DailyCostMetrics(
                    date=date_str,
                    total_cost=data['total_cost'],
                    service_costs=data['service_costs'],
                    records_processed=data['records_processed'],
                    cost_per_million_records=data['cost_per_million_records'],
                    cost_change_percent=change_percent
                ))
            
            logger.info(f"Retrieved {len(daily_metrics)} days of cost metrics")
            return daily_metrics
        
        except ClientError as e:
            logger.error(f"Error retrieving daily cost metrics: {e}")
            return []

    def _get_records_processed(self, date_str: str) -> int:
        """Get the number of records processed on a specific date."""
        try:
            # Convert date string to datetime for CloudWatch query
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_time = target_date
            end_time = target_date + timedelta(days=1)
            
            # Try to get custom metrics for records processed
            # This would need to be implemented based on your specific application metrics
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace=f'{self.app_name}/Processing',
                MetricName='RecordsProcessed',
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily
                Statistics=['Sum']
            )
            
            if response['Datapoints']:
                return int(response['Datapoints'][0]['Sum'])
            else:
                # Fallback: estimate based on Lambda invocations
                return self._estimate_records_from_lambda_invocations(start_time, end_time)
        
        except Exception as e:
            logger.warning(f"Could not get records processed for {date_str}: {e}")
            return 0

    def _estimate_records_from_lambda_invocations(self, start_time: datetime, end_time: datetime) -> int:
        """Estimate records processed from Lambda invocations."""
        try:
            # Get Lambda invocation count for flight data functions
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': f'{self.app_name}*'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )
            
            if response['Datapoints']:
                invocations = int(response['Datapoints'][0]['Sum'])
                # Estimate: each invocation processes ~100 records
                return invocations * 100
            
        except Exception as e:
            logger.warning(f"Could not estimate records from Lambda invocations: {e}")
        
        return 1000  # Default estimate

    def get_service_cost_breakdown(self, days: int = 30) -> List[ServiceCostBreakdown]:
        """Get service-by-service cost breakdown with trends."""
        end_date = datetime.now().date()
        current_start = end_date - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)
        
        service_breakdown = []
        
        try:
            # Get current period costs
            current_response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': current_start.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': self.key_services
                    }
                }
            )
            
            # Get previous period costs for comparison
            previous_response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': previous_start.strftime('%Y-%m-%d'),
                    'End': current_start.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                ]
            )
            
            # Process current period data
            current_costs = {}
            for result in current_response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    current_costs[service] = current_costs.get(service, 0.0) + cost
            
            # Process previous period data
            previous_costs = {}
            for result in previous_response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    previous_costs[service] = previous_costs.get(service, 0.0) + cost
            
            # Create service breakdown
            for service in self.key_services:
                current_cost = current_costs.get(service, 0.0)
                previous_cost = previous_costs.get(service, 0.0)
                
                if previous_cost > 0:
                    change_percent = ((current_cost - previous_cost) / previous_cost) * 100
                else:
                    change_percent = 0.0 if current_cost == 0 else 100.0
                
                # Identify cost drivers and optimization potential
                cost_drivers = self._identify_cost_drivers(service)
                optimization_potential = self._estimate_optimization_potential(service, current_cost)
                
                service_breakdown.append(ServiceCostBreakdown(
                    service_name=service,
                    current_cost=current_cost,
                    previous_cost=previous_cost,
                    change_percent=change_percent,
                    cost_drivers=cost_drivers,
                    optimization_potential=optimization_potential
                ))
            
            # Sort by current cost (highest first)
            service_breakdown.sort(key=lambda x: x.current_cost, reverse=True)
            
            logger.info(f"Generated service breakdown for {len(service_breakdown)} services")
            return service_breakdown
        
        except ClientError as e:
            logger.error(f"Error getting service cost breakdown: {e}")
            return []

    def _identify_cost_drivers(self, service: str) -> List[str]:
        """Identify the main cost drivers for each service."""
        cost_driver_mapping = {
            'Amazon Simple Storage Service': [
                'Data storage volume',
                'Request charges (GET, PUT, LIST)',
                'Data transfer charges',
                'Storage class distribution'
            ],
            'AWS Lambda': [
                'Function execution time',
                'Memory allocation',
                'Number of invocations',
                'Provisioned concurrency'
            ],
            'Amazon Athena': [
                'Data scanned per query',
                'Query complexity',
                'Lack of partitioning',
                'SELECT * queries'
            ],
            'Amazon DynamoDB': [
                'Provisioned throughput',
                'On-demand request units',
                'Storage volume',
                'Global tables replication'
            ],
            'AWS Glue': [
                'ETL job runtime',
                'Number of DPUs allocated',
                'Data catalog requests',
                'Crawler execution frequency'
            ],
            'Amazon CloudWatch': [
                'Custom metrics volume',
                'Log ingestion volume',
                'Dashboard and alarm count',
                'API requests'
            ]
        }
        
        return cost_driver_mapping.get(service, ['General usage patterns'])

    def _estimate_optimization_potential(self, service: str, current_cost: float) -> float:
        """Estimate optimization potential for each service."""
        # Service-specific optimization potential percentages
        optimization_rates = {
            'Amazon Simple Storage Service': 0.4,  # 40% through lifecycle policies
            'AWS Lambda': 0.25,  # 25% through memory optimization
            'Amazon Athena': 0.6,   # 60% through query optimization
            'Amazon DynamoDB': 0.3,  # 30% through capacity optimization
            'AWS Glue': 0.35,      # 35% through job optimization
            'Amazon CloudWatch': 0.2  # 20% through metric optimization
        }
        
        rate = optimization_rates.get(service, 0.15)  # 15% default
        return current_cost * rate

    def get_budget_alerts(self) -> List[BudgetAlert]:
        """Get current budget alerts and forecasts."""
        alerts = []
        
        try:
            # List all budgets
            budgets_response = self.budgets_client.describe_budgets(
                AccountId=self._get_account_id()
            )
            
            for budget in budgets_response['Budgets']:
                budget_name = budget['BudgetName']
                budget_limit = float(budget['BudgetLimit']['Amount'])
                
                # Get budget performance
                performance_response = self.budgets_client.describe_budget_performance(
                    AccountId=self._get_account_id(),
                    BudgetName=budget_name
                )
                
                # Check for alerts
                alerts_response = self.budgets_client.describe_subscribers_for_notification(
                    AccountId=self._get_account_id(),
                    BudgetName=budget_name,
                    Notification={
                        'NotificationType': 'ACTUAL',
                        'ComparisonOperator': 'GREATER_THAN',
                        'Threshold': 80.0
                    }
                )
                
                # Calculate current spend percentage
                actual_spend = 0.0
                forecasted_spend = 0.0
                
                if 'BudgetedAndActualAmountsList' in performance_response:
                    for period in performance_response['BudgetedAndActualAmountsList']:
                        if 'ActualAmount' in period:
                            actual_spend += float(period['ActualAmount']['Amount'])
                        if 'ForecastedAmount' in period:
                            forecasted_spend += float(period['ForecastedAmount']['Amount'])
                
                current_percent = (actual_spend / budget_limit * 100) if budget_limit > 0 else 0
                forecasted_percent = (forecasted_spend / budget_limit * 100) if budget_limit > 0 else 0
                
                # Generate alerts based on thresholds
                if current_percent >= 90 or forecasted_percent >= 100:
                    severity = 'critical'
                    alert_type = 'budget_exceeded' if current_percent >= 100 else 'forecast_exceeded'
                elif current_percent >= 80 or forecasted_percent >= 90:
                    severity = 'high'
                    alert_type = 'approaching_limit'
                elif current_percent >= 60:
                    severity = 'medium'
                    alert_type = 'early_warning'
                else:
                    continue  # No alert needed
                
                # Generate recommended actions
                recommended_actions = self._generate_budget_recommendations(
                    current_percent, forecasted_percent
                )
                
                alerts.append(BudgetAlert(
                    alert_id=f"budget-{budget_name}-{datetime.now().strftime('%Y%m%d')}",
                    budget_name=budget_name,
                    alert_type=alert_type,
                    threshold_percent=80.0,
                    current_percent=current_percent,
                    forecasted_cost=forecasted_spend,
                    budget_limit=budget_limit,
                    severity=severity,
                    recommended_actions=recommended_actions
                ))
        
        except ClientError as e:
            logger.warning(f"Error getting budget alerts: {e}")
        
        return alerts

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            sts_client = boto3.client('sts')
            return sts_client.get_caller_identity()['Account']
        except ClientError:
            return '123456789012'  # Fallback

    def _generate_budget_recommendations(self, current_percent: float, forecasted_percent: float) -> List[str]:
        """Generate budget alert recommendations."""
        recommendations = []
        
        if current_percent >= 90:
            recommendations.extend([
                "Immediately review largest cost drivers",
                "Consider scaling down non-production resources",
                "Implement emergency cost controls"
            ])
        elif current_percent >= 80:
            recommendations.extend([
                "Review recent cost spikes",
                "Implement cost optimization recommendations",
                "Monitor daily spend closely"
            ])
        
        if forecasted_percent >= 100:
            recommendations.append("Adjust budget or implement cost reduction measures")
        
        return recommendations

    def generate_savings_recommendations(self, service_breakdown: List[ServiceCostBreakdown]) -> List[SavingsRecommendation]:
        """Generate specific savings recommendations based on cost analysis."""
        recommendations = []
        
        for service in service_breakdown:
            service_recs = self._get_service_specific_recommendations(service)
            recommendations.extend(service_recs)
        
        # Sort by estimated savings
        recommendations.sort(key=lambda x: x.estimated_monthly_savings, reverse=True)
        
        return recommendations[:20]  # Top 20 recommendations

    def _get_service_specific_recommendations(self, service: ServiceCostBreakdown) -> List[SavingsRecommendation]:
        """Get service-specific savings recommendations."""
        recommendations = []
        service_name = service.service_name
        current_cost = service.current_cost
        
        if service_name == 'Amazon Simple Storage Service':
            if current_cost > 100:  # High S3 costs
                recommendations.append(SavingsRecommendation(
                    recommendation_id=f"s3-lifecycle-{datetime.now().strftime('%Y%m%d')}",
                    service='S3',
                    opportunity_type='Lifecycle Management',
                    estimated_monthly_savings=current_cost * 0.4,
                    confidence_score=0.8,
                    implementation_effort='Medium',
                    description='Implement intelligent tiering and lifecycle policies for infrequently accessed data',
                    next_steps=[
                        'Run S3 access pattern analysis',
                        'Configure Intelligent Tiering',
                        'Set up lifecycle policies for archival'
                    ]
                ))
        
        elif service_name == 'AWS Lambda':
            if current_cost > 50:  # Significant Lambda costs
                recommendations.append(SavingsRecommendation(
                    recommendation_id=f"lambda-memory-{datetime.now().strftime('%Y%m%d')}",
                    service='Lambda',
                    opportunity_type='Memory Optimization',
                    estimated_monthly_savings=current_cost * 0.25,
                    confidence_score=0.7,
                    implementation_effort='Low',
                    description='Optimize Lambda function memory allocation based on actual usage',
                    next_steps=[
                        'Analyze memory utilization patterns',
                        'Right-size function memory',
                        'Monitor performance impact'
                    ]
                ))
        
        elif service_name == 'Amazon Athena':
            if current_cost > 20:  # High query costs
                recommendations.append(SavingsRecommendation(
                    recommendation_id=f"athena-query-{datetime.now().strftime('%Y%m%d')}",
                    service='Athena',
                    opportunity_type='Query Optimization',
                    estimated_monthly_savings=current_cost * 0.6,
                    confidence_score=0.9,
                    implementation_effort='Medium',
                    description='Optimize queries through partitioning, column projection, and result caching',
                    next_steps=[
                        'Analyze query patterns and data scanned',
                        'Implement partition pruning',
                        'Add result caching for frequent queries'
                    ]
                ))
        
        return recommendations

    def generate_cost_forecasts(self, daily_metrics: List[DailyCostMetrics], days_ahead: int = 30) -> Dict[str, Any]:
        """Generate cost forecasts based on historical trends."""
        if not daily_metrics or len(daily_metrics) < 7:
            return {}
        
        # Extract cost data for analysis
        costs = [metric.total_cost for metric in daily_metrics[-14:]]  # Last 2 weeks
        dates = [datetime.strptime(metric.date, '%Y-%m-%d').date() for metric in daily_metrics[-14:]]
        
        # Calculate trend
        daily_costs = costs
        if len(daily_costs) >= 3:
            # Simple linear trend
            avg_daily_change = sum(daily_costs[i] - daily_costs[i-1] for i in range(1, len(daily_costs))) / (len(daily_costs) - 1)
            
            # Forecast future costs
            current_cost = daily_costs[-1]
            forecasted_costs = []
            
            for day in range(1, days_ahead + 1):
                forecast_date = dates[-1] + timedelta(days=day)
                forecasted_cost = current_cost + (avg_daily_change * day)
                forecasted_costs.append({
                    'date': forecast_date.strftime('%Y-%m-%d'),
                    'forecasted_cost': max(0, forecasted_cost)  # Ensure non-negative
                })
            
            # Monthly forecast
            monthly_forecast = sum(fc['forecasted_cost'] for fc in forecasted_costs)
            
            # Confidence intervals based on historical variance
            cost_variance = statistics.variance(daily_costs) if len(daily_costs) > 1 else 0
            confidence_range = cost_variance ** 0.5 * 1.96  # 95% confidence
            
            return {
                'monthly_forecast': monthly_forecast,
                'daily_forecasts': forecasted_costs,
                'trend_direction': 'increasing' if avg_daily_change > 0 else 'decreasing' if avg_daily_change < 0 else 'stable',
                'confidence_range': confidence_range,
                'forecast_accuracy': self._calculate_forecast_accuracy(daily_metrics)
            }
        
        return {}

    def _calculate_forecast_accuracy(self, daily_metrics: List[DailyCostMetrics]) -> float:
        """Calculate historical forecast accuracy."""
        if len(daily_metrics) < 7:
            return 0.7  # Default accuracy
        
        # Simple accuracy calculation based on trend consistency
        recent_changes = []
        for i in range(1, min(8, len(daily_metrics))):  # Last week
            change = daily_metrics[-i].cost_change_percent
            recent_changes.append(abs(change))
        
        # Lower variance = higher accuracy
        if recent_changes:
            variance = statistics.variance(recent_changes)
            accuracy = max(0.3, min(0.95, 1 - (variance / 100)))  # Scale variance to accuracy
            return accuracy
        
        return 0.7

    def generate_dashboard_data(self, days: int = 30) -> CostDashboardData:
        """Generate comprehensive cost dashboard data."""
        logger.info("Generating cost monitoring dashboard data...")
        
        # Get core data
        daily_metrics = self.get_daily_cost_metrics(days)
        service_breakdown = self.get_service_cost_breakdown(days)
        budget_alerts = self.get_budget_alerts()
        savings_recommendations = self.generate_savings_recommendations(service_breakdown)
        forecasts = self.generate_cost_forecasts(daily_metrics)
        
        # Generate summary statistics
        summary = self._generate_summary_stats(daily_metrics, service_breakdown)
        
        dashboard_data = CostDashboardData(
            dashboard_id=f"cost-dashboard-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            date_range=f"{days} days",
            daily_metrics=daily_metrics,
            service_breakdown=service_breakdown,
            budget_alerts=budget_alerts,
            savings_recommendations=savings_recommendations,
            summary=summary,
            forecasts=forecasts
        )
        
        logger.info("Cost dashboard data generation completed")
        return dashboard_data

    def _generate_summary_stats(self, daily_metrics: List[DailyCostMetrics], 
                               service_breakdown: List[ServiceCostBreakdown]) -> Dict[str, Any]:
        """Generate summary statistics for the dashboard."""
        if not daily_metrics:
            return {}
        
        total_cost = sum(metric.total_cost for metric in daily_metrics)
        avg_daily_cost = total_cost / len(daily_metrics)
        
        # Cost trends
        recent_week = daily_metrics[-7:] if len(daily_metrics) >= 7 else daily_metrics
        week_avg = sum(metric.total_cost for metric in recent_week) / len(recent_week)
        
        trend = 'stable'
        if len(daily_metrics) >= 14:
            prev_week = daily_metrics[-14:-7]
            prev_week_avg = sum(metric.total_cost for metric in prev_week) / len(prev_week)
            
            change_percent = ((week_avg - prev_week_avg) / prev_week_avg * 100) if prev_week_avg > 0 else 0
            
            if change_percent > 10:
                trend = 'increasing'
            elif change_percent < -10:
                trend = 'decreasing'
        
        # Top services by cost
        top_services = sorted(service_breakdown, key=lambda x: x.current_cost, reverse=True)[:3]
        
        # Records processing efficiency
        total_records = sum(metric.records_processed for metric in daily_metrics)
        avg_cost_per_million = (total_cost / total_records * 1000000) if total_records > 0 else 0
        
        return {
            'total_cost_period': total_cost,
            'avg_daily_cost': avg_daily_cost,
            'cost_trend': trend,
            'total_records_processed': total_records,
            'avg_cost_per_million_records': avg_cost_per_million,
            'top_cost_services': [{'service': s.service_name, 'cost': s.current_cost} for s in top_services],
            'total_optimization_potential': sum(s.optimization_potential for s in service_breakdown),
            'active_budget_alerts': len([a for a in self.get_budget_alerts() if a.severity in ['high', 'critical']])
        }

def main():
    parser = argparse.ArgumentParser(description='Cost Monitoring Dashboard')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--days', type=int, default=30, help='Days of cost data to analyze')
    parser.add_argument('--output', help='Output file for dashboard data')
    parser.add_argument('--format', choices=['json', 'summary'], default='json', help='Output format')
    
    args = parser.parse_args()
    
    dashboard = CostMonitoringDashboard(region=args.region)
    
    # Generate dashboard data
    dashboard_data = dashboard.generate_dashboard_data(days=args.days)
    
    if args.format == 'json':
        # Convert to dict for JSON serialization
        dashboard_dict = asdict(dashboard_data)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(dashboard_dict, f, indent=2)
            logger.info(f"Dashboard data written to {args.output}")
        else:
            print(json.dumps(dashboard_dict, indent=2))
    
    else:  # summary format
        summary = dashboard_data.summary
        print(f"\n=== COST MONITORING DASHBOARD SUMMARY ===")
        print(f"Period: {dashboard_data.date_range}")
        print(f"Total Cost: ${summary.get('total_cost_period', 0):.2f}")
        print(f"Avg Daily Cost: ${summary.get('avg_daily_cost', 0):.2f}")
        print(f"Cost Trend: {summary.get('cost_trend', 'Unknown').upper()}")
        print(f"Records Processed: {summary.get('total_records_processed', 0):,}")
        print(f"Cost per Million Records: ${summary.get('avg_cost_per_million_records', 0):.2f}")
        
        print(f"\nTop Cost Services:")
        for service in summary.get('top_cost_services', [])[:3]:
            print(f"  - {service['service']}: ${service['cost']:.2f}")
        
        print(f"\nBudget Alerts: {summary.get('active_budget_alerts', 0)}")
        print(f"Total Optimization Potential: ${summary.get('total_optimization_potential', 0):.2f}")
        
        if dashboard_data.forecasts:
            print(f"\nMonthly Forecast: ${dashboard_data.forecasts.get('monthly_forecast', 0):.2f}")
            print(f"Forecast Trend: {dashboard_data.forecasts.get('trend_direction', 'stable').upper()}")

if __name__ == '__main__':
    main()