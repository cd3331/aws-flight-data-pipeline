import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    
    # List buckets to find the right one
    buckets = s3.list_buckets()
    raw_bucket = [b['Name'] for b in buckets['Buckets'] if 'raw-data' in b['Name']][0]
    
    test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
    
    try:
        response = s3.put_object(
            Bucket=raw_bucket,
            Key=f"test/{datetime.now().strftime('%Y%m%d%H%M%S')}.json",
            Body=json.dumps(test_data)
        )
        return {"statusCode": 200, "body": json.dumps({"success": True, "bucket": raw_bucket})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e), "bucket": raw_bucket})}
