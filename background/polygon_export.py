"""
Enhanced Polygon Export Script for QGIS Analysis
Exports coastline-generated polygons to both CSV (WKT) and GPKG formats for QGIS import
"""
import csv
import os
from shapely.geometry import Polygon, LineString, box
from shapely.ops import polygonize

# Try to import geopandas for GPKG export
try:
    import geopandas as gpd
    import pandas as pd
    GPKG_AVAILABLE = True
    print("✓ GeoPandas available - GPKG export enabled")
except ImportError:
    GPKG_AVAILABLE = False
    print("⚠ GeoPandas not available - only CSV export will work")


def ensure_output_directory(output_path):
    """Ensure the output directory exists."""
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        print(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    return output_dir


def export_coastline_polygons_for_qgis(coastline_segments, map_bounds, greenery_data=None,
                                       output_base="D:/QGIS/gastro_map/python/output/stockholm_polygons",
                                       utm_zone=34, hemisphere='N'):
    """Export all polygons created by coastlines to both CSV and GPKG formats."""

    try:
        print(f"\n=== Starting Polygon Export ===")
        print(f"Input data:")
        print(f"  - Coastline segments: {len(coastline_segments) if coastline_segments else 0}")
        print(f"  - Map bounds: {map_bounds}")
        print(f"  - Greenery areas: {len(greenery_data) if greenery_data else 0}")
        print(f"  - UTM Zone: {utm_zone}{hemisphere}")

        # Create the correct EPSG code for UTM
        hemisphere_code = '7' if hemisphere == 'S' else '6'
        utm_epsg = f"EPSG:32{hemisphere_code}{utm_zone:02d}"
        print(f"  - Using CRS: {utm_epsg}")

        # Ensure output directory exists
        output_dir = ensure_output_directory(output_base + ".csv")

        # Create map boundary
        map_polygon = box(
            map_bounds['xlim'][0],
            map_bounds['ylim'][0],
            map_bounds['xlim'][1],
            map_bounds['ylim'][1]
        )

        print(f"Map polygon area: {map_polygon.area:.2f}")

        # Combine coastlines with map boundary for polygonization
        all_lines = list(coastline_segments) if coastline_segments else []
        map_boundary = LineString(list(map_polygon.exterior.coords))
        all_lines.append(map_boundary)

        print(f"Running polygonize on {len(all_lines)} lines...")

        # Create all polygons
        all_polygons = list(polygonize(all_lines))
        print(f"Created {len(all_polygons)} polygons from polygonize")

        if not all_polygons:
            print("❌ No polygons created - cannot export")
            return None

        # Convert greenery data to Shapely polygons
        greenery_polygons = []
        if greenery_data and len(greenery_data) > 0:
            print(f"Converting {len(greenery_data)} greenery areas...")
            for i, greenery_coords in enumerate(greenery_data):
                try:
                    if len(greenery_coords) >= 3:
                        greenery_poly = Polygon(greenery_coords)
                        if greenery_poly.is_valid and greenery_poly.area > 100:
                            greenery_polygons.append(greenery_poly)
                except Exception as e:
                    print(f"    Skipping greenery polygon {i}: {e}")
                    continue
            print(f"Valid greenery polygons: {len(greenery_polygons)}")

        # Analyze each polygon
        polygon_data = []
        print(f"Analyzing polygons...")

        for i, poly in enumerate(all_polygons):
            if not poly.is_valid:
                print(f"  Skipping invalid polygon {i}")
                continue

            area = poly.area
            area_ratio = area / map_polygon.area

            # Count greenery intersections
            greenery_count = 0
            total_greenery_area = 0

            for greenery_poly in greenery_polygons:
                try:
                    if poly.intersects(greenery_poly):
                        intersection = poly.intersection(greenery_poly)
                        if hasattr(intersection, 'area') and intersection.area > 50:
                            greenery_count += 1
                            total_greenery_area += intersection.area
                except Exception as e:
                    continue

            greenery_ratio = total_greenery_area / area if area > 0 else 0

            # Classification
            has_greenery = greenery_count > 0
            classification = "LAND" if has_greenery else "WATER"

            polygon_data.append({
                'polygon_id': i + 1,
                'area_sqm': round(area, 2),
                'area_percent': round(area_ratio * 100, 3),
                'greenery_count': greenery_count,
                'greenery_area_sqm': round(total_greenery_area, 2),
                'greenery_percent': round(greenery_ratio * 100, 2),
                'has_greenery': has_greenery,
                'classification': classification,
                'geometry': poly
            })

        if not polygon_data:
            print("❌ No valid polygons to export")
            return None

        print(f"Valid polygons to export: {len(polygon_data)}")

        # Export to CSV
        csv_path = output_base + ".csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['polygon_id', 'area_sqm', 'area_percent', 'greenery_count',
                          'greenery_area_sqm', 'greenery_percent', 'has_greenery',
                          'classification', 'geometry_wkt']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in polygon_data:
                csv_row = row.copy()
                csv_row['geometry_wkt'] = row['geometry'].wkt
                del csv_row['geometry']
                writer.writerow(csv_row)

        print(f"✓ CSV exported to: {csv_path}")

        # Export to GPKG if available
        gpkg_path = None
        if GPKG_AVAILABLE:
            try:
                gpkg_path = output_base + ".gpkg"

                # Create GeoDataFrame
                gdf_data = []
                for row in polygon_data:
                    gdf_row = row.copy()
                    del gdf_row['geometry']  # Remove geometry key, will be added as geometry column
                    gdf_data.append(gdf_row)

                geometries = [row['geometry'] for row in polygon_data]

                gdf = gpd.GeoDataFrame(gdf_data, geometry=geometries, crs=utm_epsg)
                gdf.to_file(gpkg_path, driver="GPKG", layer="polygons")

                print(f"✓ GPKG exported to: {gpkg_path}")

            except Exception as e:
                print(f"❌ GPKG export failed: {e}")
                gpkg_path = None

        # Sort by area and print summary
        polygon_data.sort(key=lambda x: x['area_sqm'], reverse=True)

        print(f"\n=== Export Summary ===")
        print(f"Total polygons: {len(polygon_data)}")
        print(f"Land polygons: {len([p for p in polygon_data if p['classification'] == 'LAND'])}")
        print(f"Water polygons: {len([p for p in polygon_data if p['classification'] == 'WATER'])}")

        print(f"\nTop 5 largest polygons:")
        for row in polygon_data[:5]:
            print(f"  {row['polygon_id']}: {row['area_sqm']:.0f} sq m ({row['area_percent']:.1f}%) - {row['classification']}")
            print(f"    Greenery: {row['greenery_count']} areas, {row['greenery_percent']:.1f}% coverage")

        return {"csv": csv_path, "gpkg": gpkg_path}

    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_coastlines_for_qgis(coastline_segments, output_base="D:/QGIS/gastro_map/python/output/stockholm_coastlines",
                               utm_zone=34, hemisphere='N'):
    """Export coastline segments to both CSV and GPKG formats."""

    try:
        print(f"\n=== Exporting Coastlines ===")
        print(f"Coastline segments: {len(coastline_segments)}")
        print(f"UTM Zone: {utm_zone}{hemisphere}")

        if not coastline_segments:
            print("No coastline segments to export")
            return None

        # Create the correct EPSG code for UTM
        hemisphere_code = '7' if hemisphere == 'S' else '6'
        utm_epsg = f"EPSG:32{hemisphere_code}{utm_zone:02d}"
        print(f"Using CRS: {utm_epsg}")

        # Ensure output directory exists
        ensure_output_directory(output_base + ".csv")

        # Export to CSV
        csv_path = output_base + ".csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['segment_id', 'length_m', 'num_points', 'geometry_wkt']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for i, segment in enumerate(coastline_segments):
                writer.writerow({
                    'segment_id': i + 1,
                    'length_m': round(segment.length, 2),
                    'num_points': len(list(segment.coords)),
                    'geometry_wkt': segment.wkt
                })

        print(f"✓ CSV exported to: {csv_path}")

        # Export to GPKG if available
        gpkg_path = None
        if GPKG_AVAILABLE:
            try:
                gpkg_path = output_base + ".gpkg"

                data = []
                geometries = []
                for i, segment in enumerate(coastline_segments):
                    data.append({
                        'segment_id': i + 1,
                        'length_m': round(segment.length, 2),
                        'num_points': len(list(segment.coords))
                    })
                    geometries.append(segment)

                gdf = gpd.GeoDataFrame(data, geometry=geometries, crs=utm_epsg)
                gdf.to_file(gpkg_path, driver="GPKG", layer="coastlines")

                print(f"✓ GPKG exported to: {gpkg_path}")

            except Exception as e:
                print(f"❌ GPKG export failed: {e}")

        return {"csv": csv_path, "gpkg": gpkg_path}

    except Exception as e:
        print(f"❌ Coastline export failed: {e}")
        return None


