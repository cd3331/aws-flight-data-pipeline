#!/usr/bin/env python3
"""
Smoke tests for API endpoints after deployment.
These tests verify that the deployed API is responding correctly.
"""

import os
import time
import json
import requests
import pytest
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SmokeTestConfig:
    """Configuration for smoke tests."""
    api_base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 5
    environment: str = "dev"


class APISmokeTests:
    """Smoke tests for Flight Data Pipeline API."""
    
    def __init__(self, config: SmokeTestConfig):
        self.config = config
        self.session = requests.Session()
        self.session.timeout = config.timeout
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic."""
        url = f"{self.config.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                return response
            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise
                print(f"Request attempt {attempt + 1} failed: {e}")
                time.sleep(self.config.retry_delay)
        
        raise Exception("All retry attempts failed")
    
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health check endpoint."""
        print("Testing health endpoint...")
        
        response = self._make_request("GET", "/health")
        
        assert response.status_code == 200, f"Health check failed with status {response.status_code}"
        
        try:
            health_data = response.json()
        except json.JSONDecodeError:
            # If not JSON, check if response contains expected text
            assert "healthy" in response.text.lower(), "Health response doesn't indicate healthy status"
            health_data = {"status": "healthy", "message": response.text}
        
        # Verify health response structure
        assert "status" in health_data, "Health response missing 'status' field"
        assert health_data["status"] in ["healthy", "ok"], f"Unexpected health status: {health_data['status']}"
        
        print(f"✅ Health endpoint passed: {health_data}")
        return health_data
    
    def test_version_endpoint(self) -> Dict[str, Any]:
        """Test the version endpoint."""
        print("Testing version endpoint...")
        
        response = self._make_request("GET", "/version")
        
        if response.status_code == 404:
            print("⚠️  Version endpoint not found, skipping test")
            return {"status": "skipped"}
        
        assert response.status_code == 200, f"Version check failed with status {response.status_code}"
        
        version_data = response.json()
        
        # Verify version response has expected fields
        expected_fields = ["version", "build", "environment"]
        for field in expected_fields:
            if field not in version_data:
                print(f"⚠️  Version response missing '{field}' field")
        
        print(f"✅ Version endpoint passed: {version_data}")
        return version_data
    
    def test_cors_headers(self) -> Dict[str, Any]:
        """Test CORS headers are properly configured."""
        print("Testing CORS configuration...")
        
        # Make OPTIONS request to check CORS
        response = self._make_request("OPTIONS", "/health")
        
        # Check for CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
            "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
            "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
        }
        
        if any(cors_headers.values()):
            print(f"✅ CORS headers present: {cors_headers}")
        else:
            print("⚠️  No CORS headers found (may be intentional)")
        
        return {"cors_headers": cors_headers, "status": "checked"}
    
    def test_flight_data_endpoint(self) -> Dict[str, Any]:
        """Test flight data retrieval endpoint."""
        print("Testing flight data endpoint...")
        
        # Test with basic query parameters
        params = {
            "lamin": "45.8389",
            "lomin": "5.9962", 
            "lamax": "47.8229",
            "lomax": "10.5226",
            "limit": "10"
        }
        
        response = self._make_request("GET", "/flights", params=params)
        
        if response.status_code == 404:
            print("⚠️  Flight data endpoint not found, skipping test")
            return {"status": "skipped"}
        
        # Accept both 200 (success) and 202 (accepted/processing)
        acceptable_codes = [200, 202]
        assert response.status_code in acceptable_codes, \
            f"Flight data request failed with status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            try:
                flight_data = response.json()
                
                # Basic structure validation
                if isinstance(flight_data, dict):
                    assert "flights" in flight_data or "data" in flight_data or "results" in flight_data, \
                        "Flight data response missing expected data field"
                elif isinstance(flight_data, list):
                    print(f"✅ Flight data returned as list with {len(flight_data)} items")
                else:
                    print(f"⚠️  Unexpected flight data format: {type(flight_data)}")
                
                print(f"✅ Flight data endpoint passed")
                return {"status": "success", "data_type": type(flight_data).__name__}
                
            except json.JSONDecodeError:
                print("⚠️  Flight data response is not valid JSON")
                return {"status": "warning", "message": "Non-JSON response"}
        
        else:  # 202 status
            print("✅ Flight data request accepted (async processing)")
            return {"status": "accepted"}
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test API error handling."""
        print("Testing error handling...")
        
        # Test invalid endpoint
        response = self._make_request("GET", "/nonexistent-endpoint")
        assert response.status_code == 404, \
            f"Expected 404 for invalid endpoint, got {response.status_code}"
        
        # Test invalid method on valid endpoint
        response = self._make_request("DELETE", "/health")
        assert response.status_code in [405, 404], \
            f"Expected 405 or 404 for invalid method, got {response.status_code}"
        
        print("✅ Error handling tests passed")
        return {"status": "passed"}
    
    def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting (if configured)."""
        print("Testing rate limiting...")
        
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            try:
                response = self._make_request("GET", "/health")
                responses.append(response.status_code)
            except requests.RequestException:
                responses.append("error")
        
        # Check if any requests were rate limited (429 status)
        rate_limited = sum(1 for r in responses if r == 429)
        
        if rate_limited > 0:
            print(f"✅ Rate limiting active: {rate_limited}/10 requests limited")
        else:
            print("⚠️  No rate limiting detected (may not be configured)")
        
        return {"rate_limited_requests": rate_limited, "total_requests": len(responses)}
    
    def test_response_times(self) -> Dict[str, Any]:
        """Test API response times."""
        print("Testing response times...")
        
        response_times = []
        
        # Test multiple requests to get average response time
        for _ in range(5):
            start_time = time.time()
            response = self._make_request("GET", "/health")
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            response_times.append(response_time)
            assert response.status_code == 200, "Health check failed during response time test"
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        # Warn if response times are high
        if avg_response_time > 5000:  # 5 seconds
            print(f"⚠️  High average response time: {avg_response_time:.2f}ms")
        elif avg_response_time > 2000:  # 2 seconds
            print(f"⚠️  Moderate response time: {avg_response_time:.2f}ms")
        else:
            print(f"✅ Good response times: avg={avg_response_time:.2f}ms, max={max_response_time:.2f}ms")
        
        return {
            "average_response_time_ms": avg_response_time,
            "max_response_time_ms": max_response_time,
            "all_response_times_ms": response_times
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all smoke tests and return results."""
        print(f"🧪 Running API smoke tests for environment: {self.config.environment}")
        print(f"🔗 API Base URL: {self.config.api_base_url}")
        print()
        
        results = {
            "environment": self.config.environment,
            "api_base_url": self.config.api_base_url,
            "timestamp": time.time(),
            "tests": {}
        }
        
        # List of tests to run
        tests = [
            ("health_endpoint", self.test_health_endpoint),
            ("version_endpoint", self.test_version_endpoint),
            ("cors_headers", self.test_cors_headers),
            ("flight_data_endpoint", self.test_flight_data_endpoint),
            ("error_handling", self.test_error_handling),
            ("rate_limiting", self.test_rate_limiting),
            ("response_times", self.test_response_times),
        ]
        
        passed_tests = 0
        failed_tests = 0
        
        for test_name, test_func in tests:
            try:
                print(f"\n--- {test_name.replace('_', ' ').title()} ---")
                test_result = test_func()
                results["tests"][test_name] = {
                    "status": "passed",
                    "result": test_result
                }
                passed_tests += 1
                
            except Exception as e:
                print(f"❌ Test {test_name} failed: {str(e)}")
                results["tests"][test_name] = {
                    "status": "failed",
                    "error": str(e)
                }
                failed_tests += 1
        
        # Summary
        results["summary"] = {
            "total_tests": len(tests),
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / len(tests)) * 100
        }
        
        print(f"\n🎯 Test Summary:")
        print(f"   Total Tests: {len(tests)}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {results['summary']['success_rate']:.1f}%")
        
        if failed_tests == 0:
            print("🎉 All smoke tests passed!")
        else:
            print("⚠️  Some smoke tests failed - check logs above")
        
        return results


def get_config_from_env() -> SmokeTestConfig:
    """Get smoke test configuration from environment variables."""
    api_base_url = os.getenv("API_BASE_URL", "https://api.flightdata-pipeline.com")
    environment = os.getenv("ENVIRONMENT", "dev")
    timeout = int(os.getenv("SMOKE_TEST_TIMEOUT", "30"))
    
    return SmokeTestConfig(
        api_base_url=api_base_url,
        timeout=timeout,
        environment=environment
    )


def main():
    """Main function for running smoke tests."""
    config = get_config_from_env()
    
    smoke_tests = APISmokeTests(config)
    results = smoke_tests.run_all_tests()
    
    # Save results to file if specified
    output_file = os.getenv("SMOKE_TEST_OUTPUT_FILE")
    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Results saved to: {output_file}")
    
    # Exit with error code if any tests failed
    if results["summary"]["failed"] > 0:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()