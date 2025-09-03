# User Guide
## Flight Data Pipeline System

### 📋 Table of Contents

- [Getting Started](#getting-started)
- [Dashboard Usage](#dashboard-usage)
- [API Usage](#api-usage)
- [Data Query Guide](#data-query-guide)
- [Troubleshooting](#troubleshooting)
- [FAQ](#frequently-asked-questions)

## 🚀 Getting Started

### Overview
The Flight Data Pipeline provides real-time flight tracking and analytics through both a web dashboard and REST API. Whether you're a data analyst, developer, or aviation enthusiast, this guide will help you get the most out of the system.

### Quick Start
1. **Access the Dashboard**: Visit `https://dashboard.flightdata-pipeline.com`
2. **Get API Access**: Request an API key at `https://developers.flightdata-pipeline.com`
3. **Explore Data**: Start with our interactive tutorials and examples

### Account Types
| Feature | Free Tier | Pro | Enterprise |
|---------|-----------|-----|------------|
| API Requests/Day | 10,000 | 1,000,000 | Unlimited |
| Historical Data | 7 days | 1 year | 5 years |
| Real-time Updates | ❌ | ✅ | ✅ |
| Support Level | Community | Email | 24/7 Phone |
| Custom Analytics | ❌ | Limited | Full Access |

## 🎛️ Dashboard Usage

### Navigation Overview

```
┌─────────────────────────────────────────┐
│ Flight Data Pipeline      🔍 Search  👤 │
├─────────────────────────────────────────┤
│ 🗺️ Live Map  📊 Analytics  🛫 Flights  │
│                                         │
│ ┌─────────────┐ ┌─────────────────────┐ │
│ │   Filters   │ │    Main Content     │ │
│ │             │ │                     │ │
│ │ Geographic  │ │   Interactive Map   │ │
│ │ Time Range  │ │     or Tables       │ │
│ │ Aircraft    │ │                     │ │
│ │ Airlines    │ │                     │ │
│ └─────────────┘ └─────────────────────┘ │
│                                         │
│ Status: ✅ Online    Updates: Real-time │
└─────────────────────────────────────────┘
```

### 1. Live Map View

#### Features
- **Real-time Flight Tracking**: See aircraft positions updated every 30 seconds
- **Interactive Controls**: Zoom, pan, and click for flight details
- **Layer Controls**: Toggle airports, routes, weather overlays
- **Filtering**: Show only specific aircraft types, airlines, or routes

#### Using the Map
```
Controls:
- Mouse Wheel: Zoom in/out
- Click + Drag: Pan the map
- Click Aircraft: View flight details
- Right Click: Context menu with options

Filter Panel:
┌─────────────────┐
│ 🔍 Filters      │
├─────────────────┤
│ ☑️ Commercial   │
│ ☑️ Private      │
│ ☐ Military      │
│                 │
│ Altitude Range: │
│ ████████░░ 35k  │
│                 │
│ Airlines:       │
│ ☑️ All Selected │
│ ☐ Lufthansa     │
│ ☐ Swiss Air     │
│ ☐ British Airways│
└─────────────────┘
```

#### Flight Information Panel
When you click on an aircraft, you'll see:
```json
{
  "flight": {
    "callsign": "SWR123",
    "airline": "Swiss International Air Lines",
    "aircraft": {
      "type": "Airbus A320",
      "registration": "HB-IJK"
    },
    "route": {
      "origin": "LSZH (Zurich)",
      "destination": "EGLL (London Heathrow)",
      "progress": "67%"
    },
    "current_position": {
      "altitude": "37,000 ft",
      "speed": "485 knots",
      "heading": "285°"
    },
    "estimated_arrival": "14:35 UTC"
  }
}
```

### 2. Analytics Dashboard

#### Key Metrics Overview
```
┌─────────────────────────────────────────┐
│ 📊 Flight Analytics - Last 24 Hours    │
├─────────────────────────────────────────┤
│ Total Flights: 127,543  ↗️ +5.2%        │
│ Active Now: 8,234       ↗️ +12.1%       │
│ Avg Altitude: 35,420 ft ↘️ -0.8%        │
│ Top Route: LHR→JFK (47 flights)        │
└─────────────────────────────────────────┘
```

#### Chart Types Available

##### 1. Traffic Heatmap
Shows flight density across geographic regions:
```
Usage:
1. Select time period (1h, 24h, 7d, 30d)
2. Choose map region or global view
3. Adjust heatmap intensity
4. Export data or screenshots

Insights:
- Identify busy air corridors
- Compare traffic patterns over time
- Analyze seasonal variations
```

##### 2. Altitude Distribution
Visualizes aircraft altitude patterns:
```
Flight Count
    ↑
5000│    ████████
4000│   █████████
3000│  ██████████
2000│ ███████████
1000│████████████
    └─────────────→
     0   10k  20k  30k  40k+ Altitude
```

##### 3. Route Analytics
Most popular flight routes and their statistics:
```
Top 10 Routes (Today)
1. JFK ← → LHR: 23 flights, Avg delay: 12 min
2. FRA ← → LHR: 19 flights, Avg delay: 8 min
3. CDG ← → LHR: 17 flights, Avg delay: 15 min
...
```

#### Custom Analytics Builder
Create your own visualizations:
```
Steps:
1. Select data source (Flights, Airports, Routes)
2. Choose dimensions (Time, Geography, Aircraft)
3. Pick metrics (Count, Average, Max, Min)
4. Apply filters
5. Select visualization type
6. Save and share
```

### 3. Flight Search & Tables

#### Basic Search
```
Search Bar Features:
- Flight Number: "LH441", "BA123"
- Aircraft ID: ICAO24 hex codes
- Route: "JFK to LHR", "London Paris"
- Airline: "Lufthansa", "United"
- Registration: "N123AB", "D-ABCD"

Examples:
🔍 "Swiss 123" → Shows Swiss flight 123
🔍 "LSZH EGLL" → Flights from Zurich to London
🔍 "A320" → All Airbus A320 aircraft
```

#### Advanced Filters
```yaml
Geographic Filters:
  - Bounding Box: Draw area on map
  - Radius Search: Point + radius in km/miles
  - Country/Region: Select from dropdown
  - Airport Codes: ICAO or IATA codes

Temporal Filters:
  - Time Range: Custom start/end times
  - Relative: "Last hour", "Today", "This week"
  - Recurring: Daily/weekly patterns

Aircraft Filters:
  - Type: A320, B737, etc.
  - Age: Aircraft manufacturing date
  - Operator: Airline or private owner
  - Size Category: Light, Medium, Heavy

Flight Status:
  - Active: Currently in flight
  - Scheduled: Future departures
  - Landed: Recently completed
  - Cancelled: Cancelled flights
```

#### Table View Features
```
Flight Table Columns:
┌─────────┬─────────────┬────────┬──────────┬──────────┐
│ Callsign│ Route       │ Status │ Altitude │ Speed    │
├─────────┼─────────────┼────────┼──────────┼──────────┤
│ SWR123  │ LSZH→EGLL  │ Active │ 37,000'  │ 485 kts  │
│ LH441   │ EDDF→KJFK  │ Active │ 41,000'  │ 521 kts  │
│ BA456   │ EGLL→LFPG  │ Landed │ Ground   │ 0 kts    │
└─────────┴─────────────┴────────┴──────────┴──────────┘

Features:
✅ Sort by any column
✅ Multi-column filtering
✅ Export to CSV/Excel
✅ Real-time updates
✅ Pagination (50/100/500 rows)
```

### 4. Historical Data Analysis

#### Time Travel Feature
```
Access Historical Data:
1. Click the time picker in top navigation
2. Select date and time range
3. Choose resolution (1min, 5min, 1hour)
4. Apply to current view

Use Cases:
- Analyze traffic patterns during events
- Compare seasonal variations
- Investigate specific incidents
- Generate historical reports
```

#### Playback Mode
Watch historical flight movements:
```
Playback Controls:
⏮️ ⏸️ ▶️ ⏭️ ⏩ [====●====] 1.5x speed
00:15:30 / 02:30:00

Features:
- Speed control (0.5x to 10x)
- Jump to specific times
- Loop playback
- Export as video (Pro feature)
```

## 🔌 API Usage

### Authentication
```bash
# Add your API key to requests
curl -H "X-API-Key: your-api-key" \
     "https://api.flightdata-pipeline.com/v1/flights"

# Or use query parameter (less secure)
curl "https://api.flightdata-pipeline.com/v1/flights?api_key=your-api-key"
```

### Basic API Examples

#### 1. Get Current Flights
```bash
# All active flights (limited to 50)
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights"

# Flights in a specific area (Swiss airspace)
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?lamin=45.8&lamax=47.8&lomin=5.9&lomax=10.5"

# Response example:
{
  "flights": [
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
      "timestamp": 1705318200
    }
  ],
  "pagination": {
    "total": 1247,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

#### 2. Get Specific Flight
```bash
# By ICAO24 address
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights/4ca7b4"

# By callsign
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/flights?callsign=SWR123"
```

#### 3. Airport Information
```bash
# Get airport details
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/airports/LSZH"

# Find nearby airports
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/airports/nearby?lat=47.4647&lon=8.5492&radius=50"
```

#### 4. Analytics Endpoints
```bash
# Traffic statistics
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/analytics/statistics?time_range=24h"

# Popular routes
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/analytics/routes?limit=10"

# Traffic density heatmap
curl -H "X-API-Key: YOUR_KEY" \
     "https://api.flightdata-pipeline.com/v1/analytics/density?lamin=45&lamax=50&lomin=5&lomax=15"
```

### Python SDK Usage

#### Installation
```bash
pip install flight-data-pipeline-sdk
# or
pip install requests python-dateutil pandas  # Manual dependencies
```

#### Basic Usage
```python
from flight_data_sdk import FlightDataClient

# Initialize client
client = FlightDataClient(api_key="your-api-key")

# Get flights in Switzerland
flights = client.get_flights(
    lat_min=45.8, lat_max=47.8,
    lon_min=5.9, lon_max=10.5
)

print(f"Found {len(flights['flights'])} flights")

for flight in flights['flights']:
    print(f"Flight {flight['callsign']} at {flight['altitude']}ft")
```

#### Advanced Usage
```python
from datetime import datetime, timedelta
import pandas as pd

# Get historical flight data
end_time = datetime.now()
start_time = end_time - timedelta(hours=24)

historical_flights = client.get_flights(
    lat_min=45.8, lat_max=47.8,
    lon_min=5.9, lon_max=10.5,
    time_start=start_time,
    time_end=end_time,
    limit=1000
)

# Convert to DataFrame for analysis
df = pd.DataFrame(historical_flights['flights'])
print(f"Average altitude: {df['altitude'].mean():.0f} feet")
print(f"Most common airline: {df['callsign'].str[:3].mode()[0]}")

# Export to CSV
client.export_flights_to_csv(
    'swiss_flights.csv',
    lat_min=45.8, lat_max=47.8,
    lon_min=5.9, lon_max=10.5
)
```

#### Real-time Data Streaming
```python
# Monitor flights in real-time
for flights in client.get_flights_in_area_realtime(
    lat_min=45.8, lat_max=47.8,
    lon_min=5.9, lon_max=10.5,
    interval=30  # Check every 30 seconds
):
    print(f"Current flights in area: {len(flights)}")
    for flight in flights[:5]:  # Show first 5
        print(f"  {flight['callsign']}: {flight['altitude']}ft")
```

### JavaScript/Node.js Usage

#### Installation
```bash
npm install flight-data-client
```

#### Usage Example
```javascript
const FlightDataClient = require('flight-data-client');

const client = new FlightDataClient({
  apiKey: 'your-api-key',
  baseURL: 'https://api.flightdata-pipeline.com/v1'
});

// Get current flights
async function getCurrentFlights() {
  try {
    const flights = await client.getFlights({
      lamin: 45.8,
      lamax: 47.8,
      lomin: 5.9,
      lomax: 10.5,
      limit: 100
    });
    
    console.log(`Found ${flights.flights.length} flights`);
    return flights;
  } catch (error) {
    console.error('Error fetching flights:', error.message);
  }
}

// Real-time updates with WebSocket (if available)
client.subscribeToFlights({
  bounds: { lamin: 45.8, lamax: 47.8, lomin: 5.9, lomax: 10.5 }
}, (flights) => {
  console.log('Received real-time update:', flights.length, 'flights');
});
```

## 📊 Data Query Guide

### Understanding Coordinate Systems

#### Geographic Bounds
```
Coordinate System: WGS84 (World Geodetic System 1984)
Latitude Range: -90 to +90 degrees
Longitude Range: -180 to +180 degrees

Examples:
Switzerland: lat_min=45.8, lat_max=47.8, lon_min=5.9, lon_max=10.5
New York: lat_min=40.4, lat_max=40.9, lon_min=-74.3, lon_max=-73.7
London: lat_min=51.3, lat_max=51.7, lon_min=-0.5, lon_max=0.2

Tip: Use online tools like bboxfinder.com to find coordinates
```

#### Time Zones and Timestamps
```
Default: UTC timestamps (Unix epoch seconds)
Supported formats:
- Unix timestamp: 1705318200
- ISO 8601: "2024-01-15T14:30:00Z"
- Human readable: "2024-01-15 14:30:00 UTC"

Examples:
# Last 24 hours
start_time = current_time - 86400
end_time = current_time

# Specific date range
start_time = "2024-01-15T00:00:00Z"
end_time = "2024-01-15T23:59:59Z"
```

### Query Optimization Tips

#### 1. Efficient Geographic Queries
```yaml
✅ Good Practices:
  - Use reasonable bounding boxes (not too large)
  - Combine with time filters to reduce data
  - Consider timezone differences for local queries

❌ Avoid:
  - Global queries without time limits
  - Very small bounding boxes (< 0.1 degree)
  - Overlapping concurrent requests

Example - Efficient query:
GET /flights?lamin=45.8&lamax=47.8&lomin=5.9&lomax=10.5&limit=100&time_range=1h
```

#### 2. Pagination Best Practices
```yaml
Default Behavior:
  - limit: 50 (max: 1000)
  - offset: 0
  - sorted by timestamp (descending)

Large Dataset Handling:
# Instead of large offset values
❌ /flights?limit=100&offset=10000

# Use cursor-based pagination
✅ /flights?limit=100&cursor=eyJ0aW1lc3RhbXAiOjE3MDUz...

# Or time-based pagination
✅ /flights?limit=100&time_end=1705318200
```

#### 3. Caching and Rate Limits
```yaml
Caching Strategy:
  - API responses cached for 30-60 seconds
  - Use ETags and conditional requests
  - Cache frequently accessed data locally

Rate Limits by Tier:
  Free:     10 requests/minute, 10,000/day
  Pro:      100 requests/minute, 1,000,000/day
  Enterprise: No limits

Headers to Check:
  X-RateLimit-Remaining: 95
  X-RateLimit-Reset: 1705318260
  X-RateLimit-Limit: 100
```

### Complex Query Examples

#### 1. Multi-Airport Route Analysis
```python
# Find all flights between major European hubs
airports = ['EGLL', 'LFPG', 'EDDF', 'EHAM', 'LSZH']
routes = {}

for origin in airports:
    for destination in airports:
        if origin != destination:
            flights = client.get_flights(
                origin=origin,
                destination=destination,
                time_range='7d'
            )
            route_key = f"{origin}-{destination}"
            routes[route_key] = len(flights['flights'])

# Find busiest routes
sorted_routes = sorted(routes.items(), key=lambda x: x[1], reverse=True)
print("Busiest routes this week:")
for route, count in sorted_routes[:10]:
    print(f"{route}: {count} flights")
```

#### 2. Altitude Pattern Analysis
```python
# Analyze flight altitude patterns by time of day
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

hours = range(24)
avg_altitudes = []

for hour in hours:
    # Get flights for specific hour across multiple days
    flights_data = []
    for day in range(7):  # Last 7 days
        start_time = datetime.now().replace(hour=hour, minute=0, second=0) - timedelta(days=day)
        end_time = start_time + timedelta(hours=1)
        
        flights = client.get_flights(
            time_start=start_time,
            time_end=end_time,
            altitude_min=1000  # Only airborne flights
        )
        
        altitudes = [f['altitude'] for f in flights['flights'] if f['altitude']]
        flights_data.extend(altitudes)
    
    avg_altitude = sum(flights_data) / len(flights_data) if flights_data else 0
    avg_altitudes.append(avg_altitude)

# Plot the results
plt.plot(hours, avg_altitudes)
plt.xlabel('Hour of Day (UTC)')
plt.ylabel('Average Altitude (feet)')
plt.title('Flight Altitude Patterns by Hour')
plt.show()
```

#### 3. Real-time Alert System
```python
# Monitor for specific aircraft or unusual patterns
def monitor_aircraft(icao24_list, alert_callback):
    """Monitor specific aircraft and trigger alerts"""
    
    while True:
        for icao24 in icao24_list:
            try:
                flight = client.get_flight_by_icao24(icao24)
                
                # Check for alerts
                alerts = []
                
                # Altitude alert
                if flight.get('altitude', 0) < 1000 and flight.get('velocity', 0) > 200:
                    alerts.append(f"Low altitude at high speed: {flight['altitude']}ft at {flight['velocity']}kts")
                
                # Speed alert  
                if flight.get('velocity', 0) > 600:
                    alerts.append(f"High speed detected: {flight['velocity']}kts")
                
                # Geographic alert (example: entering restricted airspace)
                if (45.0 < flight.get('latitude', 0) < 46.0 and 
                    6.0 < flight.get('longitude', 0) < 7.0):
                    alerts.append("Aircraft entering restricted zone")
                
                if alerts:
                    alert_callback(icao24, flight, alerts)
                    
            except Exception as e:
                print(f"Error monitoring {icao24}: {e}")
        
        time.sleep(30)  # Check every 30 seconds

# Usage
def handle_alert(icao24, flight, alerts):
    print(f"ALERT for {icao24} ({flight.get('callsign', 'Unknown')}):")
    for alert in alerts:
        print(f"  - {alert}")
    
    # Could send email, SMS, webhook, etc.

# Monitor specific aircraft
monitor_aircraft(['4ca7b4', '3c4b2a'], handle_alert)
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. API Key Problems
```yaml
Issue: "Invalid API key" error
Solutions:
  - Check key format (should be 32-40 characters)
  - Verify key is active in developer portal
  - Ensure key has proper permissions
  - Check for extra spaces or special characters

Issue: "Rate limit exceeded"
Solutions:
  - Check current usage in dashboard
  - Implement exponential backoff in code
  - Consider upgrading account tier
  - Cache responses to reduce API calls

Example - Handling rate limits:
import time
import random

def api_call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = e.retry_after or (2 ** attempt + random.uniform(0, 1))
                time.sleep(wait_time)
            else:
                raise
```

#### 2. Data Quality Issues
```yaml
Issue: "No flights returned" for valid area
Causes & Solutions:
  - Time zone confusion:
    ✅ Use UTC timestamps consistently
  - Area too small or in ocean:
    ✅ Verify coordinates with mapping tool
  - Time range too narrow:
    ✅ Expand time window, check for flights manually
  - Filters too restrictive:
    ✅ Remove filters one by one to isolate issue

Issue: "Inconsistent flight positions"
Causes & Solutions:
  - Different update intervals:
    ✅ Account for 30-second update frequency
  - Network delays:
    ✅ Use timestamp field to order events
  - Multiple data sources:
    ✅ Prefer higher quality sources (check metadata)
```

#### 3. Performance Issues
```yaml
Issue: Slow API responses
Solutions:
  1. Optimize queries:
     - Use smaller geographic bounds
     - Add time range filters
     - Limit result count
  
  2. Implement caching:
     - Cache frequently accessed data
     - Use conditional requests (ETags)
     - Implement local data stores
  
  3. Use bulk operations:
     - Batch multiple requests
     - Use pagination efficiently
     - Consider WebSocket for real-time data

Example - Efficient data fetching:
# Instead of multiple small requests
for airport in airports:
    flights = client.get_flights_at_airport(airport)  # ❌ Slow

# Use single larger request with filtering
all_flights = client.get_flights(
    bounds=calculate_combined_bounds(airports),
    limit=1000
)
# Filter locally
flights_by_airport = group_flights_by_airport(all_flights)  # ✅ Fast
```

#### 4. Integration Issues
```yaml
Issue: CORS errors in browser
Solutions:
  - Use server-side proxy
  - Configure CORS headers properly
  - Use JSONP for simple requests (limited)
  - Consider WebSocket connections

Issue: SSL/TLS certificate errors
Solutions:
  - Update certificates and trust stores
  - Use proper hostname (not IP address)
  - Check firewall and proxy settings
  - Verify system time is correct

Issue: Timeout errors
Solutions:
  - Increase timeout values
  - Implement retry logic
  - Use streaming for large datasets
  - Break large requests into smaller chunks
```

### Debug Mode and Logging

#### Enable Detailed Logging
```python
import logging
from flight_data_sdk import FlightDataClient

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('flight_data_sdk')

client = FlightDataClient(
    api_key="your-key",
    debug=True  # Enables request/response logging
)

# This will now show detailed request/response info
flights = client.get_flights(lat_min=45, lat_max=47, lon_min=5, lon_max=10)
```

#### Request Tracing
```bash
# Use curl with verbose output for debugging
curl -v \
     -H "X-API-Key: YOUR_KEY" \
     -H "X-Request-ID: debug-123" \
     "https://api.flightdata-pipeline.com/v1/flights?lamin=45&lamax=47"

# Check response headers for debugging info
HTTP/1.1 200 OK
X-Request-ID: debug-123
X-Cache-Status: MISS
X-Processing-Time: 127ms
X-RateLimit-Remaining: 99
```

### Health Check and Status

#### API Health Check
```bash
# Check API status
curl "https://api.flightdata-pipeline.com/v1/health"

# Response
{
  "status": "healthy",
  "version": "1.2.3",
  "timestamp": "2024-01-15T14:30:00Z",
  "checks": {
    "database": "healthy",
    "external_apis": "healthy",
    "cache": "healthy"
  },
  "response_time_ms": 45
}
```

#### System Status Page
Check `https://status.flightdata-pipeline.com` for:
- Real-time system status
- Planned maintenance windows
- Historical uptime data
- Performance metrics
- Incident reports

## ❓ Frequently Asked Questions

### Data Questions

**Q: How often is flight data updated?**
A: Flight positions are updated every 30 seconds. Airport information and static data are updated daily.

**Q: What's the historical data retention period?**
A: 
- Free tier: 7 days
- Pro tier: 1 year  
- Enterprise: 5+ years (configurable)

**Q: Why don't I see military flights?**
A: Military aircraft often don't broadcast ADS-B signals or use encrypted transponders. We only show civilian aircraft that broadcast openly.

**Q: Are flight delays and cancellations included?**
A: Currently we focus on real-time position data. Flight status information is on our roadmap for future releases.

### Technical Questions

**Q: What's the API rate limit?**
A: Depends on your tier:
- Free: 10 requests/minute, 10,000/day
- Pro: 100 requests/minute, 1M/day
- Enterprise: Custom limits

**Q: Can I get WebSocket/real-time streaming?**
A: WebSocket support is in beta. Contact support for early access.

**Q: Is there a GraphQL API?**
A: GraphQL is in development. Current REST API covers all functionality.

**Q: What about data export formats?**
A: We support JSON (default), CSV, and are adding Parquet for large datasets.

### Business Questions

**Q: Can I use this data commercially?**
A: Yes, with Pro or Enterprise tiers. Check our terms of service for specific use cases.

**Q: Is there an SLA guarantee?**
A: Enterprise customers get 99.9% uptime SLA. Pro and Free tiers are best-effort.

**Q: Can I white-label the dashboard?**
A: Enterprise customers can customize branding and embed the dashboard.

**Q: What support is available?**
A: 
- Free: Community forum and documentation
- Pro: Email support (24-48 hour response)
- Enterprise: 24/7 phone and dedicated success manager

### Getting Help

- **Documentation**: https://docs.flightdata-pipeline.com
- **API Reference**: https://docs.flightdata-pipeline.com/api
- **Community Forum**: https://community.flightdata-pipeline.com
- **Support Email**: support@flightdata-pipeline.com
- **Status Page**: https://status.flightdata-pipeline.com

---

This user guide should get you started with the Flight Data Pipeline system. For more advanced use cases or specific integration questions, please refer to our comprehensive API documentation or contact our support team.