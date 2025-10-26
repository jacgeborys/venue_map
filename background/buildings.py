"""
Building Background Processing
Handles fetching and processing building data for map backgrounds.
"""
from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox


class BuildingProcessor:
    """Handles building data fetching and processing."""

    def __init__(self):
        self.client = osm_client

    def fetch_buildings(self, center_lat, center_lon, radius_km):
        """
        Fetch building data from OSM.

        Args:
            center_lat (float): Center latitude
            center_lon (float): Center longitude
            radius_km (float): Search radius

        Returns:
            dict: OSM data with building elements
        """
        bbox = calculate_bbox(center_lat, center_lon, radius_km)

        # Building query - ways and relations
        query = f"""[out:json][timeout:180][bbox:{bbox}];
(
  way["building"];
  relation["building"];
);
out geom;"""

        print(f"    Fetching buildings...")

        try:
            return self.client.query(query, "buildings", timeout=120)
        except Exception as e:
            print(f"    Failed to fetch buildings: {e}")
            return {'elements': []}

    def process_buildings(self, buildings_data, transformer):
        """
        Process building data into polygons.

        Args:
            buildings_data (dict): Raw OSM building data
            transformer: Coordinate transformer

        Returns:
            list: Building polygons as coordinate lists
        """
        buildings = []

        for element in buildings_data.get('elements', []):
            if element['type'] == 'way' and 'geometry' in element:
                # Transform coordinates
                coords = []
                for node in element['geometry']:
                    x, y = transformer.transform(node['lon'], node['lat'])
                    coords.append((x, y))

                # Close polygon if not already closed
                if len(coords) >= 3:
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    buildings.append(coords)

        return buildings

    def render_buildings(self, ax, buildings_data, style=None):
        """
        Render buildings on a matplotlib axis.

        Args:
            ax: Matplotlib axis
            buildings_data (list): Processed building polygons
            style (dict): Style configuration
        """
        if style is None:
            style = {
                'facecolor': '#e0e0e0',
                'alpha': 0.6,
                'zorder': 2,
                'linewidth': 0,
                'edgecolor': 'none'
            }

        for coords in buildings_data:
            try:
                xs, ys = zip(*coords)
                ax.fill(xs, ys, **style)
            except:
                continue


# Default building style
DEFAULT_BUILDING_STYLE = {
    'facecolor': '#e0e0e0',
    'alpha': 0.6,
    'zorder': 2,
    'linewidth': 0,
    'edgecolor': 'none'
}