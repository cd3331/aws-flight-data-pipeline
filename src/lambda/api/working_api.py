import json
import boto3
from datetime import datetime
def lambda_handler(event, context):
    s3 = boto3.client('s3')
    bucket = 'flight-data-pipeline-dev-raw-data-y10swyy3'
# List objects to find latest file
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix='year=2025/',
            MaxKeys=1
        )
  try:
        # List objects to find latest file
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix='year=2025/',
            MaxKeys=1
        )
        
        if 'Contents' in response:
            latest_file = response['Contents'][0]
            file_info = {
                'key': latest_file['Key'],
                'size_mb': round(latest_file['Size'] / 1024 / 1024, 2),
                'last_modified': latest_file['LastModified'].isoformat()
            }
        else:
            file_info = {'message': 'No data files found'}
            
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': 'https://main.d2zdmzm6s2zgyk.amplifyapp.com',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'success': True,
                'bucket': bucket,
                'latest_file': file_info,
                'pipeline_status': 'operational'
            })
        }
    except Exception as e:
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': 'https://main.d2zdmzm6s2zgyk.amplifyapp.com',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
