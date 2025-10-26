"""
Road Network Background
Handles fetching and processing road network data for map backgrounds.
"""
from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox
from matplotlib.collections import LineCollection

class RoadNetworkProcessor:
    """Handles road network data fetching and processing."""

    ROAD_QUERIES = {
        'comprehensive': [
            'way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]',
            'way["highway"~"^(motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]',
            'way["highway"~"^(residential)$"]',
            'way["railway"~"^(rail|light_rail|subway|tram)$"]'
        ],
        'simple': [
            'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|motorway_link|trunk_link|primary_link)$"]',
            'way["railway"~"^(rail|light_rail|subway|tram)$"]'
        ]
    }

    ROAD_HIERARCHY = {
        'major': ['motorway', 'trunk', 'primary', 'motorway_link', 'trunk_link', 'primary_link'],
        'medium': ['secondary', 'tertiary', 'secondary_link', 'tertiary_link'],
        'minor': ['residential', 'living_street'],
        'railway': ['rail', 'light_rail', 'subway', 'tram']
    }


    def __init__(self):
        self.client = osm_client

    def fetch_roads(self, center_lat, center_lon, radius_km):
        """
        Fetch road network data from OSM.

        Args:
            center_lat (float): Center latitude
            center_lon (float): Center longitude
            radius_km (float): Search radius

        Returns:
            dict: OSM data with road elements
        """
        bbox = calculate_bbox(center_lat, center_lon, radius_km)

        # Build comprehensive query
        road_parts = self.ROAD_QUERIES['comprehensive']
        road_union = ';\n  '.join(road_parts) + ';'

        primary_query = f"""[out:json][timeout:180][bbox:{bbox}];
(
  {road_union}
);
out geom;"""

        # Build simple fallback query
        simple_parts = self.ROAD_QUERIES['simple']
        simple_union = ';\n  '.join(simple_parts) + ';'

        fallback_query = f"""[out:json][timeout:120][bbox:{bbox}];
{simple_union[0]};
out geom;"""

        print(f"    Fetching road network...")

        try:
            return self.client.query_with_fallback(
                primary_query,
                fallback_query,
                "roads"
            )
        except Exception as e:
            print(f"    Failed to fetch roads: {e}")
            return {'elements': []}

    def process_roads(self, roads_data, transformer):
        """
        Process road data into hierarchical categories.

        Args:
            roads_data (dict): Raw OSM road data
            transformer: Coordinate transformer

        Returns:
            dict: Roads organized by hierarchy (major, medium, minor)
        """
        roads = {
            'major': [],
            'medium': [],
            'minor': []
        }

        for element in roads_data.get('elements', []):
            if element['type'] == 'way' and 'geometry' in element:
                highway = element.get('tags', {}).get('highway', '')

                # Transform coordinates
                coords = []
                for node in element['geometry']:
                    x, y = transformer.transform(node['lon'], node['lat'])
                    coords.append((x, y))

                if len(coords) >= 2:
                    # Classify road by hierarchy
                    road_category = self._classify_road(highway)
                    if road_category:
                        roads[road_category].append(coords)

        return roads

    def _classify_road(self, highway):
        """Classify a highway/railway type into hierarchy category."""
        for category, types in self.ROAD_HIERARCHY.items():
            if highway in types:
                return category
        return None

    def process_roads(self, roads_data, transformer):
        """Process road data into hierarchical categories including railways."""
        roads = {
            'major': [],
            'medium': [],
            'minor': [],
            'railway': []
        }

        for element in roads_data.get('elements', []):
            if element['type'] == 'way' and 'geometry' in element:
                tags = element.get('tags', {})
                highway = tags.get('highway', '')
                railway = tags.get('railway', '')

                # Transform coordinates
                coords = []
                for node in element['geometry']:
                    x, y = transformer.transform(node['lon'], node['lat'])
                    coords.append((x, y))

                if len(coords) >= 2:
                    # Classify by highway or railway
                    road_type = highway if highway else railway
                    road_category = self._classify_road(road_type)
                    if road_category:
                        roads[road_category].append(coords)

        return roads

    def render_roads(self, ax, roads_data, styles):
        for road_type, roads in roads_data.items():
            if road_type in styles and roads:
                style = styles[road_type]
                line_collection = LineCollection(roads, colors=style['color'],
                                               linewidths=style['linewidth'],
                                               alpha=style['alpha'], zorder=style['zorder'])
                ax.add_collection(line_collection)

# Default road styles - white roads on top with extremely pale background colors
DEFAULT_ROAD_STYLES = {
    'major': {
        'color': '#ffffff',     # Pure white
        'linewidth': 2.5,
        'alpha': 1.0,
        'zorder': 4
    },
    'medium': {
        'color': '#ffffff',     # Pure white
        'linewidth': 1.8,
        'alpha': 1.0,
        'zorder': 4
    },
    'minor': {
        'color': '#ffffff',     # Pure white
        'linewidth': 1.0,
        'alpha': 1.0,
        'zorder': 4
    },
    'railway': {
        'color': '#fcfcfc',     # Very slightly gray
        'linewidth': 0.6,
        'alpha': 1.0,
        'zorder': 4
    }
}