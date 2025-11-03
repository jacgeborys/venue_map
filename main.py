# In main.py

import argparse
import time
from config.cities import CITIES
from config.settings import ensure_output_dir
from gastronomy.data_fetcher import GastronomyDataFetcher
from background.manager import BackgroundManager
from utils.data_cache import save_data_to_cache, load_data_from_cache
from gastronomy.map_generator import GastronomyMapGenerator



def main():
    parser = argparse.ArgumentParser(description='Urban Maps Generator')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Action to perform')

    fetch_parser = subparsers.add_parser('fetch', help='Download and cache map data for a city')
    fetch_parser.add_argument('city', help='City key (e.g., "berlin") or "all"')

    generate_parser = subparsers.add_parser('generate', help='Generate a map from cached data')
    generate_parser.add_argument('city', help='City key (e.g., "berlin") or "all"')
    generate_parser.add_argument('--clubs', action='store_true', help='Include nightclubs')
    generate_parser.add_argument('--palette', choices=['default', 'dark'], default='dark', help='Color palette')
    generate_parser.add_argument('--hotspots', action='store_true', help='Analyze and display gastronomy hotspots')

    args = parser.parse_args()
    ensure_output_dir()

    if args.command == 'fetch':
        run_fetch(args)
    elif args.command == 'generate':
        run_generate(args)


def run_fetch(args):
    """Handles the data fetching and caching process."""
    cities_to_fetch = CITIES.keys() if args.city.lower() == 'all' else [args.city.lower()]

    for city_key in cities_to_fetch:
        if city_key not in CITIES:
            print(f"City '{city_key}' not found. Skipping.")
            continue

        print(f"\n=== Fetching data for {CITIES[city_key]['name']} ===")
        city_config = CITIES[city_key]
        center_lat, center_lon = city_config['center']
        radius_km = city_config['bounds_km'] / 2

        raw_data = {'background': {}, 'venues': {}}

        print("  Fetching background layers...")
        bg_manager = BackgroundManager()
        raw_data['background'] = bg_manager.fetch_all_background(center_lat, center_lon, radius_km, 'full')

        print("  Pausing for 10 seconds to be polite to the API...")
        time.sleep(10)

        print("  Fetching venue layers...")
        venue_fetcher = GastronomyDataFetcher()
        raw_data['venues'] = venue_fetcher.fetch_all_venues(center_lat, center_lon, radius_km, include_clubs=True)

        save_data_to_cache(raw_data, city_key)


def run_generate(args):
    """Handles the map generation process from cached data."""
    cities_to_process = CITIES.keys() if args.city.lower() == 'all' else [args.city.lower()]

    for city_key in cities_to_process:
        if city_key not in CITIES:
            print(f"City '{city_key}' not found. Skipping.")
            continue

        raw_data = load_data_from_cache(city_key)
        if not raw_data:
            continue

        generator = GastronomyMapGenerator()
        generator.generate_map(
            city_key=city_key,
            raw_data=raw_data,
            include_clubs=args.clubs,
            palette=args.palette,
            analyze_hotspots=args.hotspots
        )


if __name__ == "__main__":
    import sys
    # === CONFIG 1: DATA FETCHING ===
    sys.argv = ['main.py', 'fetch', 'all']
    main()

# === CONFIG 2: MAP GENERATION (RUN AFTER FETCH IS COMPLETE) ===
    from config.cities import CITIES
    for city_key in CITIES.keys():
        import sys
        print(f"\n--- Queuing map generation for: {city_key.upper()} ---")
        sys.argv = ['main.py', 'generate', city_key, '--clubs', '--palette', 'dark', '--hotspots']
        main()
