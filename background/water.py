"""
Water Features Processing
Enhanced precision with working multipolygon assembly.
"""
import math
import overpy
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union, linemerge, polygonize
from shapely.validation import make_valid
from utils.osm_client import osm_client
from utils.coordinate_transform import calculate_bbox

def connect_coastlines_to_polygon(lines, buffer_distance=0.001):
    """Connect coastline segments into a closed polygon - improved for rivers/estuaries."""
    if not lines:
        return None

    try:
        # First, try the standard linemerge approach
        merged = linemerge(lines)

        all_coords = []
        if hasattr(merged, 'geoms'):
            # Multiple separate lines - collect all coordinates
            for line in merged.geoms:
                coords = list(line.coords)
                if coords:
                    all_coords.extend(coords)
        else:
            # Single merged line
            all_coords = list(merged.coords)

        if len(all_coords) < 3:
            print(f"        Not enough coordinates: {len(all_coords)}")
            return None

        # Remove consecutive duplicates
        clean_coords = [all_coords[0]]
        for coord in all_coords[1:]:
            if coord != clean_coords[-1]:
                clean_coords.append(coord)

        print(f"        Trying to create polygon from {len(clean_coords)} coordinates...")

        if len(clean_coords) >= 3:
            # Strategy 1: Check if endpoints are close (natural closure)
            start_point = Point(clean_coords[0])
            end_point = Point(clean_coords[-1])
            endpoint_distance = start_point.distance(end_point)

            print(f"        Endpoint distance: {endpoint_distance:.6f}")

            # If endpoints are close, connect them
            if endpoint_distance < buffer_distance:
                if clean_coords[0] != clean_coords[-1]:
                    clean_coords.append(clean_coords[0])
                try:
                    poly = Polygon(clean_coords)
                    if poly.is_valid and poly.area > 0:
                        print(f"        ✓ Created polygon with natural closure")
                        return poly
                except Exception as e:
                    print(f"        ✗ Failed natural closure: {e}")

            # Strategy 2: Force closure for river/estuary cases
            if len(clean_coords) >= 4:
                # Force close the polygon
                if clean_coords[0] != clean_coords[-1]:
                    clean_coords.append(clean_coords[0])

                try:
                    poly = Polygon(clean_coords)
                    if poly.is_valid and poly.area > 0:
                        print(f"        ✓ Created polygon with forced closure")
                        return poly
                    else:
                        # Try to fix invalid polygon
                        fixed_poly = make_valid(poly)
                        if hasattr(fixed_poly, 'area') and fixed_poly.area > 0:
                            print(f"        ✓ Created polygon after fixing geometry")
                            return fixed_poly
                except Exception as e:
                    print(f"        ✗ Failed forced closure: {e}")

            # Strategy 3: For river systems, try creating a buffered line polygon
            if len(clean_coords) >= 2:
                try:
                    # Create a line from the coordinates
                    line = LineString(clean_coords)

                    # Buffer the line slightly to create a polygon
                    # This works well for narrow rivers/estuaries
                    buffered = line.buffer(0.0001)  # Very small buffer

                    if hasattr(buffered, 'area') and buffered.area > 0:
                        print(f"        ✓ Created polygon using line buffer method")
                        return buffered

                except Exception as e:
                    print(f"        ✗ Failed line buffer method: {e}")

        print(f"        ✗ All polygon creation strategies failed")

    except Exception as e:
        print(f"        Warning: Could not connect coastlines: {e}")

    return None

