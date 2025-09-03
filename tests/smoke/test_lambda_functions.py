#!/usr/bin/env python3
"""
Smoke tests for Lambda functions after deployment.
These tests verify that deployed Lambda functions are working correctly.
"""

import os
import json
import boto3
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from botocore.exceptions import ClientError


@dataclass
class LambdaSmokeTestConfig:
    """Configuration for Lambda smoke tests."""
    environment: str = "dev"
    region: str = "us-east-1"
    timeout: int = 30
    max_retries: int = 3


class LambdaSmokeTests:
    """Smoke tests for Flight Data Pipeline Lambda functions."""
    
    def __init__(self, config: LambdaSmokeTestConfig):
        self.config = config
        self.lambda_client = boto3.client('lambda', region_name=config.region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=config.region)
        
        # Expected Lambda functions for this environment
        self.expected_functions = [
            f"flightdata-processor-{config.environment}",
            f"flightdata-api-handler-{config.environment}", 
            f"flightdata-aggregator-{config.environment}",
            f"flightdata-scheduler-{config.environment}"
        ]
    
    def get_function_list(self) -> List[str]:
        """Get list of deployed Lambda functions."""
        try:
            response = self.lambda_client.list_functions()
            functions = [f['FunctionName'] for f in response['Functions'] 
                        if f['FunctionName'].startswith(f"flightdata-") and 
                        f['FunctionName'].endswith(f"-{self.config.environment}")]
            
            print(f"Found {len(functions)} Lambda functions for environment '{self.config.environment}'")
            return functions
            
        except ClientError as e:
            print(f"❌ Error listing Lambda functions: {e}")
            return []
    
    def test_function_existence(self, functions: List[str]) -> Dict[str, Any]:
        """Test that all expected Lambda functions exist."""
        print("Testing Lambda function existence...")
        
        missing_functions = []
        existing_functions = []
        
        for expected_func in self.expected_functions:
            if expected_func in functions:
                existing_functions.append(expected_func)
                print(f"✅ Found expected function: {expected_func}")
            else:
                missing_functions.append(expected_func)
                print(f"❌ Missing expected function: {expected_func}")
        
        # Check for unexpected functions
        unexpected_functions = [f for f in functions if f not in self.expected_functions]
        if unexpected_functions:
            print(f"⚠️  Found unexpected functions: {unexpected_functions}")
        
        result = {
            "expected": self.expected_functions,
            "existing": existing_functions,
            "missing": missing_functions,
            "unexpected": unexpected_functions,
            "all_expected_found": len(missing_functions) == 0
        }
        
        assert len(missing_functions) == 0, f"Missing expected functions: {missing_functions}"
        
        print(f"✅ Function existence test passed")
        return result
    
    def test_function_configuration(self, function_name: str) -> Dict[str, Any]:
        """Test Lambda function configuration."""
        print(f"Testing configuration for {function_name}...")
        
        try:
            response = self.lambda_client.get_function_configuration(FunctionName=function_name)
            
            config_check = {
                "function_name": function_name,
                "state": response.get('State'),
                "last_update_status": response.get('LastUpdateStatus'),
                "runtime": response.get('Runtime'),
                "timeout": response.get('Timeout'),
                "memory_size": response.get('MemorySize'),
                "environment_variables": bool(response.get('Environment', {}).get('Variables')),
                "layers": len(response.get('Layers', [])),
                "code_size": response.get('CodeSize', 0)
            }
            
            # Verify function is in Active state
            assert config_check['state'] == 'Active', f"Function {function_name} is not Active (state: {config_check['state']})"
            
            # Verify last update was successful
            assert config_check['last_update_status'] == 'Successful', \
                f"Function {function_name} last update failed (status: {config_check['last_update_status']})"
            
            # Check reasonable timeout (not too low or too high)
            if config_check['timeout'] < 10:
                print(f"⚠️  {function_name} has very low timeout: {config_check['timeout']}s")
            elif config_check['timeout'] > 900:
                print(f"⚠️  {function_name} has maximum timeout: {config_check['timeout']}s")
            
            # Check memory allocation
            if config_check['memory_size'] < 128:
                print(f"⚠️  {function_name} has minimum memory: {config_check['memory_size']}MB")
            
            print(f"✅ Configuration test passed for {function_name}")
            return config_check
            
        except ClientError as e:
            error_msg = f"Failed to get configuration for {function_name}: {e}"
            print(f"❌ {error_msg}")
            raise AssertionError(error_msg)
    
    def test_function_invocation(self, function_name: str) -> Dict[str, Any]:
        """Test Lambda function invocation."""
        print(f"Testing invocation for {function_name}...")
        
        # Create test payload based on function type
        if "api-handler" in function_name:
            test_payload = {
                "httpMethod": "GET",
                "path": "/health",
                "headers": {},
                "queryStringParameters": None,
                "body": None,
                "isBase64Encoded": False
            }
        elif "processor" in function_name:
            test_payload = {
                "test": True,
                "source": "smoke-test",
                "records": [
                    {
                        "s3": {
                            "bucket": {"name": "test-bucket"},
                            "object": {"key": "test-object"}
                        }
                    }
                ]
            }
        elif "aggregator" in function_name:
            test_payload = {
                "test": True,
                "source": "smoke-test",
                "aggregation_type": "daily",
                "date": "2024-01-01"
            }
        elif "scheduler" in function_name:
            test_payload = {
                "test": True,
                "source": "smoke-test",
                "schedule_time": "2024-01-01T00:00:00Z"
            }
        else:
            test_payload = {
                "test": True,
                "source": "smoke-test"
            }
        
        try:
            start_time = time.time()
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_payload)
            )
            
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            invocation_result = {
                "function_name": function_name,
                "status_code": response.get('StatusCode'),
                "execution_time_ms": execution_time,
                "log_result": response.get('LogResult'),
                "payload_size": len(json.dumps(test_payload))
            }
            
            # Check response status
            assert invocation_result['status_code'] == 200, \
                f"Function {function_name} invocation failed with status {invocation_result['status_code']}"
            
            # Parse response payload
            payload = response.get('Payload')
            if payload:
                try:
                    payload_data = json.loads(payload.read())
                    invocation_result['response_payload'] = payload_data
                    
                    # For API handler, check for proper HTTP response structure
                    if "api-handler" in function_name:
                        if isinstance(payload_data, dict) and 'statusCode' in payload_data:
                            api_status = payload_data['statusCode']
                            assert api_status in [200, 201, 202], \
                                f"API handler returned non-success status: {api_status}"
                            invocation_result['api_status_code'] = api_status
                        else:
                            print(f"⚠️  API handler response doesn't have expected structure")
                    
                except json.JSONDecodeError:
                    print(f"⚠️  Could not parse response payload for {function_name}")
                    invocation_result['response_payload'] = "unparseable"
            
            # Warn about long execution times
            if execution_time > 10000:  # > 10 seconds
                print(f"⚠️  {function_name} took {execution_time:.0f}ms to execute")
            elif execution_time > 30000:  # > 30 seconds
                print(f"🚨 {function_name} took {execution_time:.0f}ms to execute (very slow)")
            
            print(f"✅ Invocation test passed for {function_name} ({execution_time:.0f}ms)")
            return invocation_result
            
        except ClientError as e:
            error_msg = f"Failed to invoke {function_name}: {e}"
            print(f"❌ {error_msg}")
            raise AssertionError(error_msg)
    
    def test_function_metrics(self, function_name: str) -> Dict[str, Any]:
        """Test Lambda function CloudWatch metrics."""
        print(f"Testing metrics for {function_name}...")
        
        # Get metrics for the last hour
        end_time = time.time()
        start_time = end_time - 3600  # 1 hour ago
        
        metrics = {}
        
        try:
            # Get invocation count
            invocation_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            invocations = 0
            if invocation_response['Datapoints']:
                invocations = invocation_response['Datapoints'][0]['Sum']
            
            metrics['invocations_last_hour'] = invocations
            
            # Get error count
            error_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            errors = 0
            if error_response['Datapoints']:
                errors = error_response['Datapoints'][0]['Sum']
            
            metrics['errors_last_hour'] = errors
            
            # Calculate error rate
            if invocations > 0:
                error_rate = (errors / invocations) * 100
                metrics['error_rate_percent'] = error_rate
                
                if error_rate > 10:  # > 10% error rate
                    print(f"🚨 High error rate for {function_name}: {error_rate:.2f}%")
                elif error_rate > 5:  # > 5% error rate
                    print(f"⚠️  Elevated error rate for {function_name}: {error_rate:.2f}%")
            else:
                metrics['error_rate_percent'] = 0
            
            # Get duration metrics
            duration_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            
            if duration_response['Datapoints']:
                datapoint = duration_response['Datapoints'][0]
                metrics['avg_duration_ms'] = datapoint.get('Average', 0)
                metrics['max_duration_ms'] = datapoint.get('Maximum', 0)
            else:
                metrics['avg_duration_ms'] = 0
                metrics['max_duration_ms'] = 0
            
            print(f"✅ Metrics test passed for {function_name}")
            print(f"   Invocations: {metrics['invocations_last_hour']}")
            print(f"   Errors: {metrics['errors_last_hour']}")
            print(f"   Error Rate: {metrics['error_rate_percent']:.2f}%")
            print(f"   Avg Duration: {metrics['avg_duration_ms']:.0f}ms")
            
            return metrics
            
        except ClientError as e:
            print(f"⚠️  Could not retrieve metrics for {function_name}: {e}")
            return {"error": str(e)}
    
    def test_function_logs(self, function_name: str) -> Dict[str, Any]:
        """Test Lambda function logs availability."""
        print(f"Testing log availability for {function_name}...")
        
        log_group_name = f"/aws/lambda/{function_name}"
        
        try:
            logs_client = boto3.client('logs', region_name=self.config.region)
            
            # Check if log group exists
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_name
            )
            
            log_groups = response.get('logGroups', [])
            matching_log_group = None
            
            for log_group in log_groups:
                if log_group['logGroupName'] == log_group_name:
                    matching_log_group = log_group
                    break
            
            if not matching_log_group:
                print(f"⚠️  Log group not found for {function_name}")
                return {"log_group_exists": False}
            
            # Get recent log events
            log_streams_response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )
            
            log_result = {
                "log_group_exists": True,
                "log_group_name": log_group_name,
                "creation_time": matching_log_group.get('creationTime'),
                "retention_days": matching_log_group.get('retentionInDays'),
                "stored_bytes": matching_log_group.get('storedBytes', 0)
            }
            
            if log_streams_response['logStreams']:
                latest_stream = log_streams_response['logStreams'][0]
                log_result['latest_log_stream'] = latest_stream['logStreamName']
                log_result['last_event_time'] = latest_stream.get('lastEventTime')
                
                # Check how recent the latest log is
                if log_result['last_event_time']:
                    time_since_last_log = time.time() * 1000 - log_result['last_event_time']
                    log_result['time_since_last_log_ms'] = time_since_last_log
                    
                    if time_since_last_log > 86400000:  # > 24 hours
                        print(f"⚠️  No recent logs for {function_name} (last log > 24h ago)")
            else:
                print(f"⚠️  No log streams found for {function_name}")
            
            print(f"✅ Log test passed for {function_name}")
            return log_result
            
        except ClientError as e:
            print(f"⚠️  Could not check logs for {function_name}: {e}")
            return {"error": str(e)}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all Lambda smoke tests and return results."""
        print(f"🧪 Running Lambda smoke tests for environment: {self.config.environment}")
        print(f"📍 Region: {self.config.region}")
        print()
        
        results = {
            "environment": self.config.environment,
            "region": self.config.region,
            "timestamp": time.time(),
            "functions": {},
            "summary": {}
        }
        
        # Get list of deployed functions
        functions = self.get_function_list()
        
        if not functions:
            print("❌ No Lambda functions found - deployment may have failed")
            results["summary"] = {
                "total_functions": 0,
                "tested_functions": 0,
                "passed_functions": 0,
                "failed_functions": 0,
                "success_rate": 0
            }
            return results
        
        # Test function existence
        existence_result = self.test_function_existence(functions)
        results["existence_check"] = existence_result
        
        # Test each function
        tested_functions = 0
        passed_functions = 0
        failed_functions = 0
        
        for function_name in existence_result["existing"]:
            print(f"\n--- Testing {function_name} ---")
            
            function_results = {
                "function_name": function_name,
                "tests": {}
            }
            
            # List of tests to run for each function
            function_tests = [
                ("configuration", lambda: self.test_function_configuration(function_name)),
                ("invocation", lambda: self.test_function_invocation(function_name)),
                ("metrics", lambda: self.test_function_metrics(function_name)),
                ("logs", lambda: self.test_function_logs(function_name)),
            ]
            
            function_passed = True
            
            for test_name, test_func in function_tests:
                try:
                    test_result = test_func()
                    function_results["tests"][test_name] = {
                        "status": "passed",
                        "result": test_result
                    }
                except Exception as e:
                    print(f"❌ {test_name} test failed for {function_name}: {str(e)}")
                    function_results["tests"][test_name] = {
                        "status": "failed",
                        "error": str(e)
                    }
                    function_passed = False
            
            function_results["overall_status"] = "passed" if function_passed else "failed"
            results["functions"][function_name] = function_results
            
            tested_functions += 1
            if function_passed:
                passed_functions += 1
            else:
                failed_functions += 1
        
        # Generate summary
        results["summary"] = {
            "total_functions": len(self.expected_functions),
            "found_functions": len(functions),
            "tested_functions": tested_functions,
            "passed_functions": passed_functions,
            "failed_functions": failed_functions,
            "success_rate": (passed_functions / tested_functions * 100) if tested_functions > 0 else 0
        }
        
        print(f"\n🎯 Lambda Test Summary:")
        print(f"   Expected Functions: {results['summary']['total_functions']}")
        print(f"   Found Functions: {results['summary']['found_functions']}")
        print(f"   Tested Functions: {results['summary']['tested_functions']}")
        print(f"   Passed: {results['summary']['passed_functions']}")
        print(f"   Failed: {results['summary']['failed_functions']}")
        print(f"   Success Rate: {results['summary']['success_rate']:.1f}%")
        
        if failed_functions == 0 and results['summary']['found_functions'] == results['summary']['total_functions']:
            print("🎉 All Lambda smoke tests passed!")
        else:
            print("⚠️  Some Lambda smoke tests failed - check logs above")
        
        return results


def get_config_from_env() -> LambdaSmokeTestConfig:
    """Get smoke test configuration from environment variables."""
    environment = os.getenv("ENVIRONMENT", "dev")
    region = os.getenv("AWS_REGION", "us-east-1")
    timeout = int(os.getenv("LAMBDA_TEST_TIMEOUT", "30"))
    
    return LambdaSmokeTestConfig(
        environment=environment,
        region=region,
        timeout=timeout
    )


def main():
    """Main function for running Lambda smoke tests."""
    config = get_config_from_env()
    
    smoke_tests = LambdaSmokeTests(config)
    results = smoke_tests.run_all_tests()
    
    # Save results to file if specified
    output_file = os.getenv("LAMBDA_SMOKE_TEST_OUTPUT_FILE")
    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Results saved to: {output_file}")
    
    # Exit with error code if any tests failed
    summary = results.get("summary", {})
    if summary.get("failed_functions", 0) > 0 or summary.get("found_functions", 0) != summary.get("total_functions", 0):
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()