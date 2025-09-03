#!/usr/bin/env python3
"""
S3 Lifecycle Optimization Tool
Analyzes access patterns, recommends storage classes, implements intelligent tiering
"""

import boto3
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import argparse
from dataclasses import dataclass
from enum import Enum
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StorageClass(Enum):
    """S3 Storage Classes."""
    STANDARD = "STANDARD"
    STANDARD_IA = "STANDARD_IA"
    ONEZONE_IA = "ONEZONE_IA"
    GLACIER = "GLACIER"
    GLACIER_IR = "GLACIER_IR"
    DEEP_ARCHIVE = "DEEP_ARCHIVE"
    INTELLIGENT_TIERING = "INTELLIGENT_TIERING"

@dataclass
class S3CostAnalysis:
    """S3 cost analysis results."""
    bucket_name: str
    current_storage_gb: float
    current_monthly_cost: float
    recommended_storage_class: StorageClass
    projected_monthly_cost: float
    monthly_savings: float
    annual_savings: float
    breakeven_months: float
    access_pattern: str
    recommendation_confidence: float

@dataclass
class AccessPattern:
    """Object access pattern analysis."""
    object_key: str
    size_gb: float
    last_accessed: datetime
    access_frequency: int
    storage_class: StorageClass
    age_days: int
    retrieval_pattern: str

