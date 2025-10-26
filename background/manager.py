"""
Background Manager
Orchestrates all background layers with proper z-ordering and extremely pale colors.
"""
from background.roads import RoadNetworkProcessor, DEFAULT_ROAD_STYLES
from background.water import WaterProcessor, DEFAULT_WATER_STYLE
from background.greenery import GreeneryProcessor, DEFAULT_GREENERY_STYLE

class BackgroundManager:
    """Manages all background layers with proper layering."""

    def __init__(self):
        self.road_processor = RoadNetworkProcessor()
        self.water_processor = WaterProcessor()
        self.greenery_processor = GreeneryProcessor()

    def fetch_all_background(self, center_lat, center_lon, radius_km, background_type='full'):
        """Fetch all background data layers."""
        background_data = {}

        if background_type in ['roads', 'full']:
            # Always fetch roads
            print("  Fetching background layers...")
            roads_raw = self.road_processor.fetch_roads(center_lat, center_lon, radius_km)
            background_data['roads'] = roads_raw

            if background_type == 'full':
                # Fetch water and greenery for full background
                water_raw = self.water_processor.fetch_water(center_lat, center_lon, radius_km)
                background_data['water'] = water_raw

                greenery_raw = self.greenery_processor.fetch_greenery(center_lat, center_lon, radius_km)
                background_data['greenery'] = greenery_raw

        return background_data

    def process_all_background(self, background_data, transformer, map_bounds=None, center_lat=None, center_lon=None, radius_km=None):
        """Process all background data into renderable format."""
        processed = {}

        if 'roads' in background_data:
            processed['roads'] = self.road_processor.process_roads(background_data['roads'], transformer)
            road_count = sum(len(roads) for roads in processed['roads'].values())
            print(f"    Roads: {road_count} segments")

        # Process greenery BEFORE water so coastline water can use it for land detection
        if 'greenery' in background_data:
            processed['greenery'] = self.greenery_processor.process_greenery(background_data['greenery'], transformer)
            print(f"    Greenery: {len(processed['greenery'])} areas")

        if 'water' in background_data:
            processed['water'] = self.water_processor.process_water(background_data['water'], transformer)
            water_count = len(processed['water'].get('polygons', [])) + len(processed['water'].get('lines', []))
            print(f"    Water: {water_count} features")

            # Add coastline water automatically if we have required parameters
            if map_bounds and center_lat and center_lon and radius_km:
                try:
                    print("    Generating coastline water...")
                    from background.coastline_water import fetch_enhanced_coastline_water

                    # Pass greenery data if available for land detection
                    greenery_data = processed.get('greenery', [])
                    print(f"    Available for coastline processing:")
                    print(f"      - Map bounds: {map_bounds}")
                    print(f"      - Center: {center_lat}, {center_lon}")
                    print(f"      - Radius: {radius_km}")
                    print(f"      - Greenery areas: {len(greenery_data)}")

                    coastline_data = fetch_enhanced_coastline_water(
                        center_lat, center_lon, radius_km, transformer, map_bounds, greenery_data
                    )

                    print(f"    Coastline data returned: {list(coastline_data.keys()) if coastline_data else 'None'}")

                    # Add water polygons to existing water features (same color, no transparency)
                    water_polygons = coastline_data.get('water_polygons', []) if coastline_data else []
                    if water_polygons:
                        processed['water']['polygons'].extend(water_polygons)
                        print(f"    ✓ Added {len(water_polygons)} coastline water areas")

                    # Store coastlines and debug data for polygon export
                    coastlines = coastline_data.get('coastlines', []) if coastline_data else []
                    if coastlines:
                        processed['coastlines'] = coastlines
                        print(f"    ✓ Added {len(coastlines)} coastline segments")

                    # ALWAYS store coastline debug data for polygon export (even if no coastlines found)
                    coastline_segments = coastline_data.get('coastline_segments', []) if coastline_data else []
                    print(f"    Raw coastline segments for export: {len(coastline_segments)}")

                    # Force polygon export if we have any data to work with
                    processed['coastline_debug'] = {
                        'coastline_segments': coastline_segments,
                        'map_bounds': map_bounds,
                        'greenery_data': greenery_data
                    }
                    print(f"    ✓ Stored coastline debug data for polygon export")

                    if not water_polygons and not coastlines:
                        print("    No coastline water/coastlines generated, but will still run polygon export")

                except Exception as e:
                    print(f"    Coastline water generation failed: {e}")
                    import traceback
                    traceback.print_exc()

                    # Even if coastline processing fails, try to run polygon export with basic data
                    greenery_data = processed.get('greenery', [])
                    processed['coastline_debug'] = {
                        'coastline_segments': [],  # Empty but will still create map boundary polygon
                        'map_bounds': map_bounds,
                        'greenery_data': greenery_data
                    }
                    print(f"    Stored minimal debug data for polygon export despite coastline failure")
            else:
                print("    Skipping coastline water (missing required parameters)")
                print(f"      - map_bounds: {map_bounds is not None}")
                print(f"      - center_lat: {center_lat is not None}")
                print(f"      - center_lon: {center_lon is not None}")
                print(f"      - radius_km: {radius_km is not None}")

        return processed

    def render_all_background(self, ax, processed_background, background_type='full'):
        """Render all background layers in correct z-order."""
        if background_type == 'none':
            return

        # 1. Built-up area - use Rectangle instead of fill_between
        from matplotlib.patches import Rectangle
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Create rectangle covering entire map area
        built_up_rect = Rectangle(
            (xlim[0], ylim[0]),
            xlim[1] - xlim[0],
            ylim[1] - ylim[0],
            facecolor='#ebebeb',
            alpha=0.8,
            zorder=1,
            edgecolor='none'
        )
        ax.add_patch(built_up_rect)

        # 2. Render greenery (zorder 2)
        if 'greenery' in processed_background:
            self.greenery_processor.render_greenery(
                ax, processed_background['greenery'], DEFAULT_GREENERY_STYLE
            )

        # 3. Render water (zorder 3) - includes both regular and coastline water
        if 'water' in processed_background:
            # Use water style with no transparency for seamless merging
            water_style = {
                'polygon': {
                    'color': DEFAULT_WATER_STYLE['polygon']['color'],
                    'alpha': 1.0,  # No transparency for seamless merging
                    'zorder': 3
                },
                'line': DEFAULT_WATER_STYLE['line']
            }

            self.water_processor.render_water(
                ax, processed_background['water'], water_style
            )

        # 3.5. Render coastlines for debugging (optional, zorder 3.5)
        if 'coastlines' in processed_background and False:  # Set to True for debugging
            for coastline in processed_background['coastlines']:
                if len(coastline) >= 2:
                    xs, ys = zip(*coastline)
                    ax.plot(xs, ys, color='red', linewidth=1.5, alpha=0.8, zorder=3.5)
            print(f"    Rendered {len(processed_background['coastlines'])} coastline segments")

        # 4. Export polygons for QGIS analysis (if coastline debug data available)
        print(f"    Checking for polygon export...")
        print(f"    Available processed data keys: {list(processed_background.keys())}")

        if 'coastline_debug' in processed_background:
            try:
                print(f"    ✓ Coastline debug data found - starting QGIS export...")
                from background.polygon_export import export_coastline_polygons_for_qgis, export_coastlines_for_qgis, export_greenery_for_qgis

                debug_data = processed_background['coastline_debug']
                coastline_segments = debug_data['coastline_segments']
                map_bounds = debug_data['map_bounds']
                greenery_data = debug_data['greenery_data']

                print(f"    Debug data contents:")
                print(f"      - Coastline segments: {len(coastline_segments) if coastline_segments else 0}")
                print(f"      - Map bounds: {map_bounds}")
                print(f"      - Greenery areas: {len(greenery_data) if greenery_data else 0}")

                # Export all data layers (enhanced versions support both CSV and GPKG)
                # Use Stockholm's UTM zone (we can make this dynamic later if needed)
                utm_zone = 34  # Stockholm is in UTM Zone 34N
                hemisphere = 'N'
                print(f"    Using UTM Zone {utm_zone}{hemisphere} for export")

                polygon_files = export_coastline_polygons_for_qgis(
                    coastline_segments, map_bounds, greenery_data,
                    "D:/QGIS/gastro_map/python/output/stockholm_polygons",
                    utm_zone, hemisphere
                )

                coastline_files = export_coastlines_for_qgis(
                    coastline_segments,
                    "D:/QGIS/gastro_map/python/output/stockholm_coastlines",
                    utm_zone, hemisphere
                )

                greenery_files = export_greenery_for_qgis(
                    greenery_data,
                    "D:/QGIS/gastro_map/python/output/stockholm_greenery",
                    utm_zone, hemisphere
                )

                print(f"    ✓ Export completed!")
                if polygon_files:
                    print(f"      - Polygons: {polygon_files}")
                else:
                    print(f"      - Polygons: Export failed or returned None")
                if coastline_files:
                    print(f"      - Coastlines: {coastline_files}")
                else:
                    print(f"      - Coastlines: Export failed or returned None")
                if greenery_files:
                    print(f"      - Greenery: {greenery_files}")
                else:
                    print(f"      - Greenery: Export failed or returned None")

            except Exception as e:
                print(f"    ❌ QGIS export failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"    ❌ No coastline debug data available for export")
            print(f"    This means either:")
            print(f"      1. Coastline water generation was skipped")
            print(f"      2. Coastline water generation failed")
            print(f"      3. Debug data wasn't stored properly")

        # 5. Render roads on top (zorder 4)
        if 'roads' in processed_background:
            self.road_processor.render_roads(
                ax, processed_background['roads'], DEFAULT_ROAD_STYLES
            )

# Extremely pale background colors
BACKGROUND_COLORS = {
    'built_up': '#f7f5f2',      # Very pale gray for built-up areas
    'clean': '#ffffff'          # White for no-background maps
}