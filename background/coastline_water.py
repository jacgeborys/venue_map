# In background/coastline_water.py

import geopandas as gpd
from shapely.geometry import LineString, box, Point, Polygon
from shapely.ops import polygonize, unary_union
import numpy as np
from shapely.validation import make_valid


def is_on_right_side(polygon, coastline_segment):
    """Checks if a polygon is on the right-hand side of a directed coastline segment."""
    try:
        shared_boundary = polygon.boundary.intersection(coastline_segment)
        if shared_boundary.is_empty or not isinstance(shared_boundary,
                                                      (LineString)) or shared_boundary.length < 1.0: return None
        test_point = shared_boundary.interpolate(0.5, normalized=True)
        start_node_idx = -1;
        min_dist = float('inf')
        for i in range(len(coastline_segment.coords) - 1):
            dist = Point(test_point).distance(LineString(list(coastline_segment.coords)[i:i + 2]))
            if dist < min_dist: min_dist = dist; start_node_idx = i
        if start_node_idx == -1: return None
        p1, p2 = coastline_segment.coords[start_node_idx], coastline_segment.coords[start_node_idx + 1]
        vec_coastline = np.array(p2) - np.array(p1)
        vec_to_internal = np.array(polygon.representative_point().coords[0]) - np.array(test_point.coords[0])
        cross_product = np.cross(vec_coastline, vec_to_internal)
        return cross_product < 0
    except Exception:
        return None


def process_coastlines_from_cache(coastline_data, greenery_data, transformer, map_bounds):
    """
    Takes cached data and performs polygonization and classification,
    now with robust cleaning of all input geometries.
    """
    # 1. Extract and transform coastlines
    coastline_lines = []
    for el in coastline_data.get('elements', []):
        if el.get('type') == 'way':
            coords_raw = el.get('geometry', [])
            if len(coords_raw) >= 2:
                try:
                    coords = [transformer.transform(n['lon'], n['lat']) for n in coords_raw]
                    line = LineString(coords)
                    # Clean the coastline geometry
                    cleaned_line = make_valid(line)
                    if isinstance(cleaned_line, LineString):
                        coastline_lines.append(cleaned_line)
                except:
                    continue

    print(f"    -> Processed {len(coastline_lines)} coastline segments.")

    # 2. Extract, transform, AND CLEAN greenery polygons
    greenery_polygons = []
    for el in greenery_data.get('elements', []):
        coords_raw = el.get('geometry', [])
        if len(coords_raw) >= 3:
            try:
                # --- CRITICAL: Proactive Cleaning ---
                poly = Polygon([transformer.transform(n['lon'], n['lat']) for n in coords_raw])
                # Clean the polygon immediately after creation
                cleaned_poly = make_valid(poly)
                greenery_polygons.append(cleaned_poly)
            except:
                continue
    print(f"    -> Using {len(greenery_polygons)} cleaned greenery polygons for classification.")

    # 3. Polygonize with the map frame
    xmin, xmax = map_bounds['xlim'];
    ymin, ymax = map_bounds['ylim']
    map_frame = box(xmin, ymin, xmax, ymax)
    clipped_lines = [line.intersection(map_frame) for line in coastline_lines]
    final_coastline_lines = [g for line in clipped_lines if not line.is_empty for g in
                             (list(line.geoms) if line.geom_type == 'MultiLineString' else [line])]
    all_lines = final_coastline_lines + [map_frame.boundary]
    try:
        result_polygons = list(polygonize(unary_union(all_lines)))
        print(f"    -> Polygonization successful! Found {len(result_polygons)} polygons.")
    except Exception as e:
        print(f"    ✗ Coastline polygonization failed: {e}");
        return []

    # 4. Hybrid Classification with robust geometry handling
    water_polygons_shapely = []
    for poly in result_polygons:
        # --- CRITICAL: Clean all result polygons ---
        poly = make_valid(poly)

        initial_type = 'unknown'
        votes = {'water': 0, 'land': 0}
        for coastline in coastline_lines:
            if poly.boundary.intersects(coastline):
                result = is_on_right_side(poly, coastline)
                if result is True:
                    votes['water'] += 1
                elif result is False:
                    votes['land'] += 1

        if votes['land'] > votes['water']:
            initial_type = 'land'
        elif votes['water'] > votes['land']:
            initial_type = 'water'

        if initial_type == 'unknown':
            initial_type = 'water' if poly.boundary.intersects(map_frame.boundary) else 'land'

        final_type = initial_type
        if initial_type != 'land':
            # --- ROBUST GREENERY CHECK: Use try-catch for safety ---
            try:
                if any(poly.intersects(gp) and poly.intersection(gp).area > 50000 for gp in greenery_polygons):
                    final_type = 'land'
            except Exception as e:
                print(f"    Warning: Geometry intersection failed during classification: {e}")
                # Keep the initial classification if intersection fails

        if final_type == 'water':
            water_polygons_shapely.append(poly)

    print(f"    -> Classification complete: {len(water_polygons_shapely)} water polygons identified.")

    # 5. Convert to the standard dictionary format for the manager
    return [{'exterior': list(p.exterior.coords), 'holes': [list(i.coords) for i in p.interiors]} for p in
            water_polygons_shapely]