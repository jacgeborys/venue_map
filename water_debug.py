# In water_debug.py

import geopandas as gpd
from shapely.geometry import LineString, box, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid
import os
import numpy as np

from config.cities import CITIES
from utils.coordinate_transform import create_transformer, get_map_bounds

# --- Configuration ---
CITY_KEY = 'san_francisco'
OUTPUT_FILENAME = "debug_polygons_{}.gpkg".format(CITY_KEY)

# --- Define paths ---
CACHE_DIR, OUTPUT_DIR = "data", "output"
city_cache_dir = os.path.join(CACHE_DIR, CITY_KEY)
coastline_filepath = os.path.join(city_cache_dir, 'coastlines.gpkg')
greenery_filepath = os.path.join(city_cache_dir, 'greenery.gpkg')
output_filepath = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)


def is_on_right_side(polygon, coastline_segment):
    # (This helper function is unchanged and works well)
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


def main():
    """
    Loads coastlines, polygonizes them, and classifies them using a robust,
    multi-stage hybrid approach (Right-Hand Rule + Greenery Veto).
    """
    print(f"--- Starting Hybrid Land/Water Classification for: {CITY_KEY.upper()} ---")
    if CITY_KEY not in CITIES: return

    # 1. Load Data (unchanged)
    if not os.path.exists(coastline_filepath): return
    coastlines_gdf_latlon = gpd.read_file(coastline_filepath)
    if coastlines_gdf_latlon.empty: return
    city_config = CITIES[CITY_KEY]
    transformer = create_transformer(city_config)
    map_bounds = get_map_bounds(city_config, transformer)
    coastlines_gdf_proj = coastlines_gdf_latlon.to_crs(transformer.target_crs)
    coastline_lines = [line for line in coastlines_gdf_proj.geometry if isinstance(line, LineString)]

    greenery_polygons = []
    if os.path.exists(greenery_filepath):
        greenery_gdf_latlon = gpd.read_file(greenery_filepath)
        greenery_gdf_proj = greenery_gdf_latlon.to_crs(transformer.target_crs)
        for geom in greenery_gdf_proj.geometry:
            if geom and not geom.is_empty and isinstance(geom, LineString) and len(geom.coords) >= 3:
                try:
                    # --- CRITICAL FIX: Clean invalid geometries using make_valid ---
                    poly = Polygon(geom.coords)
                    cleaned_poly = make_valid(poly)
                    greenery_polygons.append(cleaned_poly)
                except:
                    continue
        print(f"  ✓ Loaded and converted {len(greenery_polygons)} cleaned greenery polygons.")

    # 2. Polygonize (unchanged)
    xmin, xmax = map_bounds['xlim'];
    ymin, ymax = map_bounds['ylim']
    map_frame = box(xmin, ymin, xmax, ymax)
    clipped_lines = [line.intersection(map_frame) for line in coastline_lines]
    final_coastline_lines = [g for line in clipped_lines if not line.is_empty for g in
                             (list(line.geoms) if line.geom_type == 'MultiLineString' else [line])]
    all_lines = final_coastline_lines + [map_frame.boundary]
    try:
        result_polygons = list(polygonize(unary_union(all_lines)))
        print(f"  ✓ Polygonization successful! Found {len(result_polygons)} polygons.")
    except Exception as e:
        print(f"ERROR: Polygonization failed: {e}");
        return

    # --- START OF THE DEFINITIVE HYBRID CLASSIFICATION ---
    # 3. Classify polygons using the new multi-stage approach
    print("  -> Classifying polygons using hybrid rules...")
    classified_polygons = []
    for poly in result_polygons:
        # --- ADDITIONAL FIX: Clean the result polygons too ---
        poly = make_valid(poly)

        # Rule 1: Use the Right-Hand Rule to get an initial classification
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

        # If still unknown, use the frame as a weak indicator
        if initial_type == 'unknown':
            initial_type = 'water' if poly.boundary.intersects(map_frame.boundary) else 'land'

        # Rule 2: The Greenery Veto.
        # If the polygon was NOT classified as land, check for greenery.
        final_type = initial_type
        if initial_type != 'land':
            # If it has any significant greenery, override the classification to LAND.
            # --- ROBUST INTERSECTION: Use try-catch for safety ---
            try:
                if any(poly.intersects(gp) and poly.intersection(gp).area > 20000 for gp in greenery_polygons):
                    final_type = 'land'
            except Exception as e:
                print(f"    Warning: Geometry intersection failed, skipping greenery check: {e}")
                # Keep the initial_type if intersection fails

        classified_polygons.append({'polygon': poly, 'type': final_type})
    # --- END OF THE DEFINITIVE HYBRID CLASSIFICATION ---

    land_count = sum(1 for p in classified_polygons if p['type'] == 'land')
    water_count = sum(1 for p in classified_polygons if p['type'] == 'water')
    print(f"  ✓ Classification complete: {land_count} land polygon(s), {water_count} water polygon(s).")

    # 4. Save the results (unchanged)
    output_gdf = gpd.GeoDataFrame(
        [{'type': p['type'], 'area_sqkm': p['polygon'].area / 1e6} for p in classified_polygons],
        geometry=[p['polygon'] for p in classified_polygons], crs=transformer.target_crs
    )
    if os.path.exists(output_filepath): os.remove(output_filepath)
    output_gdf.to_file(output_filepath, driver="GPKG")
    print(f"\nSUCCESS! Saved {len(output_gdf)} polygons to '{output_filepath}'.")


if __name__ == "__main__":
    main()