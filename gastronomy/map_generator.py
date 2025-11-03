# In gastronomy/map_generator.py

import matplotlib.pyplot as plt
import time
import os
import numpy as np

from config.cities import CITIES
from config.settings import (
    setup_fonts, DEFAULT_FIGURE_SIZE, COPYRIGHT_TEXT, DPI, OUTPUT_DIR,
    GASTRONOMY_LABELS
)
from config.palettes import PALETTES
from utils.coordinate_transform import create_transformer, get_map_bounds
from utils.color_utils import darken_color
from gastronomy.venue_processor import VenueProcessor
from background.manager import BackgroundManager
from gastronomy.hotspot_analyzer import HotspotAnalyzer
from gastronomy.cluster_annotator import ClusterAnnotator


class GastronomyMapGenerator:
    """
    Main class for generating gastronomy maps from pre-fetched, cached data.
    """

    def __init__(self):
        self.font_available, self.font_paths = setup_fonts()
        self.venue_processor = VenueProcessor()
        self.background_manager = BackgroundManager()

    def generate_map(self, city_key, raw_data, include_clubs=False, palette='default', analyze_hotspots=False):
        """
        Generates a complete gastronomy map for a given city using provided raw data.
        """
        city_config = CITIES[city_key]
        city_name = city_config['name']
        mode = "Hotspot Analysis" if analyze_hotspots else "Standard"
        print(f"\n=== Generating map for {city_name} ({mode}) ===")

        try:
            start_time = time.time()
            transformer = create_transformer(city_config)
            map_bounds = get_map_bounds(city_config, transformer)

            # --- MODIFICATION: Use provided raw data, do NOT fetch ---
            print("  Processing cached background data...")
            background_data = self.background_manager.process_all_background(
                raw_data['background'], transformer, map_bounds,
                city_config['center'][0], city_config['center'][1],
                city_config['bounds_km'] / 2
            )

            print("  Processing cached venue data...")
            venues_by_category = {cat: self.venue_processor.process_venues(data, transformer) for cat, data in
                                  raw_data['venues'].items()}
            # --- END OF MODIFICATION ---

            annotator = None
            if analyze_hotspots:
                analyzer = HotspotAnalyzer(venues_by_category)
                top_clusters = analyzer.find_hubs()
                if top_clusters:
                    all_city_venues = [venue for venues in venues_by_category.values() for venue in venues]
                    annotator = ClusterAnnotator(top_clusters, all_city_venues)

            print("  Creating map figure...")
            fig = self._create_map_figure(venues_by_category, background_data, city_config, map_bounds, include_clubs,
                                          PALETTES.get(palette), annotator)

            filename = self._generate_filename(city_key, 'full', include_clubs, None, palette, analyze_hotspots)
            filepath = os.path.join(OUTPUT_DIR, filename)
            plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor=PALETTES.get(palette)['background'])
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

    # (The rest of this file, _create_map_figure and its helpers, does NOT need to change)
    def _create_map_figure(self, venues_by_category, background_data, city_config,
                           map_bounds, include_clubs, palette, annotator=None):
        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE)
        ax.set_facecolor(palette['background'])
        ax.set_xlim(map_bounds['xlim'])
        ax.set_ylim(map_bounds['ylim'])
        ax.set_aspect('equal')
        ax.axis('off')
        self.background_manager.render_all_background(ax, background_data, palette, 'full')
        self._render_standard_venues(ax, venues_by_category, include_clubs, palette)
        if annotator:
            annotator.draw_annotations(ax, palette, self._get_font_properties)
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

    def _add_scale_bar(self, ax, palette):
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        map_width_m = xlim[1] - xlim[0]
        target_width_m = map_width_m / 4
        power = 10 ** np.floor(np.log10(target_width_m))
        relative_target = target_width_m / power
        if relative_target < 2:
            scale_length_map_units = 1 * power
        elif relative_target < 5:
            scale_length_map_units = 2 * power
        else:
            scale_length_map_units = 5 * power
        label = f'{int(scale_length_map_units / 1000)} km' if scale_length_map_units >= 1000 else f'{int(scale_length_map_units)} m'
        margin = 0.05
        x_end = xlim[1] - (margin * map_width_m)
        x_start = x_end - scale_length_map_units
        y_pos = ylim[0] + (margin * (ylim[1] - ylim[0]))
        cap_height = (ylim[1] - ylim[0]) * 0.01
        bar_color = palette['title_text']
        ax.plot([x_start, x_end], [y_pos, y_pos], color=bar_color, linewidth=1.5, solid_capstyle='butt', zorder=100)
        ax.plot([x_start, x_start], [y_pos - cap_height, y_pos], color=bar_color, linewidth=1.5, zorder=100)
        ax.plot([x_end, x_end], [y_pos - cap_height, y_pos], color=bar_color, linewidth=1.5, zorder=100)
        ax.text(x_start + scale_length_map_units / 2, y_pos + cap_height * 0.5, label,
                ha='center', va='bottom', color=bar_color, fontproperties=self._get_font_properties('regular', 9),
                zorder=100)

    def _render_standard_venues(self, ax, venues_by_category, include_clubs, palette):
        categories = ['restaurants', 'cafes', 'bars']
        if include_clubs: categories.append('clubs')
        for category in categories:
            venues = venues_by_category.get(category, [])
            if venues:
                xs, ys = zip(*venues)
                base_color, outline_color = palette['gastronomy'][category], darken_color(
                    palette['gastronomy'][category], 0.6)
                ax.scatter(xs, ys, c=base_color, s=14, alpha=0.9, label=GASTRONOMY_LABELS[category],
                           edgecolors=outline_color, linewidth=0.5, zorder=5)
        legend_props = self._get_font_properties('regular', 12)
        legend = ax.legend(loc='lower left', bbox_to_anchor=(0.02, 0.02), frameon=True, fancybox=True, shadow=True,
                           framealpha=0.95, facecolor=palette['background'], prop=legend_props,
                           edgecolor='#cccccc', markerscale=2.0)
        legend.set_zorder(100)
        for text in legend.get_texts(): text.set_color(palette['title_text'])

    def _get_font_properties(self, weight, size):
        if self.font_available:
            from matplotlib import font_manager
            path = self.font_paths['bold'] if weight == 'bold' else self.font_paths['regular']
            return font_manager.FontProperties(fname=path, size=size)
        else:
            from matplotlib import font_manager
            return font_manager.FontProperties(size=size, weight='bold' if weight == 'bold' else 'normal')

    def _generate_filename(self, city_key, background_type, include_clubs, output_suffix, palette, analyze_hotspots):
        parts = [city_key, 'gastronomy']
        if background_type != 'none': parts.append(f'{background_type}_bg')
        if include_clubs: parts.append('clubs')
        if palette != 'default': parts.append(palette)
        if analyze_hotspots: parts.append('hubs_annotated')
        if output_suffix: parts.append(output_suffix)
        return '_'.join(parts) + '.png'