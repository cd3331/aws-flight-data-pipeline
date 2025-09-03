# Technical Architecture Document
## Flight Data Pipeline System

### 📋 Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagrams](#architecture-diagrams)
- [Data Flow](#data-flow)
- [Component Design](#component-design)
- [Technology Stack](#technology-stack)
- [Design Decisions](#design-decisions)
- [Security Architecture](#security-architecture)
- [Performance & Scalability](#performance--scalability)

## 🏗️ System Overview

The Flight Data Pipeline is a cloud-native, event-driven system designed to collect, process, and serve real-time flight data at scale. The architecture follows microservices patterns with serverless compute, managed databases, and event-driven communication.

### Key Characteristics
- **Real-time Processing**: Sub-second data ingestion and processing
- **High Availability**: 99.9% uptime with multi-region deployment
- **Scalability**: Auto-scaling to handle 10M+ requests/day
- **Cost Optimization**: Serverless-first approach with pay-per-use pricing
- **Data Quality**: Built-in validation and enrichment pipelines

## 📊 Architecture Diagrams

### High-Level System Architecture

```mermaid
graph TB
    subgraph "External Data Sources"
        A1[OpenSky Network API]
        A2[ADS-B Exchange]
        A3[Airport Databases]
    end
    
    subgraph "AWS Cloud Infrastructure"
        subgraph "Data Ingestion Layer"
            B1[API Gateway]
            B2[Lambda - Data Fetcher]
            B3[EventBridge]
            B4[SQS Dead Letter Queue]
        end
        
        subgraph "Processing Layer"
            C1[Lambda - Data Processor]
            C2[Lambda - Data Validator]
            C3[Lambda - Data Enricher]
            C4[Step Functions]
        end
        
        subgraph "Storage Layer"
            D1[DynamoDB - Flight Data]
            D2[DynamoDB - Airport Data]
            D3[S3 - Raw Data Archive]
            D4[S3 - Processed Data]
            D5[ElastiCache - Redis]
        end
        
        subgraph "API Layer"
            E1[API Gateway - REST]
            E2[Lambda - API Handlers]
            E3[Lambda - GraphQL Resolver]
            E4[AppSync - GraphQL]
        end
        
        subgraph "Analytics Layer"
            F1[Lambda - Analytics]
            F2[Athena - Data Query]
            F3[QuickSight - BI]
            F4[CloudWatch - Metrics]
        end
        
        subgraph "Frontend Layer"
            G1[CloudFront CDN]
            G2[S3 - Static Hosting]
            G3[React Dashboard]
        end
    end
    
    subgraph "Clients"
        H1[Web Dashboard]
        H2[Mobile Apps]
        H3[Third-party APIs]
        H4[Analytics Tools]
    end
    
    %% Data Sources to Ingestion
    A1 --> B1
    A2 --> B1
    A3 --> B2
    
    %% Ingestion Flow
    B1 --> B2
    B2 --> B3
    B3 --> C1
    B2 -.-> B4
    
    %% Processing Flow
    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> D1
    C4 --> D2
    
    %% Storage Flow
    C1 --> D3
    C3 --> D4
    E2 --> D5
    
    %% API Flow
    E1 --> E2
    E2 --> D1
    E2 --> D2
    E4 --> E3
    E3 --> D1
    
    %% Analytics Flow
    F1 --> D1
    F2 --> D4
    F1 --> F4
    F3 --> F2
    
    %% Frontend Flow
    G1 --> G2
    G2 --> G3
    G3 --> E1
    G3 --> E4
    
    %% Client Access
    H1 --> G1
    H2 --> E1
    H3 --> E1
    H4 --> F3
```

### Detailed Component Architecture

```mermaid
graph TB
    subgraph "API Gateway Layer"
        AG1[REST API Gateway]
        AG2[WebSocket API Gateway]
        AG3[Rate Limiting]
        AG4[Request Validation]
        AG5[CORS Handling]
    end
    
    subgraph "Lambda Functions"
        L1[flight-data-fetcher]
        L2[flight-data-processor]
        L3[flight-data-validator]
        L4[flight-api-handler]
        L5[airport-api-handler]
        L6[analytics-processor]
        L7[websocket-handler]
    end
    
    subgraph "Data Stores"
        DS1[DynamoDB Tables]
        DS2[S3 Buckets]
        DS3[ElastiCache]
        DS4[Parameter Store]
    end
    
    subgraph "Event Processing"
        EP1[EventBridge Rules]
        EP2[SQS Queues]
        EP3[SNS Topics]
        EP4[Step Functions]
    end
    
    subgraph "Monitoring & Observability"
        M1[CloudWatch Logs]
        M2[CloudWatch Metrics]
        M3[X-Ray Tracing]
        M4[CloudTrail Audit]
    end
    
    AG1 --> AG3
    AG1 --> AG4
    AG1 --> AG5
    AG1 --> L4
    AG1 --> L5
    AG2 --> L7
    
    L1 --> EP1
    L2 --> DS1
    L3 --> DS1
    L4 --> DS1
    L4 --> DS3
    L5 --> DS1
    L6 --> DS2
    
    EP1 --> EP2
    EP2 --> L2
    EP2 --> L3
    EP3 --> L6
    EP4 --> L1
    EP4 --> L2
    
    L1 -.-> M1
    L2 -.-> M1
    L3 -.-> M1
    L4 -.-> M2
    L5 -.-> M3
    L6 -.-> M4
```

## 🔄 Data Flow

### Real-time Data Ingestion Flow

```mermaid
sequenceDiagram
    participant EXT as External APIs
    participant SF as Step Functions
    participant LF as Lambda Fetcher
    participant EB as EventBridge
    participant SQS as SQS Queue
    participant LP as Lambda Processor
    participant DDB as DynamoDB
    participant S3 as S3 Storage
    participant CDN as CloudFront
    
    Note over SF: Scheduled every 30 seconds
    SF->>+LF: Trigger data fetch
    LF->>+EXT: Request flight data
    EXT-->>-LF: Return flight data (JSON)
    
    alt Success
        LF->>EB: Publish DataReceived event
        LF->>S3: Store raw data
        EB->>SQS: Queue processing job
        SQS->>+LP: Process flight data
        LP->>LP: Validate & enrich data
        LP->>DDB: Store processed data
        LP->>EB: Publish DataProcessed event
        EB->>CDN: Invalidate cache
        LP-->>-SQS: Ack message
    else Failure
        LF->>SQS: Send to DLQ
        SQS->>+LP: Retry processing
        LP-->>-SQS: Ack or DLQ
    end
    
    LF-->>-SF: Complete execution
```

### API Request Flow

```mermaid
sequenceDiagram
    participant Client as API Client
    participant CF as CloudFront
    participant AG as API Gateway
    participant LH as Lambda Handler
    participant Cache as ElastiCache
    participant DDB as DynamoDB
    participant CW as CloudWatch
    
    Client->>+CF: GET /v1/flights
    CF->>CF: Check edge cache
    
    alt Cache Hit
        CF-->>Client: Return cached response
    else Cache Miss
        CF->>+AG: Forward request
        AG->>AG: Validate API key
        AG->>AG: Check rate limits
        AG->>+LH: Invoke handler
        
        LH->>+Cache: Check cache
        alt Cache Hit
            Cache-->>-LH: Return cached data
        else Cache Miss
            LH->>+DDB: Query flight data
            DDB-->>-LH: Return results
            LH->>Cache: Store in cache (TTL: 30s)
        end
        
        LH->>CW: Log metrics
        LH-->>-AG: Return response
        AG-->>-CF: Return response
        CF->>CF: Cache response (TTL: 60s)
        CF-->>Client: Return response
    end
```

### Data Processing Pipeline

```mermaid
flowchart TD
    A[Raw Flight Data] --> B{Data Quality Check}
    B -->|Pass| C[Schema Validation]
    B -->|Fail| D[Error Queue]
    
    C -->|Valid| E[Data Enrichment]
    C -->|Invalid| D
    
    E --> F[Geospatial Processing]
    F --> G[Aircraft Info Lookup]
    G --> H[Route Calculation]
    
    H --> I{Processing Complete}
    I -->|Success| J[Store in DynamoDB]
    I -->|Error| K[Retry Logic]
    
    J --> L[Update Cache]
    L --> M[Publish Event]
    M --> N[Analytics Update]
    
    K --> O{Retry Count < 3}
    O -->|Yes| E
    O -->|No| D
    
    D --> P[Dead Letter Queue]
    P --> Q[Manual Review]
```

## 🧩 Component Design

### Lambda Functions Architecture

#### 1. Flight Data Fetcher
```yaml
Function: flight-data-fetcher
Runtime: Python 3.11
Memory: 512 MB
Timeout: 5 minutes
Trigger: EventBridge (every 30 seconds)

Environment Variables:
  - OPENSKY_API_URL
  - OPENSKY_USERNAME (from SSM)
  - OPENSKY_PASSWORD (from SSM)
  - S3_RAW_BUCKET
  - EVENTBRIDGE_BUS_NAME

Permissions:
  - S3: PutObject on raw data bucket
  - EventBridge: PutEvents
  - SSM: GetParameter (for credentials)
  - CloudWatch: Logs and Metrics
```

#### 2. Flight Data Processor
```yaml
Function: flight-data-processor
Runtime: Python 3.11
Memory: 1024 MB
Timeout: 15 minutes
Trigger: SQS Queue (batch size: 10)

Environment Variables:
  - DYNAMODB_FLIGHTS_TABLE
  - DYNAMODB_AIRPORTS_TABLE
  - REDIS_CLUSTER_ENDPOINT
  - GEOCODING_API_KEY

Permissions:
  - DynamoDB: Read/Write on flights and airports tables
  - ElastiCache: Redis cluster access
  - SQS: ReceiveMessage, DeleteMessage
  - EventBridge: PutEvents
```

#### 3. API Handler Functions
```yaml
Function: flight-api-handler
Runtime: Python 3.11
Memory: 256 MB
Timeout: 30 seconds
Trigger: API Gateway

Layers:
  - aws-lambda-powertools
  - requests-layer
  - geopy-layer

Environment Variables:
  - DYNAMODB_FLIGHTS_TABLE
  - REDIS_CLUSTER_ENDPOINT
  - CORS_ORIGINS
  - MAX_PAGE_SIZE: 1000

Reserved Concurrency: 100
Provisioned Concurrency: 10 (for warm starts)
```

### Database Design

#### DynamoDB Tables

##### Flights Table
```json
{
  "TableName": "flightdata-flights-prod",
  "AttributeDefinitions": [
    {"AttributeName": "icao24", "AttributeType": "S"},
    {"AttributeName": "timestamp", "AttributeType": "N"},
    {"AttributeName": "region_time", "AttributeType": "S"}
  ],
  "KeySchema": [
    {"AttributeName": "icao24", "KeyType": "HASH"},
    {"AttributeName": "timestamp", "KeyType": "RANGE"}
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "RegionTimeIndex",
      "KeySchema": [
        {"AttributeName": "region_time", "KeyType": "HASH"},
        {"AttributeName": "timestamp", "KeyType": "RANGE"}
      ],
      "Projection": {"ProjectionType": "ALL"}
    }
  ],
  "BillingMode": "PAY_PER_REQUEST",
  "StreamSpecification": {
    "StreamEnabled": true,
    "StreamViewType": "NEW_AND_OLD_IMAGES"
  },
  "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": true}
}
```

##### Airports Table
```json
{
  "TableName": "flightdata-airports-prod",
  "AttributeDefinitions": [
    {"AttributeName": "icao_code", "AttributeType": "S"},
    {"AttributeName": "country_region", "AttributeType": "S"},
    {"AttributeName": "iata_code", "AttributeType": "S"}
  ],
  "KeySchema": [
    {"AttributeName": "icao_code", "KeyType": "HASH"}
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "CountryRegionIndex",
      "KeySchema": [
        {"AttributeName": "country_region", "KeyType": "HASH"}
      ]
    },
    {
      "IndexName": "IataCodeIndex", 
      "KeySchema": [
        {"AttributeName": "iata_code", "KeyType": "HASH"}
      ]
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### S3 Bucket Structure
```
flightdata-storage-prod/
├── raw/
│   ├── year=2024/month=01/day=15/hour=14/
│   │   ├── flights-20240115-140000.json.gz
│   │   └── flights-20240115-143000.json.gz
│   └── airports/
│       └── airports-reference-20240101.json
├── processed/
│   ├── flights/
│   │   ├── year=2024/month=01/day=15/
│   │   │   ├── region=europe/flights.parquet
│   │   │   └── region=americas/flights.parquet
│   │   └── aggregates/
│   │       └── daily/2024-01-15-summary.json
│   └── analytics/
│       ├── traffic-density/
│       └── route-statistics/
└── exports/
    ├── user-exports/
    └── scheduled-reports/
```

## 💻 Technology Stack

### Cloud Infrastructure (AWS)
```yaml
Compute:
  - AWS Lambda (Serverless functions)
  - AWS Step Functions (Workflow orchestration)
  - AWS Fargate (Container workloads - future)

Storage:
  - Amazon DynamoDB (NoSQL database)
  - Amazon S3 (Object storage)
  - Amazon ElastiCache Redis (In-memory cache)
  - AWS Systems Manager Parameter Store (Configuration)

Networking:
  - Amazon API Gateway (REST & WebSocket APIs)
  - Amazon CloudFront (CDN)
  - AWS AppSync (GraphQL API - future)
  - Amazon VPC (Network isolation)

Integration:
  - Amazon EventBridge (Event routing)
  - Amazon SQS (Message queuing)
  - Amazon SNS (Notifications)

Monitoring:
  - Amazon CloudWatch (Metrics & Logs)
  - AWS X-Ray (Distributed tracing)
  - AWS CloudTrail (API auditing)

Analytics:
  - Amazon Athena (SQL queries on S3)
  - Amazon QuickSight (Business Intelligence)
  - AWS Glue (Data catalog & ETL)
```

### Development Stack
```yaml
Languages:
  - Python 3.11 (Backend services)
  - JavaScript/TypeScript (Frontend)
  - SQL (Analytics queries)
  - YAML (Infrastructure as Code)

Frameworks & Libraries:
  Backend:
    - AWS Lambda Powertools (Python)
    - Boto3 (AWS SDK)
    - Pydantic (Data validation)
    - Requests (HTTP client)
    - GeoPy (Geospatial processing)
    
  Frontend:
    - React 18
    - TypeScript
    - Material-UI
    - React Query
    - Leaflet (Maps)
    - Chart.js (Visualizations)

Infrastructure:
  - AWS CDK (Infrastructure as Code)
  - Docker (Local development)
  - GitHub Actions (CI/CD)
  - Terraform (Alternative IaC)

Development Tools:
  - Poetry (Python dependency management)
  - Pre-commit hooks (Code quality)
  - Black (Python formatting)
  - ESLint/Prettier (JavaScript formatting)
  - pytest (Python testing)
  - Jest (JavaScript testing)
```

### Third-party Services
```yaml
Data Sources:
  - OpenSky Network API (Primary flight data)
  - ADS-B Exchange (Backup flight data)
  - OurAirports Database (Airport information)

External APIs:
  - Google Maps API (Geocoding - future)
  - Weather API (Weather data - future)
  - Aircraft Database API (Aircraft details - future)

Monitoring:
  - Datadog (APM - optional)
  - Sentry (Error tracking - future)
  - PagerDuty (Alerting - production)
```

## 🎯 Design Decisions

### 1. Serverless-First Architecture

**Decision**: Use AWS Lambda for all compute workloads
```yaml
Rationale:
  - Cost Efficiency: Pay only for actual usage
  - Auto Scaling: Handles traffic spikes automatically
  - Maintenance: No server management required
  - Development Speed: Focus on business logic

Trade-offs:
  - Cold Starts: Initial latency for infrequent functions
  - Vendor Lock-in: AWS-specific implementation
  - Debugging Complexity: Distributed system challenges
  - Resource Limits: 15-minute max execution time

Mitigations:
  - Provisioned Concurrency: For critical functions
  - Keep Functions Warm: Periodic invocation
  - Multi-cloud Strategy: Planned for future
  - Function Composition: Break down long processes
```

### 2. NoSQL Database Choice

**Decision**: DynamoDB as primary database
```yaml
Rationale:
  - Performance: Single-digit millisecond latency
  - Scalability: Handles millions of requests/second
  - Managed Service: No database administration
  - Cost Model: Pay per request pricing

Trade-offs:
  - Query Flexibility: Limited compared to SQL
  - Learning Curve: NoSQL data modeling complexity
  - Vendor Lock-in: AWS-specific features

Mitigations:
  - Careful Schema Design: Optimize access patterns
  - Global Secondary Indexes: Support multiple queries
  - DynamoDB Streams: Event-driven architectures
  - Data Export: Regular backups to S3
```

### 3. Event-Driven Architecture

**Decision**: EventBridge for service communication
```yaml
Rationale:
  - Decoupling: Services communicate asynchronously
  - Scalability: Handle high-volume events
  - Reliability: Built-in retry and DLQ
  - Extensibility: Easy to add new consumers

Implementation:
  Event Types:
    - FlightDataReceived
    - FlightDataProcessed
    - DataQualityAlert
    - RateLimitExceeded
    - SystemHealthCheck

  Event Flow:
    Producer → EventBridge → Rule → Target (Lambda/SQS)
```

### 4. Caching Strategy

**Decision**: Multi-layered caching approach
```yaml
Layers:
  1. CloudFront (Edge caching): 60-second TTL
  2. ElastiCache Redis (Application caching): 30-second TTL
  3. DynamoDB (Database caching): Built-in caching

Cache Keys:
  - API Responses: "flights:bounds:{hash}:page:{n}"
  - Airport Data: "airport:{icao_code}"
  - Analytics: "analytics:{type}:{timerange}:{hash}"

Invalidation Strategy:
  - Time-based expiration
  - Event-driven invalidation
  - Manual cache clearing for emergencies
```

### 5. Data Partitioning Strategy

**Decision**: Time and geographic-based partitioning
```yaml
DynamoDB Partitioning:
  Primary Key: icao24 (Aircraft identifier)
  Sort Key: timestamp (Time-based ordering)
  GSI: region_time (Geographic + temporal queries)

S3 Partitioning:
  Path: /year=YYYY/month=MM/day=DD/hour=HH/
  Benefits:
    - Efficient date-range queries
    - Parallel processing
    - Lifecycle management
    - Cost optimization

Rationale:
  - Query Patterns: Most queries are time-based
  - Hot Partitioning: Distribute load evenly
  - Data Lifecycle: Older data accessed less frequently
```

### 6. API Design Philosophy

**Decision**: RESTful API with GraphQL option
```yaml
REST API:
  - Simple to understand and implement
  - Wide client support
  - HTTP caching benefits
  - Clear resource-based URLs

GraphQL (Planned):
  - Flexible data fetching
  - Reduces over/under-fetching
  - Single endpoint
  - Real-time subscriptions

API Versioning:
  Strategy: URL path versioning (/v1/, /v2/)
  Rationale: Clear, explicit, and cacheable
```

## 🔐 Security Architecture

### Authentication & Authorization
```yaml
API Authentication:
  Method: API Key in X-API-Key header
  Storage: AWS API Gateway usage plans
  Rotation: 90-day automatic rotation
  Scoping: Per-client rate limits and quotas

Future Enhancements:
  - OAuth 2.0 / JWT tokens
  - Role-based access control (RBAC)
  - IP whitelisting
  - Request signing (HMAC)
```

### Data Protection
```yaml
Encryption:
  In Transit:
    - TLS 1.3 for all API endpoints
    - Certificate management via ACM
    - HTTPS redirect enforcement
  
  At Rest:
    - DynamoDB: AWS managed keys
    - S3: AES-256 encryption
    - ElastiCache: Encryption at rest and in transit
    - Lambda: Environment variables encrypted

Access Control:
  - IAM roles with least privilege principle
  - VPC endpoints for AWS service access
  - Security groups and NACLs
  - CloudTrail for audit logging
```

### Security Monitoring
```yaml
Threat Detection:
  - AWS GuardDuty (Threat detection)
  - AWS Config (Compliance monitoring)
  - CloudWatch alarms (Anomaly detection)
  - API Gateway throttling (DDoS protection)

Incident Response:
  - Automated alerting via SNS
  - Runbook automation
  - Security event logging
  - Regular security reviews
```

## ⚡ Performance & Scalability

### Performance Targets
```yaml
Latency Requirements:
  - API Response Time: < 200ms (P95)
  - Data Processing: < 5 minutes end-to-end
  - Cache Hit Ratio: > 80%
  - Error Rate: < 0.1%

Throughput Requirements:
  - API Requests: 10,000 requests/minute
  - Data Ingestion: 1MB/minute sustained
  - Concurrent Users: 1,000 simultaneous
  - Geographic Distribution: Global access
```

### Scalability Design
```yaml
Horizontal Scaling:
  - Lambda: Automatic scaling up to 1,000 concurrent executions
  - DynamoDB: On-demand scaling
  - API Gateway: Handles any traffic volume
  - CloudFront: Global edge locations

Vertical Scaling:
  - Lambda Memory: 128MB to 10GB per function
  - DynamoDB: Provisioned capacity for predictable workloads
  - ElastiCache: Cluster scaling for memory needs

Auto-scaling Policies:
  - CPU-based: Scale when CPU > 70%
  - Request-based: Scale when requests > threshold
  - Schedule-based: Pre-scale for known peaks
  - Predictive scaling: ML-based scaling (future)
```

### Performance Optimization
```yaml
Database Optimization:
  - Query optimization with proper indexes
  - Connection pooling
  - Read replicas for read-heavy workloads
  - Data archiving for historical data

Application Optimization:
  - Function warming strategies
  - Async processing for non-critical tasks
  - Batch processing for bulk operations
  - Memory-efficient data structures

Network Optimization:
  - CDN for static content and API responses
  - Compression (gzip) for API responses
  - Keep-alive connections
  - Geographic distribution of resources
```

## 🔍 Monitoring & Observability

### Metrics Collection
```yaml
Business Metrics:
  - API response times by endpoint
  - Data freshness and quality scores
  - User engagement and retention
  - Cost per request and data point

System Metrics:
  - Lambda function duration and errors
  - DynamoDB throttling and capacity
  - API Gateway request counts and latency
  - Cache hit rates and memory usage

Custom Metrics:
  - Flight data accuracy scores
  - Geographic coverage metrics
  - Data pipeline health scores
  - Client application performance
```

### Logging Strategy
```yaml
Centralized Logging:
  - All logs aggregated in CloudWatch Logs
  - Structured JSON logging format
  - Log retention policies (30 days default)
  - Log encryption and access controls

Log Levels:
  - ERROR: System errors and failures
  - WARN: Performance issues and anomalies
  - INFO: Business events and milestones
  - DEBUG: Detailed troubleshooting info (dev only)

Correlation:
  - Request ID tracking across services
  - User session tracking
  - Distributed tracing with X-Ray
  - Error context and stack traces
```

### Alerting & Notifications
```yaml
Alert Categories:
  Critical:
    - API error rate > 1%
    - Data pipeline failure
    - Security breach detection
    - Service unavailability
  
  Warning:
    - Response time > 500ms
    - Cache hit rate < 70%
    - Cost anomaly detection
    - Data quality issues

Notification Channels:
  - Email for non-urgent alerts
  - SMS for critical issues
  - Slack for team notifications
  - PagerDuty for escalation (production)
```

---

This technical architecture document provides a comprehensive view of the system design, technology choices, and implementation decisions. The architecture is designed for scalability, reliability, and cost-effectiveness while maintaining high performance and security standards.