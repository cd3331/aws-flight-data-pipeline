#!/bin/bash
echo "=== Flight Data Pipeline Demo ==="
echo "1. Triggering Lambda function..."
aws lambda invoke --function-name flight-data-pipeline-dev-flight-ingestion --payload '{}' demo-result.json
echo "2. Lambda response:"
cat demo-result.json | python -m json.tool
echo ""
echo "3. Checking S3 for stored data..."
aws s3 ls s3://flight-data-pipeline-dev-raw-data-y10swyy3/ --recursive --human-readable
echo ""
echo "4. Recent Lambda executions:"
aws logs tail /aws/lambda/flight-data-pipeline-dev-flight-ingestion --since 5m | grep "SUCCESS\|records"
