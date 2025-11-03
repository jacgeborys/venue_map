# In config/palettes.py

# --- GASTRO COLORS FOR LIGHT MODE (Original and Correct) ---
GASTRONOMY_COLORS_LIGHT = {
    'restaurants': '#d9534f', # Red
    'cafes': '#f0ad4e',       # Orange
    'bars': '#5bc0de',        # Blue
    'clubs': '#9b59b6'        # Purple
}

# --- VIBRANT GASTRO COLORS FOR DARK MODE (Corrected with more orange cafe) ---
GASTRONOMY_COLORS_DARK = {
    'restaurants': '#0b8cff',
    'cafes': '#eda008',        # <<< CHANGED: Now slightly more orangeish
    'bars': '#fe0094',
    'clubs': '#d90033'
}

DEFAULT_GREENERY_STYLES = {
    'forest': {'facecolor': '#d1e8cf', 'zorder': 2.2, 'edgecolor': 'none'},
    'farmland': {'facecolor': '#e1f0d5', 'zorder': 2.1, 'edgecolor': 'none'}, # Slightly lighter
    'leisure': {'facecolor': '#cce6c3', 'zorder': 2.0, 'edgecolor': 'none'}  # Parks, slightly more saturated
}

# --- Default Light Palette ---
DEFAULT_PALETTE = {
    'background': '#f7f5f2',
    'built_up': '#ebebeb',
    'water': '#e3eeff',
    'greenery_forest': '#d1e8cf',
    'greenery_farmland': '#e1f0d5', # Lighter
    'greenery_leisure': '#cce6c3', # Parks
    'road_major': '#ffffff',
    'road_medium': '#ffffff',
    'road_minor': '#ffffff',
    'road_railway': '#fcfcfc',
    'title_text': '#000000',
    'copyright_text': '#666666',
    # 'point_outline': '#ffffff', # <<< DELETED: This is now dynamic
    'gastronomy': GASTRONOMY_COLORS_LIGHT
}

# --- New Dark Palette ---
DARK_PALETTE = {
    'background': '#1c1c1c',
    'built_up': '#2a2a2a',
    'water': '#334155',
    'greenery_forest': '#2E4034', # Dark, moody forest green
    'greenery_farmland': '#35473A', # Slightly lighter/desaturated dark green
    'greenery_leisure': '#2A3A2F', # Parks, slightly different dark green
    'road_major': '#505050',
    'road_medium': '#404040',
    'road_minor': '#303030',
    'road_railway': '#383838',
    'title_text': '#ffffff',
    'copyright_text': '#a0a0a0',
    # 'point_outline': '#000000', # <<< DELETED: This is now dynamic
    'gastronomy': GASTRONOMY_COLORS_DARK
}

# Master dictionary to hold all available palettes
PALETTES = {
    'default': DEFAULT_PALETTE,
    'dark': DARK_PALETTE
}