"""
Water Fetcher - Clean and Smooth
Keeps what works for inland water bodies, simplifies bay handling for now.
"""
import overpy
import json
import time
import os
import math
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union, linemerge, polygonize
from shapely.validation import make_valid
from config.cities import CITIES

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

def assemble_multipolygon_simple(relation, result):
    """Simplified multipolygon assembly - combines ALL boundary segments."""
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
                    is_coastline = way.tags.get('natural') == 'coastline'
                    is_closed = len(coords) >= 3 and coords[0] == coords[-1]
                    way_tags_str = ', '.join([f"{k}={v}" for k, v in way.tags.items()]) if way.tags else "no tags"

                    print(f"        Way {member.ref} ({member.role}): {len(coords)} coords, closed={is_closed}, tags=[{way_tags_str}]")

                    if member.role == 'outer':
                        # For outer ways, collect everything as line segments to be connected
                        all_outer_segments.append(LineString(coords))

                        # Also check if it's already a valid closed polygon
                        if is_closed and len(coords) >= 4:
                            try:
                                poly = Polygon(coords)
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
                        all_inner_segments.append(LineString(coords))

                        # Also check if it's already a valid closed polygon
                        if is_closed and len(coords) >= 4:
                            try:
                                poly = Polygon(coords)
                                if poly.is_valid and poly.area > 0:
                                    inner_polys.append(poly)
                                    print(f"        ✓ Added complete inner polygon from way {member.ref}")
                                else:
                                    fixed_poly = make_valid(poly)
                                    if isinstance(fixed_poly, Polygon) and fixed_poly.area > 0:
                                        inner_polys.append(fixed_poly)
                                        print(f"        ✓ Added fixed inner polygon from way {member.ref}")
                            except Exception as e:
                                print(f"        Warning: Invalid inner polygon from way {member.ref}: {e}")

            except Exception as e:
                print(f"        Warning: Could not process member way {member.ref}: {e}")
                continue

    # Try to connect ALL outer segments together (coastline + non-coastline)
    if all_outer_segments and not outer_polys:
        print(f"        Connecting {len(all_outer_segments)} outer segments (all types)...")
        connected_poly = connect_coastlines_to_polygon(all_outer_segments)
        if connected_poly:
            outer_polys.append(connected_poly)
            print(f"        ✓ Successfully connected all outer segments")
        else:
            print(f"        ✗ Failed to connect outer segments")

    # Try to connect ALL inner segments together
    if all_inner_segments:
        print(f"        Connecting {len(all_inner_segments)} inner segments (all types)...")
        connected_inner = connect_coastlines_to_polygon(all_inner_segments)
        if connected_inner:
            inner_polys.append(connected_inner)
            print(f"        ✓ Successfully connected all inner segments")

    # Also try polygonize as fallback for complex line arrangements
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

        # Apply holes (inner polygons)
        if inner_polys:
            try:
                if len(inner_polys) == 1:
                    unified_inner = inner_polys[0]
                else:
                    unified_inner = unary_union(inner_polys)

                if unified_inner.is_valid:
                    result_geom = unified_outer.difference(unified_inner)
                    if hasattr(result_geom, 'area') and result_geom.area > 0:
                        print(f"        ✓ Successfully created geometry with {len(inner_polys)} hole(s)")
                        return result_geom
            except Exception as e:
                print(f"        Warning: Could not apply holes: {e}")

        # Return outer polygons without holes if hole processing failed
        if hasattr(unified_outer, 'area') and unified_outer.area > 0:
            print(f"        ✓ Successfully created geometry")
            return unified_outer

    except Exception as e:
        print(f"        ✗ Could not assemble final geometry: {e}")
        return None

    return None

