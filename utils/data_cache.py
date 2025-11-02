# In utils/data_cache.py

import geopandas as gpd
from shapely.geometry import Point, LineString
import os
import fiona
import pickle

CACHE_DIR = "data"


def get_city_cache_dir(city_key):
    """Creates and returns the path to a city-specific cache directory."""
    city_dir = os.path.join(CACHE_DIR, city_key)
    os.makedirs(city_dir, exist_ok=True)
    return city_dir


def save_data_to_cache(raw_data, city_key):
    """
    Saves each data layer to its own separate file within a city-specific folder.
    This version correctly handles all layers, including the new 'coastlines' layer.
    """
    city_cache_dir = get_city_cache_dir(city_key)
    print(f"    Saving data for {city_key} to folder: {city_cache_dir}")

    # --- Save Background Layers ---
    if raw_data.get('background'):
        for layer_name, data in raw_data['background'].items():
            if not data: continue

            # --- START OF THE DEFINITIVE BUG FIX ---

            # Step 1: Handle the special case for the water object's pickle file
            if layer_name == 'water' and '_overpy_result' in data:
                pkl_path = os.path.join(city_cache_dir, 'water.pkl')
                with open(pkl_path, 'wb') as f:
                    pickle.dump(data['_overpy_result'], f)
                print(f"      ✓ Saved 'water' object to {pkl_path}.")

            # Step 2: A single, unified process to save ALL layers (including water and coastlines) to GPKG
            source_elements = []
            if '_overpy_result' in data:  # For water
                source_elements = data['_overpy_result'].ways
            elif 'elements' in data:  # For roads, greenery, and coastlines
                source_elements = data.get('elements', [])
            else:
                continue

            features = []
            for element in source_elements:
                geom, tags = None, {}
                try:
                    tags = element.tags if hasattr(element, 'tags') else element.get('tags', {})
                    coords_raw = element.nodes if hasattr(element, 'nodes') else element.get('geometry', [])
                    coords = [(n.lon, n.lat) if hasattr(n, 'lon') else (n['lon'], n['lat']) for n in coords_raw]
                    if len(coords) >= 2: geom = LineString(coords)
                    if geom: features.append({'geometry': geom, 'tags': str(tags)})
                except:
                    continue

            if features:
                gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
                layer_path = os.path.join(city_cache_dir, f"{layer_name}.gpkg")
                gdf.to_file(layer_path, driver="GPKG")
                print(f"      ✓ Saved '{layer_name}' layer to {layer_path}.")
            # --- END OF THE DEFINITIVE BUG FIX ---

    # --- Save Venue Layers (Unchanged, this part is working well) ---
    if raw_data.get('venues'):
        for category, data in raw_data['venues'].items():
            elements = data.get('elements', [])
            if not elements: continue
            features = []
            for el in elements:
                geom = None
                if el.get('type') == 'node':
                    geom = Point(el['lon'], el['lat'])
                elif 'center' in el:
                    geom = Point(el.get('center', {}).get('lon'), el.get('center', {}).get('lat'))
                if geom: features.append({'geometry': geom, 'tags': str(el.get('tags', {}))})
            if features:
                gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
                layer_path = os.path.join(city_cache_dir, f"venues_{category}.gpkg")
                gdf.to_file(layer_path, driver="GPKG")
                print(f"      ✓ Saved 'venues_{category}' layer to {layer_path}.")

def load_data_from_cache(city_key):
    """
    Loads data from a city-specific folder, reading each file as a separate layer.
    """
    city_cache_dir = get_city_cache_dir(city_key)
    if not os.path.isdir(city_cache_dir):
        print(f"Error: Cache directory not found for '{city_key}'.")
        return None

    print(f"    Loading data from cache for {city_key}...")
    raw_data = {'background': {}, 'venues': {}}

    # Load the special water pickle file first
    water_pkl_path = os.path.join(city_cache_dir, 'water.pkl')
    if os.path.exists(water_pkl_path):
        with open(water_pkl_path, 'rb') as f:
            raw_data['background']['water'] = {'_overpy_result': pickle.load(f)}
        print("      ✓ Loaded 'water' data from pickle.")

    # Load all GPKG files in the directory
    for filename in os.listdir(city_cache_dir):
        if not filename.endswith('.gpkg'): continue

        layer_path = os.path.join(city_cache_dir, filename)
        layer_name = filename.replace('.gpkg', '')

        # Don't re-load the water geometry, we have the pickle object
        if layer_name == 'water': continue

        try:
            gdf = gpd.read_file(layer_path)
            elements = []
            for _, row in gdf.iterrows():
                geom, tags_str = row['geometry'], row.get('tags', '{}')
                if geom is None: continue
                element = {'tags': eval(tags_str) if tags_str else {}}
                if geom.geom_type == 'Point':
                    element.update({'type': 'node', 'lon': geom.x, 'lat': geom.y})
                else:
                    element.update({'type': 'way', 'geometry': [{'lon': x, 'lat': y} for x, y in geom.coords]})
                elements.append(element)

            if layer_name.startswith('venues_'):
                raw_data['venues'][layer_name.replace('venues_', '')] = {'elements': elements}
            else:
                raw_data['background'][layer_name] = {'elements': elements}
        except Exception as e:
            print(f"    ! Warning: Could not load layer file '{filename}': {e}")

    print(f"    ✓ Loaded {len(raw_data['background'])} background layers and {len(raw_data['venues'])} venue layers.")
    return raw_data