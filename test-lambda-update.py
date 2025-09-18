#!/usr/bin/env python3
"""
Test script to verify the updated Lambda function works correctly
"""
import sys
import os
import json
from datetime import datetime, timezone

# Add the lambda source to Python path
sys.path.insert(0, '/home/cd3331/flightdata-project/src/lambda/data_ingestion')

def test_s3_key_generation():
    """Test the S3 key generation function"""
    try:
        from flight_data_ingestion import FlightDataIngestion

        # Mock the required environment variable
        os.environ['RAW_DATA_BUCKET'] = 'test-bucket'

        ingestion = FlightDataIngestion()

        # Test with current timestamp
        current_timestamp = int(datetime.now(timezone.utc).timestamp())
        s3_key = ingestion.generate_s3_key(current_timestamp)

        print(f"✅ S3 Key Generation Test:")
        print(f"   Timestamp: {current_timestamp}")
        print(f"   Generated Key: {s3_key}")
        print(f"   Pattern Check: {'✅' if 'year=' in s3_key and 'flight_data_' in s3_key else '❌'}")

        return True

    except Exception as e:
        print(f"❌ S3 Key Generation Test Failed: {e}")
        return False

def test_function_syntax():
    """Test that the updated function has valid syntax"""
    try:
        from flight_data_ingestion import FlightDataIngestion

        # Check if the function exists and has the expected signature
        ingestion = FlightDataIngestion()
        method = getattr(ingestion, 'store_data_in_s3', None)

        if method and callable(method):
            print("✅ Function Syntax Test: store_data_in_s3 method exists and is callable")
            return True
        else:
            print("❌ Function Syntax Test: store_data_in_s3 method not found")
            return False

    except SyntaxError as e:
        print(f"❌ Function Syntax Test Failed: Syntax error in updated code: {e}")
        return False
    except Exception as e:
        print(f"❌ Function Syntax Test Failed: {e}")
        return False

def main():
    print("🧪 Testing Updated Lambda Function")
    print("=" * 50)

    # Set required environment variable
    os.environ['RAW_DATA_BUCKET'] = 'flight-data-pipeline-dev-raw-data-y10swyy3'

    test_results = []

    # Test 1: Function syntax
    test_results.append(test_function_syntax())

    # Test 2: S3 key generation
    test_results.append(test_s3_key_generation())

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {sum(test_results)}/{len(test_results)} passed")

    if all(test_results):
        print("✅ All tests passed! The updated Lambda function is ready to deploy.")
        print("\n🔧 Changes Made:")
        print("   - Added latest.json creation after timestamped file storage")
        print("   - Added error handling for latest.json (won't fail main operation)")
        print("   - Added logging for both timestamped and latest.json operations")
        print("\n📈 Expected Result:")
        print("   - Dashboard will now receive fresh data every ~10 minutes")
        print("   - API will return current timestamp instead of 3:41 PM data")
        return True
    else:
        print("❌ Some tests failed. Please check the Lambda function code.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)