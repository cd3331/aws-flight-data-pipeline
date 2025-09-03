"""
Flight Data Pipeline Python SDK Examples
========================================

This module demonstrates how to use the Flight Data Pipeline API with Python,
including authentication, data retrieval, pagination, and error handling.

Requirements:
    pip install requests python-dateutil pandas

Usage:
    from flight_data_sdk import FlightDataClient
    
    client = FlightDataClient(api_key="your-api-key")
    flights = client.get_flights(lat_min=45.0, lat_max=47.0, lon_min=5.0, lon_max=10.0)
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Iterator, Any
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FlightDataConfig:
    """Configuration for the Flight Data SDK."""
    api_key: str
    base_url: str = "https://api.flightdata-pipeline.com/v1"
    timeout: int = 30
    max_retries: int = 3
    retry_backoff_factor: float = 0.3
    rate_limit_delay: float = 1.0
    user_agent: str = "FlightDataPython/1.0"


class FlightDataError(Exception):
    """Base exception for Flight Data API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(FlightDataError):
    """Authentication failed."""
    pass


class RateLimitError(FlightDataError):
    """Rate limit exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(FlightDataError):
    """Request validation failed."""
    pass


class NotFoundError(FlightDataError):
    """Resource not found."""
    pass


class FlightDataClient:
    """
    Python client for the Flight Data Pipeline API.
    
    This client provides methods for accessing flight data, airports,
    analytics, and system information with built-in error handling,
    pagination, and rate limiting.
    
    Example:
        client = FlightDataClient(api_key="your-api-key")
        flights = client.get_flights(lat_min=45.0, lat_max=47.0)
    """
    
    def __init__(self, config: Union[FlightDataConfig, str]):
        """
        Initialize the client.
        
        Args:
            config: FlightDataConfig object or API key string
        """
        if isinstance(config, str):
            config = FlightDataConfig(api_key=config)
        
        self.config = config
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy and authentication."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "X-API-Key": self.config.api_key,
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        return session
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make HTTP request with error handling and rate limiting.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response data
            
        Raises:
            FlightDataError: Various API errors
        """
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.config.timeout,
                **kwargs
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    retry_after=retry_after
                )
            
            # Handle authentication errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key or authentication failed")
            
            # Handle validation errors
            if response.status_code == 400:
                error_data = response.json() if response.content else {}
                raise ValidationError(
                    error_data.get("message", "Request validation failed"),
                    status_code=400,
                    response_data=error_data
                )
            
            # Handle not found
            if response.status_code == 404:
                raise NotFoundError("Resource not found", status_code=404)
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            if response.content:
                return response.json()
            else:
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise FlightDataError(f"Request failed: {str(e)}")
    
    def get_flights(self, 
                   lat_min: Optional[float] = None,
                   lat_max: Optional[float] = None,
                   lon_min: Optional[float] = None,
                   lon_max: Optional[float] = None,
                   time_start: Optional[datetime] = None,
                   time_end: Optional[datetime] = None,
                   callsign: Optional[str] = None,
                   icao24: Optional[str] = None,
                   altitude_min: Optional[float] = None,
                   altitude_max: Optional[float] = None,
                   limit: int = 50,
                   offset: int = 0) -> Dict:
        """
        Get flight data with optional filtering.
        
        Args:
            lat_min: Minimum latitude for bounding box
            lat_max: Maximum latitude for bounding box
            lon_min: Minimum longitude for bounding box
            lon_max: Maximum longitude for bounding box
            time_start: Start time for temporal filtering
            time_end: End time for temporal filtering
            callsign: Filter by callsign
            icao24: Filter by ICAO24 address
            altitude_min: Minimum altitude filter
            altitude_max: Maximum altitude filter
            limit: Maximum number of results (1-1000)
            offset: Pagination offset
            
        Returns:
            Dictionary containing flight data and metadata
            
        Example:
            # Get flights in Switzerland bounding box
            flights = client.get_flights(
                lat_min=45.8, lat_max=47.8,
                lon_min=5.9, lon_max=10.5,
                limit=100
            )
        """
        params = {}
        
        # Geographic bounds
        if lat_min is not None:
            params["lamin"] = lat_min
        if lat_max is not None:
            params["lamax"] = lat_max
        if lon_min is not None:
            params["lomin"] = lon_min
        if lon_max is not None:
            params["lomax"] = lon_max
            
        # Time range
        if time_start:
            params["time_start"] = int(time_start.timestamp())
        if time_end:
            params["time_end"] = int(time_end.timestamp())
            
        # Flight filters
        if callsign:
            params["callsign"] = callsign
        if icao24:
            params["icao24"] = icao24
        if altitude_min is not None:
            params["altitude_min"] = altitude_min
        if altitude_max is not None:
            params["altitude_max"] = altitude_max
            
        # Pagination
        params["limit"] = min(limit, 1000)
        params["offset"] = offset
        
        return self._make_request("GET", "flights", params=params)
    
    def get_flight_by_icao24(self, icao24: str) -> Dict:
        """
        Get specific flight by ICAO24 address.
        
        Args:
            icao24: ICAO24 address
            
        Returns:
            Flight data dictionary
        """
        return self._make_request("GET", f"flights/{icao24}")
    
    def get_flight_history(self, icao24: str, 
                          start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None) -> Dict:
        """
        Get flight history for an aircraft.
        
        Args:
            icao24: ICAO24 address
            start_time: History start time
            end_time: History end time
            
        Returns:
            Flight history data
        """
        params = {}
        if start_time:
            params["start_time"] = int(start_time.timestamp())
        if end_time:
            params["end_time"] = int(end_time.timestamp())
            
        return self._make_request("GET", f"flights/{icao24}/history", params=params)
    
    def get_airports(self, 
                    country: Optional[str] = None,
                    region: Optional[str] = None,
                    airport_type: Optional[str] = None,
                    limit: int = 50,
                    offset: int = 0) -> Dict:
        """
        Get airport data with optional filtering.
        
        Args:
            country: Filter by country code
            region: Filter by region
            airport_type: Filter by airport type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            Dictionary containing airport data and metadata
        """
        params = {
            "limit": min(limit, 1000),
            "offset": offset
        }
        
        if country:
            params["country"] = country
        if region:
            params["region"] = region
        if airport_type:
            params["type"] = airport_type
            
        return self._make_request("GET", "airports", params=params)
    
    def get_airport(self, identifier: str) -> Dict:
        """
        Get airport by ICAO or IATA code.
        
        Args:
            identifier: ICAO or IATA code
            
        Returns:
            Airport data dictionary
        """
        return self._make_request("GET", f"airports/{identifier}")
    
    def get_nearby_airports(self, latitude: float, longitude: float, 
                           radius_km: float = 50) -> Dict:
        """
        Get airports near a geographic point.
        
        Args:
            latitude: Latitude of center point
            longitude: Longitude of center point
            radius_km: Search radius in kilometers
            
        Returns:
            List of nearby airports
        """
        params = {
            "lat": latitude,
            "lon": longitude,
            "radius": radius_km
        }
        
        return self._make_request("GET", "airports/nearby", params=params)
    
    def get_flight_statistics(self, 
                             lat_min: Optional[float] = None,
                             lat_max: Optional[float] = None,
                             lon_min: Optional[float] = None,
                             lon_max: Optional[float] = None,
                             time_range: str = "24h") -> Dict:
        """
        Get flight statistics for a region and time period.
        
        Args:
            lat_min: Minimum latitude for bounding box
            lat_max: Maximum latitude for bounding box
            lon_min: Minimum longitude for bounding box
            lon_max: Maximum longitude for bounding box
            time_range: Time range (1h, 24h, 7d, 30d)
            
        Returns:
            Statistics data dictionary
        """
        params = {"time_range": time_range}
        
        if lat_min is not None:
            params["lamin"] = lat_min
        if lat_max is not None:
            params["lamax"] = lat_max
        if lon_min is not None:
            params["lomin"] = lon_min
        if lon_max is not None:
            params["lomax"] = lon_max
            
        return self._make_request("GET", "analytics/statistics", params=params)
    
    def get_traffic_density(self, 
                           lat_min: float, lat_max: float,
                           lon_min: float, lon_max: float,
                           grid_size: float = 0.1) -> Dict:
        """
        Get traffic density heatmap data for a region.
        
        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude
            grid_size: Grid cell size in degrees
            
        Returns:
            Traffic density data
        """
        params = {
            "lamin": lat_min,
            "lamax": lat_max,
            "lomin": lon_min,
            "lomax": lon_max,
            "grid_size": grid_size
        }
        
        return self._make_request("GET", "analytics/density", params=params)
    
    def get_health(self) -> Dict:
        """Get system health status."""
        return self._make_request("GET", "health")
    
    def get_version(self) -> Dict:
        """Get API version information."""
        return self._make_request("GET", "version")
    
    # Pagination helper methods
    
    def paginate_flights(self, **kwargs) -> Iterator[Dict]:
        """
        Generator that yields all flights across multiple pages.
        
        Args:
            **kwargs: Arguments passed to get_flights()
            
        Yields:
            Individual flight dictionaries
            
        Example:
            for flight in client.paginate_flights(lat_min=45.0, lat_max=47.0):
                print(f"Flight {flight['callsign']} at {flight['latitude']}, {flight['longitude']}")
        """
        offset = 0
        limit = kwargs.pop("limit", 100)
        
        while True:
            response = self.get_flights(limit=limit, offset=offset, **kwargs)
            flights = response.get("flights", [])
            
            if not flights:
                break
                
            for flight in flights:
                yield flight
            
            # Check if there are more pages
            if len(flights) < limit:
                break
                
            offset += limit
            
            # Be nice to the API
            time.sleep(self.config.rate_limit_delay)
    
    def paginate_airports(self, **kwargs) -> Iterator[Dict]:
        """
        Generator that yields all airports across multiple pages.
        
        Args:
            **kwargs: Arguments passed to get_airports()
            
        Yields:
            Individual airport dictionaries
        """
        offset = 0
        limit = kwargs.pop("limit", 100)
        
        while True:
            response = self.get_airports(limit=limit, offset=offset, **kwargs)
            airports = response.get("airports", [])
            
            if not airports:
                break
                
            for airport in airports:
                yield airport
            
            if len(airports) < limit:
                break
                
            offset += limit
            time.sleep(self.config.rate_limit_delay)
    
    # Utility methods
    
    def export_flights_to_csv(self, filename: str, **kwargs) -> int:
        """
        Export flights to CSV file.
        
        Args:
            filename: Output CSV filename
            **kwargs: Arguments passed to paginate_flights()
            
        Returns:
            Number of flights exported
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for CSV export. Install with: pip install pandas")
        
        flights = list(self.paginate_flights(**kwargs))
        
        if not flights:
            logger.warning("No flights found for export")
            return 0
        
        df = pd.DataFrame(flights)
        df.to_csv(filename, index=False)
        
        logger.info(f"Exported {len(flights)} flights to {filename}")
        return len(flights)
    
    def get_flights_in_area_realtime(self, 
                                   lat_min: float, lat_max: float,
                                   lon_min: float, lon_max: float,
                                   interval: int = 30) -> Iterator[List[Dict]]:
        """
        Continuously poll for flights in an area.
        
        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude
            interval: Polling interval in seconds
            
        Yields:
            Lists of flight data at each polling interval
        """
        while True:
            try:
                response = self.get_flights(
                    lat_min=lat_min, lat_max=lat_max,
                    lon_min=lon_min, lon_max=lon_max,
                    limit=1000
                )
                yield response.get("flights", [])
                
            except FlightDataError as e:
                logger.error(f"Error fetching real-time data: {e}")
                # Continue polling even if one request fails
            
            time.sleep(interval)


# Example usage and demonstrations
def main():
    """Demonstrate SDK usage with examples."""
    
    # Initialize client
    client = FlightDataClient(api_key="your-api-key-here")
    
    try:
        # Example 1: Get system health
        print("=== System Health ===")
        health = client.get_health()
        print(f"API Status: {health.get('status')}")
        print(f"Version: {health.get('version')}")
        print()
        
        # Example 2: Get flights in Switzerland
        print("=== Flights in Switzerland ===")
        swiss_flights = client.get_flights(
            lat_min=45.8, lat_max=47.8,
            lon_min=5.9, lon_max=10.5,
            limit=10
        )
        
        for flight in swiss_flights.get("flights", []):
            print(f"Flight {flight.get('callsign', 'Unknown')} at "
                  f"{flight.get('latitude'):.3f}, {flight.get('longitude'):.3f}")
        print()
        
        # Example 3: Get airports in Germany
        print("=== German Airports ===")
        german_airports = client.get_airports(country="DE", limit=5)
        
        for airport in german_airports.get("airports", []):
            print(f"{airport.get('name')} ({airport.get('icao_code')}) - "
                  f"{airport.get('city')}")
        print()
        
        # Example 4: Get flight statistics
        print("=== Flight Statistics ===")
        stats = client.get_flight_statistics(
            lat_min=45.0, lat_max=50.0,
            lon_min=5.0, lon_max=15.0,
            time_range="24h"
        )
        
        print(f"Total flights: {stats.get('total_flights', 0)}")
        print(f"Active flights: {stats.get('active_flights', 0)}")
        print(f"Average altitude: {stats.get('average_altitude', 0):.0f} ft")
        print()
        
        # Example 5: Pagination example
        print("=== Pagination Example ===")
        flight_count = 0
        for flight in client.paginate_flights(
            lat_min=45.0, lat_max=50.0,
            lon_min=0.0, lon_max=10.0
        ):
            flight_count += 1
            if flight_count >= 5:  # Just show first 5 for demo
                break
            print(f"Flight #{flight_count}: {flight.get('callsign', 'Unknown')}")
        print()
        
        # Example 6: Error handling
        print("=== Error Handling Example ===")
        try:
            # This should fail with invalid coordinates
            client.get_flights(lat_min=200, lat_max=300)
        except ValidationError as e:
            print(f"Validation error caught: {e}")
            print(f"Error details: {e.response_data}")
        print()
        
    except AuthenticationError:
        print("Authentication failed. Please check your API key.")
    except RateLimitError as e:
        print(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
    except FlightDataError as e:
        print(f"API error: {e}")


if __name__ == "__main__":
    # Note: Replace with your actual API key
    import os
    api_key = os.getenv("FLIGHT_DATA_API_KEY", "your-api-key-here")
    
    if api_key == "your-api-key-here":
        print("Please set your API key in the FLIGHT_DATA_API_KEY environment variable")
        print("or replace 'your-api-key-here' in the code with your actual API key.")
    else:
        main()