def fetch_water_bodies_for_city(city_key, max_retries=3):
    """Fetch water bodies with clean, working approach."""
    if city_key not in CITIES:
        print(f"City '{city_key}' not found in cities config")
        return []

    city_config = CITIES[city_key]
    city_name = city_config['name']
    center_lat, center_lon = city_config['center']
    bounds_km = city_config['bounds_km']

    print(f"\n=== Fetching water bodies for {city_name} ===")

    # Calculate search area - use a larger radius to catch nearby water bodies
    search_radius_km = bounds_km / 2 * 1.5  # 1.5x the city bounds for good coverage

    search_lat_offset = search_radius_km / 111.0
    search_lon_offset = search_radius_km / (111.0 * abs(math.cos(math.radians(center_lat))))

    search_south = center_lat - search_lat_offset
    search_north = center_lat + search_lat_offset
    search_west = center_lon - search_lon_offset
    search_east = center_lon + search_lon_offset

    print(f"  Center: {center_lat:.4f}, {center_lon:.4f}")
    print(f"  Search radius: {search_radius_km:.1f} km")
    print(f"  Search bbox: {search_south:.4f},{search_west:.4f},{search_north:.4f},{search_east:.4f}")

    api = overpy.Overpass()
    geojson_features = []

    retries = 0
    while retries < max_retries:
        try:
            print(f"  Querying Overpass API... (attempt {retries + 1}/{max_retries})")

            # Enhanced query that fetches ALL member ways of water relations
            query = f'''
            [out:json][timeout:300];
            (
                // Direct water features
                way["natural"="water"]({search_south},{search_west},{search_north},{search_east});
                way["natural"="bay"]({search_south},{search_west},{search_north},{search_east});
                way["place"="sea"]({search_south},{search_west},{search_north},{search_east});
                way["water"~"^(river|lake|pond|reservoir|bay)$"]({search_south},{search_west},{search_north},{search_east});
                way["waterway"="riverbank"]({search_south},{search_west},{search_north},{search_east});
                
                // Water relations
                relation["natural"="water"]({search_south},{search_west},{search_north},{search_east});
                relation["natural"="bay"]({search_south},{search_west},{search_north},{search_east});
                relation["place"="sea"]({search_south},{search_west},{search_north},{search_east});
                relation["type"="multipolygon"]["natural"="water"]({search_south},{search_west},{search_north},{search_east});
                relation["type"="multipolygon"]["natural"="bay"]({search_south},{search_west},{search_north},{search_east});
                relation["type"="multipolygon"]["place"="sea"]({search_south},{search_west},{search_north},{search_east});
                relation["type"="multipolygon"]["water"]({search_south},{search_west},{search_north},{search_east});
            );
            // CRITICAL: This fetches ALL ways referenced by the relations above, 
            // including non-coastline edges that form water boundaries
            (._;>;);
            out geom;
            '''

            start_time = time.time()
            result = api.query(query)
            query_time = time.time() - start_time

            print(f"  Query completed in {query_time:.2f} seconds")
            print(f"  Found {len(result.ways)} ways and {len(result.relations)} relations")

            # Collect relation member ways to avoid double processing
            relation_member_ways = set()
            for relation in result.relations:
                if relation.tags.get("type") == "multipolygon":
                    for member in relation.members:
                        if isinstance(member, overpy.RelationWay):
                            relation_member_ways.add(member.ref)

            # Process simple ways first
            way_count = 0
            for water_body in result.ways:
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

                        geometry = Polygon(coordinates)
                        if geometry.is_valid and geometry.area > 0:
                            geojson_features.append({
                                "type": "Feature",
                                "geometry": geometry.__geo_interface__,
                                "properties": {
                                    "name": water_body.tags.get("name", "Unknown"),
                                    "natural": water_body.tags.get("natural", ""),
                                    "water": water_body.tags.get("water", ""),
                                    "waterway": water_body.tags.get("waterway", ""),
                                    "place": water_body.tags.get("place", ""),
                                    "osm_id": water_body.id,
                                    "osm_type": "way"
                                }
                            })
                            way_count += 1

                            # Show progress for interesting water bodies
                            water_name = water_body.tags.get("name", "")
                            water_type = water_body.tags.get("natural", water_body.tags.get("water", "water"))
                            if water_name or water_type in ['bay', 'sea', 'lake']:
                                print(f"    ✓ Way {water_body.id}: {water_type} '{water_name}' (area: {geometry.area:.6f})")

                except Exception as e:
                    print(f"    Warning: Could not process way {water_body.id}: {e}")

            # Process multipolygon relations
            relation_count = 0
            for water_body in result.relations:
                if water_body.tags.get("type") == "multipolygon":
                    try:
                        water_name = water_body.tags.get("name", "Unknown")
                        water_type = water_body.tags.get("natural", water_body.tags.get("place", "water"))
                        print(f"    Processing relation {water_body.id}: {water_type} '{water_name}'...")

                        # Use simplified multipolygon assembly
                        geometry = assemble_multipolygon_simple(water_body, result)

                        if geometry and hasattr(geometry, '__geo_interface__'):
                            if hasattr(geometry, 'area') and geometry.area > 0:
                                geojson_features.append({
                                    "type": "Feature",
                                    "geometry": geometry.__geo_interface__,
                                    "properties": {
                                        "name": water_name,
                                        "natural": water_body.tags.get("natural", ""),
                                        "water": water_body.tags.get("water", ""),
                                        "place": water_body.tags.get("place", ""),
                                        "osm_id": water_body.id,
                                        "osm_type": "relation"
                                    }
                                })
                                relation_count += 1
                                print(f"    ✓ Successfully processed relation {water_body.id} (area: {geometry.area:.6f})")
                            else:
                                print(f"    ✗ Relation {water_body.id} has no area")
                        else:
                            print(f"    ✗ Could not create geometry for relation {water_body.id}")
                    except Exception as e:
                        print(f"    ✗ Failed to process relation {water_body.id}: {e}")

            print(f"  ✓ Processed {way_count} ways and {relation_count} relations")
            print(f"  Total water features: {len(geojson_features)}")

            break

        except Exception as e:
            retries += 1
            print(f"  Error (retry {retries}/{max_retries}): {e}")
            if retries < max_retries:
                wait_time = 10 * retries
                print(f"  Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

    return geojson_features

def save_water_to_file(features, city_key):
    """Save water features to GeoJSON file."""
    if not os.path.exists('output'):
        os.makedirs('output')

    filename = f"output/water_{city_key}.geojson"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            "type": "FeatureCollection",
            "features": features
        }, f, indent=2, ensure_ascii=False)

    print(f"  Saved to {filename}")
    return filename

