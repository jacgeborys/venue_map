# In background/manager.py

from background.roads import RoadNetworkProcessor
from background.water import WaterProcessor
from background.greenery import GreeneryProcessor
from background.coastline import CoastlineProcessor
from matplotlib.patches import Rectangle

class BackgroundManager:
    """Manages all background layers with proper layering."""

    def __init__(self):
        self.road_processor = RoadNetworkProcessor()
        self.water_processor = WaterProcessor()
        self.greenery_processor = GreeneryProcessor()
        self.coastline_processor = CoastlineProcessor()

    def fetch_all_background(self, center_lat, center_lon, radius_km, background_type='full'):
        """Fetch all background data layers."""
        background_data = {}
        if background_type == 'full':
            print("  Fetching all background layers...")
            background_data['roads'] = self.road_processor.fetch_roads(center_lat, center_lon, radius_km)
            background_data['water'] = self.water_processor.fetch_water(center_lat, center_lon, radius_km)
            background_data['greenery'] = self.greenery_processor.fetch_greenery(center_lat, center_lon, radius_km)
            background_data['coastlines'] = self.coastline_processor.fetch_coastlines(center_lat, center_lon, radius_km)
        return background_data

    def process_all_background(self, background_data, transformer, map_bounds=None, center_lat=None, center_lon=None, radius_km=None):
        """Processes all background data using the unified water pipeline."""
        processed = {}
        if 'greenery' in background_data:
            processed['greenery'] = self.greenery_processor.process_greenery(background_data['greenery'], transformer)
            print(f"    Greenery: {sum(len(p) for p in processed['greenery'].values())} areas processed.")
        if 'roads' in background_data:
            processed['roads'] = self.road_processor.process_roads(background_data['roads'], transformer)
            print(f"    Roads: {sum(len(r) for r in processed['roads'].values())} segments")
        if 'water' in background_data:
            processed['water'] = self.water_processor.process_water(background_data['water'], transformer)
            print(f"    Inland Water: {len(processed['water'].get('polygons', []))} features processed.")
        if 'coastlines' in background_data and background_data['coastlines'].get('elements'):
            from background.coastline_water import process_coastlines_from_cache
            coastline_water_polygons = process_coastlines_from_cache(
                coastline_data=background_data['coastlines'],
                greenery_data=background_data.get('greenery'),
                transformer=transformer,
                map_bounds=map_bounds
            )
            if coastline_water_polygons:
                processed['water']['polygons'].extend(coastline_water_polygons)
                print(f"    ✓ Added {len(coastline_water_polygons)} coastline water polygons.")
        return processed

    def render_all_background(self, ax, processed_background, palette, background_type='full'):
        """Renders all processed background layers, now with categorized greenery."""
        if background_type == 'none': return

        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        ax.add_patch(Rectangle((xlim[0], ylim[0]), xlim[1] - xlim[0], ylim[1] - ylim[0],
                               facecolor=palette['built_up'], alpha=1.0, zorder=1, edgecolor='none'))

        if 'greenery' in processed_background:
            greenery_styles = {
                "forest": {'facecolor': palette['greenery_forest'], 'zorder': 2.2, 'edgecolor': 'none'},
                "farmland": {'facecolor': palette['greenery_farmland'], 'zorder': 2.1, 'edgecolor': 'none'},
                "leisure": {'facecolor': palette['greenery_leisure'], 'zorder': 2.0, 'edgecolor': 'none'}
            }
            self.greenery_processor.render_greenery(ax, processed_background['greenery'], greenery_styles)

        if 'water' in processed_background:
            self.water_processor.render_water(ax, processed_background['water'],
                                              {'polygon': {'color': palette['water'], 'alpha': 1.0, 'zorder': 3}})
        if 'roads' in processed_background:
            road_styles = {
                'major': {'color': palette['road_major'], 'linewidth': 2.5, 'alpha': 1.0, 'zorder': 4},
                'medium': {'color': palette['road_medium'], 'linewidth': 1.8, 'alpha': 1.0, 'zorder': 4},
                'minor': {'color': palette['road_minor'], 'linewidth': 1.0, 'alpha': 1.0, 'zorder': 4},
                'railway': {'color': palette['road_railway'], 'linewidth': 0.6, 'alpha': 1.0, 'zorder': 4}
            }
            self.road_processor.render_roads(ax, processed_background['roads'], road_styles)