"""
Gastronomy Data Fetcher
Handles fetching venue data from OpenStreetMap for gastronomy mapping.
"""
from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox


class GastronomyDataFetcher:
    """Handles fetching gastronomy venue data from OSM."""

    def __init__(self):
        self.client = osm_client

    def fetch_venues(self, center_lat, center_lon, radius_km, category):
        """Fetch venue data for a specific category, including both nodes and ways."""
        bbox = calculate_bbox(center_lat, center_lon, radius_km)

        # Define queries for each category - include both nodes AND ways
        if category == 'bars':
            query = f"""[out:json][timeout:180][bbox:{bbox}];
    (
      node["amenity"="bar"];
      node["amenity"="pub"];
      way["amenity"="bar"];
      way["amenity"="pub"];
    );
    out geom;"""
        elif category == 'cafes':
            query = f"""[out:json][timeout:180][bbox:{bbox}];
    (
      node["amenity"="cafe"];
      node["shop"="bakery"];
      node["shop"="pastry"];
      way["amenity"="cafe"];
      way["shop"="bakery"];
      way["shop"="pastry"];
    );
    out geom;"""
        elif category == 'restaurants':
            query = f"""[out:json][timeout:180][bbox:{bbox}];
    (
      node["amenity"="restaurant"];
      node["amenity"="fast_food"];
      way["amenity"="restaurant"];
      way["amenity"="fast_food"];
    );
    out geom;"""
        elif category == 'clubs':
            query = f"""[out:json][timeout:180][bbox:{bbox}];
    (
      node["amenity"="nightclub"];
      way["amenity"="nightclub"];
    );
    out geom;"""
        else:
            raise ValueError(f"Unknown venue category: {category}")

        print(f"    Fetching {category}...")
        return self.client.query(query, category)

    def fetch_all_venues(self, center_lat, center_lon, radius_km, include_clubs=False):
        """Fetch all venue categories for a location."""
        categories = ['bars', 'cafes', 'restaurants']
        if include_clubs:
            categories.append('clubs')

        venues_data = {}

        for category in categories:
            try:
                data = self.fetch_venues(center_lat, center_lon, radius_km, category)
                venues_data[category] = data
                venue_count = len(data.get('elements', []))
                print(f"    Found {venue_count} {category}")
            except Exception as e:
                print(f"    Error fetching {category}: {e}")
                venues_data[category] = {'elements': []}

        return venues_data