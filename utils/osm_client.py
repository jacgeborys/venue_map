"""
OpenStreetMap API Client
Shared client for all OSM data fetching with retry logic and error handling.
"""
import requests
import time
from config.settings import OVERPASS_URL, MAX_RETRIES, INITIAL_RETRY_DELAY

class OSMClient:
    """Shared OSM client with retry logic and error handling."""

    def __init__(self):
        self.url = OVERPASS_URL
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_RETRY_DELAY

    def query(self, overpass_query, data_type="data", timeout=60):
        """Execute an Overpass query with retry logic."""
        retries = 0

        while retries < self.max_retries:
            try:
                if retries > 0:
                    delay = self.initial_delay * (2 ** (retries - 1))
                    print(f"    Waiting {delay}s before retry {retries + 1}/{self.max_retries} for {data_type}...")
                    time.sleep(delay)
                else:
                    time.sleep(1)  # Small delay between requests

                response = requests.post(
                    self.url,
                    data={"data": overpass_query},
                    timeout=timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    print(f"    Bad request (400) for {data_type}")
                    raise RuntimeError(f"Bad request for {data_type}. Check query syntax.")
                elif response.status_code in [429, 504]:
                    delay = max(self.initial_delay * (2 ** retries), 20)
                    print(f"    Overpass API {response.status_code} for {data_type}. Waiting {delay}s...")
                    time.sleep(delay)
                    retries += 1
                else:
                    print(f"    Unexpected status code {response.status_code} for {data_type}")
                    raise RuntimeError(f"Overpass error: {response.status_code}")

            except requests.exceptions.RequestException as e:
                delay = self.initial_delay * (2 ** retries)
                print(f"    Network error for {data_type}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                retries += 1

        raise RuntimeError(f"Failed to fetch {data_type} data after {self.max_retries} retries")

    def query_with_fallback(self, primary_query, fallback_query, data_type="data", timeout=60):
        """Execute a query with a fallback option if the primary fails."""
        try:
            return self.query(primary_query, data_type, timeout)
        except RuntimeError as e:
            if "Bad request" in str(e) and fallback_query:
                print(f"    Primary query failed, trying fallback for {data_type}...")
                time.sleep(1)
                return self.query(fallback_query, f"{data_type} (fallback)", timeout)
            else:
                raise

# Global client instance
osm_client = OSMClient()