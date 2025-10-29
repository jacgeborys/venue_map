"""
Coastline-based Water Generation - Clean Version
For cities where seas aren't explicitly tagged as water (Stockholm, Helsinki, etc.)
"""
import math
import overpy
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union, linemerge, polygonize
from shapely.validation import make_valid


def fetch_coastlines_and_water_boundaries(center_lat, center_lon, radius_km, transformer):
    """Fetch coastlines AND water boundaries (rivers, existing water edges) for complete water generation."""

    # Use larger search radius for complete coverage
    search_radius_km = radius_km * 2.0

    # Calculate bbox manually
    lat_offset = search_radius_km / 111.0
    lon_offset = search_radius_km / (111.0 * abs(math.cos(math.radians(center_lat))))

    south = center_lat - lat_offset
    north = center_lat + lat_offset
    west = center_lon - lon_offset
    east = center_lon + lon_offset

    print(f"    Fetching coastlines + water boundaries ({search_radius_km:.1f} km radius)...")
    print(f"    Bbox: S={south:.4f}, W={west:.4f}, N={north:.4f}, E={east:.4f}")

    api = overpy.Overpass()

    # --- START OF MODIFICATION ---
    # Add island and islet polygons to the query to identify known land areas.
    query = f'''
    [out:json][timeout:360];
    (
        // Natural coastlines
        way["natural"="coastline"]({south},{west},{north},{east});
        
        // Rivers that could be boundaries
        way["waterway"="river"]({south},{west},{north},{east});
        way["waterway"="stream"]({south},{west},{north},{east});
        
        // Water body edges that could be boundaries
        way["natural"="water"]({south},{west},{north},{east});
        way["natural"="bay"]({south},{west},{north},{east});
        
        // Riverbanks (edges of water)
        way["waterway"="riverbank"]({south},{west},{north},{east});

        // KNOWN LAND: Explicitly tagged islands and islets
        way["place"~"^(island|islet)"]({south},{west},{north},{east});
        relation["place"~"^(island|islet)"]({south},{west},{north},{east});
    );
    (._;>;);
    out geom;
    '''
    # --- END OF MODIFICATION ---

    try:
        import time
        time.sleep(3)  # Space out API calls

        result = api.query(query)
        print(f"    ✓ Found {len(result.ways)} potential boundary segments and land features")

        return result

    except Exception as e:
        print(f"    Failed to fetch boundaries: {e}")
        return None


def create_complete_water_polygons(boundary_result, transformer, map_bounds, greenery_data=None):
    """CLEAN VERSION: Create water polygons with special handling for archipelago cities."""

    print(f"    *** CLEAN create_complete_water_polygons called ***")

    if not boundary_result or not boundary_result.ways:
        print(f"    No boundary result or ways")
        return []

    print(f"    Processing {len(boundary_result.ways)} boundary segments...")

    # Get all coastline segments
    coastline_segments = []

    for way in boundary_result.ways:
        # OSM nodes are in lat, lon order
        coords = [(node.lat, node.lon) for node in way.nodes]
        if len(coords) >= 2:
            # Transform coordinates - your transformer expects (lon, lat) due to always_xy=True
            transformed_coords = []
            for lat, lon in coords:
                x, y = transformer.transform(lon, lat)
                transformed_coords.append((x, y))

            way_type = way.tags.get('natural', way.tags.get('waterway', 'unknown'))

            if way_type == 'coastline':
                coastline_segments.append(LineString(transformed_coords))
                print(f"    ✓ Added coastline segment: {len(transformed_coords)} points")

    print(f"    Found {len(coastline_segments)} total coastline segments")

    if not coastline_segments:
        print("    No coastlines found - skipping water generation")
        return []

    water_polygons = []

    # Strategy decision based on coastline complexity
    if len(coastline_segments) > 20:  # Complex archipelago like Stockholm
        print(f"    Complex archipelago detected - using greenery-based approach")
        water_polygons = create_archipelago_water(coastline_segments, map_bounds, greenery_data)
    else:
        print(f"    Simple coastline - using individual polygon approach")
        water_polygons = create_individual_water_polygons(coastline_segments, map_bounds)

    print(f"    *** FINAL: Generated {len(water_polygons)} water polygons ***")
    return water_polygons


