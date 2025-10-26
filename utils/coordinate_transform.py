"""
Coordinate Transformation Utilities
"""
import math
from pyproj import Transformer


def create_transformer(city_config):
    hemisphere_code = '7' if city_config.get('hemisphere') == 'S' else '6'
    utm_epsg = f"EPSG:32{hemisphere_code}{city_config['utm_zone']:02d}"
    return Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)


def calculate_bbox(center_lat, center_lon, radius_km):
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * math.cos(math.radians(center_lat)))

    south, north = center_lat - lat_offset, center_lat + lat_offset
    west, east = center_lon - lon_offset, center_lon + lon_offset

    return f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}"


def get_map_bounds(city_config, transformer):
    center_x, center_y = transformer.transform(city_config['center'][1], city_config['center'][0])
    bounds_size = city_config['bounds_km'] * 1000 / 2

    return {
        'center_x': center_x,
        'center_y': center_y,
        'bounds_size': bounds_size,
        'xlim': (center_x - bounds_size, center_x + bounds_size),
        'ylim': (center_y - bounds_size, center_y + bounds_size)
    }