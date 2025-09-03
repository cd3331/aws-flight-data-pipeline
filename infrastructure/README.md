# Infrastructure as Code

This directory contains AWS CDK (Cloud Development Kit) infrastructure definitions for the Flight Data Pipeline. All cloud resources are defined as code for consistent, reproducible deployments across environments.

## 🏗️ Architecture Overview

The infrastructure is organized into logical stacks that can be deployed independently:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │   Processing    │    │      API        │
│     Stack       │    │     Stack       │    │     Stack       │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • DynamoDB      │    │ • Lambda        │    │ • API Gateway   │
│ • ElastiCache   │    │ • EventBridge   │    │ • Lambda        │
│ • S3 Buckets    │    │ • Step Func     │    │ • CloudFront    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                    ┌─────────────────┐
                    │   Monitoring    │
                    │     Stack       │
                    ├─────────────────┤
                    │ • CloudWatch    │
                    │ • Alarms        │
                    │ • Dashboards    │
                    └─────────────────┘
```

## 📁 Directory Structure

```
infrastructure/
├── 📁 lib/                    # CDK stack definitions
│   ├── database-stack.ts         # Data storage resources
│   ├── processing-stack.ts       # Data processing pipeline
│   ├── api-stack.ts              # API and web serving
│   ├── monitoring-stack.ts       # Observability and alerting
│   └── shared/                   # Common constructs and utilities
│       ├── lambda-construct.ts   # Reusable Lambda patterns
│       ├── api-construct.ts      # API Gateway patterns  
│       └── database-construct.ts # Database patterns
├── 📁 config/                 # Environment configurations
│   ├── dev.ts                    # Development settings
│   ├── staging.ts                # Staging settings
│   ├── prod.ts                   # Production settings
│   └── common.ts                 # Shared configuration
├── 📁 tests/                  # Infrastructure tests
│   ├── unit/                     # Unit tests for constructs
│   └── integration/              # Stack integration tests
├── app.ts                     # CDK app entry point
├── cdk.json                   # CDK configuration
├── package.json              # Node.js dependencies
└── tsconfig.json             # TypeScript configuration
```

## 🚀 Quick Start

### Prerequisites
```bash
# Install Node.js 18+
node --version  # Should be 18.x or higher

# Install AWS CDK CLI
npm install -g aws-cdk

# Verify installation
cdk --version
```

### Setup
```bash
# Install dependencies
npm install

# Configure AWS credentials
aws configure
# or use AWS SSO
aws sso login --profile your-profile

# Bootstrap CDK (first time only per account/region)
cdk bootstrap --profile your-profile
```

### Deploy Infrastructure

#### Development Environment
```bash
# Deploy all stacks to development
cdk deploy --all --context environment=dev --profile dev-profile

# Deploy specific stack
cdk deploy FlightDataDatabaseStack --context environment=dev

# View what will be deployed (dry run)
cdk diff --context environment=dev
```

#### Production Environment
```bash
# Deploy with approval for sensitive changes
cdk deploy --all --context environment=prod --require-approval broadening

# Deploy with change sets for safety
cdk deploy --context environment=prod --no-execute
# Review the change set in AWS Console, then execute
```

## 📊 Stack Definitions

### 1. Database Stack (`database-stack.ts`)

**Resources Created:**
- **DynamoDB Tables**: Flight data and airports with GSIs
- **ElastiCache Redis**: API response caching
- **S3 Buckets**: Raw data storage and processed data
- **Parameter Store**: Configuration values

```typescript
export class DatabaseStack extends Stack {
  public readonly flightsTable: Table;
  public readonly airportsTable: Table;
  public readonly cacheCluster: CfnReplicationGroup;
  public readonly dataBuckets: {
    raw: Bucket;
    processed: Bucket;
    exports: Bucket;
  };

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    // DynamoDB table for flight data
    this.flightsTable = new Table(this, 'FlightsTable', {
      tableName: `flightdata-flights-${props.environment}`,
      partitionKey: { name: 'icao24', type: AttributeType.STRING },
      sortKey: { name: 'timestamp', type: AttributeType.NUMBER },
      billingMode: BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: props.environment !== 'dev',
      stream: StreamViewType.NEW_AND_OLD_IMAGES,
      // Add Global Secondary Indexes
    });