def create_archipelago_water(coastline_segments, map_bounds, greenery_data=None):
    """Create network of connected lines by connecting coastline endpoints to map frame."""

    try:
        # Create map boundary points
        xmin, xmax = map_bounds['xlim']
        ymin, ymax = map_bounds['ylim']

        print(f"    Connecting {len(coastline_segments)} coastlines to map frame...")

        # Collect all line segments for the network
        network_lines = []

        # Add all coastline segments
        for segment in coastline_segments:
            network_lines.append(segment)

        # For each coastline that's not a closed loop, connect its endpoints to map boundary
        for i, segment in enumerate(coastline_segments):
            coords = list(segment.coords)
            start_point = coords[0]
            end_point = coords[-1]

            # Check if it's a closed loop (like Djurgården)
            start_to_end_dist = ((start_point[0] - end_point[0])**2 + (start_point[1] - end_point[1])**2)**0.5

            if start_to_end_dist > 100:  # Not a closed loop
                # Connect start point to nearest map edge
                start_edge_point = get_nearest_boundary_point(start_point, xmin, xmax, ymin, ymax)
                if start_edge_point != start_point:
                    connector1 = LineString([start_point, start_edge_point])
                    network_lines.append(connector1)

                # Connect end point to nearest map edge
                end_edge_point = get_nearest_boundary_point(end_point, xmin, xmax, ymin, ymax)
                if end_edge_point != end_point:
                    connector2 = LineString([end_point, end_edge_point])
                    network_lines.append(connector2)

        # Add the map boundary as four separate edges
        boundary_edges = [
            LineString([(xmin, ymin), (xmax, ymin)]),  # bottom
            LineString([(xmax, ymin), (xmax, ymax)]),  # right
            LineString([(xmax, ymax), (xmin, ymax)]),  # top
            LineString([(xmin, ymax), (xmin, ymin)])   # left
        ]

        for edge in boundary_edges:
            network_lines.append(edge)

        print(f"    Network: {len(coastline_segments)} coastlines + connectors + 4 boundary edges = {len(network_lines)} total lines")

        # Now polygonize the connected network
        polygons = list(polygonize(network_lines))
        valid_polygons = [p for p in polygons if p.is_valid and p.area > 1000]

        print(f"    Result: {len(valid_polygons)} polygons")

        return valid_polygons

    except Exception as e:
        print(f"    Failed: {e}")
        return []


def get_nearest_boundary_point(point, xmin, xmax, ymin, ymax):
    """Get the nearest point on the map boundary."""
    x, y = point

    # Calculate distance to each edge
    distances = [
        (abs(y - ymin), (x, ymin)),  # bottom edge
        (abs(x - xmax), (xmax, y)),  # right edge
        (abs(y - ymax), (x, ymax)),  # top edge
        (abs(x - xmin), (xmin, y))   # left edge
    ]

    # Return the closest boundary point
    _, nearest_point = min(distances)
    return nearest_point


def create_individual_water_polygons(coastline_segments, map_bounds):
    """Create individual water polygons for simpler coastline areas."""

    water_polygons = []

    try:
        # Create map boundary
        map_polygon = box(
            map_bounds['xlim'][0],
            map_bounds['ylim'][0],
            map_bounds['xlim'][1],
            map_bounds['ylim'][1]
        )

        print(f"    Individual polygon approach for {len(coastline_segments)} segments")

        for i, segment in enumerate(coastline_segments):
            print(f"    Processing coastline segment {i+1}/{len(coastline_segments)}...")

            water_poly = create_water_polygon_from_coastline(segment, map_polygon)
            if water_poly:
                water_polygons.append(water_poly)

        print(f"    *** INDIVIDUAL ANALYSIS: {len(water_polygons)} water polygons created ***")

    except Exception as e:
        print(f"    Individual water creation failed: {e}")
        import traceback
        traceback.print_exc()

    return water_polygons


