# In background/coastline.py

from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox


class CoastlineProcessor:
    """A dedicated processor for fetching raw coastline ways."""

    def __init__(self):
        self.client = osm_client

    def fetch_coastlines(self, center_lat, center_lon, radius_km):
        """
        Fetches all ways tagged with 'natural=coastline' within a given area.
        """
        # We use a larger radius to ensure we get coastlines that might start just outside the map bounds
        search_radius = radius_km * 2.0
        bbox = calculate_bbox(center_lat, center_lon, search_radius)

        query = f'''
        [out:json][timeout:300];
        (
          way["natural"="coastline"]({bbox});
        );
        (._;>;);
        out geom;
        '''

        print(f"    Fetching coastlines ({search_radius:.1f} km radius)...")
        try:
            # Use our robust client to get the data as JSON
            response_json = self.client.query(query, data_type="coastlines")
            print(f"    ✓ Found {len(response_json.get('elements', []))} coastline ways.")
            return response_json
        except Exception as e:
            print(f"    ✗ Failed to fetch coastlines: {e}")
            return {'elements': []}