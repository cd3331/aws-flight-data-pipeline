#!/usr/bin/env python3

import json
import boto3
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError
import logging
import argparse
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LambdaMetrics:
    function_name: str
    current_memory: int
    avg_duration: float
    max_duration: float
    avg_memory_used: float
    max_memory_used: float
    invocation_count: int
    error_rate: float
    cold_start_percentage: float
    concurrent_executions: int
    throttles: int
    current_monthly_cost: float

@dataclass
class MemoryRecommendation:
    function_name: str
    current_memory: int
    recommended_memory: int
    confidence_score: float
    projected_duration: float
    cost_change_monthly: float
    performance_improvement: float
    reasoning: str

@dataclass
class ConcurrencyRecommendation:
    function_name: str
    current_concurrency: Optional[int]
    recommended_concurrency: int
    reasoning: str
    cost_impact_monthly: float

@dataclass
class ColdStartOptimization:
    function_name: str
    current_cold_start_rate: float
    optimization_opportunities: List[str]
    estimated_improvement: float
    implementation_priority: str

class LambdaOptimizer:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
        
        self.pricing = {
            'request_cost': 0.0000002,  # $0.20 per 1M requests
            'gb_second_cost': 0.0000166667,  # $16.67 per 1M GB-seconds
            'provisioned_concurrency_cost': 0.0000041667,  # $4.17 per GB-hour
            'duration_cost': 0.0000000017  # Additional duration cost
        }

    def get_function_list(self, name_prefix: str = None) -> List[str]:
        """Get list of Lambda functions, optionally filtered by prefix."""
        try:
            paginator = self.lambda_client.get_paginator('list_functions')
            functions = []
            
            for page in paginator.paginate():
                for func in page['Functions']:
                    if name_prefix is None or func['FunctionName'].startswith(name_prefix):
                        functions.append(func['FunctionName'])
            
            logger.info(f"Found {len(functions)} Lambda functions")
            return functions
        except ClientError as e:
            logger.error(f"Error listing functions: {e}")
            return []

    def get_function_metrics(self, function_name: str, days: int = 30) -> LambdaMetrics:
        """Get comprehensive metrics for a Lambda function."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        try:
            # Get function configuration
            func_config = self.lambda_client.get_function(FunctionName=function_name)
            current_memory = func_config['Configuration']['MemorySize']
            
            # Get CloudWatch metrics
            metrics = self._get_cloudwatch_metrics(function_name, start_time, end_time)
            
            # Calculate current cost
            monthly_cost = self._calculate_monthly_cost(
                metrics['invocation_count'], 
                metrics['avg_duration'], 
                current_memory
            )
            
            return LambdaMetrics(
                function_name=function_name,
                current_memory=current_memory,
                avg_duration=metrics['avg_duration'],
                max_duration=metrics['max_duration'],
                avg_memory_used=metrics['avg_memory_used'],
                max_memory_used=metrics['max_memory_used'],
                invocation_count=metrics['invocation_count'],
                error_rate=metrics['error_rate'],
                cold_start_percentage=metrics['cold_start_percentage'],
                concurrent_executions=metrics['concurrent_executions'],
                throttles=metrics['throttles'],
                current_monthly_cost=monthly_cost
            )
        
        except ClientError as e:
            logger.error(f"Error getting metrics for {function_name}: {e}")
            return None

    def _get_cloudwatch_metrics(self, function_name: str, start_time: datetime, end_time: datetime) -> Dict[str, float]:
        """Retrieve CloudWatch metrics for a Lambda function."""
        metrics = {
            'avg_duration': 0.0,
            'max_duration': 0.0,
            'avg_memory_used': 0.0,
            'max_memory_used': 0.0,
            'invocation_count': 0,
            'error_rate': 0.0,
            'cold_start_percentage': 0.0,
            'concurrent_executions': 0,
            'throttles': 0
        }
        
        try:
            # Duration metrics
            duration_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily
                Statistics=['Average', 'Maximum']
            )
            
            if duration_response['Datapoints']:
                metrics['avg_duration'] = statistics.mean([dp['Average'] for dp in duration_response['Datapoints']])
                metrics['max_duration'] = max([dp['Maximum'] for dp in duration_response['Datapoints']])
            
            # Invocation count
            invocation_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )
            
            if invocation_response['Datapoints']:
                metrics['invocation_count'] = sum([dp['Sum'] for dp in invocation_response['Datapoints']])
            
            # Error rate
            error_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )
            
            if error_response['Datapoints']:
                total_errors = sum([dp['Sum'] for dp in error_response['Datapoints']])
                metrics['error_rate'] = (total_errors / metrics['invocation_count'] * 100) if metrics['invocation_count'] > 0 else 0
            
            # Throttles
            throttle_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Throttles',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )
            
            if throttle_response['Datapoints']:
                metrics['throttles'] = sum([dp['Sum'] for dp in throttle_response['Datapoints']])
            
            # Concurrent executions
            concurrent_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='ConcurrentExecutions',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Maximum']
            )
            
            if concurrent_response['Datapoints']:
                metrics['concurrent_executions'] = max([dp['Maximum'] for dp in concurrent_response['Datapoints']])
            
            # Get memory utilization from logs (if available)
            memory_metrics = self._get_memory_utilization(function_name, start_time, end_time)
            metrics.update(memory_metrics)
            
            # Estimate cold start percentage
            metrics['cold_start_percentage'] = self._estimate_cold_start_percentage(function_name, start_time, end_time)
            
        except ClientError as e:
            logger.warning(f"Error getting CloudWatch metrics for {function_name}: {e}")
        
        return metrics

    def _get_memory_utilization(self, function_name: str, start_time: datetime, end_time: datetime) -> Dict[str, float]:
        """Extract memory utilization from CloudWatch logs."""
        metrics = {'avg_memory_used': 0.0, 'max_memory_used': 0.0}
        
        try:
            log_group = f"/aws/lambda/{function_name}"
            
            # Query logs for memory usage reports
            query = """
            fields @timestamp, @message
            | filter @message like /REPORT RequestId/
            | parse @message /Max Memory Used: (?<memory_used>\d+) MB/
            | stats avg(memory_used), max(memory_used)
            """
            
            start_query_response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            query_id = start_query_response['queryId']
            
            # Wait for query to complete
            max_wait = 30
            wait_time = 0
            while wait_time < max_wait:
                query_response = self.logs_client.get_query_results(queryId=query_id)
                if query_response['status'] == 'Complete':
                    break
                time.sleep(1)
                wait_time += 1
            
            if query_response['status'] == 'Complete' and query_response['results']:
                result = query_response['results'][0]
                if len(result) >= 2:
                    metrics['avg_memory_used'] = float(result[0]['value']) if result[0]['value'] != 'null' else 0.0
                    metrics['max_memory_used'] = float(result[1]['value']) if result[1]['value'] != 'null' else 0.0
        
        except Exception as e:
            logger.warning(f"Could not get memory utilization for {function_name}: {e}")
        
        return metrics

    def _estimate_cold_start_percentage(self, function_name: str, start_time: datetime, end_time: datetime) -> float:
        """Estimate cold start percentage from logs."""
        try:
            log_group = f"/aws/lambda/{function_name}"
            
            # Query for init duration (cold starts)
            query = """
            fields @timestamp, @message
            | filter @message like /REPORT RequestId/
            | parse @message /Init Duration: (?<init_duration>[\d.]+) ms/
            | stats count() as total_with_init
            """
            
            init_query = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            # Query for total invocations
            total_query = """
            fields @timestamp, @message
            | filter @message like /REPORT RequestId/
            | stats count() as total_invocations
            """
            
            total_query_response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=total_query
            )
            
            # Wait and get results
            time.sleep(3)
            
            init_results = self.logs_client.get_query_results(queryId=init_query['queryId'])
            total_results = self.logs_client.get_query_results(queryId=total_query_response['queryId'])
            
            if (init_results['status'] == 'Complete' and total_results['status'] == 'Complete' and 
                init_results['results'] and total_results['results']):
                
                cold_starts = float(init_results['results'][0][0]['value']) if init_results['results'][0][0]['value'] != 'null' else 0
                total_invocations = float(total_results['results'][0][0]['value']) if total_results['results'][0][0]['value'] != 'null' else 1
                
                return (cold_starts / total_invocations * 100) if total_invocations > 0 else 0
        
        except Exception as e:
            logger.warning(f"Could not estimate cold start percentage for {function_name}: {e}")
        
        return 0.0

    def _calculate_monthly_cost(self, invocations: int, avg_duration_ms: float, memory_mb: int) -> float:
        """Calculate monthly Lambda cost based on usage."""
        monthly_invocations = invocations * (30 / 7)  # Scale weekly data to monthly
        duration_seconds = avg_duration_ms / 1000
        gb_seconds = (memory_mb / 1024) * duration_seconds * monthly_invocations
        
        request_cost = monthly_invocations * self.pricing['request_cost']
        duration_cost = gb_seconds * self.pricing['gb_second_cost']
        
        return request_cost + duration_cost

    def analyze_memory_optimization(self, function_name: str) -> MemoryRecommendation:
        """Analyze and recommend optimal memory configuration."""
        metrics = self.get_function_metrics(function_name)
        if not metrics:
            return None
        
        current_memory = metrics.current_memory
        avg_memory_used = metrics.avg_memory_used
        max_memory_used = metrics.max_memory_used
        
        # Memory optimization logic
        if avg_memory_used == 0:
            # No memory data available, use duration-based heuristics
            recommended_memory = self._recommend_memory_by_duration(metrics.avg_duration, current_memory)
            confidence = 0.3
            reasoning = "Based on duration analysis (no memory utilization data available)"
        else:
            # Memory utilization data available
            memory_utilization = avg_memory_used / current_memory
            
            if memory_utilization > 0.8:
                # Over-utilized, increase memory
                recommended_memory = min(10240, int(current_memory * 1.5))
                confidence = 0.9
                reasoning = f"High memory utilization ({memory_utilization:.1%}), increase recommended"
            elif memory_utilization < 0.3:
                # Under-utilized, decrease memory
                recommended_memory = max(128, int(max_memory_used * 1.2))
                confidence = 0.8
                reasoning = f"Low memory utilization ({memory_utilization:.1%}), decrease recommended"
            else:
                # Optimal range
                recommended_memory = current_memory
                confidence = 0.9
                reasoning = f"Memory utilization optimal ({memory_utilization:.1%})"
        
        # Calculate cost impact
        new_monthly_cost = self._calculate_monthly_cost(
            metrics.invocation_count * 4,  # Scale to monthly
            metrics.avg_duration,
            recommended_memory
        )
        
        cost_change = new_monthly_cost - metrics.current_monthly_cost
        
        # Estimate performance improvement
        performance_improvement = self._estimate_performance_improvement(
            current_memory, recommended_memory, metrics.avg_duration
        )
        
        return MemoryRecommendation(
            function_name=function_name,
            current_memory=current_memory,
            recommended_memory=recommended_memory,
            confidence_score=confidence,
            projected_duration=metrics.avg_duration * (1 - performance_improvement),
            cost_change_monthly=cost_change,
            performance_improvement=performance_improvement,
            reasoning=reasoning
        )

    def _recommend_memory_by_duration(self, avg_duration_ms: float, current_memory: int) -> int:
        """Recommend memory based on duration patterns."""
        if avg_duration_ms > 30000:  # > 30 seconds
            return min(10240, current_memory * 2)
        elif avg_duration_ms > 10000:  # > 10 seconds
            return min(3008, int(current_memory * 1.5))
        elif avg_duration_ms < 1000:  # < 1 second
            return max(128, int(current_memory * 0.7))
        else:
            return current_memory

    def _estimate_performance_improvement(self, current_memory: int, new_memory: int, current_duration: float) -> float:
        """Estimate performance improvement from memory change."""
        if new_memory > current_memory:
            # More memory typically improves performance
            memory_ratio = new_memory / current_memory
            # Performance improvement plateaus at higher memory levels
            improvement = min(0.3, (memory_ratio - 1) * 0.2)
            return improvement
        elif new_memory < current_memory:
            # Less memory might slightly reduce performance
            memory_ratio = current_memory / new_memory
            degradation = min(0.1, (memory_ratio - 1) * 0.05)
            return -degradation
        
        return 0.0

    def analyze_concurrency_optimization(self, function_name: str) -> ConcurrencyRecommendation:
        """Analyze and recommend concurrency settings."""
        metrics = self.get_function_metrics(function_name)
        if not metrics:
            return None
        
        try:
            # Get current provisioned concurrency
            concurrency_config = self.lambda_client.get_provisioned_concurrency_config(
                FunctionName=function_name
            )
            current_concurrency = concurrency_config.get('AllocatedConcurrencyExecutions', 0)
        except ClientError:
            current_concurrency = None
        
        # Analyze concurrency needs
        max_concurrent = metrics.concurrent_executions
        throttles = metrics.throttles
        
        if throttles > 0:
            # Function is being throttled, needs reserved concurrency
            recommended_concurrency = max(max_concurrent * 2, 10)
            reasoning = f"Function throttled {throttles} times, reserved concurrency recommended"
            cost_impact = recommended_concurrency * self.pricing['provisioned_concurrency_cost'] * 730  # Monthly
        elif max_concurrent > 100:
            # High concurrency function, consider provisioned concurrency for consistent performance
            recommended_concurrency = int(max_concurrent * 0.7)
            reasoning = f"High concurrency function ({max_concurrent} max), provisioned concurrency for performance"
            cost_impact = recommended_concurrency * self.pricing['provisioned_concurrency_cost'] * 730
        else:
            # No concurrency optimization needed
            recommended_concurrency = 0
            reasoning = "No concurrency optimization needed"
            cost_impact = 0.0
        
        return ConcurrencyRecommendation(
            function_name=function_name,
            current_concurrency=current_concurrency,
            recommended_concurrency=recommended_concurrency,
            reasoning=reasoning,
            cost_impact_monthly=cost_impact
        )

    def analyze_cold_start_optimization(self, function_name: str) -> ColdStartOptimization:
        """Analyze cold start patterns and recommend optimizations."""
        metrics = self.get_function_metrics(function_name)
        if not metrics:
            return None
        
        cold_start_rate = metrics.cold_start_percentage
        optimization_opportunities = []
        
        try:
            # Get function configuration for analysis
            func_config = self.lambda_client.get_function(FunctionName=function_name)
            runtime = func_config['Configuration']['Runtime']
            code_size = func_config['Configuration']['CodeSize']
            layers = func_config['Configuration'].get('Layers', [])
            
            # Analyze optimization opportunities
            if cold_start_rate > 20:
                optimization_opportunities.append("High cold start rate detected")
                
                if code_size > 50 * 1024 * 1024:  # > 50MB
                    optimization_opportunities.append("Large deployment package - consider code splitting")
                
                if len(layers) > 3:
                    optimization_opportunities.append("Multiple layers - consolidate if possible")
                
                if 'java' in runtime.lower():
                    optimization_opportunities.append("Java runtime - consider GraalVM native compilation")
                
                if 'node' in runtime.lower():
                    optimization_opportunities.append("Node.js - minimize dependencies and use ES modules")
                
                if 'python' in runtime.lower():
                    optimization_opportunities.append("Python - reduce import overhead and use Lambda layers")
                
                optimization_opportunities.append("Consider provisioned concurrency for consistent performance")
            
            elif cold_start_rate > 10:
                optimization_opportunities.append("Moderate cold start rate - monitor and optimize if needed")
            
            else:
                optimization_opportunities.append("Cold start rate within acceptable range")
            
            # Estimate improvement potential
            if cold_start_rate > 20:
                estimated_improvement = 0.6  # Can reduce cold starts by 60%
                priority = "high"
            elif cold_start_rate > 10:
                estimated_improvement = 0.4  # Can reduce cold starts by 40%
                priority = "medium"
            else:
                estimated_improvement = 0.2  # Can reduce cold starts by 20%
                priority = "low"
            
        except Exception as e:
            logger.warning(f"Error analyzing cold starts for {function_name}: {e}")
            optimization_opportunities = ["Unable to analyze - check function configuration"]
            estimated_improvement = 0.0
            priority = "unknown"
        
        return ColdStartOptimization(
            function_name=function_name,
            current_cold_start_rate=cold_start_rate,
            optimization_opportunities=optimization_opportunities,
            estimated_improvement=estimated_improvement,
            implementation_priority=priority
        )

    def generate_optimization_report(self, function_names: List[str] = None) -> Dict[str, Any]:
        """Generate comprehensive optimization report for Lambda functions."""
        if function_names is None:
            function_names = self.get_function_list()
        
        report = {
            'analysis_id': f"lambda-optimization-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'region': self.region,
            'functions_analyzed': len(function_names),
            'memory_recommendations': [],
            'concurrency_recommendations': [],
            'cold_start_optimizations': [],
            'total_current_monthly_cost': 0.0,
            'total_projected_monthly_cost': 0.0,
            'total_monthly_savings': 0.0,
            'summary': {}
        }
        
        logger.info(f"Analyzing {len(function_names)} Lambda functions for optimization")
        
        for func_name in function_names:
            try:
                logger.info(f"Analyzing function: {func_name}")
                
                # Get current metrics and cost
                metrics = self.get_function_metrics(func_name)
                if metrics:
                    report['total_current_monthly_cost'] += metrics.current_monthly_cost
                
                # Memory optimization
                memory_rec = self.analyze_memory_optimization(func_name)
                if memory_rec:
                    report['memory_recommendations'].append(asdict(memory_rec))
                    report['total_projected_monthly_cost'] += (
                        metrics.current_monthly_cost + memory_rec.cost_change_monthly
                    )
                
                # Concurrency optimization
                concurrency_rec = self.analyze_concurrency_optimization(func_name)
                if concurrency_rec:
                    report['concurrency_recommendations'].append(asdict(concurrency_rec))
                
                # Cold start optimization
                cold_start_opt = self.analyze_cold_start_optimization(func_name)
                if cold_start_opt:
                    report['cold_start_optimizations'].append(asdict(cold_start_opt))
            
            except Exception as e:
                logger.error(f"Error analyzing function {func_name}: {e}")
        
        # Calculate total savings
        report['total_monthly_savings'] = (
            report['total_current_monthly_cost'] - report['total_projected_monthly_cost']
        )
        
        # Generate summary
        report['summary'] = self._generate_summary(report)
        
        logger.info("Lambda optimization analysis completed")
        return report

    def _generate_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimization summary statistics."""
        memory_recs = report['memory_recommendations']
        concurrency_recs = report['concurrency_recommendations']
        cold_start_opts = report['cold_start_optimizations']
        
        summary = {
            'functions_with_memory_optimization': len([r for r in memory_recs if r['recommended_memory'] != r['current_memory']]),
            'functions_with_concurrency_optimization': len([r for r in concurrency_recs if r['recommended_concurrency'] > 0]),
            'functions_with_high_cold_starts': len([r for r in cold_start_opts if r['implementation_priority'] == 'high']),
            'average_memory_utilization': 0.0,
            'total_potential_performance_improvement': 0.0,
            'highest_impact_optimizations': []
        }
        
        if memory_recs:
            # Calculate average performance improvement
            performance_improvements = [r['performance_improvement'] for r in memory_recs if r['performance_improvement'] > 0]
            if performance_improvements:
                summary['total_potential_performance_improvement'] = sum(performance_improvements)
        
        # Identify highest impact optimizations
        high_impact = []
        
        # High cost savings
        for rec in memory_recs:
            if abs(rec['cost_change_monthly']) > 50:
                high_impact.append({
                    'function': rec['function_name'],
                    'type': 'memory',
                    'impact': f"${abs(rec['cost_change_monthly']):.2f}/month cost change",
                    'priority': 'high' if rec['cost_change_monthly'] < 0 else 'medium'
                })
        
        # High cold start functions
        for opt in cold_start_opts:
            if opt['implementation_priority'] == 'high':
                high_impact.append({
                    'function': opt['function_name'],
                    'type': 'cold_start',
                    'impact': f"{opt['current_cold_start_rate']:.1f}% cold start rate",
                    'priority': 'high'
                })
        
        summary['highest_impact_optimizations'] = sorted(
            high_impact, key=lambda x: x['priority'], reverse=True
        )[:10]
        
        return summary

    def implement_memory_optimization(self, function_name: str, new_memory: int, dry_run: bool = True) -> bool:
        """Implement memory optimization for a function."""
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would update {function_name} memory to {new_memory}MB")
                return True
            
            self.lambda_client.update_function_configuration(
                FunctionName=function_name,
                MemorySize=new_memory
            )
            
            logger.info(f"Updated {function_name} memory to {new_memory}MB")
            return True
        
        except ClientError as e:
            logger.error(f"Error updating memory for {function_name}: {e}")
            return False

    def implement_concurrency_optimization(self, function_name: str, concurrency: int, dry_run: bool = True) -> bool:
        """Implement concurrency optimization for a function."""
        try:
            if dry_run:
                if concurrency > 0:
                    logger.info(f"[DRY RUN] Would set provisioned concurrency for {function_name} to {concurrency}")
                else:
                    logger.info(f"[DRY RUN] Would remove provisioned concurrency for {function_name}")
                return True
            
            if concurrency > 0:
                self.lambda_client.put_provisioned_concurrency_config(
                    FunctionName=function_name,
                    ProvisionedConcurrencyExecutions=concurrency
                )
                logger.info(f"Set provisioned concurrency for {function_name} to {concurrency}")
            else:
                # Remove provisioned concurrency
                try:
                    self.lambda_client.delete_provisioned_concurrency_config(
                        FunctionName=function_name
                    )
                    logger.info(f"Removed provisioned concurrency for {function_name}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        raise
            
            return True
        
        except ClientError as e:
            logger.error(f"Error updating concurrency for {function_name}: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Lambda Cost and Performance Optimizer')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--function-prefix', help='Function name prefix filter')
    parser.add_argument('--function-names', nargs='+', help='Specific function names to analyze')
    parser.add_argument('--days', type=int, default=30, help='Days of metrics to analyze')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--implement', action='store_true', help='Implement optimizations (not dry run)')
    parser.add_argument('--memory-only', action='store_true', help='Only analyze memory optimization')
    parser.add_argument('--concurrency-only', action='store_true', help='Only analyze concurrency optimization')
    parser.add_argument('--cold-start-only', action='store_true', help='Only analyze cold start optimization')
    
    args = parser.parse_args()
    
    optimizer = LambdaOptimizer(region=args.region)
    
    # Determine functions to analyze
    if args.function_names:
        function_names = args.function_names
    else:
        function_names = optimizer.get_function_list(args.function_prefix)
    
    if not function_names:
        logger.error("No functions found to analyze")
        return
    
    # Generate optimization report
    report = optimizer.generate_optimization_report(function_names)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(report, indent=2))
    
    # Implement optimizations if requested
    if args.implement:
        logger.info("Implementing optimizations...")
        
        if not args.concurrency_only and not args.cold_start_only:
            # Implement memory optimizations
            for rec in report['memory_recommendations']:
                if rec['recommended_memory'] != rec['current_memory']:
                    optimizer.implement_memory_optimization(
                        rec['function_name'], 
                        rec['recommended_memory'], 
                        dry_run=False
                    )
        
        if not args.memory_only and not args.cold_start_only:
            # Implement concurrency optimizations
            for rec in report['concurrency_recommendations']:
                if rec['recommended_concurrency'] > 0:
                    optimizer.implement_concurrency_optimization(
                        rec['function_name'], 
                        rec['recommended_concurrency'], 
                        dry_run=False
                    )
        
        logger.info("Optimization implementation completed")

if __name__ == '__main__':
    main()