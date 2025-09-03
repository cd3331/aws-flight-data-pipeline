# API Documentation

This directory contains comprehensive API documentation, specifications, and client examples for the Flight Data Pipeline API.

## 📋 Overview

The Flight Data Pipeline provides a RESTful API and GraphQL interface for accessing real-time flight data, airport information, and aviation analytics. The API is designed for high performance, scalability, and developer ease-of-use.

**Base URL**: `https://api.flightdata-pipeline.com/v1`

## 📁 Documentation Files

| File | Description | Purpose |
|------|-------------|---------|
| [`openapi.yaml`](openapi.yaml) | OpenAPI 3.0.3 specification | Complete REST API documentation with request/response schemas |
| [`graphql-schema.graphql`](graphql-schema.graphql) | GraphQL schema definition | Query, mutation, and subscription definitions |
| [`python-sdk-examples.py`](python-sdk-examples.py) | Python SDK implementation | Complete client library with examples |
| [`postman-collection.json`](postman-collection.json) | Postman collection | Ready-to-use API testing collection |
| [`versioning-strategy.md`](versioning-strategy.md) | API versioning guide | Version management and deprecation policies |

## 🚀 Quick Start

### 1. Get API Access
```bash
# Request API key at https://developers.flightdata-pipeline.com
# Or use demo key for testing (limited requests)
export API_KEY="demo-key"
```

### 2. Basic API Call
```bash
# Get flights in Switzerland
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?lamin=45.8&lamax=47.8&lomin=5.9&lomax=10.5&limit=10"
```

### 3. Python SDK
```python
from flight_data_sdk import FlightDataClient

client = FlightDataClient(api_key="your-api-key")
flights = client.get_flights(lat_min=45.8, lat_max=47.8, lon_min=5.9, lon_max=10.5)

for flight in flights['flights'][:5]:
    print(f"✈️  {flight.get('callsign', 'Unknown')} at {flight['altitude']}ft")
```

## 🔌 API Endpoints Overview

### Core Endpoints

#### Flight Data
```
GET    /flights                    # List flights with filtering
GET    /flights/{icao24}          # Get specific flight by ICAO24
GET    /flights/{icao24}/history  # Get flight history
```

#### Airport Information
```
GET    /airports                  # List airports
GET    /airports/{code}           # Get airport by ICAO/IATA code
GET    /airports/nearby           # Find airports near coordinates
```

#### Analytics
```
GET    /analytics/statistics      # Flight statistics and metrics
GET    /analytics/density         # Traffic density heatmap data
GET    /analytics/routes          # Popular routes analysis
```

#### System Information
```
GET    /health                    # API health check
GET    /version                   # API version information
```

### Request Examples

#### Geographic Filtering
```bash
# Flights in specific region
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?lamin=45.0&lamax=50.0&lomin=5.0&lomax=15.0"

# Flights above 30,000 feet
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?altitude_min=30000"

# Specific airline flights
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?callsign=SWR*"
```

#### Pagination
```bash
# First page (50 results)
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?limit=50&offset=0"

# Second page
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?limit=50&offset=50"
```

#### Airport Queries
```bash
# Airport details
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/airports/LSZH"

# Nearby airports (50km radius)
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/airports/nearby?lat=47.4647&lon=8.5492&radius=50"
```

#### Analytics
```bash
# Traffic statistics for last 24 hours
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/analytics/statistics?time_range=24h"

# Traffic density heatmap
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/analytics/density?lamin=45&lamax=50&lomin=5&lomax=15&grid_size=1.0"
```

## 📊 Response Formats

### Standard Response Structure
```json
{
  "flights": [...],
  "pagination": {
    "total": 1247,
    "limit": 50,
    "offset": 0,
    "has_more": true
  },
  "metadata": {
    "request_id": "req_abc123",
    "processing_time_ms": 127,
    "cached": false,
    "api_version": "1.2.0"
  }
}
```

### Flight Data Example
```json
{
  "icao24": "4ca7b4",
  "callsign": "SWR123",
  "origin": "LSZH",
  "destination": "EGLL",
  "latitude": 46.5234,
  "longitude": 7.1234,
  "altitude": 37000,
  "velocity": 485,
  "heading": 285,
  "vertical_rate": 0.0,
  "timestamp": 1705318200,
  "on_ground": false,
  "aircraft": {
    "registration": "HB-JCA",
    "type": "A320",
    "manufacturer": "Airbus"
  }
}
```

### Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid latitude bounds",
    "details": [
      {
        "field": "lamin",
        "value": 200,
        "message": "Latitude must be between -90 and 90"
      }
    ],
    "suggestions": [
      "Check coordinate values are within valid ranges",
      "Use geographic tools to verify bounding box"
    ]
  },
  "request_id": "req_def456",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## 🔑 Authentication & Authorization