def detect_coastline_gaps(coastline_segments, tolerance=100):
    """Detect gaps between coastline segments."""

    gaps = []

    if len(coastline_segments) < 2:
        return gaps

    print(f"    Checking for gaps between {len(coastline_segments)} segments (tolerance: {tolerance}m)...")

    for i, seg1 in enumerate(coastline_segments):
        seg1_start = Point(seg1.coords[0])
        seg1_end = Point(seg1.coords[-1])

        for j, seg2 in enumerate(coastline_segments):
            if i >= j:  # Only check each pair once
                continue

            seg2_start = Point(seg2.coords[0])
            seg2_end = Point(seg2.coords[-1])

            # Check all endpoint combinations
            combinations = [
                (seg1_end, seg2_start, 'end-start'),
                (seg1_end, seg2_end, 'end-end'),
                (seg1_start, seg2_start, 'start-start'),
                (seg1_start, seg2_end, 'start-end')
            ]

            for point1, point2, connection_type in combinations:
                distance = point1.distance(point2)

                if tolerance < distance < tolerance * 10:  # Significant gap but not too huge
                    gaps.append({
                        'seg1_idx': i,
                        'seg2_idx': j,
                        'distance': distance,
                        'connection_type': connection_type,
                        'point1': (point1.x, point1.y),
                        'point2': (point2.x, point2.y)
                    })

    # Sort by distance
    gaps.sort(key=lambda x: x['distance'])

    return gaps


def create_water_polygon_from_coastline(coastline_segment, map_polygon):
    """Create a water polygon by connecting a coastline segment to the map boundary."""

    try:
        coords = list(coastline_segment.coords)
        if len(coords) < 2:
            return None

        print(f"      Coastline segment: {len(coords)} points")

        start_point = Point(coords[0])
        end_point = Point(coords[-1])

        # Get map boundary coordinates
        map_coords = list(map_polygon.exterior.coords)[:-1]  # Remove duplicate last point

        # Find closest boundary points
        start_distances = [(i, Point(mc).distance(start_point)) for i, mc in enumerate(map_coords)]
        end_distances = [(i, Point(mc).distance(end_point)) for i, mc in enumerate(map_coords)]

        start_boundary_idx = min(start_distances, key=lambda x: x[1])[0]
        end_boundary_idx = min(end_distances, key=lambda x: x[1])[0]

        print(f"      Connecting to boundary indices: {start_boundary_idx} to {end_boundary_idx}")

        # Get boundary path - try both directions and pick the one that makes sense
        if start_boundary_idx <= end_boundary_idx:
            # Forward direction
            boundary_path = map_coords[start_boundary_idx:end_boundary_idx + 1]
        else:
            # Wrap around
            boundary_path = map_coords[start_boundary_idx:] + map_coords[:end_boundary_idx + 1]

        # Alternative path (the other way around)
        if start_boundary_idx >= end_boundary_idx:
            alt_boundary_path = map_coords[end_boundary_idx:start_boundary_idx + 1]
            alt_boundary_path.reverse()
        else:
            alt_boundary_path = map_coords[end_boundary_idx:] + map_coords[:start_boundary_idx + 1]
            alt_boundary_path.reverse()

        # Choose the boundary path that creates a reasonable water area
        # Try both and pick the one that makes more sense
        water_coords1 = coords + boundary_path
        water_coords2 = coords + alt_boundary_path

        print(f"      Option 1: {len(coords)} coastline + {len(boundary_path)} boundary")
        print(f"      Option 2: {len(coords)} coastline + {len(alt_boundary_path)} boundary")

        # Test both options and pick the better one
        best_polygon = None
        best_area = 0

        for i, test_coords in enumerate([water_coords1, water_coords2], 1):
            try:
                if len(test_coords) >= 3:
                    test_poly = Polygon(test_coords)
                    if test_poly.is_valid and test_poly.area > 100000:  # 0.1 sq km minimum
                        # Prefer polygons that reach map boundary
                        boundary_coverage = calculate_boundary_coverage(test_poly, map_polygon)
                        score = test_poly.area * (1 + boundary_coverage)

                        print(f"      Option {i}: area={test_poly.area:.0f}, boundary_coverage={boundary_coverage:.2f}, score={score:.0f}")

                        if score > best_area:
                            best_area = score
                            best_polygon = test_poly
                            print(f"      → New best option: {i}")
            except Exception as e:
                print(f"      Option {i} failed: {e}")

        if best_polygon:
            print(f"      ✓ Selected water polygon: {best_polygon.area:.0f} sq m")
            return best_polygon
        else:
            print(f"      ✗ No valid water polygon created")

    except Exception as e:
        print(f"      Water polygon creation failed: {e}")
        import traceback
        traceback.print_exc()

    return None


