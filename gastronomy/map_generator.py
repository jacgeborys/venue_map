"""
Gastronomy Map Generator
Main class for generating gastronomy maps with various background options.
"""
import matplotlib.pyplot as plt
import time
import os

from config.cities import CITIES
from config.settings import (
    setup_fonts, DEFAULT_FIGURE_SIZE, COPYRIGHT_TEXT, DPI, OUTPUT_DIR,
    GASTRONOMY_COLORS, GASTRONOMY_LABELS
)
from utils.coordinate_transform import create_transformer, get_map_bounds
from gastronomy.data_fetcher import GastronomyDataFetcher
from gastronomy.venue_processor import VenueProcessor
from background.manager import BackgroundManager, BACKGROUND_COLORS

class GastronomyMapGenerator:
    """Main class for generating gastronomy maps."""

    def __init__(self):
        self.font_available, self.font_paths = setup_fonts()
        self.data_fetcher = GastronomyDataFetcher()
        self.venue_processor = VenueProcessor()
        self.background_manager = BackgroundManager()

    def generate_map(self, city_key, include_clubs=False, background_type='roads', output_suffix=None):
        """Generate a gastronomy map for a city."""
        if city_key not in CITIES:
            print(f"City '{city_key}' not found.")
            return

        city_config = CITIES[city_key]
        city_name = city_config['name']
        center_lat, center_lon = city_config['center']
        radius_km = city_config['bounds_km'] / 2

        print(f"\n=== Generating gastronomy map for {city_name} ===")
        print(f"  Center: {center_lat:.4f}, {center_lon:.4f}")
        print(f"  Radius: {radius_km} km")
        print(f"  Background: {background_type}")
        print(f"  Clubs: {'Yes' if include_clubs else 'No'}")

        try:
            start_time = time.time()

            # Setup coordinate transformation
            transformer = create_transformer(city_config)
            map_bounds = get_map_bounds(city_config, transformer)

            # Fetch background data if requested
            raw_background = self.background_manager.fetch_all_background(
                center_lat, center_lon, radius_km, background_type
            )

            # Process background data
            background_data = self.background_manager.process_all_background(
                raw_background, transformer, map_bounds, center_lat, center_lon, radius_km
            )

            # Fetch venue data
            print("  Fetching venue data...")
            venues_data = self.data_fetcher.fetch_all_venues(
                center_lat, center_lon, radius_km, include_clubs
            )

            # Process venues
            venues_by_category = {}
            for category, data in venues_data.items():
                venues_by_category[category] = self.venue_processor.process_venues(data, transformer)

            fetch_time = time.time() - start_time
            print(f"  Data fetching complete in {fetch_time:.2f} seconds.")

            # Generate map
            print("  Creating map...")
            fig = self._create_map_figure(
                venues_by_category,
                background_data,
                city_config,
                map_bounds,
                include_clubs,
                background_type
            )

            # Save map
            filename = self._generate_filename(city_key, background_type, include_clubs, output_suffix)
            filepath = os.path.join(OUTPUT_DIR, filename)
            plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            total_time = time.time() - start_time
            print(f"  Map saved as {filename}")
            print(f"  Total time: {total_time:.2f} seconds.")

        except Exception as e:
            print(f"Error generating map for {city_name}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            plt.close('all')

    def _create_map_figure(self, venues_by_category, background_data, city_config,
                           map_bounds, include_clubs, background_type):
        """Create the matplotlib figure for the map."""

        # Create figure
        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE)

        # Set background color - extremely pale gray for built-up areas
        if background_type != 'none':
            ax.set_facecolor(BACKGROUND_COLORS['built_up'])
        else:
            ax.set_facecolor(BACKGROUND_COLORS['clean'])

        # Set map bounds
        ax.set_xlim(map_bounds['xlim'])
        ax.set_ylim(map_bounds['ylim'])
        ax.set_aspect('equal')
        ax.axis('off')

        # Render all background layers in correct order
        self.background_manager.render_all_background(ax, background_data, background_type)

        # Plot venues
        categories = ['restaurants', 'cafes', 'bars']
        if include_clubs:
            categories.append('clubs')

        for category in categories:
            venues = venues_by_category.get(category, [])
            if venues:
                xs, ys = zip(*venues)
                ax.scatter(
                    xs, ys,
                    c=GASTRONOMY_COLORS[category],
                    s=14,
                    alpha=0.9,
                    label=GASTRONOMY_LABELS[category],
                    edgecolors='white',
                    linewidth=0.5,
                    zorder=5  # Changed from 15 to 5
                )

        # Add title with HIGH z-order
        title_props = self._get_font_properties('bold', 22)
        title_text = ax.text(0.02, 0.98, city_config['name'], transform=ax.transAxes,
                             fontproperties=title_props, va='top', ha='left',
                             bbox=dict(boxstyle="round,pad=0.4", facecolor='white', alpha=0.95,
                                       edgecolor='#cccccc'),
                             zorder=100)  # Very high z-order

        # Add copyright with HIGH z-order
        copyright_props = self._get_font_properties('regular', 10)
        copyright_text = ax.text(0.5, 0.01, COPYRIGHT_TEXT, transform=ax.transAxes,
                                 fontproperties=copyright_props, va='bottom', ha='center',
                                 color='#666666', alpha=0.8,
                                 zorder=100)  # Very high z-order

        # Add legend with HIGH z-order
        legend_props = self._get_font_properties('regular', 12)
        legend = ax.legend(loc='lower left', bbox_to_anchor=(0.02, 0.02),
                           frameon=True, fancybox=True, shadow=True,
                           framealpha=0.95, facecolor='white', prop=legend_props,
                           edgecolor='#cccccc', markerscale=2.0)
        legend.set_zorder(100)  # Very high z-order for legend

        plt.tight_layout()
        return fig

    def _get_font_properties(self, weight, size):
        """Get font properties with fallback."""
        if self.font_available:
            if weight == 'bold':
                from matplotlib import font_manager
                return font_manager.FontProperties(fname=self.font_paths['bold'], size=size)
            else:
                from matplotlib import font_manager
                return font_manager.FontProperties(fname=self.font_paths['regular'], size=size)
        else:
            from matplotlib import font_manager
            weight_val = 'bold' if weight == 'bold' else 'normal'
            return font_manager.FontProperties(size=size, weight=weight_val)

    def _generate_filename(self, city_key, background_type, include_clubs, output_suffix):
        """Generate output filename based on options."""
        parts = [city_key, 'gastronomy']

        if background_type == 'roads':
            parts.append('roads')
        elif background_type == 'full':
            parts.append('full_bg')

        if include_clubs:
            parts.append('clubs')

        if output_suffix:
            parts.append(output_suffix)

        return '_'.join(parts) + '.png'