"""
Gastronomy Map Generator
Main class for generating gastronomy maps with various background options.
"""
import matplotlib.pyplot as plt
import time
import os
import numpy as np # <-- ADD THIS IMPORT

from config.cities import CITIES
from config.settings import (
    setup_fonts, DEFAULT_FIGURE_SIZE, COPYRIGHT_TEXT, DPI, OUTPUT_DIR,
    GASTRONOMY_LABELS
)
from config.palettes import PALETTES
from utils.coordinate_transform import create_transformer, get_map_bounds
from utils.color_utils import darken_color
from gastronomy.data_fetcher import GastronomyDataFetcher
from gastronomy.venue_processor import VenueProcessor
from background.manager import BackgroundManager

class GastronomyMapGenerator:
    """Main class for generating gastronomy maps."""

    def __init__(self):
        self.font_available, self.font_paths = setup_fonts()
        self.data_fetcher = GastronomyDataFetcher()
        self.venue_processor = VenueProcessor()
        self.background_manager = BackgroundManager()

    def generate_map(self, city_key, include_clubs=False, background_type='roads', output_suffix=None, palette='default'):
        """Generate a gastronomy map for a city."""
        if city_key not in CITIES:
            print(f"City '{city_key}' not found.")
            return

        selected_palette = PALETTES.get(palette, PALETTES['default'])
        city_config = CITIES[city_key]
        city_name = city_config['name']
        center_lat, center_lon = city_config['center']
        radius_km = city_config['bounds_km'] / 2

        print(f"\n=== Generating gastronomy map for {city_name} ===")
        print(f"  Palette: '{palette}'")
        print(f"  Background: {background_type}")
        print(f"  Clubs: {'Yes' if include_clubs else 'No'}")

        try:
            start_time = time.time()
            transformer = create_transformer(city_config)
            map_bounds = get_map_bounds(city_config, transformer)
            raw_background = self.background_manager.fetch_all_background(center_lat, center_lon, radius_km, background_type)
            background_data = self.background_manager.process_all_background(raw_background, transformer, map_bounds, center_lat, center_lon, radius_km)

            print("  Fetching venue data...")
            venues_data = self.data_fetcher.fetch_all_venues(center_lat, center_lon, radius_km, include_clubs)
            venues_by_category = {cat: self.venue_processor.process_venues(data, transformer) for cat, data in venues_data.items()}

            fetch_time = time.time() - start_time
            print(f"  Data fetching and processing complete in {fetch_time:.2f} seconds.")

            print("  Creating map figure...")
            fig = self._create_map_figure(venues_by_category, background_data, city_config, map_bounds, include_clubs, background_type, selected_palette)

            filename = self._generate_filename(city_key, background_type, include_clubs, output_suffix, palette)
            filepath = os.path.join(OUTPUT_DIR, filename)
            plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor=selected_palette['background'])
            plt.close(fig)

            total_time = time.time() - start_time
            print(f"  ✓ Map saved as {filename}")
            print(f"  Total time: {total_time:.2f} seconds.")

        except Exception as e:
            print(f"Error generating map for {city_name}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            plt.close('all')

    # --- START OF REPLACEMENT ---
    # Replace the old _add_scale_bar method with this new, smarter one.
    def _add_scale_bar(self, ax, palette):
        """Add a stylish, dynamically-sized, palette-aware scale bar."""
        # Get the current map view's width in meters
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        map_width_m = xlim[1] - xlim[0]

        # --- 1. Calculate a sensible, "round" length for the scale bar ---
        # Aim for a bar that is roughly 1/4 of the map's width
        target_width_m = map_width_m / 4

        # Find the nearest "nice" round number (e.g., 1000, 2000, 5000)
        power = 10**np.floor(np.log10(target_width_m))
        relative_target = target_width_m / power
        if relative_target < 2:
            scale_length_map_units = 1 * power
        elif relative_target < 5:
            scale_length_map_units = 2 * power
        else:
            scale_length_map_units = 5 * power

        # --- 2. Create the label for the bar ---
        if scale_length_map_units >= 1000:
            label = f'{int(scale_length_map_units / 1000)} km'
        else:
            label = f'{int(scale_length_map_units)} m'

        # --- 3. Position and draw the bar ---
        margin = 0.05
        map_height_m = ylim[1] - ylim[0]

        x_end = xlim[1] - (margin * map_width_m)
        x_start = x_end - scale_length_map_units
        y_pos = ylim[0] + (margin * map_height_m)

        cap_height = map_height_m * 0.01
        bar_color = palette['title_text']

        # Drawing
        ax.plot([x_start, x_end], [y_pos, y_pos], color=bar_color, linewidth=1.5, solid_capstyle='butt', zorder=100)
        ax.plot([x_start, x_start], [y_pos - cap_height, y_pos], color=bar_color, linewidth=1.5, zorder=100)
        ax.plot([x_end, x_end], [y_pos - cap_height, y_pos], color=bar_color, linewidth=1.5, zorder=100)

        # Add text label
        font_props = self._get_font_properties('regular', 9)
        ax.text(x_start + scale_length_map_units / 2, y_pos + cap_height * 0.5,
                label,
                ha='center', va='bottom', color=bar_color, fontproperties=font_props, zorder=100)
    # --- END OF REPLACEMENT ---

    def _create_map_figure(self, venues_by_category, background_data, city_config,
                           map_bounds, include_clubs, background_type, palette):
        """Create the matplotlib figure for the map."""

        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE)
        ax.set_facecolor(palette['background'])
        ax.set_xlim(map_bounds['xlim'])
        ax.set_ylim(map_bounds['ylim'])
        ax.set_aspect('equal')
        ax.axis('off')

        self.background_manager.render_all_background(ax, background_data, palette, background_type)

        categories = ['restaurants', 'cafes', 'bars']
        if include_clubs:
            categories.append('clubs')
        for category in categories:
            venues = venues_by_category.get(category, [])
            if venues:
                xs, ys = zip(*venues)
                base_color = palette['gastronomy'][category]
                outline_color = darken_color(base_color, 0.5)
                ax.scatter(xs, ys, c=base_color, s=14, alpha=0.9, label=GASTRONOMY_LABELS[category],
                           edgecolors=outline_color, linewidth=0.5, zorder=5)

        legend_props = self._get_font_properties('regular', 12)
        legend = ax.legend(loc='lower left', bbox_to_anchor=(0.02, 0.02), frameon=True, fancybox=True, shadow=True,
                           framealpha=0.95, facecolor=palette['background'], prop=legend_props,
                           edgecolor='#cccccc', markerscale=2.0)
        legend.set_zorder(100)
        for text in legend.get_texts():
            text.set_color(palette['title_text'])

        title_props = self._get_font_properties('bold', 22)
        ax.text(0.02, 0.98, city_config['name'], transform=ax.transAxes, fontproperties=title_props,
                va='top', ha='left', color=palette['title_text'],
                bbox=dict(boxstyle="round,pad=0.4", facecolor=palette['background'], alpha=0.95, edgecolor='#cccccc'),
                zorder=100)

        copyright_props = self._get_font_properties('regular', 10)
        ax.text(0.5, 0.01, COPYRIGHT_TEXT, transform=ax.transAxes, fontproperties=copyright_props,
                va='bottom', ha='center', color=palette['copyright_text'], alpha=0.8, zorder=100)

        self._add_scale_bar(ax, palette)

        plt.tight_layout()
        return fig

    def _get_font_properties(self, weight, size):
        """Get font properties with fallback."""
        if self.font_available:
            from matplotlib import font_manager
            path = self.font_paths['bold'] if weight == 'bold' else self.font_paths['regular']
            return font_manager.FontProperties(fname=path, size=size)
        else:
            from matplotlib import font_manager
            return font_manager.FontProperties(size=size, weight='bold' if weight == 'bold' else 'normal')

    def _generate_filename(self, city_key, background_type, include_clubs, output_suffix, palette):
        """Generate output filename based on options."""
        parts = [city_key, 'gastronomy']
        if background_type != 'none':
            parts.append(f'{background_type}_bg')
        if include_clubs:
            parts.append('clubs')
        if palette != 'default':
            parts.append(palette)
        if output_suffix:
            parts.append(output_suffix)
        return '_'.join(parts) + '.png'