    // ElastiCache for API caching
    this.cacheCluster = new CfnReplicationGroup(this, 'CacheCluster', {
      replicationGroupDescription: 'Flight Data API Cache',
      numCacheClusters: props.environment === 'prod' ? 3 : 1,
      cacheNodeType: 'cache.t3.micro',
      engine: 'redis',
      // Additional configuration...
    });
  }
}
```

### 2. Processing Stack (`processing-stack.ts`)

**Resources Created:**
- **Lambda Functions**: Data fetching, processing, analytics
- **EventBridge Rules**: Scheduled data collection
- **SQS Queues**: Message processing with DLQs
- **Step Functions**: Complex workflow orchestration

```typescript
export class ProcessingStack extends Stack {
  constructor(scope: Construct, id: string, props: ProcessingStackProps) {
    super(scope, id, props);

    // Data fetcher Lambda
    const dataFetcher = new Function(this, 'DataFetcher', {
      functionName: `flight-data-fetcher-${props.environment}`,
      runtime: Runtime.PYTHON_3_11,
      code: Code.fromAsset('../backend/functions/flight-data-fetcher'),
      handler: 'handler.lambda_handler',
      timeout: Duration.minutes(5),
      memorySize: 512,
      environment: {
        ENVIRONMENT: props.environment,
        S3_RAW_BUCKET: props.dataBuckets.raw.bucketName,
      },
    });

    // EventBridge rule for scheduled execution
    new Rule(this, 'DataFetchRule', {
      schedule: Schedule.rate(Duration.seconds(30)),
      targets: [new LambdaFunction(dataFetcher)],
    });

    // SQS queue for processing with DLQ
    const processingDLQ = new Queue(this, 'ProcessingDLQ', {
      queueName: `flight-data-processing-dlq-${props.environment}`,
      retentionPeriod: Duration.days(14),
    });

    const processingQueue = new Queue(this, 'ProcessingQueue', {
      queueName: `flight-data-processing-${props.environment}`,
      visibilityTimeout: Duration.minutes(15),
      deadLetterQueue: {
        queue: processingDLQ,
        maxReceiveCount: 3,
      },
    });
  }
}
```

### 3. API Stack (`api-stack.ts`)

**Resources Created:**
- **API Gateway**: REST API with custom domain
- **Lambda Functions**: API request handlers
- **CloudFront Distribution**: CDN for global access
- **Route 53**: DNS configuration
- **ACM Certificate**: SSL/TLS certificates

```typescript
export class ApiStack extends Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    // API Lambda function
    const apiHandler = new Function(this, 'ApiHandler', {
      functionName: `flight-api-${props.environment}`,
      runtime: Runtime.PYTHON_3_11,
      code: Code.fromAsset('../backend/functions/flight-api'),
      handler: 'handler.lambda_handler',
      timeout: Duration.seconds(30),
      memorySize: 256,
      reservedConcurrentExecutions: props.environment === 'prod' ? 100 : undefined,
    });

    // API Gateway
    const api = new RestApi(this, 'FlightDataApi', {
      restApiName: `flight-data-api-${props.environment}`,
      description: 'Flight Data Pipeline REST API',
      deployOptions: {
        stageName: 'v1',
        throttle: {
          rateLimit: 1000,
          burstLimit: 2000,
        },
      },
      defaultCorsPreflightOptions: {
        allowOrigins: props.corsOrigins,
        allowMethods: ['GET', 'POST', 'OPTIONS'],
        allowHeaders: ['Content-Type', 'X-API-Key', 'Authorization'],
      },
    });

    // Add API resources and methods
    const flightsResource = api.root.addResource('flights');
    flightsResource.addMethod('GET', new LambdaIntegration(apiHandler));
  }
}
```

### 4. Monitoring Stack (`monitoring-stack.ts`)

**Resources Created:**
- **CloudWatch Dashboards**: System metrics visualization
- **CloudWatch Alarms**: Threshold-based alerting
- **SNS Topics**: Alert notifications
- **Lambda Functions**: Custom metric processing

```typescript
export class MonitoringStack extends Stack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    // SNS topic for alerts
    const alertTopic = new Topic(this, 'AlertTopic', {
      topicName: `flight-data-alerts-${props.environment}`,
    });

    // CloudWatch Dashboard
    const dashboard = new Dashboard(this, 'FlightDataDashboard', {
      dashboardName: `FlightDataPipeline-${props.environment}`,
    });

    // API Gateway metrics
    dashboard.addWidgets(
      new GraphWidget({
        title: 'API Gateway Metrics',
        left: [
          new Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Count',
            dimensionsMap: {
              ApiName: props.apiName,
            },
          }),
        ],
        right: [
          new Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Latency',
            dimensionsMap: {
              ApiName: props.apiName,
            },
          }),
        ],
      })
    );

    // High error rate alarm
    new Alarm(this, 'HighErrorRateAlarm', {
      alarmName: `flight-data-high-error-rate-${props.environment}`,
      metric: new Metric({
        namespace: 'AWS/ApiGateway',
        metricName: '4XXError',
        dimensionsMap: {
          ApiName: props.apiName,
        },
        statistic: 'Sum',
      }),
      threshold: 10,
      evaluationPeriods: 2,
    });
  }
}
```

## ⚙️ Configuration Management

### Environment-Specific Configuration

#### `config/dev.ts`
```typescript
export const devConfig: EnvironmentConfig = {
  environment: 'dev',
  region: 'us-east-1',
  
  database: {
    billingMode: BillingMode.PAY_PER_REQUEST,
    pointInTimeRecovery: false,
  },
  
  lambda: {
    memorySize: 256,
    timeout: Duration.seconds(30),
    reservedConcurrency: undefined,
  },
  
  api: {
    throttle: {
      rateLimit: 100,
      burstLimit: 200,
    },
    corsOrigins: ['http://localhost:3000'],
  },
  
  monitoring: {
    enableDetailedMonitoring: false,
    enableAlarming: false,
    logRetentionDays: 7,
  },
};
```

#### `config/prod.ts`
```typescript
export const prodConfig: EnvironmentConfig = {
  environment: 'prod',
  region: 'us-east-1',
  domainName: 'api.flightdata-pipeline.com',
  
  database: {
    billingMode: BillingMode.PAY_PER_REQUEST,
    pointInTimeRecovery: true,
    backupRetentionDays: 35,
  },
  
  lambda: {
    memorySize: 512,
    timeout: Duration.minutes(5),
    reservedConcurrency: 100,
    provisionedConcurrency: 10,
  },
  
  api: {
    throttle: {
      rateLimit: 2000,
      burstLimit: 5000,
    },
    corsOrigins: ['https://dashboard.flightdata-pipeline.com'],
  },
  
  monitoring: {
    enableDetailedMonitoring: true,
    enableAlarming: true,
    logRetentionDays: 365,
    alertEmail: 'alerts@flightdata-pipeline.com',
  },
};
```

### Context Variables
Pass configuration via CDK context:

```bash
# Development deployment
cdk deploy --context environment=dev --context debug=true

