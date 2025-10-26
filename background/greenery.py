"""
Greenery and Nature Areas Processing
"""
from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox

class GreeneryProcessor:
    """Handles green spaces and nature area data fetching and processing."""

    def __init__(self):
        self.client = osm_client

    def fetch_greenery(self, center_lat, center_lon, radius_km):
        """Fetch greenery and nature areas from OSM, including multipolygons."""
        bbox = calculate_bbox(center_lat, center_lon, radius_km)

        # Updated query to include multipolygon relations
        query = f"""[out:json][timeout:180][bbox:{bbox}];
    (
      way["natural"~"^(wood|forest|scrub|grassland|heath|meadow)$"];
      way["landuse"~"^(forest|grass|meadow|orchard|vineyard|recreation_ground)$"];
      way["leisure"~"^(park|garden|nature_reserve|golf_course|pitch|playground|sports_centre)$"];
      relation["natural"~"^(wood|forest|scrub|grassland|heath|meadow)$"];
      relation["landuse"~"^(forest|grass|meadow|orchard|vineyard|recreation_ground)$"];
      relation["leisure"~"^(park|garden|nature_reserve|golf_course)$"];
      relation["type"="multipolygon"]["natural"~"^(wood|forest|scrub|grassland|heath|meadow)$"];
      relation["type"="multipolygon"]["landuse"~"^(forest|grass|meadow|orchard|vineyard|recreation_ground)$"];
      relation["type"="multipolygon"]["leisure"~"^(park|garden|nature_reserve|golf_course)$"];
    );
    out geom;"""

        print(f"    Fetching greenery and nature areas...")

        try:
            return self.client.query(query, "greenery", timeout=120)
        except Exception as e:
            print(f"    Failed to fetch greenery: {e}")
            return {'elements': []}

    def process_greenery(self, greenery_data, transformer):
        """Process greenery data into polygons, including multipolygon relations."""
        greenery_areas = []

        for element in greenery_data.get('elements', []):
            if element['type'] == 'way' and 'geometry' in element:
                # Handle regular ways
                coords = []
                for node in element['geometry']:
                    x, y = transformer.transform(node['lon'], node['lat'])
                    coords.append((x, y))

                if len(coords) >= 3:
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    greenery_areas.append(coords)

            elif element['type'] == 'relation':
                # Handle multipolygon relations
                tags = element.get('tags', {})
                if tags.get('type') == 'multipolygon' and (
                        tags.get('natural') in ['wood', 'forest', 'scrub', 'grassland', 'heath', 'meadow'] or
                        tags.get('landuse') in ['forest', 'grass', 'meadow', 'orchard', 'vineyard',
                                                'recreation_ground'] or
                        tags.get('leisure') in ['park', 'garden', 'nature_reserve', 'golf_course']
                ):
                    # Process outer member ways
                    members = element.get('members', [])
                    for member in members:
                        if member.get('role') == 'outer' and member.get('type') == 'way':
                            if 'geometry' in member:
                                coords = []
                                for node in member['geometry']:
                                    x, y = transformer.transform(node['lon'], node['lat'])
                                    coords.append((x, y))

                                if len(coords) >= 3:
                                    if coords[0] != coords[-1]:
                                        coords.append(coords[0])
                                    greenery_areas.append(coords)

        return greenery_areas

    def render_greenery(self, ax, greenery_data, style=None):
        """Render greenery areas on a matplotlib axis."""
        if style is None:
            style = DEFAULT_GREENERY_STYLE

        for coords in greenery_data:
            try:
                xs, ys = zip(*coords)
                ax.fill(xs, ys, **style)
            except:
                continue

DEFAULT_GREENERY_STYLE = {
    'facecolor': '#d1e8cf',  # Slightly less pale green
    'alpha': 0.8,
    'zorder': 2,
    'linewidth': 0,
    'edgecolor': 'none'
}