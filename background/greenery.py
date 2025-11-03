# In background/greenery.py

from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.validation import make_valid


class GreeneryProcessor:
    """
    Handles fetching, processing, and rendering of categorized green spaces,
    working directly and robustly with the standard Overpass JSON format.
    Enhanced to properly handle complex multipolygons with many member ways.
    """
    FOREST_TAGS = {"natural": {"wood", "forest"}, "landuse": {"forest"}}
    FARMLAND_TAGS = {"landuse": {"farmland", "meadow", "grass", "orchard", "vineyard", "allotments"},
                     "natural": {"grassland", "heath", "scrub"}}
    LEISURE_TAGS = {"leisure": {"park", "garden", "golf_course", "recreation_ground", "pitch", "playground"}}

    def __init__(self):
        self.client = osm_client

    def fetch_greenery(self, center_lat, center_lon, radius_km):
        """Fetches all greenery and returns it as a standard JSON dictionary."""
        bbox = calculate_bbox(center_lat, center_lon, radius_km)

        natural_tags = "wood|forest|scrub|grassland|heath|meadow"
        landuse_tags = "forest|meadow|farmland|orchard|vineyard|recreation_ground|allotments|grass"
        leisure_tags = "park|garden|golf_course|pitch|playground"

        # FIXED QUERY: Use a two-stage approach to ensure we get relations with members in the area
        query = f"""
        [out:json][timeout:300];
        (
          // First: Get all ways in the area
          way["natural"~"^({natural_tags})$"]({bbox});
          way["landuse"~"^({landuse_tags})$"]({bbox});
          way["leisure"~"^({leisure_tags})$"]({bbox});

          // Second: Get relations that have members in the area (not just bbox-filtered relations)
          rel(bw)["natural"~"^({natural_tags})$"]["type"="multipolygon"];
          rel(bw)["landuse"~"^({landuse_tags})$"]["type"="multipolygon"];
          rel(bw)["leisure"~"^({leisure_tags})$"]["type"="multipolygon"];

          // Third: Also include relations directly in the bbox as backup
          relation["natural"~"^({natural_tags})$"]({bbox});
          relation["landuse"~"^({landuse_tags})$"]({bbox});
          relation["leisure"~"^({leisure_tags})$"]({bbox});
        );
        (._;>;);
        out geom;
        """
        print(f"    Fetching all greenery types with enhanced relation detection...")
        try:
            # --- THE CRITICAL FIX: Return the raw JSON, NOT an Overpy object ---
            response_json = self.client.query(query, "greenery")
            print(f"    ✓ Found {len(response_json.get('elements', []))} greenery features.")
            return response_json
        except Exception as e:
            print(f"    ✗ Failed to fetch greenery: {e}")
            return {'elements': []}

    def _classify_element(self, tags):
        """Classifies an element's tags into one of our defined categories."""
        if any(tags.get(k) in v for k, v in self.FOREST_TAGS.items()): return "forest"
        if any(tags.get(k) in v for k, v in self.FARMLAND_TAGS.items()): return "farmland"
        if any(tags.get(k) in v for k, v in self.LEISURE_TAGS.items()): return "leisure"
        return "forest"  # Default to forest if no specific match (for untagged greenery)

    def _stitch_ways_into_rings(self, way_segments):
        """
        Takes a list of LineString segments and stitches them together into closed rings.
        This is crucial for complex multipolygons with many member ways.
        """
        if not way_segments:
            return []

        rings = []
        remaining_segments = way_segments.copy()

        while remaining_segments:
            # Start a new ring with the first remaining segment
            current_ring = [remaining_segments.pop(0)]
            ring_complete = False

            while not ring_complete and remaining_segments:
                ring_end = current_ring[-1].coords[-1]  # Last point of current ring

                # Find a segment that connects to the end of our current ring
                for i, segment in enumerate(remaining_segments):
                    segment_start = segment.coords[0]
                    segment_end = segment.coords[-1]

                    # Check if this segment connects to our ring end
                    if self._points_are_close(ring_end, segment_start):
                        # Segment connects normally
                        current_ring.append(remaining_segments.pop(i))
                        break
                    elif self._points_are_close(ring_end, segment_end):
                        # Segment connects but needs to be reversed
                        reversed_coords = list(reversed(segment.coords))
                        reversed_segment = LineString(reversed_coords)
                        current_ring.append(reversed_segment)
                        remaining_segments.pop(i)
                        break
                else:
                    # No connecting segment found, try to close the ring
                    ring_start = current_ring[0].coords[0]
                    ring_end = current_ring[-1].coords[-1]

                    if self._points_are_close(ring_start, ring_end):
                        ring_complete = True
                    else:
                        # Ring can't be completed, abandon it
                        break

            # Convert the ring segments into a single coordinate list
            if ring_complete or len(current_ring) == 1:
                try:
                    ring_coords = []
                    for segment in current_ring:
                        if not ring_coords:
                            ring_coords.extend(segment.coords)
                        else:
                            # Skip the first coordinate to avoid duplication
                            ring_coords.extend(segment.coords[1:])

                    # Ensure the ring is closed
                    if len(ring_coords) >= 3:
                        if not self._points_are_close(ring_coords[0], ring_coords[-1]):
                            ring_coords.append(ring_coords[0])
                        rings.append(ring_coords)
                except:
                    continue

        return rings

    def _points_are_close(self, p1, p2, tolerance=1e-6):
        """Check if two points are within tolerance distance."""
        return abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance

    def process_greenery(self, greenery_data, transformer):
        """
        Processes a standard {'elements':...} list into categorized polygons,
        correctly handling all multipolygons with holes from the raw JSON.
        Enhanced to handle complex relations with many member ways.
        """
        processed_greenery = {"forest": [], "farmland": [], "leisure": []}
        elements = greenery_data.get('elements', [])
        if not elements: return processed_greenery

        # Create a lookup for ways by ID
        ways_by_id = {}
        for el in elements:
            if el.get('type') == 'way':
                ways_by_id[el.get('id')] = el

        ways_in_relations = {m.get('ref') for el in elements if el.get('type') == 'relation' for m in
                             el.get('members', [])}

        # Process relations first to build multipolygons correctly
        for el in elements:
            if el['type'] == 'relation' and el.get('tags', {}).get('type') == 'multipolygon':
                category = self._classify_element(el.get('tags', {}))

                outer_way_segments, inner_way_segments = [], []

                # Collect all member ways and convert them to LineStrings
                for member in el.get('members', []):
                    if member.get('type') == 'way':
                        way_id = member.get('ref')
                        role = member.get('role', '')

                        # Try to get the way either from the member geometry or the ways lookup
                        coords = None
                        if 'geometry' in member:
                            coords = [transformer.transform(n['lon'], n['lat']) for n in member['geometry']]
                        elif way_id in ways_by_id:
                            way_data = ways_by_id[way_id]
                            if 'geometry' in way_data:
                                coords = [transformer.transform(n['lon'], n['lat']) for n in way_data['geometry']]

                        if coords and len(coords) >= 2:
                            try:
                                line_segment = LineString(coords)
                                if role == 'outer':
                                    outer_way_segments.append(line_segment)
                                elif role == 'inner':
                                    inner_way_segments.append(line_segment)
                                else:
                                    # If no role specified, assume outer
                                    outer_way_segments.append(line_segment)
                            except:
                                continue

                try:
                    if not outer_way_segments:
                        continue

                    # Stitch the way segments into complete rings
                    outer_rings = self._stitch_ways_into_rings(outer_way_segments)
                    inner_rings = self._stitch_ways_into_rings(inner_way_segments)

                    if not outer_rings:
                        continue

                    # Create polygons from the rings
                    outer_polygons = []
                    for ring_coords in outer_rings:
                        try:
                            if len(ring_coords) >= 4:  # Need at least 4 points for a valid polygon
                                poly = make_valid(Polygon(ring_coords))
                                if not poly.is_empty:
                                    outer_polygons.append(poly)
                        except:
                            continue

                    inner_polygons = []
                    for ring_coords in inner_rings:
                        try:
                            if len(ring_coords) >= 4:
                                poly = make_valid(Polygon(ring_coords))
                                if not poly.is_empty:
                                    inner_polygons.append(poly)
                        except:
                            continue

                    if not outer_polygons:
                        continue

                    # Create the final polygon by cutting the inner holes from the outer shell(s)
                    unified_outer = make_valid(unary_union(outer_polygons))
                    poly_with_holes = unified_outer

                    if inner_polygons:
                        unified_inner = make_valid(unary_union(inner_polygons))
                        poly_with_holes = unified_outer.difference(unified_inner)

                    if poly_with_holes and not poly_with_holes.is_empty:
                        # Handle both single Polygons and MultiPolygons that result from the difference
                        geoms = list(poly_with_holes.geoms) if hasattr(poly_with_holes, 'geoms') else [poly_with_holes]
                        for poly in geoms:
                            if isinstance(poly, Polygon):
                                processed_greenery[category].append(
                                    {'exterior': list(poly.exterior.coords),
                                     'holes': [list(i.coords) for i in poly.interiors]}
                                )
                except Exception as e:
                    print(f"    Warning: Failed to process complex relation {el.get('id', 'unknown')}: {e}")
                    continue

        # Process simple ways that were not part of any relation
        for el in elements:
            if el['type'] == 'way' and el.get('id') not in ways_in_relations:
                category = self._classify_element(el.get('tags', {}))
                coords_raw = el.get('geometry', [])
                if len(coords_raw) < 3: continue
                coords = [transformer.transform(n['lon'], n['lat']) for n in coords_raw]
                if coords[0] != coords[-1]: coords.append(coords[0])
                try:
                    processed_greenery[category].append({'exterior': coords, 'holes': []})
                except Exception:
                    continue

        return processed_greenery

    def render_greenery(self, ax, greenery_data, styles):
        """
        Renders the categorized greenery using Matplotlib's Path object, which
        correctly handles polygons with holes.
        """
        from matplotlib.path import Path
        import matplotlib.patches as patches

        for category, polygons_data in greenery_data.items():
            style = styles.get(category)
            if not style: continue

            for poly_data in polygons_data:
                try:
                    exterior = poly_data.get('exterior', [])
                    if len(exterior) < 3: continue

                    path_verts = list(exterior)
                    path_codes = [Path.MOVETO] + [Path.LINETO] * (len(exterior) - 2) + [Path.CLOSEPOLY]

                    for hole in poly_data.get('holes', []):
                        if len(hole) < 3: continue
                        path_verts.extend(hole)
                        path_codes.extend([Path.MOVETO] + [Path.LINETO] * (len(hole) - 2) + [Path.CLOSEPOLY])

                    path = Path(path_verts, path_codes)
                    patch = patches.PathPatch(path, **style)
                    ax.add_patch(patch)
                except Exception:
                    continue