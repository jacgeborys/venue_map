"""
Global Settings and Configuration
"""
import os
from matplotlib import font_manager

# API Configuration
OVERPASS_URL = "http://overpass-api.de/api/interpreter"
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 5

# Font Configuration
FONT_PATHS = {
    'regular': r"D:\QGIS\functional_map\script\font\Inter_28pt-Regular.ttf",
    'bold': r"D:\QGIS\functional_map\script\font\Inter_28pt-Bold.ttf"
}

def setup_fonts():
    try:
        font_manager.fontManager.addfont(FONT_PATHS['regular'])
        font_manager.fontManager.addfont(FONT_PATHS['bold'])
        return True, FONT_PATHS
    except:
        return False, None

# Output Configuration
OUTPUT_DIR = 'output'
DPI = 300
DEFAULT_FIGURE_SIZE = (16, 12)
COPYRIGHT_TEXT = '© Jacek Gęborys, OpenStreetMap contributors'

# Color Schemes
GASTRONOMY_COLORS = {
    'bars': '#e82ad8',
    'cafes': '#eda51f',
    'restaurants': '#1079e3',
    'clubs': '#9b59b6'
}

GASTRONOMY_LABELS = {
    'bars': 'Bars & Pubs',
    'cafes': 'Cafes & Bakeries',
    'restaurants': 'Restaurants & Fast Food',
    'clubs': 'Nightclubs'
}

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)