# Backend Services

This directory contains all serverless backend services for the Flight Data Pipeline, built with AWS Lambda and supporting cloud services.

## 🏗️ Architecture Overview

The backend consists of several specialized Lambda functions that work together to provide a complete data pipeline:

```
Data Flow:
External APIs → Data Fetcher → EventBridge → Data Processor → DynamoDB
                                    ↓
Client Requests → API Gateway → API Handler → Cache/Database → Response
```

## 📁 Directory Structure

```
backend/
├── 📁 functions/           # Individual Lambda functions
│   ├── flight-data-fetcher/    # Fetches data from external APIs
│   ├── flight-data-processor/  # Processes and validates flight data
│   ├── flight-api/            # REST API request handlers
│   └── analytics-processor/   # Generates analytics and reports
├── 📁 shared/             # Shared libraries and utilities
│   ├── models/               # Pydantic data models
│   ├── utils/                # Common utility functions
│   ├── clients/              # External API clients
│   └── validation/           # Data validation schemas
└── 📁 tests/              # Backend-specific tests
    ├── unit/                 # Unit tests for individual functions
    ├── integration/          # Cross-function integration tests
    └── fixtures/             # Test data and mock objects
```

## 🛠️ Lambda Functions

### 1. Flight Data Fetcher
**Purpose**: Collects real-time flight data from external APIs
- **Runtime**: Python 3.11
- **Trigger**: EventBridge scheduled rule (every 30 seconds)
- **Memory**: 512 MB
- **Timeout**: 5 minutes

**Key Features**:
- Fetches data from OpenSky Network API
- Handles rate limiting and retries
- Stores raw data in S3 for backup
- Publishes events for downstream processing

### 2. Flight Data Processor
**Purpose**: Validates, enriches, and transforms flight data
- **Runtime**: Python 3.11
- **Trigger**: SQS queue from EventBridge
- **Memory**: 1024 MB
- **Timeout**: 15 minutes

**Key Features**:
- Data validation and quality checks
- Geographic coordinate validation
- Aircraft information enrichment
- DynamoDB batch writing

### 3. Flight API Handler
**Purpose**: Handles REST API requests for flight data
- **Runtime**: Python 3.11
- **Trigger**: API Gateway
- **Memory**: 256 MB
- **Timeout**: 30 seconds

**Key Features**:
- Geographic bounding box queries
- Pagination and filtering
- Response caching with ElastiCache
- Rate limiting and authentication

### 4. Analytics Processor
**Purpose**: Generates statistics and analytics
- **Runtime**: Python 3.11
- **Trigger**: Scheduled EventBridge rules
- **Memory**: 512 MB
- **Timeout**: 10 minutes

**Key Features**:
- Traffic density calculations
- Route popularity analysis
- Historical trend computation
- Performance metrics aggregation

## 🚀 Local Development

### Prerequisites
```bash
# Install Poetry for dependency management
curl -sSL https://install.python-poetry.org | python3 -

# Install Python 3.11
pyenv install 3.11.0
pyenv local 3.11.0
```

### Setup Development Environment
```bash
# Install dependencies
cd backend/
poetry install

# Activate virtual environment
poetry shell

# Install pre-commit hooks
pre-commit install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration
```

### Running Functions Locally

#### Individual Function Testing
```bash
# Test flight data fetcher
cd functions/flight-data-fetcher/
poetry run python handler.py

# Test with SAM Local
sam local invoke FlightDataFetcher --event events/sample-event.json
```

#### API Testing with Local Server
```bash
# Run API handler as local server
cd functions/flight-api/
poetry run uvicorn app:app --reload --port 8001

# Test endpoints
curl "http://localhost:8001/flights?lamin=45&lamax=47"
```

### Database Setup (Local)
```bash
# Start local DynamoDB
docker run -p 8000:8000 amazon/dynamodb-local

# Create tables
python scripts/create-local-tables.py

# Load test data
python scripts/load-test-data.py
```

## 🧪 Testing

### Unit Tests
```bash
# Run all unit tests
poetry run pytest tests/unit/ -v --cov

# Test specific function
poetry run pytest tests/unit/test_flight_api.py -v

# Generate coverage report
poetry run pytest tests/unit/ --cov --cov-report=html
```

### Integration Tests
```bash
# Run integration tests (requires local services)
docker-compose up -d  # Start local services
poetry run pytest tests/integration/ -v

# Test against deployed environment
ENVIRONMENT=dev poetry run pytest tests/integration/ -v
```

### Load Testing
```bash
# Install locust
pip install locust

# Run load tests
locust -f tests/load/api_load_test.py --host=http://localhost:8001
```

## 📦 Deployment

### Package Functions
```bash
# Package individual function
cd functions/flight-api/
poetry export -f requirements.txt --output requirements.txt
zip -r flight-api.zip . -x "tests/*" "*.pyc" "__pycache__/*"

# Package all functions
./scripts/package-functions.sh
```

### Deploy with CDK
```bash
# Deploy to development
cd ../../infrastructure/
npm run cdk deploy -- --context environment=dev

# Deploy to production
npm run cdk deploy -- --context environment=prod --require-approval broadening
```

