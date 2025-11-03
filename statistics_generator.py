# In statistics_generator.py

import os
import csv
from config.cities import CITIES
from utils.data_cache import load_data_from_cache
from gastronomy.venue_processor import VenueProcessor
from utils.coordinate_transform import create_transformer, get_map_bounds
import ast


class CityStatisticsGenerator:
    """
    Generates comprehensive statistics and rankings for all cached cities.
    Produces CSV files with density metrics and cultural ratios.
    Enhanced with restaurant vs fast food distinction and improved ratios.
    """

    def __init__(self):
        self.venue_processor = VenueProcessor()
        self.results = []

    def analyze_all_cities(self):
        """Analyze all cities with cached data."""
        print("=== Generating City Statistics ===")

        for city_key, city_config in CITIES.items():
            try:
                print(f"Analyzing {city_config['name']}...")
                stats = self.analyze_city(city_key)
                if stats:
                    self.results.append(stats)
            except Exception as e:
                print(f"  Error analyzing {city_key}: {e}")
                continue

        print(f"\nAnalyzed {len(self.results)} cities successfully.")
        return self.results

    def analyze_city(self, city_key):
        """Analyze a single city and return statistics."""
        # Load cached data
        raw_data = load_data_from_cache(city_key)
        if not raw_data or not raw_data.get('venues'):
            print(f"  No venue data found for {city_key}")
            return None

        city_config = CITIES[city_key]
        transformer = create_transformer(city_config)
        map_bounds = get_map_bounds(city_config, transformer)

        # Calculate map area in km²
        map_width_m = map_bounds['xlim'][1] - map_bounds['xlim'][0]
        map_height_m = map_bounds['ylim'][1] - map_bounds['ylim'][0]
        map_area_km2 = (map_width_m * map_height_m) / 1_000_000

        # Process venues with amenity type detection
        venue_counts = self._count_venues_by_type(raw_data['venues'], transformer)
        total_venues = sum(venue_counts.values())

        # Calculate basic metrics
        density_per_km2 = total_venues / map_area_km2 if map_area_km2 > 0 else 0

        # Calculate improved ratios
        restaurants = venue_counts.get('restaurants', 0)
        fast_food = venue_counts.get('fast_food', 0)
        cafes = venue_counts.get('cafes', 0)
        bars = venue_counts.get('bars', 0)
        clubs = venue_counts.get('clubs', 0)

        # Percentage breakdowns (as % of total venues)
        restaurant_pct = (restaurants / total_venues * 100) if total_venues > 0 else 0
        fast_food_pct = (fast_food / total_venues * 100) if total_venues > 0 else 0
        cafe_pct = (cafes / total_venues * 100) if total_venues > 0 else 0
        bar_pct = (bars / total_venues * 100) if total_venues > 0 else 0
        club_pct = (clubs / total_venues * 100) if total_venues > 0 else 0

        # Cultural ratios
        # Nightlife vs Dining Ratio (Bars+Clubs / Cafés+Restaurants+Fast Food)
        nightlife_dining_ratio = (bars + clubs) / (cafes + restaurants + fast_food) if (
                                                                                                   cafes + restaurants + fast_food) > 0 else float(
            'inf')

        # Fine vs Fast Ratio (Restaurants / Fast Food)
        fine_fast_ratio = restaurants / fast_food if fast_food > 0 else float('inf')

        # Dining vs Drinking Ratio (Restaurants+Fast Food / Bars+Clubs)
        dining_drinking_ratio = (restaurants + fast_food) / (bars + clubs) if (bars + clubs) > 0 else float('inf')

        # Nightlife Intensity (Clubs / Total venues) - as percentage
        nightlife_intensity = club_pct

        return {
            'city_key': city_key,
            'city_name': city_config['name'],
            'total_venues': total_venues,
            'restaurants': restaurants,
            'fast_food': fast_food,
            'cafes': cafes,
            'bars': bars,
            'clubs': clubs,
            'map_area_km2': round(map_area_km2, 2),
            'density_per_km2': round(density_per_km2, 1),
            'restaurant_pct': round(restaurant_pct, 1),
            'fast_food_pct': round(fast_food_pct, 1),
            'cafe_pct': round(cafe_pct, 1),
            'bar_pct': round(bar_pct, 1),
            'club_pct': round(club_pct, 1),
            'nightlife_dining_ratio': round(nightlife_dining_ratio, 2) if nightlife_dining_ratio != float(
                'inf') else 'inf',
            'fine_fast_ratio': round(fine_fast_ratio, 2) if fine_fast_ratio != float('inf') else 'inf',
            'dining_drinking_ratio': round(dining_drinking_ratio, 2) if dining_drinking_ratio != float(
                'inf') else 'inf',
            'nightlife_intensity': round(nightlife_intensity, 1)
        }

    def _count_venues_by_type(self, venues_data, transformer):
        """Count venues by specific amenity type from the tags."""
        counts = {
            'restaurants': 0,
            'fast_food': 0,
            'cafes': 0,
            'bars': 0,
            'clubs': 0
        }

        for category, data in venues_data.items():
            for element in data.get('elements', []):
                # Parse tags to determine exact amenity type
                tags_str = element.get('tags', {})
                if isinstance(tags_str, str):
                    try:
                        tags = ast.literal_eval(tags_str)
                    except:
                        tags = {}
                else:
                    tags = tags_str

                amenity = tags.get('amenity', '')
                shop = tags.get('shop', '')

                # Classify based on exact amenity/shop tags
                if amenity == 'restaurant':
                    counts['restaurants'] += 1
                elif amenity == 'fast_food':
                    counts['fast_food'] += 1
                elif amenity == 'cafe':
                    counts['cafes'] += 1
                elif shop in ['bakery', 'pastry']:
                    counts['cafes'] += 1
                elif amenity in ['bar', 'pub']:
                    counts['bars'] += 1
                elif amenity == 'nightclub':
                    counts['clubs'] += 1

        return counts

    def generate_rankings(self):
        """Generate various rankings from the results."""
        if not self.results:
            print("No results to rank!")
            return

        rankings = {}

        # Density Rankings
        rankings['highest_density'] = sorted(self.results, key=lambda x: x['density_per_km2'], reverse=True)

        # Percentage Rankings
        rankings['most_restaurants'] = sorted(self.results, key=lambda x: x['restaurant_pct'], reverse=True)
        rankings['most_cafes'] = sorted(self.results, key=lambda x: x['cafe_pct'], reverse=True)
        rankings['most_bars'] = sorted(self.results, key=lambda x: x['bar_pct'], reverse=True)
        rankings['most_fast_food'] = sorted(self.results, key=lambda x: x['fast_food_pct'], reverse=True)

        # Cultural Rankings (filter out infinite values)
        valid_nightlife_dining = [r for r in self.results if r['nightlife_dining_ratio'] != 'inf']
        rankings['most_nightlife_focused'] = sorted(valid_nightlife_dining, key=lambda x: x['nightlife_dining_ratio'],
                                                    reverse=True)

        valid_fine_fast = [r for r in self.results if r['fine_fast_ratio'] != 'inf']
        rankings['finest_dining'] = sorted(valid_fine_fast, key=lambda x: x['fine_fast_ratio'], reverse=True)

        valid_dining_drinking = [r for r in self.results if r['dining_drinking_ratio'] != 'inf']
        rankings['food_focused'] = sorted(valid_dining_drinking, key=lambda x: x['dining_drinking_ratio'], reverse=True)

        rankings['nightlife_capitals'] = sorted(self.results, key=lambda x: x['nightlife_intensity'], reverse=True)

        # Size Rankings
        rankings['largest_food_scenes'] = sorted(self.results, key=lambda x: x['total_venues'], reverse=True)

        return rankings

    def save_to_csv(self, filename='city_food_statistics.csv'):
        """Save all statistics to CSV."""
        if not self.results:
            print("No results to save!")
            return

        fieldnames = [
            'city_name', 'city_key', 'total_venues', 'restaurants', 'fast_food', 'cafes', 'bars', 'clubs',
            'map_area_km2', 'density_per_km2', 'restaurant_pct', 'fast_food_pct', 'cafe_pct', 'bar_pct', 'club_pct',
            'nightlife_dining_ratio', 'fine_fast_ratio', 'dining_drinking_ratio', 'nightlife_intensity'
        ]

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Sort by density for default ordering
            sorted_results = sorted(self.results, key=lambda x: x['density_per_km2'], reverse=True)

            for row in sorted_results:
                writer.writerow(row)

        print(f"Statistics saved to {filename}")

    def print_top_rankings(self, rankings, top_n=10):
        """Print formatted top rankings."""
        print("\n" + "=" * 60)
        print("GLOBAL CITY FOOD SCENE RANKINGS")
        print("=" * 60)

        print(f"\n🏙️  HIGHEST FOOD DENSITY (venues per km²)")
        for i, city in enumerate(rankings['highest_density'][:top_n], 1):
            print(f"{i:2d}. {city['city_name']:20s} {city['density_per_km2']:6.1f} venues/km²")

        print(f"\n🍺  MOST NIGHTLIFE-FOCUSED (nightlife venues per dining venue)")
        for i, city in enumerate(rankings['most_nightlife_focused'][:top_n], 1):
            ratio = city['nightlife_dining_ratio']
            print(f"{i:2d}. {city['city_name']:20s} {ratio:6.2f} bars+clubs per café+restaurant")

        print(f"\n☕  CAFÉ CULTURE CHAMPIONS (% cafés of all venues)")
        for i, city in enumerate(rankings['most_cafes'][:top_n], 1):
            print(f"{i:2d}. {city['city_name']:20s} {city['cafe_pct']:5.1f}% of venues are cafés")

        print(f"\n🍽️  FINEST DINING CITIES (full-service restaurants per fast food)")
        for i, city in enumerate(rankings['finest_dining'][:top_n], 1):
            ratio = city['fine_fast_ratio']
            print(f"{i:2d}. {city['city_name']:20s} {ratio:6.2f} restaurants per fast food place")

        print(f"\n🍔  FAST FOOD CAPITALS (% fast food of all venues)")
        for i, city in enumerate(rankings['most_fast_food'][:top_n], 1):
            print(f"{i:2d}. {city['city_name']:20s} {city['fast_food_pct']:5.1f}% of venues are fast food")

        print(f"\n🍕  MOST FOOD-FOCUSED (total dining venues per drinking venue)")
        for i, city in enumerate(rankings['food_focused'][:top_n], 1):
            ratio = city['dining_drinking_ratio']
            print(f"{i:2d}. {city['city_name']:20s} {ratio:6.2f} restaurants+cafés+fast food per bar+club")

        print(f"\n🌃  NIGHTLIFE CAPITALS (% nightclubs of all venues)")
        for i, city in enumerate(rankings['nightlife_capitals'][:top_n], 1):
            print(f"{i:2d}. {city['city_name']:20s} {city['nightlife_intensity']:5.1f}% nightclubs")


def main():
    """Main function to run the analysis."""
    generator = CityStatisticsGenerator()

    # Analyze all cities
    results = generator.analyze_all_cities()

    if results:
        # Generate rankings
        rankings = generator.generate_rankings()

        # Print top rankings
        generator.print_top_rankings(rankings)

        # Save to CSV
        generator.save_to_csv('city_food_statistics.csv')

        print(f"\n✅ Analysis complete! Check 'city_food_statistics.csv' for full data.")
    else:
        print("❌ No cities could be analyzed. Check your cache data.")


if __name__ == "__main__":
    main()