def assemble_multipolygon_working(relation, result, transformer, map_bounds=None):
    """Working multipolygon assembly - transform coordinates early to preserve holes."""
    outer_polys = []
    inner_geometries = []
    all_outer_segments = []
    all_inner_segments = []

    relation_name = relation.tags.get('name', 'Unknown')
    print(f"      Processing {len(relation.members)} members for {relation_name}...")

    # Collect all member ways by role
    for member in relation.members:
        if isinstance(member, overpy.RelationWay):
            try:
                way = result.get_way(member.ref)
                coords = [(node.lon, node.lat) for node in way.nodes]
                if len(coords) < 2: continue

                transformed_coords = [transformer.transform(lon, lat) for lon, lat in coords]
                is_closed = len(transformed_coords) >= 3 and transformed_coords[0] == transformed_coords[-1]

                if member.role == 'outer':
                    all_outer_segments.append(LineString(transformed_coords))
                    if is_closed and len(transformed_coords) >= 4:
                        try:
                            poly = make_valid(Polygon(transformed_coords))
                            if hasattr(poly, 'area') and poly.area > 0: outer_polys.append(poly)
                        except Exception: continue
                elif member.role == 'inner':
                    all_inner_segments.append(LineString(transformed_coords))
                    if is_closed and len(transformed_coords) >= 4:
                        try:
                            poly = make_valid(Polygon(transformed_coords))
                            if hasattr(poly, 'area') and poly.area > 0:
                                inner_geometries.append({'geom': poly, 'tags': way.tags})
                        except Exception: continue
            except Exception: continue

    # Process outer and inner segments
    if all_outer_segments:
        try:
            outer_polys.extend([p for p in polygonize(linemerge(all_outer_segments)) if p.is_valid and p.area > 0])
        except Exception: pass
    if all_inner_segments:
        try:
            inner_geometries.extend([{'geom': p, 'tags': {}} for p in polygonize(linemerge(all_inner_segments)) if p.is_valid and p.area > 0])
        except Exception: pass

    if not outer_polys: return None

    try:
        unified_outer = make_valid(unary_union(outer_polys))

        # --- START OF CLIPPING MODIFICATION ---
        # If map_bounds are provided, create a clipping polygon
        if map_bounds:
            map_polygon = box(
                map_bounds['xlim'][0], map_bounds['ylim'][0],
                map_bounds['xlim'][1], map_bounds['ylim'][1]
            )
            # Clip the main water body to the map boundaries
            print("        Clipping outer geometry to map boundaries...")
            unified_outer = unified_outer.intersection(map_polygon)
            if unified_outer.is_empty:
                print("        Water body is entirely outside map boundaries.")
                return None
        # --- END OF CLIPPING MODIFICATION ---

        final_geometry = unified_outer

        if inner_geometries:
            significant_inner_polys = []
            min_hole_area = 1000.0

            print(f"        Smart filtering {len(inner_geometries)} potential holes...")
            for item in inner_geometries:
                poly = item['geom']

                # --- START OF CLIPPING MODIFICATION ---
                # Clip each island to the map boundaries BEFORE filtering
                if map_bounds:
                    poly = poly.intersection(map_polygon)

                # If the island is completely off-screen after clipping, it becomes empty.
                if poly.is_empty:
                    continue
                # --- END OF CLIPPING MODIFICATION ---

                tags = item['tags']
                area = poly.area # Use the area of the clipped polygon

                if tags.get('place') in ['island', 'islet']:
                    print(f"        ✓ Keeping tagged island '{tags.get('name', 'N/A')}' (visible area: {area:.2f} sq m)")
                    significant_inner_polys.append(poly)
                elif tags.get('bridge:support') == 'pier' or tags.get('man_made') == 'pier':
                    print(f"        ✗ Discarding tagged pier (visible area: {area:.2f} sq m)")
                elif area >= min_hole_area:
                    print(f"        ✓ Keeping significant untagged hole (visible area: {area:.2f} sq m)")
                    significant_inner_polys.append(poly)
                else:
                    print(f"        ✗ Skipping small untagged hole (visible area: {area:.2f} sq m)")

            if significant_inner_polys:
                unified_inner = make_valid(unary_union(significant_inner_polys))
                final_geometry = unified_outer.difference(unified_inner)
                if not final_geometry.is_valid:
                    final_geometry = unified_outer

        if hasattr(final_geometry, 'area') and final_geometry.area > 0:
            return final_geometry

    except Exception as e:
        print(f"        ✗ Could not assemble final geometry: {e}")
        return None

    return None

