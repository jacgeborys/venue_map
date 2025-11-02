# In utils/osm_client.py

import requests
import time

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 20

class OSMClient:
    def __init__(self):
        self.url = OVERPASS_URL
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_RETRY_DELAY

    def query(self, overpass_query, data_type="data", timeout=300):
        retries = 0
        while retries < self.max_retries:
            try:
                time.sleep(2)
                print(f"    -> Sending query for {data_type}...")
                response = requests.post(self.url, data={"data": overpass_query}, timeout=timeout)
                if response.status_code == 200:
                    print(f"    ✓ Successfully received {data_type}.")
                    return response.json()
                elif response.status_code == 400:
                    print(f"    ✗ Bad request (400) for {data_type}.")
                    raise RuntimeError(f"Bad request for {data_type}.")
                elif response.status_code in [429, 504]:
                    delay = self.initial_delay * (2 ** retries)
                    print(f"    ! Server busy ({response.status_code}). Waiting {delay}s...")
                    time.sleep(delay)
                    retries += 1
                else: raise RuntimeError(f"Overpass error: {response.status_code}")
            except requests.exceptions.RequestException as e:
                delay = self.initial_delay * (2 ** retries)
                print(f"    ! Network error: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                retries += 1
        raise RuntimeError(f"Failed to fetch {data_type} after {self.max_retries} retries")

    def query_with_fallback(self, primary_query, fallback_query, data_type="data", timeout=300):
        try:
            return self.query(primary_query, data_type, timeout)
        except RuntimeError as e:
            if "Bad request" in str(e) and fallback_query:
                print(f"    Primary query failed, trying fallback...")
                return self.query(fallback_query, f"{data_type} (fallback)", timeout)
            else: raise

osm_client = OSMClient()