# Production with custom domain
cdk deploy --context environment=prod --context domainName=api.example.com
```

## 🧪 Testing Infrastructure

### Unit Tests
```bash
# Install test dependencies
npm install --save-dev @aws-cdk/assert jest @types/jest

# Run unit tests
npm test

# Run with coverage
npm run test:coverage
```

#### Example Unit Test
```typescript
import { Template } from 'aws-cdk-lib/assertions';
import { Stack } from 'aws-cdk-lib';
import { DatabaseStack } from '../lib/database-stack';

test('DynamoDB table created with correct configuration', () => {
  const app = new App();
  const stack = new DatabaseStack(app, 'TestDatabaseStack', {
    environment: 'test',
  });
  
  const template = Template.fromStack(stack);
  
  // Assert DynamoDB table exists
  template.hasResourceProperties('AWS::DynamoDB::Table', {
    BillingMode: 'PAY_PER_REQUEST',
    PointInTimeRecoverySpecification: {
      PointInTimeRecoveryEnabled: false,
    },
  });
  
  // Assert GSI exists
  template.hasResourceProperties('AWS::DynamoDB::Table', {
    GlobalSecondaryIndexes: [
      {
        IndexName: 'RegionTimeIndex',
        KeySchema: [
          { AttributeName: 'region_time', KeyType: 'HASH' },
          { AttributeName: 'timestamp', KeyType: 'RANGE' },
        ],
      },
    ],
  });
});
```

### Integration Tests
```typescript
// Test actual AWS resource creation
import { CloudFormation } from 'aws-sdk';