def calculate_boundary_coverage(polygon, map_polygon):
    """Calculate how much of the map boundary the polygon touches (0-1)."""

    try:
        boundary_length = map_polygon.boundary.length
        intersection_length = polygon.boundary.intersection(map_polygon.boundary).length
        return min(intersection_length / boundary_length, 1.0)
    except:
        return 0.0


def get_water_side_boundary(start_coord, end_coord, boundary_coords):
    """Get the boundary segment that represents the water side (longer segment)."""

    try:
        # Find indices of start and end coordinates
        start_idx = None
        end_idx = None

        for i, coord in enumerate(boundary_coords):
            if abs(coord[0] - start_coord[0]) < 1 and abs(coord[1] - start_coord[1]) < 1:
                start_idx = i
            if abs(coord[0] - end_coord[0]) < 1 and abs(coord[1] - end_coord[1]) < 1:
                end_idx = i

        if start_idx is None or end_idx is None:
            # Fallback: use original coordinates
            return [end_coord, start_coord]

        # Get both possible boundary segments
        if start_idx < end_idx:
            segment1 = boundary_coords[end_idx:start_idx + len(boundary_coords)][:len(boundary_coords) - end_idx + start_idx]
            segment2 = boundary_coords[start_idx:end_idx + 1]
        else:
            segment1 = boundary_coords[end_idx:start_idx + 1]
            segment2 = boundary_coords[start_idx:] + boundary_coords[:end_idx + 1]

        # Return the longer segment (more likely to be the water/sea side)
        if len(segment1) > len(segment2):
            return segment1[1:-1]  # Exclude endpoints
        else:
            return segment2[1:-1]  # Exclude endpoints

    except Exception as e:
        print(f"      Boundary segment calculation failed: {e}")
        return [end_coord, start_coord]


def convert_coastline_water_to_polygons(water_polygons):
    """Convert coastline-generated water to standard polygon format."""

    print(f"    Converting {len(water_polygons)} water polygons...")
    polygon_features = []

    for i, water_poly in enumerate(water_polygons):
        try:
            if hasattr(water_poly, 'exterior'):
                exterior_coords = list(water_poly.exterior.coords)
                hole_coords_list = [list(interior.coords) for interior in water_poly.interiors
                                  if len(list(interior.coords)) >= 3]

                print(f"    Converting polygon {i+1}: {len(exterior_coords)} exterior points, {len(hole_coords_list)} holes")

                if len(exterior_coords) >= 3:
                    polygon_data = {
                        'exterior': exterior_coords,
                        'holes': hole_coords_list
                    }
                    polygon_features.append(polygon_data)
                    print(f"    ✓ Added polygon {i+1}")

        except Exception as e:
            print(f"    Warning: Could not convert polygon {i+1}: {e}")

    print(f"    *** CONVERTED: {len(polygon_features)} features ***")
    return polygon_features