def export_greenery_for_qgis(greenery_data, output_base="D:/QGIS/gastro_map/python/output/stockholm_greenery",
                             utm_zone=34, hemisphere='N'):
    """Export greenery areas to both CSV and GPKG formats."""

    try:
        print(f"\n=== Exporting Greenery ===")
        print(f"Greenery areas: {len(greenery_data) if greenery_data else 0}")
        print(f"UTM Zone: {utm_zone}{hemisphere}")

        if not greenery_data:
            print("No greenery data to export")
            return None

        # Create the correct EPSG code for UTM
        hemisphere_code = '7' if hemisphere == 'S' else '6'
        utm_epsg = f"EPSG:32{hemisphere_code}{utm_zone:02d}"
        print(f"Using CRS: {utm_epsg}")

        # Ensure output directory exists
        ensure_output_directory(output_base + ".csv")

        # Process greenery data
        valid_greenery = []
        for i, greenery_coords in enumerate(greenery_data):
            try:
                if len(greenery_coords) >= 3:
                    greenery_poly = Polygon(greenery_coords)
                    if greenery_poly.is_valid and greenery_poly.area > 100:
                        valid_greenery.append({
                            'greenery_id': i + 1,
                            'area_sqm': round(greenery_poly.area, 2),
                            'geometry': greenery_poly
                        })
            except Exception as e:
                continue

        if not valid_greenery:
            print("No valid greenery polygons to export")
            return None

        print(f"Valid greenery polygons: {len(valid_greenery)}")

        # Export to CSV
        csv_path = output_base + ".csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['greenery_id', 'area_sqm', 'geometry_wkt']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in valid_greenery:
                writer.writerow({
                    'greenery_id': row['greenery_id'],
                    'area_sqm': row['area_sqm'],
                    'geometry_wkt': row['geometry'].wkt
                })

        print(f"✓ CSV exported to: {csv_path}")

        # Export to GPKG if available
        gpkg_path = None
        if GPKG_AVAILABLE:
            try:
                gpkg_path = output_base + ".gpkg"

                data = []
                geometries = []
                for row in valid_greenery:
                    data.append({
                        'greenery_id': row['greenery_id'],
                        'area_sqm': row['area_sqm']
                    })
                    geometries.append(row['geometry'])

                gdf = gpd.GeoDataFrame(data, geometry=geometries, crs=utm_epsg)
                gdf.to_file(gpkg_path, driver="GPKG", layer="greenery")

                print(f"✓ GPKG exported to: {gpkg_path}")

            except Exception as e:
                print(f"❌ GPKG export failed: {e}")

        return {"csv": csv_path, "gpkg": gpkg_path}

    except Exception as e:
        print(f"❌ Greenery export failed: {e}")
        return None


def render_coastlines_debug(ax, coastline_debug_data):
    """Render coastlines for debugging purposes."""
    try:
        coastline_segments = coastline_debug_data.get('coastline_segments', [])

        if not coastline_segments:
            return

        for i, segment in enumerate(coastline_segments):
            if hasattr(segment, 'coords'):
                coords = list(segment.coords)
                if len(coords) >= 2:
                    xs, ys = zip(*coords)
                    ax.plot(xs, ys, color='red', linewidth=2, alpha=0.8, zorder=15)

        print(f"Rendered {len(coastline_segments)} coastline debug segments")

    except Exception as e:
        print(f"Coastline debug rendering failed: {e}")


if __name__ == "__main__":
    print("Enhanced polygon export utilities ready (CSV/GPKG format)")
    print(f"GeoPandas available: {GPKG_AVAILABLE}")