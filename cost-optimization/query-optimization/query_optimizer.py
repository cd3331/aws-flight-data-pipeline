#!/usr/bin/env python3

import json
import boto3
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Set
from botocore.exceptions import ClientError
import logging
import argparse
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class QueryMetrics:
    query_id: str
    query_text: str
    execution_time_ms: int
    data_scanned_bytes: int
    data_returned_bytes: int
    cost_usd: float
    query_type: str
    partition_filters: List[str]
    columns_selected: List[str]
    tables_accessed: List[str]

@dataclass
class PartitionAnalysis:
    table_name: str
    partition_columns: List[str]
    total_partitions: int
    partitions_scanned_avg: int
    partition_pruning_efficiency: float
    suggested_partition_filters: List[str]
    cost_reduction_potential: float

@dataclass
class ColumnProjectionAnalysis:
    table_name: str
    total_columns: int
    avg_columns_selected: int
    column_selection_efficiency: float
    unused_columns: List[str]
    cost_reduction_potential: float

@dataclass
class CacheRecommendation:
    query_pattern: str
    frequency: int
    avg_cost_per_execution: float
    cache_strategy: str
    estimated_hit_rate: float
    monthly_savings_potential: float

@dataclass
class QueryOptimizationReport:
    analysis_id: str
    timestamp: str
    queries_analyzed: int
    total_current_cost: float
    partition_optimizations: List[PartitionAnalysis]
    projection_optimizations: List[ColumnProjectionAnalysis]
    cache_recommendations: List[CacheRecommendation]
    estimated_monthly_savings: float
    top_optimization_opportunities: List[Dict[str, Any]]

