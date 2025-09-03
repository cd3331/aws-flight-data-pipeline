# Flight Data Generator

This directory contains scripts for generating and analyzing flight data for testing the pipeline.

## generate_sample_data.py

Generates realistic test flight data that mimics the OpenSky Network API format.

### Features

- **Realistic Flight Data**: Based on actual airports, airlines, and aircraft performance
- **Multiple Flight Phases**: Ground, takeoff, climb, cruise, descent, approach, landing
- **Data Quality Issues**: Configurable percentage of records with various quality problems
- **OpenSky Format**: Matches the exact format expected by the ingestion Lambda
- **Comprehensive Testing**: Includes edge cases and anomalies

### Usage

```bash
# Generate 1000 records with default settings
python3 scripts/analysis/generate_sample_data.py

# Generate specific number of records
python3 scripts/analysis/generate_sample_data.py --records 500

# Generate multiple files for testing
python3 scripts/analysis/generate_sample_data.py --records 1000 --files 5

# Custom quality issues percentage
python3 scripts/analysis/generate_sample_data.py --records 1000 --quality-issues 0.2

# Generate with summary statistics
python3 scripts/analysis/generate_sample_data.py --records 1000 --summary

# Custom output directory
python3 scripts/analysis/generate_sample_data.py --output /tmp/test-data/
```

### Command Line Options

- `--records N`: Number of records per file (default: 1000)
- `--files N`: Number of files to generate (default: 1)
- `--output DIR`: Output directory (default: data/sample/raw/)
- `--quality-issues FLOAT`: Percentage of records with issues (default: 0.15)
- `--summary`: Print dataset summary after generation

### Data Quality Issues Included

1. **Missing Critical Fields**: icao24, longitude, latitude
2. **Missing Optional Fields**: callsign, country, squawk, sensors
3. **Invalid Coordinates**: Longitude/latitude outside valid ranges
4. **Impossible Altitudes**: Negative or extremely high altitudes
5. **Impossible Speeds**: Negative or supersonic speeds
6. **Inconsistent Ground Status**: On ground but high altitude/speed
7. **Future Timestamps**: Timestamps in the future
8. **Old Timestamps**: Very old timestamps (>24 hours)
9. **Invalid ICAO24**: Wrong format or length
10. **Null Island**: Coordinates at (0, 0)
11. **Duplicate ICAO24**: Same aircraft identifier

### Output Format

The script generates JSON files in OpenSky Network API format:

```json
{
  "time": 1756827045,
  "states": [
    [
      "icao24",      // 0: ICAO24 identifier
      "callsign",    // 1: Callsign
      "country",     // 2: Origin country
      1756826734,    // 3: Time position
      1756826761,    // 4: Last contact
      -118.4081,     // 5: Longitude
      33.9425,       // 6: Latitude
      10668.0,       // 7: Barometric altitude (m)
      false,         // 8: On ground
      231.5,         // 9: Velocity (m/s)
      158.97,        // 10: True track
      1.12,          // 11: Vertical rate
      2,             // 12: Sensors
      10700.0,       // 13: Geometric altitude (m)
      "1200",        // 14: Squawk
      false,         // 15: SPI
      1              // 16: Position source
    ]
  ]
}
```

### Realistic Data Elements

- **18 Major Airports**: JFK, LAX, LHR, NRT, etc.
- **18 Airlines**: American, Delta, British Airways, JAL, etc.
- **10 Aircraft Types**: A320, B737, A380, B777, etc.
- **7 Flight Phases**: Each with appropriate altitude/speed ranges
- **Geographic Routing**: Realistic flight paths between airports

### Testing Your Pipeline

1. **Generate test data**:
   ```bash
   python3 scripts/analysis/generate_sample_data.py --records 1000 --files 3 --quality-issues 0.2
   ```

2. **Upload to S3** (for testing ingestion Lambda):
   ```bash
   aws s3 cp data/sample/raw/ s3://your-raw-bucket/ --recursive
   ```

3. **Test data quality validator**:
   - Generate data with high quality issues percentage
   - Verify alerts are triggered appropriately
   - Check CloudWatch metrics

4. **Performance testing**:
   - Generate large datasets (10,000+ records)
   - Test Lambda timeouts and memory limits
   - Validate processing times