def fetch_enhanced_coastline_water(center_lat, center_lon, radius_km, transformer, map_bounds, greenery_data=None):
    """CLEAN VERSION: Enhanced coastline + water boundary processing with greenery land detection."""

    print(f"    *** CLEAN fetch_enhanced_coastline_water called ***")
    print(f"    Parameters: center=({center_lat}, {center_lon}), radius={radius_km}km")

    boundary_result = fetch_coastlines_and_water_boundaries(center_lat, center_lon, radius_km, transformer)
    if not boundary_result:
        print(f"    No boundary result returned")
        return {
            'coastlines': [],
            'water_polygons': [],
            'coastline_segments': []
        }

    print(f"    Got boundary result with {len(boundary_result.ways)} ways")

    # Extract coastlines for visualization
    coastline_lines = extract_coastline_lines(boundary_result, transformer)

    # Extract raw coastline segments for polygon export
    coastline_segments = extract_raw_coastline_segments(boundary_result, transformer)

    # --- START OF MODIFICATION ---
    # Extract known island polygons for the land detection logic
    island_polygons = extract_island_polygons(boundary_result, transformer)
    # --- END OF MODIFICATION ---

    # CREATE MAP BOUNDARY
    map_boundary = box(
        map_bounds['xlim'][0],
        map_bounds['ylim'][0],
        map_bounds['xlim'][1],
        map_bounds['ylim'][1]
    )

    # CLIP COASTLINES TO FRAME BOUNDARY
    clipped_coastline_segments = []
    coastline_boundary_points = []  # Points where coastlines touch the boundary

    for segment in coastline_segments:
        clipped_segments = split_coastline_at_boundary_intersections(segment, map_boundary)
        clipped_coastline_segments.extend(clipped_segments)

        # Collect points where coastlines touch the boundary
        for clipped_seg in clipped_segments:
            # Check if endpoints are on the boundary
            start_point = Point(clipped_seg.coords[0])
            end_point = Point(clipped_seg.coords[-1])

            if map_boundary.boundary.distance(start_point) < 1:  # 1m tolerance
                coastline_boundary_points.append(start_point)
            if map_boundary.boundary.distance(end_point) < 1:  # 1m tolerance
                coastline_boundary_points.append(end_point)

    # CREATE FRAME BOUNDARY WITH VERTICES AT COASTLINE TOUCH POINTS
    frame_boundary_with_vertices = create_frame_with_coastline_vertices(map_boundary, coastline_boundary_points)

    # COMBINE ALL SEGMENTS
    all_segments = clipped_coastline_segments + frame_boundary_with_vertices

    print(f"    Final network: {len(clipped_coastline_segments)} clipped coastlines + {len(frame_boundary_with_vertices)} frame segments = {len(all_segments)} total")

    # --- START OF MODIFICATION ---
    # Pass the island_polygons to the classification function
    water_polygons = create_complete_water_polygons_from_segments(all_segments, map_bounds, greenery_data, island_polygons)
    # --- END OF MODIFICATION ---

    print(f"    create_complete_water_polygons returned {len(water_polygons)} polygons")

    converted = convert_coastline_water_to_polygons(water_polygons)
    print(f"    convert_coastline_water_to_polygons returned {len(converted)} features")

    return {
        'coastlines': coastline_lines,
        'water_polygons': converted,
        'coastline_segments': all_segments  # Export all segments including broken frame
    }


def create_frame_with_coastline_vertices(map_boundary, coastline_boundary_points):
    """Break frame boundary into separate segments between coastline touch points."""

    # Get the frame boundary as a closed line
    frame_coords = list(map_boundary.exterior.coords)  # Keep the closed loop
    frame_line = LineString(frame_coords)

    if not coastline_boundary_points:
        # No coastline touches, return frame as 4 separate edges
        xmin, ymin, xmax, ymax = map_boundary.bounds
        return [
            LineString([(xmin, ymin), (xmax, ymin)]),  # bottom
            LineString([(xmax, ymin), (xmax, ymax)]),  # right
            LineString([(xmax, ymax), (xmin, ymax)]),  # top
            LineString([(xmin, ymax), (xmin, ymin)])   # left
        ]

    # Project coastline touch points onto the frame boundary and get their positions
    vertex_positions = []

    for point in coastline_boundary_points:
        # Project point onto boundary and get distance along boundary
        distance_along = frame_line.project(point)
        actual_point = frame_line.interpolate(distance_along)
        vertex_positions.append((distance_along, (actual_point.x, actual_point.y)))

    # Sort by position along boundary
    vertex_positions.sort()

    # Remove duplicates (points very close to each other)
    unique_positions = []
    for i, (dist, coord) in enumerate(vertex_positions):
        if i == 0 or dist - vertex_positions[i-1][0] > 10:  # 10m minimum separation
            unique_positions.append((dist, coord))

    print(f"    Breaking frame at {len(unique_positions)} coastline touch points")

    # Create frame segments between touch points
    frame_segments = []
    total_length = frame_line.length

    for i in range(len(unique_positions)):
        # Get start and end positions
        start_dist = unique_positions[i][0]
        end_dist = unique_positions[(i + 1) % len(unique_positions)][0]

        # Handle wrap-around at the end of the frame
        if end_dist < start_dist:
            end_dist += total_length

        # Extract the segment between these points
        if end_dist - start_dist > 1:  # Only create segments longer than 1m
            try:
                # Create segment from start_dist to end_dist
                start_point = frame_line.interpolate(start_dist)
                end_point = frame_line.interpolate(end_dist % total_length)

                # Extract the actual path between these points
                if end_dist - start_dist < total_length * 0.5:
                    # Short path - direct extraction
                    segment_coords = []
                    num_points = max(10, int((end_dist - start_dist) / 100))  # One point per 100m
                    for j in range(num_points + 1):
                        dist = start_dist + (end_dist - start_dist) * j / num_points
                        point = frame_line.interpolate(dist % total_length)
                        segment_coords.append((point.x, point.y))

                    if len(segment_coords) >= 2:
                        frame_segments.append(LineString(segment_coords))

            except Exception as e:
                print(f"      Warning: Could not create frame segment {i}: {e}")

    print(f"    Created {len(frame_segments)} frame segments")
    return frame_segments