## 🔧 Configuration

### Environment Variables
Functions use the following environment variables:

#### Common Variables
```bash
ENVIRONMENT=dev|staging|prod
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
AWS_REGION=us-east-1
```

#### Function-Specific Variables
```bash
# Flight Data Fetcher
OPENSKY_API_URL=https://opensky-network.org/api
S3_RAW_BUCKET=flightdata-raw-{environment}
EVENTBRIDGE_BUS_NAME=flight-data-events

# Data Processor
DYNAMODB_FLIGHTS_TABLE=flightdata-flights-{environment}
REDIS_CLUSTER_ENDPOINT=redis-cluster.{environment}.cache.amazonaws.com

# API Handler
CORS_ORIGINS=https://dashboard.flightdata-pipeline.com
MAX_PAGE_SIZE=1000
CACHE_TTL_SECONDS=30
```

### Secrets Management
Sensitive configuration is stored in AWS Systems Manager Parameter Store:

```bash
# Store API credentials
aws ssm put-parameter \
  --name "/flightdata/dev/opensky/username" \
  --value "your-username" \
  --type "SecureString"

# Retrieve in Lambda function
import boto3
ssm = boto3.client('ssm')
username = ssm.get_parameter(Name='/flightdata/dev/opensky/username', WithDecryption=True)['Parameter']['Value']
```

## 📊 Monitoring

### CloudWatch Metrics
Key metrics tracked for each function:

- **Duration**: Function execution time
- **Memory Usage**: Peak memory consumption
- **Error Rate**: Percentage of failed invocations
- **Throttling**: Number of throttled requests

### Custom Metrics
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Track business metrics
cloudwatch.put_metric_data(
    Namespace='FlightDataPipeline',
    MetricData=[
        {
            'MetricName': 'FlightsProcessed',
            'Value': flight_count,
            'Unit': 'Count'
        }
    ]
)
```

### Logging
Structured logging with correlation IDs:

```python
import logging
import json

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    correlation_id = context.aws_request_id
    
    logger.info(json.dumps({
        'correlation_id': correlation_id,
        'event_type': 'function_start',
        'function_name': context.function_name
    }))
    
    try:
        # Function logic
        result = process_request(event)
        
        logger.info(json.dumps({
            'correlation_id': correlation_id,
            'event_type': 'function_success',
            'result_count': len(result)
        }))
        
        return result
    except Exception as e:
        logger.error(json.dumps({
            'correlation_id': correlation_id,
            'event_type': 'function_error',
            'error': str(e)
        }))
        raise
```

## 🔐 Security

### IAM Policies
Each function has minimal required permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/flightdata-*"
    }
  ]
}
```

### Input Validation
All functions validate inputs using Pydantic models:

```python
from pydantic import BaseModel, validator
from typing import Optional

class FlightSearchRequest(BaseModel):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    limit: Optional[int] = 50
    
    @validator('lat_min', 'lat_max')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Invalid latitude')
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        if not 1 <= v <= 1000:
            raise ValueError('Invalid limit')
        return v
```

## 🚨 Error Handling

### Retry Logic
```python
import time
import random
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                    
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def fetch_external_data():
    # API call that might fail
    pass
```

### Dead Letter Queues
Failed messages are sent to DLQ for manual investigation:

```python
import json
import boto3

def handle_poison_message(message):
    """Handle messages that repeatedly fail processing"""
    sqs = boto3.client('sqs')
    
    # Send to DLQ with additional context
    dlq_message = {
        'original_message': message,
        'failure_count': message.get('failure_count', 0) + 1,
        'last_error': str(e),
        'timestamp': int(time.time())
    }
    
    sqs.send_message(
        QueueUrl='https://sqs.us-east-1.amazonaws.com/123/flight-data-dlq',
        MessageBody=json.dumps(dlq_message)
    )
```

## 🔍 Debugging

### Local Debugging
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Use debugger
import pdb
pdb.set_trace()  # Add breakpoint

# VS Code debugging configuration
{
    "name": "Debug Lambda Function",
    "type": "python",
    "request": "launch",
    "program": "${workspaceFolder}/backend/functions/flight-api/handler.py",
    "env": {
        "ENVIRONMENT": "local",
        "LOG_LEVEL": "DEBUG"
    }
}
```

### AWS X-Ray Tracing
```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch AWS SDK calls
patch_all()

@xray_recorder.capture('process_flight_data')
def process_flight_data(data):
    # Function will be traced in X-Ray
    pass
```

## 📚 Additional Resources

- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Python Lambda Development](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [DynamoDB Python SDK](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html)
- [EventBridge Developer Guide](https://docs.aws.amazon.com/eventbridge/latest/userguide/)

## 🤝 Contributing

1. Create feature branch from `develop`
2. Implement changes with tests
3. Run full test suite: `poetry run pytest`
4. Run linting: `poetry run black . && poetry run isort .`
5. Submit pull request

See the main [Developer Guide](../docs/developer-guide.md) for detailed contribution guidelines.