### API Key Authentication
```bash
# Header-based (recommended)
curl -H "X-API-Key: your-api-key" "https://api.flightdata-pipeline.com/v1/flights"

# Query parameter (less secure)
curl "https://api.flightdata-pipeline.com/v1/flights?api_key=your-api-key"
```

### Rate Limits by Tier

| Tier | Requests/Minute | Requests/Day | Features |
|------|-----------------|--------------|----------|
| **Free** | 10 | 10,000 | Basic endpoints |
| **Pro** | 100 | 1,000,000 | All endpoints + history |
| **Enterprise** | Unlimited | Unlimited | Custom + SLA |

### Rate Limit Headers
```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705318260
X-RateLimit-RetryAfter: 60
```

## 🌐 GraphQL API (Beta)

### Endpoint
```
POST https://api.flightdata-pipeline.com/graphql
```

### Example Query
```graphql
query GetFlightsInRegion($bounds: GeographicBounds!, $limit: Int) {
  flights(filters: { bounds: $bounds }, pagination: { limit: $limit }) {
    edges {
      node {
        icao24
        callsign
        latitude
        longitude
        altitude
        aircraft {
          registration
          type
          manufacturer
        }
      }
    }
    pageInfo {
      hasNextPage
      totalCount
    }
  }
}
```

### Variables
```json
{
  "bounds": {
    "latMin": 45.8,
    "latMax": 47.8,
    "lonMin": 5.9,
    "lonMax": 10.5
  },
  "limit": 10
}
```

### Subscription Example
```graphql
subscription FlightUpdates($bounds: GeographicBounds!) {
  flightUpdates(filters: { bounds: $bounds }) {
    icao24
    callsign
    latitude
    longitude
    altitude
    timestamp
  }
}
```

## 📱 Client SDKs

### Python SDK
```python
# Installation
pip install flight-data-pipeline-sdk

# Usage
from flight_data_sdk import FlightDataClient

client = FlightDataClient(api_key="your-key")

# Basic usage
flights = client.get_flights(lat_min=45, lat_max=47)

# Advanced usage with pagination
for flight in client.paginate_flights(lat_min=45, lat_max=47):
    print(f"Flight: {flight['callsign']}")

# Real-time monitoring
for flights in client.get_flights_in_area_realtime(45, 47, 5, 10):
    print(f"Current flights: {len(flights)}")
```

### JavaScript/Node.js SDK
```javascript
// Installation
npm install flight-data-client

// Usage
const FlightDataClient = require('flight-data-client');

const client = new FlightDataClient({ apiKey: 'your-key' });

// Basic usage
const flights = await client.getFlights({
  lamin: 45, lamax: 47, lomin: 5, lomax: 10
});

// Real-time subscriptions (WebSocket)
client.subscribeToFlights({
  bounds: { lamin: 45, lamax: 47, lomin: 5, lomax: 10 }
}, (flights) => {
  console.log('Real-time update:', flights.length, 'flights');
});
```

### cURL Examples
```bash
# Health check
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/health"

# Specific flight lookup
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights/4ca7b4"

# Airport search
curl -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/airports?country=CH&limit=5"
```

## 📊 Postman Collection

### Import Collection
1. Download [`postman-collection.json`](postman-collection.json)
2. Open Postman
3. Click "Import" → "Upload Files"
4. Select the collection file
5. Update environment variables with your API key

### Environment Variables
```json
{
  "api_key": "your-api-key-here",
  "base_url": "https://api.flightdata-pipeline.com/v1",
  "test_icao24": "4ca7b4",
  "swiss_lat_min": "45.8389",
  "swiss_lat_max": "47.8229",
  "swiss_lon_min": "5.9962",
  "swiss_lon_max": "10.5226"
}
```

### Automated Tests
The collection includes automated tests that verify:
- Response status codes
- Response time thresholds
- Data structure validation
- Rate limit headers
- CORS configuration
- Error handling

## 📈 Performance Guidelines

### Best Practices
```yaml
Geographic Queries:
  ✅ Use reasonable bounding boxes (not too large)
  ✅ Combine geographic and time filters
  ✅ Consider timezone differences for local queries
  ❌ Avoid global queries without time limits

Pagination:
  ✅ Use limit parameter (max 1000)
  ✅ Implement offset-based pagination for consistency
  ✅ Cache responses locally when possible
  ❌ Don't use very large offset values

Caching:
  ✅ Respect cache headers (ETags, Last-Modified)
  ✅ Implement client-side caching for frequently accessed data
  ✅ Use conditional requests when data hasn't changed
  ❌ Don't over-request the same data
```