class WaterProcessor:
    """Handles water features data fetching and processing with working assembly."""

    def __init__(self):
        self.client = osm_client

    def fetch_water(self, center_lat, center_lon, radius_km):
        """Fetch water features with clean, working approach and retry handling."""

        # Use larger search radius for better coverage
        search_radius_km = radius_km * 1.5

        # Calculate bbox manually to ensure correct order
        lat_offset = search_radius_km / 111.0
        lon_offset = search_radius_km / (111.0 * abs(math.cos(math.radians(center_lat))))

        south = center_lat - lat_offset
        north = center_lat + lat_offset
        west = center_lon - lon_offset
        east = center_lon + lon_offset

        print(f"    Fetching water features (working approach, {search_radius_km:.1f} km radius)...")
        print(f"    Bbox: south={south:.4f}, west={west:.4f}, north={north:.4f}, east={east:.4f}")

        # Small delay to avoid overwhelming the API after roads/greenery queries
        import time
        time.sleep(2)

        api = overpy.Overpass()

        # Clean, focused query for water bodies
        query = f'''
        [out:json][timeout:300];
        (
            way["natural"="water"]({south},{west},{north},{east});
            way["natural"="bay"]({south},{west},{north},{east});
            way["natural"="strait"]({south},{west},{north},{east});
            way["place"="sea"]({south},{west},{north},{east});
            way["water"~"^(river|lake|pond|reservoir|bay)$"]({south},{west},{north},{east});
            way["waterway"="riverbank"]({south},{west},{north},{east});
            
            relation["natural"="water"]({south},{west},{north},{east});
            relation["natural"="bay"]({south},{west},{north},{east});
            relation["natural"="strait"]({south},{west},{north},{east});
            relation["place"="sea"]({south},{west},{north},{east});
            relation["type"="multipolygon"]["natural"="water"]({south},{west},{north},{east});
            relation["type"="multipolygon"]["natural"="bay"]({south},{west},{north},{east});
            relation["type"="multipolygon"]["place"="sea"]({south},{west},{north},{east});
            relation["type"="multipolygon"]["water"]({south},{west},{north},{east});
        );
        (._;>;);
        out geom;
        '''

        # Retry mechanism for rate limiting
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    import time
                    wait_time = 15 * attempt  # Wait longer each time
                    print(f"    Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)

                result = api.query(query)
                print(f"    ✓ Found {len(result.ways)} ways and {len(result.relations)} relations")

                return {
                    'elements': [],  # We'll process directly from overpy result
                    '_overpy_result': result
                }

            except Exception as e:
                error_msg = str(e).lower()
                if 'too many requests' in error_msg or '429' in error_msg or 'rate limit' in error_msg:
                    print(f"    Rate limited (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        print(f"    ✗ Water fetch failed after {max_retries} attempts due to rate limiting")
                        return {'elements': []}
                    # Continue to retry
                else:
                    print(f"    Failed to fetch water features: {e}")
                    return {'elements': []}

    def process_water(self, water_data, transformer, map_bounds=None):
        """Process water data with working multipolygon assembly."""

        water_features = {
            'polygons': [],
            'lines': []
        }

        overpy_result = water_data.get('_overpy_result')
        if not overpy_result:
            return self._process_water_standard(water_data, transformer)

        way_count = 0
        relation_count = 0

        # Collect relation member ways to avoid double processing
        relation_member_ways = set()
        for relation in overpy_result.relations:
            if relation.tags.get("type") == "multipolygon":
                for member in relation.members:
                    if isinstance(member, overpy.RelationWay):
                        relation_member_ways.add(member.ref)

        # Process simple ways first
        print("    Processing water ways...")
        for water_body in overpy_result.ways:
            try:
                # Skip ways that are part of relations
                if water_body.id in relation_member_ways:
                    continue

                # Skip coastlines (they're processed as part of relations)
                if water_body.tags.get('natural') == 'coastline':
                    continue

                coordinates = [(node.lon, node.lat) for node in water_body.nodes]
                if len(coordinates) >= 3:
                    # Ensure closed polygon
                    if coordinates[0] != coordinates[-1]:
                        coordinates.append(coordinates[0])

                    # Transform coordinates
                    transformed_coords = []
                    for lon, lat in coordinates:
                        x, y = transformer.transform(lon, lat)
                        transformed_coords.append((x, y))

                    if len(transformed_coords) >= 4:
                        polygon_data = {
                            'exterior': transformed_coords,
                            'holes': []
                        }
                        water_features['polygons'].append(polygon_data)
                        way_count += 1

                        # Show progress for interesting water bodies
                        water_name = water_body.tags.get("name", "")
                        water_type = water_body.tags.get("natural", water_body.tags.get("water", "water"))
                        if water_name or water_type in ['bay', 'sea', 'lake']:
                            print(f"    ✓ Way {water_body.id}: {water_type} '{water_name}'")

            except Exception as e:
                print(f"    Warning: Could not process way {water_body.id}: {e}")

        # Process multipolygon relations using working assembly
        print("    Processing water relations...")
        for water_body in overpy_result.relations:
            if water_body.tags.get("type") == "multipolygon":
                try:
                    water_name = water_body.tags.get("name", "Unknown")
                    water_type = water_body.tags.get("natural", water_body.tags.get("place", "water"))
                    print(f"    Processing relation {water_body.id}: {water_type} '{water_name}'...")

                    # Use working multipolygon assembly, passing map_bounds
                    geometry = assemble_multipolygon_working(water_body, overpy_result, transformer, map_bounds)

                    if geometry and hasattr(geometry, 'area') and geometry.area > 0:
                        print(f"        Final transformed geometry area: {geometry.area:.6f}")

                        # Convert already-transformed geometry to polygon data format
                        if hasattr(geometry, 'geoms'):  # MultiPolygon
                            print(f"        MultiPolygon with {len(geometry.geoms)} parts")
                            for i, poly in enumerate(geometry.geoms):
                                if hasattr(poly, 'exterior'):
                                    exterior_coords = list(poly.exterior.coords)
                                    hole_coords_list = [list(interior.coords) for interior in poly.interiors if len(list(interior.coords)) >= 3]

                                    if len(exterior_coords) >= 3:
                                        polygon_data = {
                                            'exterior': exterior_coords,
                                            'holes': hole_coords_list
                                        }
                                        water_features['polygons'].append(polygon_data)
                                        print(f"        ✓ Added MultiPolygon part {i+1} with {len(hole_coords_list)} holes")

                        elif hasattr(geometry, 'exterior'):  # Single Polygon
                            # Check holes more carefully
                            holes_list = list(geometry.interiors)
                            holes_count = len(holes_list)
                            print(f"        Single Polygon - found {holes_count} interior rings")

                            exterior_coords = list(geometry.exterior.coords)
                            hole_coords_list = []

                            # Process each hole carefully
                            for i, interior in enumerate(holes_list):
                                hole_coords = list(interior.coords)
                                if len(hole_coords) >= 3:
                                    hole_coords_list.append(hole_coords)
                                    print(f"          Hole {i+1}: {len(hole_coords)} coords")
                                else:
                                    print(f"          Hole {i+1}: INVALID - only {len(hole_coords)} coords")

                            if len(exterior_coords) >= 3:
                                polygon_data = {
                                    'exterior': exterior_coords,
                                    'holes': hole_coords_list
                                }
                                water_features['polygons'].append(polygon_data)
                                print(f"        ✓ Added Single Polygon with {len(hole_coords_list)} valid holes")
                            else:
                                print(f"        ✗ Invalid exterior: only {len(exterior_coords)} coords")

                        relation_count += 1
                        print(f"    ✓ Successfully processed relation {water_body.id}")
                    else:
                        print(f"    ✗ Could not create geometry for relation {water_body.id}")

                except Exception as e:
                    print(f"    ✗ Failed to process relation {water_body.id}: {e}")

        print(f"    ✓ Processed {way_count} ways and {relation_count} relations")
        print(f"    Total water features: {len(water_features['polygons'])}")

        return water_features

    def _process_water_standard(self, water_data, transformer):
        """Fallback standard processing without overpy."""
        water_features = {
            'polygons': [],
            'lines': []
        }

        for element in water_data.get('elements', []):
            if element['type'] == 'way' and 'geometry' in element:
                coords = []
                for node in element['geometry']:
                    x, y = transformer.transform(node['lon'], node['lat'])
                    coords.append((x, y))

                if len(coords) >= 3:
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    polygon_data = {
                        'exterior': coords,
                        'holes': []
                    }
                    water_features['polygons'].append(polygon_data)

        return water_features

    def render_water(self, ax, water_data, style=None):
        """Render water polygons with proper hole support for significant islands."""
        if style is None:
            style = DEFAULT_WATER_STYLE

        # Render water body polygons with holes when significant
        for polygon_data in water_data.get('polygons', []):
            try:
                # Handle both old format (list of coords) and new format (dict with exterior/holes)
                if isinstance(polygon_data, dict):
                    # New format with holes support
                    exterior_coords = polygon_data.get('exterior', [])
                    hole_coords_list = polygon_data.get('holes', [])

                    if len(exterior_coords) >= 3:
                        # Ensure exterior is a valid polygon before proceeding
                        if Polygon(exterior_coords).is_valid:
                            if hole_coords_list:
                                # Water with significant holes - use Path method
                                from matplotlib.path import Path
                                import matplotlib.patches as patches

                                # Build vertices and codes for Path
                                vertices = []
                                codes = []

                                # Add exterior ring (must be properly closed)
                                vertices.extend(exterior_coords)
                                codes.extend([Path.MOVETO] + [Path.LINETO] * (len(exterior_coords) - 2) + [Path.CLOSEPOLY])

                                # Add holes (each must be properly closed)
                                for hole_coords in hole_coords_list:
                                    if len(hole_coords) >= 3:
                                        vertices.extend(hole_coords)
                                        codes.extend([Path.MOVETO] + [Path.LINETO] * (len(hole_coords) - 2) + [Path.CLOSEPOLY])

                                # Create path and patch
                                path = Path(vertices, codes)
                                patch = patches.PathPatch(path, **style['polygon'])
                                ax.add_patch(patch)
                            else:
                                # Water without holes - use simple fill
                                xs, ys = zip(*exterior_coords)
                                ax.fill(xs, ys, **style['polygon'])

                else:
                    # Old format - simple polygon
                    coords = polygon_data
                    if len(coords) >= 3:
                        xs, ys = zip(*coords)
                        ax.fill(xs, ys, **style['polygon'])

            except Exception as e:
                print(f"Warning: Could not render polygon: {e}")
                # Fallback: try to render just the exterior without holes
                try:
                    if isinstance(polygon_data, dict):
                        exterior_coords = polygon_data.get('exterior', [])
                        if len(exterior_coords) >= 3:
                            xs, ys = zip(*exterior_coords)
                            ax.fill(xs, ys, **style['polygon'])
                except:
                    continue

# Default water styles
DEFAULT_WATER_STYLE = {
    'polygon': {
        'color': '#e3eeff',     # Slightly less pale blue
        'alpha': 0.8,
        'zorder': 3
    },
    'line': {
        'color': '#e3eeff',
        'linewidth': 1.5,
        'alpha': 0.8,
        'zorder': 3
    }
}