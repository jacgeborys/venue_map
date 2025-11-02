# In background/water.py

import math
import overpy
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.validation import make_valid
from utils.osm_client import osm_client


class WaterProcessor:
    def __init__(self):
        self.client = osm_client

    def fetch_water(self, center_lat, center_lon, radius_km):
        search_radius_km = radius_km * 1.5
        lat_offset, lon_offset = search_radius_km / 111.0, search_radius_km / (
                    111.0 * abs(math.cos(math.radians(center_lat))))
        s, n, w, e = center_lat - lat_offset, center_lat + lat_offset, center_lon - lon_offset, center_lon + lon_offset

        query = f'''[out:json][timeout:300];(
            way["natural"~"water|bay|strait"]({s},{w},{n},{e});
            way["place"="sea"]({s},{w},{n},{e});
            way["water"~"^(river|lake|pond|reservoir|bay)$"]({s},{w},{n},{e});
            way["waterway"="riverbank"]({s},{w},{n},{e});
            relation["natural"~"water|bay|strait"]({s},{w},{n},{e});
            relation["place"="sea"]({s},{w},{n},{e});
            relation["type"="multipolygon"]["natural"~"water|bay"]({s},{w},{n},{e});
            relation["type"="multipolygon"]["place"="sea"]({s},{w},{n},{e});
            relation["type"="multipolygon"]["water"]({s},{w},{n},{e});
        );(._;>;);out geom;'''

        try:
            response_json = self.client.query(query, data_type="water", timeout=300)
            result = overpy.Result.from_json(response_json)
            print(f"    ✓ Found {len(result.ways)} ways and {len(result.relations)} for water.")
            return {'_overpy_result': result}
        except Exception as e:
            print(f"    ✗ Failed to fetch water features: {e}")
            return {}

    def process_water(self, water_data, transformer):
        water_features = {'polygons': [], 'lines': []}
        overpy_result = water_data.get('_overpy_result')
        if not overpy_result: return water_features

        ways = {el.id: el for el in overpy_result.ways}
        relations = overpy_result.relations
        processed_way_ids = set()

        for rel in relations:
            if rel.tags.get('type') != 'multipolygon': continue
            outer_segments, inner_segments = [], []
            for member in rel.members:
                if isinstance(member, overpy.RelationWay) and member.ref in ways:
                    way = ways[member.ref]
                    coords = [transformer.transform(node.lon, node.lat) for node in way.nodes]
                    if len(coords) >= 2:
                        if member.role == 'outer':
                            outer_segments.append(LineString(coords))
                        elif member.role == 'inner':
                            inner_segments.append(LineString(coords))
                        processed_way_ids.add(member.ref)
            try:
                if not outer_segments: continue
                unified_outer = make_valid(unary_union(list(polygonize(outer_segments))))
                final_geom = unified_outer
                if inner_segments:
                    unified_inner = make_valid(unary_union(list(polygonize(inner_segments))))
                    final_geom = unified_outer.difference(unified_inner)
                geoms = list(final_geom.geoms) if hasattr(final_geom, 'geoms') else [final_geom]
                for poly in geoms:
                    if isinstance(poly, Polygon):
                        water_features['polygons'].append(
                            {'exterior': list(poly.exterior.coords), 'holes': [list(i.coords) for i in poly.interiors]})
            except:
                continue

        for way_id, way in ways.items():
            if way_id in processed_way_ids or len(way.nodes) < 4 or way.nodes[0].id != way.nodes[-1].id: continue
            coords = [transformer.transform(node.lon, node.lat) for node in way.nodes]
            water_features['polygons'].append({'exterior': coords, 'holes': []})
        return water_features

    def render_water(self, ax, water_data, style=None):
        if style is None: style = DEFAULT_WATER_STYLE
        from matplotlib.path import Path
        import matplotlib.patches as patches
        for poly_data in water_data.get('polygons', []):
            try:
                exterior = poly_data.get('exterior', [])
                if len(exterior) < 3: continue
                path_verts, path_codes = list(exterior), [Path.MOVETO] + [Path.LINETO] * (len(exterior) - 2) + [
                    Path.CLOSEPOLY]
                for hole in poly_data.get('holes', []):
                    if len(hole) < 3: continue
                    path_verts.extend(hole)
                    path_codes.extend([Path.MOVETO] + [Path.LINETO] * (len(hole) - 2) + [Path.CLOSEPOLY])
                ax.add_patch(patches.PathPatch(Path(path_verts, path_codes), **style['polygon']))
            except:
                continue


# --- THIS IS THE CRITICAL MISSING PIECE ---
DEFAULT_WATER_STYLE = {'polygon': {'color': '#e3eeff', 'alpha': 1.0, 'zorder': 3}}