describe('Stack Integration Tests', () => {
  let cfn: CloudFormation;
  
  beforeAll(() => {
    cfn = new CloudFormation({ region: 'us-east-1' });
  });

  test('Database stack creates expected resources', async () => {
    const stackName = 'FlightDataDatabaseStack-test';
    
    const { Stacks } = await cfn.describeStacks({
      StackName: stackName,
    }).promise();
    
    expect(Stacks).toHaveLength(1);
    expect(Stacks[0].StackStatus).toBe('CREATE_COMPLETE');
    
    // Verify outputs
    const outputs = Stacks[0].Outputs || [];
    expect(outputs.find(o => o.OutputKey === 'FlightsTableName')).toBeDefined();
  });
});
```

## 🚀 Deployment Strategies

### Blue-Green Deployment
```typescript
// Create deployment groups for blue-green
const blueStack = new ApiStack(app, 'FlightDataApiBlue', {
  environment: 'prod',
  deploymentGroup: 'blue',
});

const greenStack = new ApiStack(app, 'FlightDataApiGreen', {
  environment: 'prod', 
  deploymentGroup: 'green',
});

// Route 53 weighted routing for traffic shifting
new ARecord(this, 'ApiRecord', {
  zone: hostedZone,
  recordName: 'api',
  target: RecordTarget.fromAlias({
    bind: () => ({
      dnsName: blueStack.distribution.domainName,
      aliasTarget: new targets.CloudFrontTarget(blueStack.distribution),
    }),
  }),
  weight: 100, // Start with 100% traffic to blue
});
```

### Canary Deployment
```typescript
// API Gateway canary deployment
const deployment = new Deployment(this, 'ApiDeployment', {
  api: restApi,
});

new Stage(this, 'ProdStage', {
  deployment,
  stageName: 'prod',
  canarySettings: {
    percentTraffic: 10, // Start with 10% canary traffic
    stageVariableOverrides: {
      lambdaAlias: 'canary',
    },
    deploymentId: deployment.deploymentId,
  },
});
```

## 📊 Cost Optimization

### Tagging Strategy
```typescript
// Apply consistent tags across all resources
const commonTags = {
  Project: 'FlightDataPipeline',
  Environment: props.environment,
  Owner: 'data-platform-team',
  CostCenter: 'engineering',
  AutoShutdown: props.environment === 'dev' ? 'true' : 'false',
};