def split_coastline_at_boundary_intersections(coastline, map_boundary):
    """Clip coastline to only the part inside the map boundary."""

    try:
        # Clip the coastline to only the part inside the map boundary
        clipped = coastline.intersection(map_boundary)

        if clipped.is_empty:
            # Coastline is completely outside the boundary
            return []

        # Handle different geometry types
        if clipped.geom_type == 'LineString':
            # Single line segment inside boundary
            return [clipped]
        elif clipped.geom_type == 'MultiLineString':
            # Multiple line segments inside boundary
            return list(clipped.geoms)
        elif clipped.geom_type == 'GeometryCollection':
            # Mixed geometry types - extract only LineStrings
            lines = [geom for geom in clipped.geoms if geom.geom_type == 'LineString']
            return lines
        else:
            # Other geometry types (Point, etc.) - ignore
            return []

    except Exception as e:
        print(f"    Warning: Could not clip coastline: {e}")
        return [coastline]  # Return original if clipping fails


def create_complete_water_polygons_from_segments(coastline_segments, map_bounds, greenery_data=None, island_data=None):
    """Create water polygons by classifying each polygon based on greenery and known island data."""

    try:
        # Create map boundary for area calculations
        map_polygon = box(
            map_bounds['xlim'][0],
            map_bounds['ylim'][0],
            map_bounds['xlim'][1],
            map_bounds['ylim'][1]
        )

        print(f"    Running polygonize on {len(coastline_segments)} segments...")

        # Run polygonize with all segments
        polygons = list(polygonize(coastline_segments))
        valid_polygons = [p for p in polygons if p.is_valid and p.area > 1000]

        print(f"    Polygonize result: {len(valid_polygons)} valid polygons")

        # Convert greenery data to Shapely polygons for classification
        greenery_polygons = []
        if greenery_data and len(greenery_data) > 0:
            print(f"    Converting {len(greenery_data)} greenery areas for classification...")
            for i, greenery_coords in enumerate(greenery_data):
                try:
                    if len(greenery_coords) >= 3:
                        greenery_poly = Polygon(greenery_coords)
                        if greenery_poly.is_valid and greenery_poly.area > 100:  # 100 sq m minimum
                            greenery_polygons.append(greenery_poly)
                except:
                    continue
            print(f"    Valid greenery polygons: {len(greenery_polygons)}")

        # --- START OF MODIFICATION ---
        # The island_data is already a list of Shapely polygons, so no conversion is needed.
        # We just need to check if it exists.
        known_island_polygons = island_data if island_data else []
        if known_island_polygons:
            print(f"    Using {len(known_island_polygons)} known island polygons for classification...")
        # --- END OF MODIFICATION ---

        # Classify each polygon as land or water
        water_polygons = []

        for i, poly in enumerate(valid_polygons):
            area = poly.area
            if area <= 0: continue

            # --- START OF MODIFIED CLASSIFICATION LOGIC ---
            is_land = False
            land_reason = ""

            # Check 1: Is it a known island?
            total_island_area = 0
            for island_poly in known_island_polygons:
                try:
                    if poly.intersects(island_poly):
                        intersection = poly.intersection(island_poly)
                        total_island_area += intersection.area
                except:
                    continue

            # If over 50% of the polygon's area is covered by a known island, it's land.
            island_ratio = total_island_area / area
            if island_ratio > 0.8:
                is_land = True
                land_reason = f"is a known island ({island_ratio*100:.1f}% coverage)"

            # Check 2: If it's not a known island, does it have significant greenery?
            if not is_land:
                total_greenery_area = 0
                for greenery_poly in greenery_polygons:
                    try:
                        if poly.intersects(greenery_poly):
                            intersection = poly.intersection(greenery_poly)
                            total_greenery_area += intersection.area
                    except:
                        continue

                greenery_ratio = total_greenery_area / area
                if greenery_ratio > 0.05:  # 5% greenery threshold
                    is_land = True
                    land_reason = f"has significant greenery ({greenery_ratio*100:.1f}% coverage)"

            # Final classification
            print(f"    Polygon {i+1}: {area:.0f} sq m")
            if is_land:
                print(f"      → LAND ({land_reason})")
            else:
                print(f"      → WATER (no significant land features found)")
                water_polygons.append(poly)
            # --- END OF MODIFIED CLASSIFICATION LOGIC ---

        print(f"    Classification result: {len(water_polygons)} water polygons, {len(valid_polygons) - len(water_polygons)} land polygons")

        return water_polygons

    except Exception as e:
        print(f"    Polygon classification failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def extract_coastline_lines(boundary_result, transformer):
    """Extract coastlines as line features for visualization."""

    coastline_lines = []

    for way in boundary_result.ways:
        way_type = way.tags.get('natural', way.tags.get('waterway', 'unknown'))

        if way_type == 'coastline':
            # OSM nodes are in lat, lon order
            coords = [(node.lat, node.lon) for node in way.nodes]
            if len(coords) >= 2:
                # Transform coordinates - your transformer expects (lon, lat) due to always_xy=True
                transformed_coords = []
                for lat, lon in coords:
                    x, y = transformer.transform(lon, lat)
                    transformed_coords.append((x, y))

                coastline_lines.append(transformed_coords)

    print(f"    Extracted {len(coastline_lines)} coastline lines for visualization")
    return coastline_lines


def extract_raw_coastline_segments(boundary_result, transformer):
    """Extract coastline segments as LineString objects for polygon export."""

    coastline_segments = []

    for way in boundary_result.ways:
        way_type = way.tags.get('natural', way.tags.get('waterway', 'unknown'))

        if way_type == 'coastline':
            # OSM nodes are in lat, lon order
            coords = [(node.lat, node.lon) for node in way.nodes]
            if len(coords) >= 2:
                # Transform coordinates - your transformer expects (lon, lat) due to always_xy=True
                transformed_coords = []
                for lat, lon in coords:
                    x, y = transformer.transform(lon, lat)
                    transformed_coords.append((x, y))

                coastline_segments.append(LineString(transformed_coords))

    print(f"    Extracted {len(coastline_segments)} raw coastline segments for export")
    return coastline_segments

# --- START OF NEW HELPER FUNCTION ---
def extract_island_polygons(boundary_result, transformer):
    """Extract island/islet ways and relations as Shapely Polygons."""
    island_polygons = []

    # Process Ways tagged as island/islet
    for way in boundary_result.ways:
        if way.tags.get('place') in ['island', 'islet']:
            coords = [(node.lat, node.lon) for node in way.nodes]
            if len(coords) >= 3:
                try:
                    transformed_coords = [transformer.transform(lon, lat) for lat, lon in coords]
                    poly = Polygon(transformed_coords)
                    if poly.is_valid and poly.area > 0:
                        island_polygons.append(poly)
                except Exception:
                    continue

    # Process Relations tagged as island/islet (for complex islands with holes)
    for relation in boundary_result.relations:
        if relation.tags.get('place') in ['island', 'islet'] and relation.tags.get('type') == 'multipolygon':
            try:
                outer_polys = []
                inner_polys = []
                for member in relation.members:
                    if isinstance(member, overpy.RelationWay):
                        way = boundary_result.get_way(member.ref)
                        coords = [(node.lat, node.lon) for node in way.nodes]
                        if len(coords) < 3: continue

                        transformed_coords = [transformer.transform(lon, lat) for lat, lon in coords]
                        poly = Polygon(transformed_coords)
                        if not poly.is_valid: continue

                        if member.role == 'outer':
                            outer_polys.append(poly)
                        elif member.role == 'inner':
                            inner_polys.append(poly)

                if outer_polys:
                    unified_outer = unary_union(outer_polys)
                    final_island = unified_outer
                    if inner_polys:
                        unified_inner = unary_union(inner_polys)
                        final_island = unified_outer.difference(unified_inner)

                    if final_island.is_valid and final_island.area > 0:
                        island_polygons.append(final_island)
            except Exception:
                continue

    print(f"    Extracted {len(island_polygons)} known island/islet polygons")
    return island_polygons
# --- END OF NEW HELPER FUNCTION ---