class QueryOptimizer:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.athena_client = boto3.client('athena', region_name=region)
        self.glue_client = boto3.client('glue', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        
        # Athena pricing per GB scanned
        self.athena_price_per_gb = 5.00
        
        # Common query patterns for optimization
        self.query_patterns = {
            'full_table_scan': r'SELECT.*FROM\s+(\w+)(?!\s+WHERE)',
            'partition_filter': r'WHERE.*(?:year|month|day|date|dt)\s*[=<>]',
            'column_selection': r'SELECT\s+(.*?)\s+FROM',
            'join_query': r'JOIN\s+(\w+)',
            'aggregate_query': r'(?:COUNT|SUM|AVG|MAX|MIN)\s*\(',
            'time_range_query': r'WHERE.*(?:timestamp|date).*BETWEEN'
        }

    def get_recent_queries(self, workgroup: str = 'primary', days: int = 30, max_queries: int = 1000) -> List[QueryMetrics]:
        """Retrieve recent query execution history from Athena."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        queries = []
        next_token = None
        
        try:
            while len(queries) < max_queries:
                params = {
                    'WorkGroup': workgroup,
                    'MaxResults': min(50, max_queries - len(queries))
                }
                
                if next_token:
                    params['NextToken'] = next_token
                
                response = self.athena_client.list_query_executions(**params)
                query_ids = response['QueryExecutionIds']
                
                if not query_ids:
                    break
                
                # Get detailed execution information
                for query_id in query_ids:
                    try:
                        execution = self.athena_client.get_query_execution(QueryExecutionId=query_id)
                        exec_details = execution['QueryExecution']
                        
                        # Filter by time range
                        completion_time = exec_details.get('Status', {}).get('CompletionDateTime')
                        if completion_time and completion_time < start_time:
                            continue
                        
                        # Only include successful queries
                        if exec_details['Status']['State'] != 'SUCCEEDED':
                            continue
                        
                        query_metrics = self._parse_query_execution(exec_details)
                        if query_metrics:
                            queries.append(query_metrics)
                    
                    except ClientError as e:
                        logger.warning(f"Error getting query execution {query_id}: {e}")
                        continue
                
                next_token = response.get('NextToken')
                if not next_token:
                    break
            
            logger.info(f"Retrieved {len(queries)} query executions for analysis")
            return queries
        
        except ClientError as e:
            logger.error(f"Error listing query executions: {e}")
            return []

    def _parse_query_execution(self, execution_details: Dict[str, Any]) -> Optional[QueryMetrics]:
        """Parse Athena query execution details into QueryMetrics."""
        try:
            query_text = execution_details['Query']
            stats = execution_details.get('Statistics', {})
            
            # Extract metrics
            execution_time = stats.get('EngineExecutionTimeInMillis', 0)
            data_scanned = stats.get('DataScannedInBytes', 0)
            data_returned = stats.get('DataProcessedInBytes', 0)
            
            # Calculate cost (Athena charges $5 per TB scanned)
            cost_usd = (data_scanned / (1024**4)) * self.athena_price_per_gb
            
            # Analyze query structure
            query_type = self._classify_query_type(query_text)
            partition_filters = self._extract_partition_filters(query_text)
            columns_selected = self._extract_selected_columns(query_text)
            tables_accessed = self._extract_table_names(query_text)
            
            return QueryMetrics(
                query_id=execution_details['QueryExecutionId'],
                query_text=query_text,
                execution_time_ms=execution_time,
                data_scanned_bytes=data_scanned,
                data_returned_bytes=data_returned,
                cost_usd=cost_usd,
                query_type=query_type,
                partition_filters=partition_filters,
                columns_selected=columns_selected,
                tables_accessed=tables_accessed
            )
        
        except Exception as e:
            logger.warning(f"Error parsing query execution: {e}")
            return None

    def _classify_query_type(self, query_text: str) -> str:
        """Classify the type of query for optimization analysis."""
        query_upper = query_text.upper()
        
        if re.search(self.query_patterns['join_query'], query_upper):
            return 'JOIN'
        elif re.search(self.query_patterns['aggregate_query'], query_upper):
            return 'AGGREGATE'
        elif re.search(self.query_patterns['time_range_query'], query_upper):
            return 'TIME_RANGE'
        elif re.search(self.query_patterns['full_table_scan'], query_upper):
            return 'FULL_SCAN'
        else:
            return 'STANDARD'

    def _extract_partition_filters(self, query_text: str) -> List[str]:
        """Extract partition filter conditions from query."""
        filters = []
        
        # Common partition column patterns
        partition_patterns = [
            r'year\s*[=<>]\s*[\'"]?(\d{4})[\'"]?',
            r'month\s*[=<>]\s*[\'"]?(\d{1,2})[\'"]?',
            r'day\s*[=<>]\s*[\'"]?(\d{1,2})[\'"]?',
            r'dt\s*[=<>]\s*[\'"]?([0-9-]+)[\'"]?',
            r'date\s*[=<>]\s*[\'"]?([0-9-]+)[\'"]?'
        ]
        
        for pattern in partition_patterns:
            matches = re.findall(pattern, query_text, re.IGNORECASE)
            filters.extend(matches)
        
        return filters

    def _extract_selected_columns(self, query_text: str) -> List[str]:
        """Extract selected columns from query."""
        # Find SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query_text, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return []
        
        select_clause = select_match.group(1).strip()
        
        # Handle SELECT *
        if select_clause.strip() == '*':
            return ['*']
        
        # Split columns by comma, handling nested functions
        columns = []
        paren_count = 0
        current_col = ""
        
        for char in select_clause:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == ',' and paren_count == 0:
                columns.append(current_col.strip())
                current_col = ""
                continue
            
            current_col += char
        
        if current_col.strip():
            columns.append(current_col.strip())
        
        # Clean up column names
        cleaned_columns = []
        for col in columns:
            # Remove aliases and extract base column name
            col_clean = re.sub(r'\s+AS\s+\w+', '', col, flags=re.IGNORECASE).strip()
            cleaned_columns.append(col_clean)
        
        return cleaned_columns

    def _extract_table_names(self, query_text: str) -> List[str]:
        """Extract table names from query."""
        tables = []
        
        # FROM clause tables
        from_matches = re.findall(r'FROM\s+([`"]?\w+[`"]?)', query_text, re.IGNORECASE)
        tables.extend([t.strip('`"') for t in from_matches])
        
        # JOIN clause tables  
        join_matches = re.findall(r'JOIN\s+([`"]?\w+[`"]?)', query_text, re.IGNORECASE)
        tables.extend([t.strip('`"') for t in join_matches])
        
        return list(set(tables))

    def analyze_partition_efficiency(self, queries: List[QueryMetrics]) -> List[PartitionAnalysis]:
        """Analyze partition pruning efficiency across queries."""
        table_partition_data = defaultdict(lambda: {
            'queries': [],
            'total_scanned': 0,
            'partition_filters_used': []
        })
        
        # Group queries by table
        for query in queries:
            for table in query.tables_accessed:
                table_partition_data[table]['queries'].append(query)
                table_partition_data[table]['total_scanned'] += query.data_scanned_bytes
                table_partition_data[table]['partition_filters_used'].extend(query.partition_filters)
        
        partition_analyses = []
        
        for table_name, data in table_partition_data.items():
            try:
                # Get table metadata from Glue
                table_info = self._get_table_partition_info(table_name)
                if not table_info:
                    continue
                
                # Calculate partition pruning efficiency
                total_queries = len(data['queries'])
                queries_with_filters = len([q for q in data['queries'] if q.partition_filters])
                
                partition_efficiency = queries_with_filters / total_queries if total_queries > 0 else 0
                
                # Estimate average partitions scanned
                avg_partitions_scanned = self._estimate_partitions_scanned(table_name, data['queries'])
                
                # Suggest partition filters based on query patterns
                suggested_filters = self._suggest_partition_filters(data['queries'])
                
                # Calculate potential cost reduction
                cost_reduction = self._calculate_partition_cost_reduction(
                    data['queries'], partition_efficiency
                )
                
                partition_analyses.append(PartitionAnalysis(
                    table_name=table_name,
                    partition_columns=table_info['partition_columns'],
                    total_partitions=table_info['total_partitions'],
                    partitions_scanned_avg=avg_partitions_scanned,
                    partition_pruning_efficiency=partition_efficiency,
                    suggested_partition_filters=suggested_filters,
                    cost_reduction_potential=cost_reduction
                ))
                
            except Exception as e:
                logger.warning(f"Error analyzing partitions for table {table_name}: {e}")
        
        return partition_analyses

    def _get_table_partition_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get partition information for a table from Glue catalog."""
        try:
            # Get table details
            response = self.glue_client.get_table(
                DatabaseName='default',  # Adjust as needed
                Name=table_name
            )
            
            table = response['Table']
            partition_keys = table.get('PartitionKeys', [])
            partition_columns = [pk['Name'] for pk in partition_keys]
            
            # Get partition count (sample - in production you'd paginate)
            partitions_response = self.glue_client.get_partitions(
                DatabaseName='default',
                TableName=table_name,
                MaxResults=1000
            )
            
            total_partitions = len(partitions_response.get('Partitions', []))
            
            return {
                'partition_columns': partition_columns,
                'total_partitions': total_partitions
            }
        
        except ClientError as e:
            logger.warning(f"Could not get partition info for {table_name}: {e}")
            return None

    def _estimate_partitions_scanned(self, table_name: str, queries: List[QueryMetrics]) -> int:
        """Estimate average number of partitions scanned per query."""
        if not queries:
            return 0
        
        # Simple heuristic: queries with partition filters scan fewer partitions
        queries_with_filters = [q for q in queries if q.partition_filters]
        queries_without_filters = [q for q in queries if not q.partition_filters]
        
        if queries_with_filters and queries_without_filters:
            # Compare data scanned between filtered and unfiltered queries
            avg_scan_filtered = sum(q.data_scanned_bytes for q in queries_with_filters) / len(queries_with_filters)
            avg_scan_unfiltered = sum(q.data_scanned_bytes for q in queries_without_filters) / len(queries_without_filters)
            
            if avg_scan_unfiltered > 0:
                scan_ratio = avg_scan_filtered / avg_scan_unfiltered
                # Estimate partitions based on scan ratio (rough approximation)
                return max(1, int(100 * scan_ratio))  # Assume 100 partitions max
        
        return 50  # Default estimate

    def _suggest_partition_filters(self, queries: List[QueryMetrics]) -> List[str]:
        """Suggest partition filters based on query patterns."""
        suggestions = []
        
        # Analyze common filter patterns
        time_queries = [q for q in queries if 'date' in q.query_text.lower() or 'time' in q.query_text.lower()]
        
        if len(time_queries) / len(queries) > 0.5:  # More than 50% are time-based
            suggestions.append("Add date-based partition filters (year, month, day)")
        
        # Look for other common patterns
        if any('user' in q.query_text.lower() for q in queries):
            suggestions.append("Consider user_id or user_type partition filters")
        
        if any('region' in q.query_text.lower() for q in queries):
            suggestions.append("Consider geographic partition filters (region, country)")
        
        return suggestions

    def _calculate_partition_cost_reduction(self, queries: List[QueryMetrics], current_efficiency: float) -> float:
        """Calculate potential cost reduction from improved partition pruning."""
        total_cost = sum(q.cost_usd for q in queries)
        
        # Assume optimal partition pruning could reduce scanned data by 50-90%
        if current_efficiency < 0.3:  # Poor partition pruning
            potential_reduction = 0.7  # 70% cost reduction possible
        elif current_efficiency < 0.6:  # Moderate partition pruning
            potential_reduction = 0.4  # 40% cost reduction possible
        else:  # Good partition pruning
            potential_reduction = 0.1  # 10% cost reduction possible
        
        return total_cost * potential_reduction

    def analyze_column_projection(self, queries: List[QueryMetrics]) -> List[ColumnProjectionAnalysis]:
        """Analyze column selection efficiency."""
        table_projection_data = defaultdict(lambda: {
            'queries': [],
            'columns_used': set(),
            'select_all_count': 0
        })
        
        # Group by table and analyze column usage
        for query in queries:
            for table in query.tables_accessed:
                table_projection_data[table]['queries'].append(query)
                
                if '*' in query.columns_selected:
                    table_projection_data[table]['select_all_count'] += 1
                else:
                    table_projection_data[table]['columns_used'].update(query.columns_selected)
        
        projection_analyses = []
        
        for table_name, data in table_projection_data.items():
            try:
                # Get table schema
                table_info = self._get_table_schema(table_name)
                if not table_info:
                    continue
                
                total_columns = len(table_info['columns'])
                avg_columns_selected = len(data['columns_used'])
                select_all_queries = data['select_all_count']
                
                # Calculate selection efficiency
                if select_all_queries > 0:
                    # Penalize SELECT * queries
                    selection_efficiency = max(0, 1 - (select_all_queries / len(data['queries'])))
                else:
                    selection_efficiency = min(1, avg_columns_selected / total_columns)
                
                # Identify unused columns
                all_columns = set(table_info['columns'])
                unused_columns = list(all_columns - data['columns_used'])
                
                # Calculate cost reduction potential
                cost_reduction = self._calculate_projection_cost_reduction(
                    data['queries'], selection_efficiency, total_columns, avg_columns_selected
                )
                
                projection_analyses.append(ColumnProjectionAnalysis(
                    table_name=table_name,
                    total_columns=total_columns,
                    avg_columns_selected=avg_columns_selected,
                    column_selection_efficiency=selection_efficiency,
                    unused_columns=unused_columns[:10],  # Top 10 unused
                    cost_reduction_potential=cost_reduction
                ))
                
            except Exception as e:
                logger.warning(f"Error analyzing projections for table {table_name}: {e}")
        
        return projection_analyses

    def _get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get table schema from Glue catalog."""
        try:
            response = self.glue_client.get_table(
                DatabaseName='default',
                Name=table_name
            )
            
            table = response['Table']
            columns = [col['Name'] for col in table['StorageDescriptor']['Columns']]
            
            return {'columns': columns}
        
        except ClientError as e:
            logger.warning(f"Could not get schema for {table_name}: {e}")
            return None

    def _calculate_projection_cost_reduction(self, queries: List[QueryMetrics], 
                                           efficiency: float, total_cols: int, avg_cols: int) -> float:
        """Calculate potential cost reduction from better column projection."""
        total_cost = sum(q.cost_usd for q in queries)
        
        if avg_cols == 0:  # SELECT * queries
            # Assume 80% cost reduction possible with proper column selection
            potential_reduction = 0.8
        else:
            # Cost reduction proportional to unused columns
            unused_ratio = (total_cols - avg_cols) / total_cols
            potential_reduction = unused_ratio * 0.5  # Up to 50% reduction
        
        return total_cost * potential_reduction

    def analyze_caching_opportunities(self, queries: List[QueryMetrics]) -> List[CacheRecommendation]:
        """Identify queries that would benefit from result caching."""
        # Group similar queries
        query_patterns = defaultdict(list)
        
        for query in queries:
            # Normalize query for pattern matching
            normalized = self._normalize_query_for_caching(query.query_text)
            query_patterns[normalized].append(query)
        
        cache_recommendations = []
        
        for pattern, pattern_queries in query_patterns.items():
            if len(pattern_queries) < 2:  # Skip unique queries
                continue
            
            # Calculate metrics for this pattern
            frequency = len(pattern_queries)
            avg_cost = sum(q.cost_usd for q in pattern_queries) / frequency
            total_cost = sum(q.cost_usd for q in pattern_queries)
            
            # Estimate cache hit rate based on query frequency and timing
            cache_hit_rate = self._estimate_cache_hit_rate(pattern_queries)
            
            # Determine caching strategy
            cache_strategy = self._recommend_cache_strategy(pattern_queries)
            
            # Calculate potential savings
            monthly_savings = total_cost * cache_hit_rate * 4  # Estimate monthly from weekly data
            
            if monthly_savings > 10:  # Only recommend if savings > $10/month
                cache_recommendations.append(CacheRecommendation(
                    query_pattern=pattern,
                    frequency=frequency,
                    avg_cost_per_execution=avg_cost,
                    cache_strategy=cache_strategy,
                    estimated_hit_rate=cache_hit_rate,
                    monthly_savings_potential=monthly_savings
                ))
        
        # Sort by savings potential
        cache_recommendations.sort(key=lambda x: x.monthly_savings_potential, reverse=True)
        
        return cache_recommendations

    def _normalize_query_for_caching(self, query_text: str) -> str:
        """Normalize query text to identify cacheable patterns."""
        # Remove specific values but keep structure
        normalized = query_text.upper()
        
        # Replace specific dates with placeholders
        normalized = re.sub(r"'[0-9-]+'\s*", "'DATE'", normalized)
        normalized = re.sub(r'"[0-9-]+"', '"DATE"', normalized)
        
        # Replace specific numbers with placeholders
        normalized = re.sub(r'\b\d+\b', 'NUM', normalized)
        
        # Replace specific strings with placeholders
        normalized = re.sub(r"'[^']*'", "'STRING'", normalized)
        normalized = re.sub(r'"[^"]*"', '"STRING"', normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _estimate_cache_hit_rate(self, queries: List[QueryMetrics]) -> float:
        """Estimate cache hit rate based on query timing patterns."""
        if len(queries) < 2:
            return 0.0
        
        # Simple heuristic: more frequent queries have higher cache hit rates
        frequency = len(queries)
        
        if frequency >= 10:
            return 0.8  # High frequency queries
        elif frequency >= 5:
            return 0.6  # Medium frequency queries
        else:
            return 0.4  # Low frequency queries

    def _recommend_cache_strategy(self, queries: List[QueryMetrics]) -> str:
        """Recommend appropriate caching strategy."""
        avg_cost = sum(q.cost_usd for q in queries) / len(queries)
        avg_execution_time = sum(q.execution_time_ms for q in queries) / len(queries)
        
        if avg_cost > 10:
            return "Redis with TTL based on data freshness requirements"
        elif avg_execution_time > 60000:  # > 1 minute
            return "ElastiCache with 24-hour TTL"
        else:
            return "Application-level caching with 1-hour TTL"

    def generate_optimization_report(self, workgroup: str = 'primary', days: int = 30) -> QueryOptimizationReport:
        """Generate comprehensive query optimization report."""
        logger.info("Starting query optimization analysis...")
        
        # Get recent queries
        queries = self.get_recent_queries(workgroup, days)
        if not queries:
            logger.error("No queries found for analysis")
            return None
        
        # Calculate total current cost
        total_cost = sum(q.cost_usd for q in queries)
        
        # Analyze optimization opportunities
        partition_optimizations = self.analyze_partition_efficiency(queries)
        projection_optimizations = self.analyze_column_projection(queries)
        cache_recommendations = self.analyze_caching_opportunities(queries)
        
        # Calculate total potential savings
        partition_savings = sum(p.cost_reduction_potential for p in partition_optimizations)
        projection_savings = sum(p.cost_reduction_potential for p in projection_optimizations)
        cache_savings = sum(c.monthly_savings_potential for c in cache_recommendations)
        
        total_savings = partition_savings + projection_savings + (cache_savings / 4)  # Convert monthly to weekly
        
        # Identify top optimization opportunities
        top_opportunities = self._identify_top_opportunities(
            partition_optimizations, projection_optimizations, cache_recommendations
        )
        
        report = QueryOptimizationReport(
            analysis_id=f"query-optimization-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            queries_analyzed=len(queries),
            total_current_cost=total_cost,
            partition_optimizations=partition_optimizations,
            projection_optimizations=projection_optimizations,
            cache_recommendations=cache_recommendations,
            estimated_monthly_savings=total_savings * 4,  # Scale to monthly
            top_optimization_opportunities=top_opportunities
        )
        
        logger.info("Query optimization analysis completed")
        return report

    def _identify_top_opportunities(self, partition_opts: List[PartitionAnalysis],
                                  projection_opts: List[ColumnProjectionAnalysis],
                                  cache_opts: List[CacheRecommendation]) -> List[Dict[str, Any]]:
        """Identify the highest-impact optimization opportunities."""
        opportunities = []
        
        # Partition optimization opportunities
        for opt in sorted(partition_opts, key=lambda x: x.cost_reduction_potential, reverse=True)[:5]:
            opportunities.append({
                'type': 'partition_pruning',
                'table': opt.table_name,
                'savings_potential': opt.cost_reduction_potential,
                'priority': 'high' if opt.cost_reduction_potential > 100 else 'medium',
                'description': f"Improve partition pruning efficiency from {opt.partition_pruning_efficiency:.1%} for table {opt.table_name}",
                'implementation': opt.suggested_partition_filters
            })
        
        # Projection optimization opportunities
        for opt in sorted(projection_opts, key=lambda x: x.cost_reduction_potential, reverse=True)[:5]:
            if opt.column_selection_efficiency < 0.5:  # Low efficiency
                opportunities.append({
                    'type': 'column_projection',
                    'table': opt.table_name,
                    'savings_potential': opt.cost_reduction_potential,
                    'priority': 'high' if opt.cost_reduction_potential > 50 else 'medium',
                    'description': f"Improve column selection for table {opt.table_name} (currently {opt.avg_columns_selected}/{opt.total_columns} columns)",
                    'implementation': f"Remove SELECT * queries, focus on specific columns"
                })
        
        # Caching opportunities
        for opt in sorted(cache_opts, key=lambda x: x.monthly_savings_potential, reverse=True)[:3]:
            opportunities.append({
                'type': 'result_caching',
                'pattern': opt.query_pattern[:100] + "..." if len(opt.query_pattern) > 100 else opt.query_pattern,
                'savings_potential': opt.monthly_savings_potential,
                'priority': 'high' if opt.monthly_savings_potential > 100 else 'medium',
                'description': f"Cache frequently executed query pattern ({opt.frequency} executions)",
                'implementation': opt.cache_strategy
            })
        
        # Sort all opportunities by savings potential
        opportunities.sort(key=lambda x: x['savings_potential'], reverse=True)
        
        return opportunities[:10]  # Top 10 opportunities

def main():
    parser = argparse.ArgumentParser(description='Athena Query Optimizer')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--workgroup', default='primary', help='Athena workgroup')
    parser.add_argument('--days', type=int, default=30, help='Days of query history to analyze')
    parser.add_argument('--max-queries', type=int, default=1000, help='Maximum queries to analyze')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--table-filter', help='Filter analysis to specific tables')
    
    args = parser.parse_args()
    
    optimizer = QueryOptimizer(region=args.region)
    
    # Generate optimization report
    report = optimizer.generate_optimization_report(
        workgroup=args.workgroup,
        days=args.days
    )
    
    if not report:
        logger.error("Failed to generate optimization report")
        return
    
    # Convert report to dict for JSON serialization
    report_dict = asdict(report)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report_dict, f, indent=2)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(report_dict, indent=2))
    
    # Summary output
    print(f"\n=== QUERY OPTIMIZATION SUMMARY ===")
    print(f"Queries Analyzed: {report.queries_analyzed}")
    print(f"Current Monthly Cost: ${report.total_current_cost * 4:.2f}")
    print(f"Estimated Monthly Savings: ${report.estimated_monthly_savings:.2f}")
    print(f"Optimization Opportunities: {len(report.top_optimization_opportunities)}")
    
    print(f"\nTop Optimization Opportunities:")
    for i, opp in enumerate(report.top_optimization_opportunities[:5], 1):
        print(f"{i}. {opp['type'].upper()}: ${opp['savings_potential']:.2f} savings - {opp['description']}")

if __name__ == '__main__':
    main()