Tags.of(this).add('Project', commonTags.Project);
Tags.of(this).add('Environment', commonTags.Environment);
```

### Resource Optimization
```typescript
// Environment-specific resource sizing
const lambdaConfig = {
  dev: {
    memorySize: 256,
    reservedConcurrency: undefined,
    provisionedConcurrency: undefined,
  },
  staging: {
    memorySize: 512,
    reservedConcurrency: 50,
    provisionedConcurrency: undefined,
  },
  prod: {
    memorySize: 1024,
    reservedConcurrency: 100,
    provisionedConcurrency: 10,
  },
}[props.environment];
```

## 🔒 Security Best Practices

### IAM Least Privilege
```typescript
// Lambda execution role with minimal permissions
const lambdaRole = new Role(this, 'LambdaExecutionRole', {
  assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
  managedPolicies: [
    ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
  ],
});

// Grant specific DynamoDB permissions
flightsTable.grantReadWriteData(lambdaRole);

// Deny access to other tables
lambdaRole.addToPolicy(new PolicyStatement({
  effect: Effect.DENY,
  actions: ['dynamodb:*'],
  resources: ['*'],
  conditions: {
    StringNotLike: {
      'dynamodb:Table': `flightdata-*-${props.environment}`,
    },
  },
}));
```

### Encryption Configuration
```typescript
// S3 bucket with encryption
const dataBucket = new Bucket(this, 'DataBucket', {
  bucketName: `flightdata-storage-${props.environment}`,
  encryption: BucketEncryption.S3_MANAGED,
  publicReadAccess: false,
  blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
  versioned: true,
  lifecycleRules: [{
    id: 'delete-old-versions',
    noncurrentVersionExpiration: Duration.days(30),
  }],
});

// DynamoDB with encryption
const flightsTable = new Table(this, 'FlightsTable', {
  encryption: TableEncryption.AWS_MANAGED,
  // Additional configuration...
});
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Bootstrap Issues
```bash
# Error: "CDK bootstrap template version is too old"
cdk bootstrap --force

# Different account/region
cdk bootstrap --profile different-profile --region eu-west-1
```

#### 2. Stack Dependencies
```bash
# Error: "Stack depends on another stack"
cdk deploy --all  # Deploy all stacks in dependency order

# Or deploy in specific order
cdk deploy DatabaseStack ProcessingStack ApiStack
```

#### 3. Resource Limits
```bash
# Error: "CREATE_FAILED: Resource limit exceeded"
# Check AWS service limits in console
aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384

# Request limit increase if needed
aws service-quotas request-service-quota-increase --service-code lambda --quota-code L-B99A9384 --desired-value 2000
```

### Debugging CDK Issues
```bash
# Verbose output
cdk deploy --verbose

# Debug mode
cdk deploy --debug

# Check CloudFormation events
aws cloudformation describe-stack-events --stack-name YourStackName

# Export template for inspection
cdk synth > template.yaml
```

## 📚 Additional Resources

### CDK Documentation
- [AWS CDK Developer Guide](https://docs.aws.amazon.com/cdk/v2/guide/)
- [CDK API Reference](https://docs.aws.amazon.com/cdk/api/v2/)
- [CDK Patterns](https://cdkpatterns.com/)
- [AWS Construct Library](https://constructs.dev/)

### Best Practices
- [CDK Best Practices](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Infrastructure as Code Best Practices](https://docs.aws.amazon.com/whitepapers/latest/introduction-devops-aws/infrastructure-as-code.html)

## 🤝 Contributing

### Development Workflow
1. Create feature branch from `develop`
2. Make infrastructure changes
3. Run tests: `npm test`
4. Deploy to dev: `cdk deploy --context environment=dev`
5. Create pull request with infrastructure diagrams
6. Peer review and approve
7. Deploy to staging for validation
8. Deploy to production with approval

### Adding New Resources
1. Add resource definition to appropriate stack
2. Update interface types if needed
3. Add unit tests for new resources
4. Update documentation and README
5. Test deployment in dev environment
6. Submit pull request with detailed description

See the main [Developer Guide](../docs/developer-guide.md) for detailed contribution guidelines.