def main():
    """Test water fetching."""
    city_key = 'wroclaw'  # Change this to test different cities

    print("Water Fetcher - Clean and Smooth")
    print("=" * 50)

    water_features = fetch_water_bodies_for_city(city_key)

    if water_features:
        filename = save_water_to_file(water_features, city_key)
        print(f"\n✅ Success! Found {len(water_features)} water features")
        print(f"📁 Saved to: {filename}")

        # Show summary of what was found
        way_count = sum(1 for f in water_features if f['properties']['osm_type'] == 'way')
        relation_count = sum(1 for f in water_features if f['properties']['osm_type'] == 'relation')

        print(f"\n📊 Summary:")
        print(f"  - Simple ways: {way_count}")
        print(f"  - Complex relations: {relation_count}")

        # Show largest water bodies
        sorted_features = sorted(water_features,
                               key=lambda f: f['geometry'].get('coordinates', [[]])[0]
                               if f['geometry']['type'] == 'Polygon' else 0,
                               reverse=True)

        print(f"\n🌊 Largest water bodies found:")
        for i, feature in enumerate(sorted_features[:5]):
            props = feature['properties']
            water_type = props.get('natural') or props.get('place') or props.get('water') or 'water'
            print(f"  {i+1}. {props['osm_type']} {props['osm_id']}: {water_type} '{props['name']}'")

    else:
        print("❌ No water features found")

if __name__ == "__main__":
    main()