class S3LifecycleOptimizer:
    """S3 lifecycle optimization and cost analysis tool."""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.cost_explorer = boto3.client('ce', region_name='us-east-1')  # Cost Explorer is only in us-east-1
        
        # S3 Pricing (as of 2024, simplified)
        self.storage_pricing = {
            StorageClass.STANDARD: 0.023,  # per GB/month
            StorageClass.STANDARD_IA: 0.0125,
            StorageClass.ONEZONE_IA: 0.01,
            StorageClass.GLACIER: 0.004,
            StorageClass.GLACIER_IR: 0.0036,
            StorageClass.DEEP_ARCHIVE: 0.00099,
            StorageClass.INTELLIGENT_TIERING: 0.0225  # Standard tier pricing
        }
        
        # Retrieval costs (per GB)
        self.retrieval_pricing = {
            StorageClass.STANDARD: 0.0,
            StorageClass.STANDARD_IA: 0.01,
            StorageClass.ONEZONE_IA: 0.01,
            StorageClass.GLACIER: 0.01,
            StorageClass.GLACIER_IR: 0.003,
            StorageClass.DEEP_ARCHIVE: 0.02,
            StorageClass.INTELLIGENT_TIERING: 0.0
        }
        
        # Minimum storage duration (days)
        self.minimum_duration = {
            StorageClass.STANDARD: 0,
            StorageClass.STANDARD_IA: 30,
            StorageClass.ONEZONE_IA: 30,
            StorageClass.GLACIER: 90,
            StorageClass.GLACIER_IR: 90,
            StorageClass.DEEP_ARCHIVE: 180,
            StorageClass.INTELLIGENT_TIERING: 0
        }
    
    def analyze_all_buckets(self, bucket_prefix: str = None) -> Dict[str, Any]:
        """Analyze all S3 buckets for optimization opportunities."""
        logger.info("Starting comprehensive S3 lifecycle analysis")
        
        analysis_results = {
            'analysis_id': f"s3-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'region': self.region,
            'buckets_analyzed': 0,
            'total_current_cost': 0.0,
            'total_projected_cost': 0.0,
            'total_monthly_savings': 0.0,
            'total_annual_savings': 0.0,
            'bucket_analyses': [],
            'lifecycle_recommendations': [],
            'intelligent_tiering_recommendations': [],
            'summary': {}
        }
        
        try:
            buckets = self.s3_client.list_buckets()['Buckets']
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                
                # Filter by prefix if specified
                if bucket_prefix and not bucket_name.startswith(bucket_prefix):
                    continue
                
                logger.info(f"Analyzing bucket: {bucket_name}")
                
                try:
                    bucket_analysis = self.analyze_bucket(bucket_name)
                    analysis_results['bucket_analyses'].append(bucket_analysis)
                    analysis_results['buckets_analyzed'] += 1
                    analysis_results['total_current_cost'] += bucket_analysis.current_monthly_cost
                    analysis_results['total_projected_cost'] += bucket_analysis.projected_monthly_cost
                    analysis_results['total_monthly_savings'] += bucket_analysis.monthly_savings
                    analysis_results['total_annual_savings'] += bucket_analysis.annual_savings
                    
                    # Generate lifecycle policy recommendations
                    lifecycle_policy = self.generate_lifecycle_policy(bucket_name)
                    if lifecycle_policy:
                        analysis_results['lifecycle_recommendations'].append({
                            'bucket_name': bucket_name,
                            'policy': lifecycle_policy
                        })
                    
                    # Check intelligent tiering eligibility
                    it_recommendation = self.analyze_intelligent_tiering_eligibility(bucket_name)
                    if it_recommendation['recommended']:
                        analysis_results['intelligent_tiering_recommendations'].append(it_recommendation)
                
                except Exception as e:
                    logger.error(f"Error analyzing bucket {bucket_name}: {e}")
                    continue
            
            # Generate summary
            analysis_results['summary'] = self._generate_analysis_summary(analysis_results)
            
        except Exception as e:
            logger.error(f"Error in bucket analysis: {e}")
            analysis_results['error'] = str(e)
        
        return analysis_results
    
    def analyze_bucket(self, bucket_name: str) -> S3CostAnalysis:
        """Analyze a single bucket for optimization opportunities."""
        logger.info(f"Analyzing bucket: {bucket_name}")
        
        # Get bucket inventory and access patterns
        access_patterns = self.analyze_access_patterns(bucket_name)
        current_storage_info = self.get_bucket_storage_info(bucket_name)
        
        # Calculate current costs
        current_cost = self.calculate_current_storage_cost(current_storage_info)
        
        # Determine optimal storage class based on access patterns
        optimization_recommendation = self.recommend_storage_optimization(access_patterns, current_storage_info)
        
        # Calculate projected costs and savings
        projected_cost = self.calculate_projected_cost(
            current_storage_info,
            optimization_recommendation['recommended_class'],
            access_patterns
        )
        
        monthly_savings = max(0, current_cost - projected_cost)
        annual_savings = monthly_savings * 12
        
        # Calculate break-even period
        breakeven_months = self.calculate_breakeven_period(
            current_storage_info,
            optimization_recommendation['recommended_class'],
            monthly_savings
        )
        
        return S3CostAnalysis(
            bucket_name=bucket_name,
            current_storage_gb=current_storage_info.get('total_size_gb', 0),
            current_monthly_cost=current_cost,
            recommended_storage_class=optimization_recommendation['recommended_class'],
            projected_monthly_cost=projected_cost,
            monthly_savings=monthly_savings,
            annual_savings=annual_savings,
            breakeven_months=breakeven_months,
            access_pattern=optimization_recommendation['access_pattern'],
            recommendation_confidence=optimization_recommendation['confidence']
        )
    
    def analyze_access_patterns(self, bucket_name: str) -> List[AccessPattern]:
        """Analyze object access patterns in a bucket."""
        logger.info(f"Analyzing access patterns for bucket: {bucket_name}")
        
        access_patterns = []
        
        try:
            # Get CloudWatch metrics for S3 requests
            end_time = datetime.now()
            start_time = end_time - timedelta(days=90)  # Analyze last 90 days
            
            # Get bucket-level metrics
            bucket_requests = self._get_bucket_request_metrics(bucket_name, start_time, end_time)
            
            # List objects in bucket (sample for large buckets)
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            object_count = 0
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    object_count += 1
                    
                    # Limit analysis to first 1000 objects for large buckets
                    if object_count > 1000:
                        break
                    
                    # Analyze individual object
                    try:
                        obj_metadata = self.s3_client.head_object(Bucket=bucket_name, Key=obj['Key'])
                        
                        # Get last access time (approximated from last modified)
                        last_accessed = obj.get('LastModified', datetime.now())
                        age_days = (datetime.now(last_accessed.tzinfo) - last_accessed).days
                        
                        # Estimate access frequency based on age and bucket metrics
                        access_frequency = self._estimate_access_frequency(
                            obj['Key'], 
                            age_days, 
                            bucket_requests
                        )
                        
                        # Determine retrieval pattern
                        retrieval_pattern = self._classify_retrieval_pattern(access_frequency, age_days)
                        
                        access_pattern = AccessPattern(
                            object_key=obj['Key'],
                            size_gb=obj['Size'] / (1024**3),  # Convert to GB
                            last_accessed=last_accessed,
                            access_frequency=access_frequency,
                            storage_class=StorageClass(obj_metadata.get('StorageClass', 'STANDARD')),
                            age_days=age_days,
                            retrieval_pattern=retrieval_pattern
                        )
                        
                        access_patterns.append(access_pattern)
                        
                    except Exception as e:
                        logger.warning(f"Error analyzing object {obj['Key']}: {e}")
                        continue
                
                if object_count > 1000:
                    break
            
        except Exception as e:
            logger.error(f"Error analyzing access patterns: {e}")
        
        return access_patterns
    
    def get_bucket_storage_info(self, bucket_name: str) -> Dict[str, Any]:
        """Get detailed bucket storage information."""
        try:
            # Get bucket size from CloudWatch
            end_time = datetime.now()
            start_time = end_time - timedelta(days=2)  # Recent data
            
            size_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily
                Statistics=['Average']
            )
            
            # Get object count
            count_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            
            total_size_bytes = 0
            object_count = 0
            
            if size_response['Datapoints']:
                total_size_bytes = size_response['Datapoints'][-1]['Average']
            
            if count_response['Datapoints']:
                object_count = int(count_response['Datapoints'][-1]['Average'])
            
            return {
                'total_size_bytes': total_size_bytes,
                'total_size_gb': total_size_bytes / (1024**3),
                'object_count': object_count,
                'average_object_size_mb': (total_size_bytes / (1024**2)) / max(1, object_count)
            }
            
        except Exception as e:
            logger.error(f"Error getting bucket storage info: {e}")
            return {
                'total_size_bytes': 0,
                'total_size_gb': 0,
                'object_count': 0,
                'average_object_size_mb': 0
            }
    
    def calculate_current_storage_cost(self, storage_info: Dict[str, Any]) -> float:
        """Calculate current monthly storage cost."""
        size_gb = storage_info.get('total_size_gb', 0)
        # Assume Standard storage class if not specified
        return size_gb * self.storage_pricing[StorageClass.STANDARD]
    
    def recommend_storage_optimization(self, access_patterns: List[AccessPattern], 
                                     storage_info: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend optimal storage class based on access patterns."""
        if not access_patterns:
            return {
                'recommended_class': StorageClass.STANDARD,
                'access_pattern': 'unknown',
                'confidence': 0.0
            }
        
        # Analyze access patterns
        total_objects = len(access_patterns)
        frequently_accessed = sum(1 for p in access_patterns if p.access_frequency > 10)  # >10 accesses in 90 days
        infrequently_accessed = sum(1 for p in access_patterns if p.access_frequency <= 1)  # <=1 access in 90 days
        old_objects = sum(1 for p in access_patterns if p.age_days > 90)
        very_old_objects = sum(1 for p in access_patterns if p.age_days > 365)
        
        # Calculate percentages
        frequently_accessed_pct = frequently_accessed / total_objects
        infrequently_accessed_pct = infrequently_accessed / total_objects
        old_objects_pct = old_objects / total_objects
        very_old_objects_pct = very_old_objects / total_objects
        
        # Determine access pattern and recommendation
        if frequently_accessed_pct > 0.7:
            access_pattern = "frequent"
            recommended_class = StorageClass.STANDARD
            confidence = 0.9
        elif infrequently_accessed_pct > 0.6 and old_objects_pct > 0.5:
            if very_old_objects_pct > 0.3:
                access_pattern = "archive"
                recommended_class = StorageClass.GLACIER
                confidence = 0.8
            else:
                access_pattern = "infrequent"
                recommended_class = StorageClass.STANDARD_IA
                confidence = 0.85
        elif very_old_objects_pct > 0.8:
            access_pattern = "deep_archive"
            recommended_class = StorageClass.DEEP_ARCHIVE
            confidence = 0.9
        else:
            # Mixed access pattern - recommend Intelligent Tiering
            access_pattern = "mixed"
            recommended_class = StorageClass.INTELLIGENT_TIERING
            confidence = 0.7
        
        return {
            'recommended_class': recommended_class,
            'access_pattern': access_pattern,
            'confidence': confidence,
            'analysis': {
                'frequently_accessed_pct': frequently_accessed_pct,
                'infrequently_accessed_pct': infrequently_accessed_pct,
                'old_objects_pct': old_objects_pct,
                'very_old_objects_pct': very_old_objects_pct
            }
        }
    
    def calculate_projected_cost(self, storage_info: Dict[str, Any], 
                               recommended_class: StorageClass, 
                               access_patterns: List[AccessPattern]) -> float:
        """Calculate projected monthly cost with recommended storage class."""
        size_gb = storage_info.get('total_size_gb', 0)
        
        # Base storage cost
        storage_cost = size_gb * self.storage_pricing[recommended_class]
        
        # Add retrieval costs based on access patterns
        retrieval_cost = 0.0
        if access_patterns:
            # Estimate monthly retrievals based on access frequency
            total_retrieval_gb = 0
            for pattern in access_patterns:
                monthly_accesses = pattern.access_frequency / 3  # 90 days to monthly
                total_retrieval_gb += pattern.size_gb * monthly_accesses
            
            retrieval_cost = total_retrieval_gb * self.retrieval_pricing[recommended_class]
        
        # Add intelligent tiering monitoring costs
        if recommended_class == StorageClass.INTELLIGENT_TIERING:
            object_count = storage_info.get('object_count', 0)
            # $0.0025 per 1,000 objects monitored
            monitoring_cost = (object_count / 1000) * 0.0025
            return storage_cost + retrieval_cost + monitoring_cost
        
        return storage_cost + retrieval_cost
    
    def calculate_breakeven_period(self, storage_info: Dict[str, Any], 
                                 recommended_class: StorageClass, 
                                 monthly_savings: float) -> float:
        """Calculate break-even period in months for storage class change."""
        if monthly_savings <= 0:
            return float('inf')
        
        # Transition costs (simplified)
        size_gb = storage_info.get('total_size_gb', 0)
        
        # PUT request costs for transitioning objects
        object_count = storage_info.get('object_count', 0)
        put_request_cost = (object_count / 1000) * 0.005  # $0.005 per 1,000 PUT requests
        
        # Data retrieval cost if moving from Glacier/Deep Archive
        retrieval_cost = 0.0  # Assume no retrieval needed for transition
        
        total_transition_cost = put_request_cost + retrieval_cost
        
        return total_transition_cost / monthly_savings if monthly_savings > 0 else float('inf')
    
    def generate_lifecycle_policy(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Generate lifecycle policy recommendations for a bucket."""
        try:
            access_patterns = self.analyze_access_patterns(bucket_name)
            
            if not access_patterns:
                return None
            
            # Analyze age patterns to create lifecycle rules
            age_analysis = self._analyze_object_ages(access_patterns)
            
            lifecycle_policy = {
                "Rules": []
            }
            
            # Rule 1: Transition to IA after 30 days if infrequently accessed
            if age_analysis['avg_age_days'] > 30:
                lifecycle_policy["Rules"].append({
                    "ID": "TransitionToIA",
                    "Status": "Enabled",
                    "Transitions": [
                        {
                            "Days": 30,
                            "StorageClass": "STANDARD_IA"
                        }
                    ]
                })
            
            # Rule 2: Transition to Glacier after 90 days
            if age_analysis['old_objects_pct'] > 0.3:
                lifecycle_policy["Rules"].append({
                    "ID": "TransitionToGlacier",
                    "Status": "Enabled",
                    "Transitions": [
                        {
                            "Days": 90,
                            "StorageClass": "GLACIER"
                        }
                    ]
                })
            
            # Rule 3: Transition to Deep Archive after 365 days
            if age_analysis['very_old_objects_pct'] > 0.2:
                lifecycle_policy["Rules"].append({
                    "ID": "TransitionToDeepArchive",
                    "Status": "Enabled",
                    "Transitions": [
                        {
                            "Days": 365,
                            "StorageClass": "DEEP_ARCHIVE"
                        }
                    ]
                })
            
            # Rule 4: Delete objects after 7 years (adjust based on requirements)
            lifecycle_policy["Rules"].append({
                "ID": "DeleteOldObjects",
                "Status": "Enabled",
                "Expiration": {
                    "Days": 2555  # 7 years
                }
            })
            
            return lifecycle_policy if lifecycle_policy["Rules"] else None
            
        except Exception as e:
            logger.error(f"Error generating lifecycle policy: {e}")
            return None
    
    def analyze_intelligent_tiering_eligibility(self, bucket_name: str) -> Dict[str, Any]:
        """Analyze if bucket is eligible for Intelligent Tiering."""
        try:
            storage_info = self.get_bucket_storage_info(bucket_name)
            access_patterns = self.analyze_access_patterns(bucket_name)
            
            # Calculate potential savings with Intelligent Tiering
            current_cost = self.calculate_current_storage_cost(storage_info)
            it_cost = self.calculate_projected_cost(storage_info, StorageClass.INTELLIGENT_TIERING, access_patterns)
            
            monthly_savings = max(0, current_cost - it_cost)
            annual_savings = monthly_savings * 12
            
            # Eligibility criteria
            size_gb = storage_info.get('total_size_gb', 0)
            object_count = storage_info.get('object_count', 0)
            
            # Intelligent Tiering is cost-effective for:
            # - Buckets > 1GB
            # - Mixed access patterns
            # - Objects > 128KB (monitoring cost efficiency)
            
            avg_object_size_mb = storage_info.get('average_object_size_mb', 0)
            
            eligible = (
                size_gb > 1.0 and  # Minimum size
                object_count > 0 and
                avg_object_size_mb > 0.128 and  # 128KB minimum for cost efficiency
                monthly_savings > 1.0  # Minimum $1/month savings
            )
            
            confidence = 0.8 if eligible else 0.3
            
            # Analyze access pattern variability
            if access_patterns:
                access_frequencies = [p.access_frequency for p in access_patterns]
                access_variability = np.std(access_frequencies) if len(access_frequencies) > 1 else 0
                
                # Higher variability = better candidate for IT
                if access_variability > 5:
                    confidence = min(0.95, confidence + 0.15)
            
            return {
                'bucket_name': bucket_name,
                'recommended': eligible,
                'confidence': confidence,
                'monthly_savings': monthly_savings,
                'annual_savings': annual_savings,
                'current_monthly_cost': current_cost,
                'projected_monthly_cost': it_cost,
                'eligibility_factors': {
                    'size_gb': size_gb,
                    'object_count': object_count,
                    'avg_object_size_mb': avg_object_size_mb,
                    'access_variability': access_variability if access_patterns else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing IT eligibility: {e}")
            return {
                'bucket_name': bucket_name,
                'recommended': False,
                'error': str(e)
            }
    
    def implement_lifecycle_policy(self, bucket_name: str, policy: Dict[str, Any]) -> bool:
        """Implement lifecycle policy on a bucket."""
        try:
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=policy
            )
            logger.info(f"Successfully implemented lifecycle policy for bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error implementing lifecycle policy for {bucket_name}: {e}")
            return False
    
    def enable_intelligent_tiering(self, bucket_name: str, prefix: str = None) -> bool:
        """Enable Intelligent Tiering for a bucket or prefix."""
        try:
            configuration_id = f"intelligent-tiering-{datetime.now().strftime('%Y%m%d')}"
            
            config = {
                'Id': configuration_id,
                'Status': 'Enabled',
                'OptionalFields': ['BucketKeyStatus'],
                'Tiering': {
                    'Days': 90,
                    'AccessTier': 'ARCHIVE_ACCESS'
                }
            }
            
            if prefix:
                config['Filter'] = {'Prefix': prefix}
            
            self.s3_client.put_bucket_intelligent_tiering_configuration(
                Bucket=bucket_name,
                Id=configuration_id,
                IntelligentTieringConfiguration=config
            )
            
            logger.info(f"Successfully enabled Intelligent Tiering for bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling Intelligent Tiering for {bucket_name}: {e}")
            return False
    
    def _get_bucket_request_metrics(self, bucket_name: str, start_time: datetime, end_time: datetime) -> Dict[str, int]:
        """Get request metrics for a bucket."""
        try:
            get_requests = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[{'Name': 'BucketName', 'Value': bucket_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )
            
            total_requests = sum(dp.get('Sum', 0) for dp in get_requests['Datapoints'])
            
            return {
                'total_requests': int(total_requests),
                'daily_avg_requests': int(total_requests / 90)  # 90 days
            }
            
        except Exception as e:
            logger.warning(f"Error getting request metrics: {e}")
            return {'total_requests': 0, 'daily_avg_requests': 0}
    
    def _estimate_access_frequency(self, object_key: str, age_days: int, bucket_requests: Dict[str, int]) -> int:
        """Estimate access frequency for an object."""
        # Simple estimation based on bucket-level metrics and object age
        daily_avg_requests = bucket_requests.get('daily_avg_requests', 0)
        
        # Assume newer objects are accessed more frequently
        age_factor = max(0.1, 1.0 - (age_days / 365.0))  # Newer objects get higher factor
        
        # Estimate this object's share of requests
        estimated_daily_accesses = daily_avg_requests * age_factor * 0.001  # Small fraction per object
        
        # Convert to 90-day frequency
        return max(0, int(estimated_daily_accesses * 90))
    
    def _classify_retrieval_pattern(self, access_frequency: int, age_days: int) -> str:
        """Classify retrieval pattern based on access frequency and age."""
        if access_frequency > 10:  # More than 10 accesses in 90 days
            return "frequent"
        elif access_frequency > 1:  # 2-10 accesses in 90 days
            return "occasional"
        elif age_days < 30:
            return "recent_inactive"
        else:
            return "archive_candidate"
    
    def _analyze_object_ages(self, access_patterns: List[AccessPattern]) -> Dict[str, float]:
        """Analyze age distribution of objects."""
        if not access_patterns:
            return {
                'avg_age_days': 0,
                'old_objects_pct': 0,
                'very_old_objects_pct': 0
            }
        
        ages = [p.age_days for p in access_patterns]
        old_objects = sum(1 for age in ages if age > 90)
        very_old_objects = sum(1 for age in ages if age > 365)
        
        return {
            'avg_age_days': np.mean(ages),
            'old_objects_pct': old_objects / len(access_patterns),
            'very_old_objects_pct': very_old_objects / len(access_patterns)
        }
    
    def _generate_analysis_summary(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of analysis results."""
        total_savings = analysis_results['total_annual_savings']
        
        # Calculate ROI
        implementation_cost = len(analysis_results['bucket_analyses']) * 50  # Estimated $50 per bucket to implement
        roi_percentage = (total_savings / max(implementation_cost, 1)) * 100
        
        return {
            'optimization_opportunities': len([b for b in analysis_results['bucket_analyses'] if b.monthly_savings > 0]),
            'total_annual_savings': total_savings,
            'estimated_roi_percentage': roi_percentage,
            'payback_period_months': implementation_cost / max(analysis_results['total_monthly_savings'], 1),
            'intelligent_tiering_candidates': len(analysis_results['intelligent_tiering_recommendations']),
            'lifecycle_policies_recommended': len(analysis_results['lifecycle_recommendations'])
        }
    
    def export_analysis_results(self, results: Dict[str, Any], output_file: str) -> None:
        """Export analysis results to JSON file."""
        # Convert custom objects to dictionaries for JSON serialization
        serializable_results = self._make_serializable(results)
        
        with open(output_file, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        logger.info(f"Analysis results exported to {output_file}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """Make objects JSON serializable."""
        if isinstance(obj, S3CostAnalysis):
            return {
                'bucket_name': obj.bucket_name,
                'current_storage_gb': obj.current_storage_gb,
                'current_monthly_cost': obj.current_monthly_cost,
                'recommended_storage_class': obj.recommended_storage_class.value,
                'projected_monthly_cost': obj.projected_monthly_cost,
                'monthly_savings': obj.monthly_savings,
                'annual_savings': obj.annual_savings,
                'breakeven_months': obj.breakeven_months,
                'access_pattern': obj.access_pattern,
                'recommendation_confidence': obj.recommendation_confidence
            }
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, StorageClass):
            return obj.value
        else:
            return obj

def main():
    """Command-line interface for S3 lifecycle optimizer."""
    parser = argparse.ArgumentParser(description='S3 Lifecycle Optimizer and Cost Analyzer')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--bucket-prefix', help='Analyze only buckets with this prefix')
    parser.add_argument('--bucket', help='Analyze specific bucket')
    parser.add_argument('--output', default='s3-optimization-analysis.json', help='Output file')
    parser.add_argument('--implement', action='store_true', help='Implement recommended policies')
    parser.add_argument('--enable-intelligent-tiering', action='store_true', help='Enable Intelligent Tiering where recommended')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize optimizer
    optimizer = S3LifecycleOptimizer(region=args.region)
    
    # Run analysis
    if args.bucket:
        # Analyze single bucket
        bucket_analysis = optimizer.analyze_bucket(args.bucket)
        results = {
            'analysis_id': f"s3-single-bucket-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'bucket_analyses': [bucket_analysis],
            'total_annual_savings': bucket_analysis.annual_savings
        }
    else:
        # Analyze all buckets
        results = optimizer.analyze_all_buckets(bucket_prefix=args.bucket_prefix)
    
    # Print summary
    print("\n" + "="*60)
    print("S3 LIFECYCLE OPTIMIZATION ANALYSIS")
    print("="*60)
    print(f"Analysis Timestamp: {results['timestamp']}")
    print(f"Buckets Analyzed: {results.get('buckets_analyzed', 1)}")
    print(f"Total Current Monthly Cost: ${results.get('total_current_cost', 0):.2f}")
    print(f"Total Projected Monthly Cost: ${results.get('total_projected_cost', 0):.2f}")
    print(f"Total Monthly Savings: ${results.get('total_monthly_savings', 0):.2f}")
    print(f"Total Annual Savings: ${results.get('total_annual_savings', 0):.2f}")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"\nOptimization Opportunities: {summary.get('optimization_opportunities', 0)}")
        print(f"Estimated ROI: {summary.get('estimated_roi_percentage', 0):.1f}%")
        print(f"Payback Period: {summary.get('payback_period_months', 0):.1f} months")
        print(f"Intelligent Tiering Candidates: {summary.get('intelligent_tiering_candidates', 0)}")
    
    print("="*60)
    
    # Export results
    optimizer.export_analysis_results(results, args.output)
    
    # Implement recommendations if requested
    if args.implement:
        print("\nImplementing lifecycle policies...")
        for recommendation in results.get('lifecycle_recommendations', []):
            bucket_name = recommendation['bucket_name']
            policy = recommendation['policy']
            success = optimizer.implement_lifecycle_policy(bucket_name, policy)
            print(f"  {bucket_name}: {'✓' if success else '✗'}")
    
    # Enable Intelligent Tiering if requested
    if args.enable_intelligent_tiering:
        print("\nEnabling Intelligent Tiering...")
        for recommendation in results.get('intelligent_tiering_recommendations', []):
            bucket_name = recommendation['bucket_name']
            success = optimizer.enable_intelligent_tiering(bucket_name)
            print(f"  {bucket_name}: {'✓' if success else '✗'}")

if __name__ == '__main__':
    main()