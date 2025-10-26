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

def assemble_multipolygon_working(relation, result, transformer):
    """Working multipolygon assembly - transform coordinates early to preserve holes."""
    outer_polys = []
    inner_polys = []
    all_outer_segments = []  # ALL outer segments, coastline or not
    all_inner_segments = []  # ALL inner segments, coastline or not

    relation_name = relation.tags.get('name', 'Unknown')
    print(f"      Processing {len(relation.members)} members for {relation_name}...")

    # Collect all member ways by role - combine ALL boundary types
    for member in relation.members:
        if isinstance(member, overpy.RelationWay):
            try:
                way = result.get_way(member.ref)
                coords = [(node.lon, node.lat) for node in way.nodes]

                if len(coords) >= 2:
                    # Transform coordinates immediately
                    transformed_coords = []
                    for lon, lat in coords:
                        x, y = transformer.transform(lon, lat)
                        transformed_coords.append((x, y))

                    is_coastline = way.tags.get('natural') == 'coastline'
                    is_closed = len(transformed_coords) >= 3 and transformed_coords[0] == transformed_coords[-1]
                    way_tags_str = ', '.join([f"{k}={v}" for k, v in way.tags.items()]) if way.tags else "no tags"

                    print(f"        Way {member.ref} ({member.role}): {len(transformed_coords)} coords, closed={is_closed}, tags=[{way_tags_str}]")

                    if member.role == 'outer':
                        # For outer ways, collect everything as line segments to be connected
                        all_outer_segments.append(LineString(transformed_coords))

                        # Also check if it's already a valid closed polygon
                        if is_closed and len(transformed_coords) >= 4:
                            try:
                                poly = Polygon(transformed_coords)
                                if poly.is_valid and poly.area > 0:
                                    outer_polys.append(poly)
                                    print(f"        ✓ Added complete outer polygon from way {member.ref}")
                                else:
                                    # Try to fix invalid polygons
                                    fixed_poly = make_valid(poly)
                                    if hasattr(fixed_poly, 'area') and fixed_poly.area > 0:
                                        outer_polys.append(fixed_poly)
                                        print(f"        ✓ Added fixed outer polygon from way {member.ref}")
                            except Exception as e:
                                print(f"        Warning: Invalid outer polygon from way {member.ref}: {e}")

                    elif member.role == 'inner':
                        # For inner ways, collect everything as line segments to be connected
                        all_inner_segments.append(LineString(transformed_coords))

                        # Also check if it's already a valid closed polygon
                        if is_closed and len(transformed_coords) >= 4:
                            try:
                                poly = Polygon(transformed_coords)
                                if poly.is_valid and poly.area > 0:
                                    inner_polys.append(poly)
                                    print(f"        ✓ Added complete inner polygon from way {member.ref} (area: {poly.area:.6f})")
                                else:
                                    fixed_poly = make_valid(poly)
                                    if isinstance(fixed_poly, Polygon) and fixed_poly.area > 0:
                                        inner_polys.append(fixed_poly)
                                        print(f"        ✓ Added fixed inner polygon from way {member.ref} (area: {fixed_poly.area:.6f})")
                            except Exception as e:
                                print(f"        Warning: Invalid inner polygon from way {member.ref}: {e}")

            except Exception as e:
                print(f"        Warning: Could not process member way {member.ref}: {e}")
                continue

    # Only connect outer segments if we have incomplete segments and no complete polygons
    if all_outer_segments and not outer_polys:
        print(f"        Connecting {len(all_outer_segments)} incomplete outer segments...")
        connected_poly = connect_coastlines_to_polygon(all_outer_segments)
        if connected_poly:
            outer_polys.append(connected_poly)
            print(f"        ✓ Successfully connected all outer segments")
        else:
            print(f"        ✗ Failed to connect outer segments")
    elif outer_polys and all_outer_segments:
        print(f"        Skipping segment connection - already have {len(outer_polys)} complete outer polygons")

    # Only connect inner segments if we have incomplete segments and no complete inner polygons
    if all_inner_segments and not inner_polys:
        print(f"        Connecting {len(all_inner_segments)} incomplete inner segments...")
        connected_inner = connect_coastlines_to_polygon(all_inner_segments)
        if connected_inner:
            inner_polys.append(connected_inner)
            print(f"        ✓ Successfully connected all inner segments")

    # Use polygonize as fallback for incomplete outer segments
    if all_outer_segments and not outer_polys:
        try:
            print(f"        Trying polygonize on {len(all_outer_segments)} outer segments...")
            polygons = list(polygonize(all_outer_segments))
            for poly in polygons:
                if poly.is_valid and poly.area > 0:
                    outer_polys.append(poly)
            if outer_polys:
                print(f"        ✓ Polygonize created {len(outer_polys)} outer polygons")
        except Exception as e:
            print(f"        Warning: Polygonize failed: {e}")

    # Use polygonize as fallback for incomplete inner segments
    if all_inner_segments and not inner_polys:
        try:
            print(f"        Trying polygonize on {len(all_inner_segments)} inner segments...")
            polygons = list(polygonize(all_inner_segments))
            for poly in polygons:
                if poly.is_valid and poly.area > 0:
                    inner_polys.append(poly)
            if inner_polys:
                print(f"        ✓ Polygonize created {len(inner_polys)} inner polygons")
        except Exception as e:
            print(f"        Warning: Inner polygonize failed: {e}")

    if not outer_polys:
        print(f"        ✗ No valid outer polygons found")
        return None

    try:
        print(f"        Assembling final geometry from {len(outer_polys)} outer and {len(inner_polys)} inner polygons...")

        # Combine outer polygons
        if len(outer_polys) == 1:
            unified_outer = outer_polys[0]
        else:
            unified_outer = unary_union(outer_polys)

        if not unified_outer.is_valid:
            unified_outer = make_valid(unified_outer)

        # Apply holes (inner polygons) - but only keep significant ones
        final_geometry = unified_outer
        if inner_polys:
            try:
                # Filter out very small holes (bridge piers, etc.) - keep only significant ones
                significant_inner_polys = []
                min_hole_area = 1000.0  # 1000 square meters minimum

                for inner_poly in inner_polys:
                    if inner_poly.area >= min_hole_area:
                        significant_inner_polys.append(inner_poly)
                        print(f"        Keeping significant hole with area: {inner_poly.area:.2f} sq m")
                    else:
                        print(f"        Skipping small hole with area: {inner_poly.area:.2f} sq m (bridge pier/etc)")

                if significant_inner_polys:
                    if len(significant_inner_polys) == 1:
                        unified_inner = significant_inner_polys[0]
                    else:
                        unified_inner = unary_union(significant_inner_polys)

                    if unified_inner.is_valid:
                        result_geom = unified_outer.difference(unified_inner)
                        if hasattr(result_geom, 'area') and result_geom.area > 0:
                            print(f"        ✓ Successfully created geometry with {len(significant_inner_polys)} significant hole(s), area: {result_geom.area:.6f}")
                            final_geometry = result_geom
                        else:
                            print(f"        Warning: Difference operation failed, using outer only")
                else:
                    print(f"        No significant holes found (all were < {min_hole_area} sq m)")
            except Exception as e:
                print(f"        Warning: Could not apply holes: {e}")

        # Return the already-transformed geometry
        if hasattr(final_geometry, 'area') and final_geometry.area > 0:
            print(f"        ✓ Final geometry area: {final_geometry.area:.6f}")

            # Debug: Check if holes are actually in the final geometry
            if hasattr(final_geometry, 'interiors'):
                actual_holes = list(final_geometry.interiors)
                print(f"        ✓ Final geometry has {len(actual_holes)} interior rings")
                for i, interior in enumerate(actual_holes):
                    coords = list(interior.coords)
                    print(f"          Interior {i+1}: {len(coords)} coordinates")

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

    def process_water(self, water_data, transformer):
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

                    # Use working multipolygon assembly
                    geometry = assemble_multipolygon_working(water_body, overpy_result, transformer)

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
        """Render water polygons with proper hole support."""
        if style is None:
            style = DEFAULT_WATER_STYLE

        # Render water body polygons with holes
        for polygon_data in water_data.get('polygons', []):
            try:
                # Handle both old format (list of coords) and new format (dict with exterior/holes)
                if isinstance(polygon_data, dict):
                    # New format with holes support
                    exterior_coords = polygon_data.get('exterior', [])
                    hole_coords_list = polygon_data.get('holes', [])

                    if len(exterior_coords) >= 3:
                        # Create matplotlib Path for polygon with holes
                        from matplotlib.path import Path
                        import matplotlib.patches as patches

                        # Build vertices and codes for Path
                        vertices = []
                        codes = []

                        # Add exterior ring
                        vertices.extend(exterior_coords)
                        codes.extend([Path.MOVETO] + [Path.LINETO] * (len(exterior_coords) - 1))

                        # Add holes
                        for hole_coords in hole_coords_list:
                            if len(hole_coords) >= 3:
                                vertices.extend(hole_coords)
                                codes.extend([Path.MOVETO] + [Path.LINETO] * (len(hole_coords) - 1))

                        # Create path and patch
                        path = Path(vertices, codes)
                        patch = patches.PathPatch(path, **style['polygon'])
                        ax.add_patch(patch)

                else:
                    # Old format - simple polygon
                    coords = polygon_data
                    if len(coords) >= 3:
                        xs, ys = zip(*coords)
                        ax.fill(xs, ys, **style['polygon'])

            except Exception as e:
                print(f"Warning: Could not render polygon: {e}")
                continue

# Default water styles
DEFAULT_WATER_STYLE = {
    'polygon': {
        'color': '#e8efff',     # Slightly less pale blue
        'alpha': 0.8,
        'zorder': 3
    },
    'line': {
        'color': '#e8efff',
        'linewidth': 1.5,
        'alpha': 0.8,
        'zorder': 3
    }
}