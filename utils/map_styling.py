"""
Map Styling Utilities
Common styling functions and configurations for all map types.
"""
import matplotlib.pyplot as plt
from matplotlib import font_manager
from config.settings import BACKGROUND_COLORS, GASTRONOMY_COLORS, COPYRIGHT_TEXT


class MapStyler:
    """Common styling utilities for maps."""

    def __init__(self, font_available=False, font_paths=None):
        self.font_available = font_available
        self.font_paths = font_paths

    def setup_figure(self, figsize=(16, 12), background_color='white'):
        """Create and setup a matplotlib figure with common settings."""
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_facecolor(background_color)
        ax.set_aspect('equal')
        ax.axis('off')
        return fig, ax

    def add_title(self, ax, title_text, position=(0.02, 0.98), fontsize=22):
        """Add styled title to the map."""
        title_props = self.get_font_properties('bold', fontsize)
        ax.text(position[0], position[1], title_text, transform=ax.transAxes,
                fontproperties=title_props, va='top', ha='left',
                bbox=dict(boxstyle="round,pad=0.4", facecolor='white', alpha=0.95,
                          edgecolor='#cccccc', linewidth=1))

    def add_copyright(self, ax, position=(0.5, 0.01)):
        """Add copyright notice to the map."""
        copyright_props = self.get_font_properties('regular', 10)
        ax.text(position[0], position[1], COPYRIGHT_TEXT, transform=ax.transAxes,
                fontproperties=copyright_props, va='bottom', ha='center',
                color='#666666', alpha=0.8)

    def add_legend(self, ax, position='lower left', bbox_anchor=(0.02, 0.02)):
        """Add styled legend to the map."""
        legend_props = self.get_font_properties('regular', 12)
        legend = ax.legend(loc=position, bbox_to_anchor=bbox_anchor,
                           frameon=True, fancybox=True, shadow=True,
                           framealpha=0.95, facecolor='white', prop=legend_props,
                           edgecolor='#cccccc', linewidth=1)
        return legend

    def get_font_properties(self, weight='regular', size=12):
        """Get font properties with fallback to system fonts."""
        if self.font_available and self.font_paths:
            if weight == 'bold':
                return font_manager.FontProperties(fname=self.font_paths['bold'], size=size)
            else:
                return font_manager.FontProperties(fname=self.font_paths['regular'], size=size)
        else:
            weight_val = 'bold' if weight == 'bold' else 'normal'
            return font_manager.FontProperties(size=size, weight=weight_val)

    def style_venue_scatter(self, ax, venues, category, zorder=10):
        """Apply standard styling to venue scatter plots."""
        if not venues:
            return

        xs, ys = zip(*venues)
        color = GASTRONOMY_COLORS.get(category, '#000000')

        ax.scatter(xs, ys, c=color, s=14, alpha=0.9,
                   edgecolors='white', linewidth=0.5, zorder=zorder)

    def apply_map_bounds(self, ax, bounds):
        """Apply coordinate bounds to the map."""
        ax.set_xlim(bounds['xlim'])
        ax.set_ylim(bounds['ylim'])


# Color scheme utilities
def get_background_style(style_type='light'):
    """Get predefined background color schemes."""
    schemes = {
        'light': {
            'background': '#f9f9f9',
            'major_roads': '#b8b8b8',
            'medium_roads': '#d0d0d0',
            'minor_roads': '#e8e8e8',
            'buildings': '#e0e0e0',
            'water': '#e8e8e8'
        },
        'minimal': {
            'background': '#ffffff',
            'major_roads': '#d0d0d0',
            'medium_roads': '#e0e0e0',
            'minor_roads': '#f0f0f0',
            'buildings': '#f5f5f5',
            'water': '#f0f0f0'
        },
        'dark': {
            'background': '#2d2d2d',
            'major_roads': '#606060',
            'medium_roads': '#505050',
            'minor_roads': '#404040',
            'buildings': '#3a3a3a',
            'water': '#404040'
        }
    }
    return schemes.get(style_type, schemes['light'])


def get_venue_colors(style='default'):
    """Get venue color schemes."""
    schemes = {
        'default': GASTRONOMY_COLORS,
        'pastel': {
            'bars': '#e8a4c9',
            'cafes': '#ffcc80',
            'restaurants': '#81c4f7',
            'clubs': '#c5a8d9'
        },
        'bright': {
            'bars': '#ff1744',
            'cafes': '#ff6f00',
            'restaurants': '#2196f3',
            'clubs': '#9c27b0'
        }
    }
    return schemes.get(style, schemes['default'])