### Response Times
- **P50 (Median)**: 127ms
- **P95**: 198ms
- **P99**: 342ms
- **Target**: <500ms for all requests

### Optimization Tips
```python
# Good: Efficient geographic query
flights = client.get_flights(
    lat_min=45.8, lat_max=47.8,
    lon_min=5.9, lon_max=10.5,
    time_range='1h',  # Reduce dataset size
    limit=100
)

# Better: Use caching for repeated requests
@cache_response(ttl=30)  # Cache for 30 seconds
def get_regional_flights():
    return client.get_flights(lat_min=45, lat_max=47)

# Best: Batch requests when possible
# Instead of multiple airport requests
airports = ['LSZH', 'EGLL', 'LFPG']
for airport in airports:
    client.get_airport(airport)  # Multiple requests

# Use geographic search
nearby_airports = client.get_nearby_airports(
    lat=47.0, lon=8.0, radius=500  # Single request
)
```

## 🔍 Debugging & Troubleshooting

### Common Issues

#### 1. Authentication Errors
```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "Invalid or missing API key"
  }
}
```
**Solutions:**
- Verify API key format (32-40 characters)
- Check key is active in developer portal
- Ensure key is passed in X-API-Key header

#### 2. Rate Limiting
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds."
  }
}
```
**Solutions:**
- Implement exponential backoff
- Cache responses to reduce API calls
- Consider upgrading to higher tier
- Check current usage in developer dashboard

#### 3. Invalid Parameters
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid latitude bounds",
    "details": [
      {
        "field": "lamin",
        "value": 200,
        "message": "Latitude must be between -90 and 90"
      }
    ]
  }
}
```
**Solutions:**
- Validate coordinates before making requests
- Use geographic tools to verify bounding boxes
- Check parameter names and formats

### Debug Mode
```python
# Enable debug logging in Python SDK
import logging
logging.basicConfig(level=logging.DEBUG)

client = FlightDataClient(api_key="your-key", debug=True)
flights = client.get_flights(lat_min=45, lat_max=47)
```

```bash
# Verbose cURL requests
curl -v -H "X-API-Key: $API_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights"
```

### Response Headers for Debugging
```http
HTTP/1.1 200 OK
X-Request-ID: req_abc123
X-Processing-Time: 127ms
X-Cache-Status: MISS
X-RateLimit-Remaining: 99
X-API-Version: 1.2.0
```

## 📚 Additional Resources

### Documentation Links
- **Interactive API Docs**: [docs.flightdata-pipeline.com](https://docs.flightdata-pipeline.com)
- **OpenAPI Specification**: [View openapi.yaml](openapi.yaml)
- **GraphQL Playground**: [api.flightdata-pipeline.com/graphql](https://api.flightdata-pipeline.com/graphql)
- **Status Page**: [status.flightdata-pipeline.com](https://status.flightdata-pipeline.com)

### Developer Resources
- **Developer Portal**: [developers.flightdata-pipeline.com](https://developers.flightdata-pipeline.com)
- **Community Forum**: [community.flightdata-pipeline.com](https://community.flightdata-pipeline.com)
- **Code Examples**: [GitHub Examples Repository](https://github.com/flightdata-pipeline/examples)
- **API Changelog**: [changelog.flightdata-pipeline.com](https://changelog.flightdata-pipeline.com)

### Support Channels
- **Email Support**: [api-support@flightdata-pipeline.com](mailto:api-support@flightdata-pipeline.com)
- **Discord Community**: [discord.gg/flightdata](https://discord.gg/flightdata)
- **GitHub Issues**: [Report API Issues](https://github.com/flightdata-pipeline/api-issues)

## 🔄 API Versioning

The Flight Data Pipeline API uses semantic versioning with URL path versioning:

- **Current Version**: v1.2.0
- **Endpoint Format**: `/v1/endpoint`
- **Deprecation Policy**: 12-month notice period
- **Migration Support**: Comprehensive guides and tools

See [versioning-strategy.md](versioning-strategy.md) for complete details on version management, deprecation policies, and migration procedures.

## 🤝 Contributing

We welcome contributions to improve the API documentation:

1. **Identify Issues**: Found unclear documentation or missing examples?
2. **Suggest Improvements**: Open an issue with specific suggestions
3. **Contribute Examples**: Add code examples in different languages
4. **Test Documentation**: Verify examples work correctly
5. **Submit Pull Requests**: Help improve documentation quality

### Documentation Standards
- **Clear Examples**: Provide working code samples
- **Consistent Format**: Follow established documentation patterns
- **Error Handling**: Include error scenarios and solutions
- **Performance Notes**: Add optimization tips where relevant

---

**Built with ❤️ for developers**

For questions or support, reach out to [api-support@flightdata-pipeline.com](mailto:api-support@flightdata-pipeline.com)