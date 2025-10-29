"""
Urban Maps Generator - Main Interface
"""
import argparse
from config.cities import CITIES
from config.settings import ensure_output_dir

def main():
    parser = argparse.ArgumentParser(description='Urban Maps Generator')
    subparsers = parser.add_subparsers(dest='command', help='Map type to generate')

    # Gastronomy maps subcommand
    gastronomy_parser = subparsers.add_parser('gastronomy', help='Generate gastronomy maps')
    gastronomy_parser.add_argument('city', help='City key or "all"')
    gastronomy_parser.add_argument('--clubs', action='store_true', help='Include nightclubs')
    gastronomy_parser.add_argument('--background', choices=['none', 'roads', 'full'],
                                 default='roads', help='Background type')
    # --- START OF MODIFICATION ---
    gastronomy_parser.add_argument('--palette', choices=['default', 'dark'], default='default',
                                 help='Color palette for the map')
    # --- END OF MODIFICATION ---

    list_parser = subparsers.add_parser('list', help='List available cities')

    args = parser.parse_args()
    ensure_output_dir()

    if args.command == 'list':
        list_cities()
    elif args.command == 'gastronomy':
        run_gastronomy_maps(args)

def list_cities():
    for key, config in CITIES.items():
        print(f"  {key:15} {config['name']}")

def run_gastronomy_maps(args):
    from gastronomy.map_generator import GastronomyMapGenerator
    generator = GastronomyMapGenerator()

    if args.city.lower() == 'all':
        for city_key in CITIES.keys():
            # --- START OF MODIFICATION ---
            generator.generate_map(city_key, args.clubs, args.background, palette=args.palette)
            # --- END OF MODIFICATION ---
    else:
        # --- START OF MODIFICATION ---
        generator.generate_map(args.city.lower(), args.clubs, args.background, palette=args.palette)
        # --- END OF MODIFICATION ---

if __name__ == "__main__":
    # For direct execution in PyCharm - generate all gastronomy maps
    import sys
    sys.argv = ['main.py', 'gastronomy', 'all', '--clubs', '--background', 'full', '--palette', 'dark']
    main()