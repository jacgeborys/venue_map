"""
Debug Script for Polygon Export
Run this to test if the export functionality is working correctly
"""
import os
import sys

def test_export_setup():
    """Test if the export setup is working."""
    print("=== Testing Export Setup ===")

    # 1. Test output directory
    output_dir = "D:/QGIS/gastro_map/python/output"
    print(f"1. Testing output directory: {output_dir}")

    if os.path.exists(output_dir):
        print(f"   ✓ Directory exists")
        # List files in directory
        files = os.listdir(output_dir)
        if files:
            print(f"   Current files: {files}")
        else:
            print(f"   Directory is empty")
    else:
        print(f"   ❌ Directory does not exist")
        print(f"   Creating directory...")
        try:
            os.makedirs(output_dir, exist_ok=True)
            print(f"   ✓ Directory created successfully")
        except Exception as e:
            print(f"   ❌ Failed to create directory: {e}")
            return False

    # 2. Test write permissions
    print(f"\n2. Testing write permissions...")
    test_file = os.path.join(output_dir, "test_write.txt")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print(f"   ✓ Write permissions OK")
    except Exception as e:
        print(f"   ❌ Write permission failed: {e}")
        return False

    # 3. Test imports
    print(f"\n3. Testing required imports...")

    # Test shapely
    try:
        from shapely.geometry import Polygon, LineString, box
        from shapely.ops import polygonize
        print(f"   ✓ Shapely available")
    except ImportError as e:
        print(f"   ❌ Shapely not available: {e}")
        return False

    # Test geopandas (optional)
    try:
        import geopandas as gpd
        import pandas as pd
        print(f"   ✓ GeoPandas available (GPKG export enabled)")
    except ImportError:
        print(f"   ⚠ GeoPandas not available (only CSV export will work)")

    # 4. Test polygon export module
    print(f"\n4. Testing polygon export module...")

    # Add the correct path to your background folder
    import sys
    background_path = os.path.dirname(os.path.abspath(__file__))  # Current directory (background)
    if background_path not in sys.path:
        sys.path.insert(0, background_path)

    try:
        # Try to import from the background directory where this script is running
        from polygon_export import export_coastline_polygons_for_qgis
        print(f"   ✓ polygon_export module imports OK from background directory")
    except Exception as e:
        print(f"   ❌ polygon_export import failed: {e}")

        # Check if the file exists
        polygon_export_path = os.path.join(background_path, 'polygon_export.py')
        if os.path.exists(polygon_export_path):
            print(f"   📁 polygon_export.py exists at: {polygon_export_path}")
        else:
            print(f"   📁 polygon_export.py NOT found at: {polygon_export_path}")

        # List files in the background directory
        try:
            files = os.listdir(background_path)
            python_files = [f for f in files if f.endswith('.py')]
            print(f"   📁 Python files in background directory: {python_files}")
        except Exception as list_error:
            print(f"   📁 Could not list files in background directory: {list_error}")

    print(f"\n=== Test Complete ===")
    return True

def test_simple_export():
    """Test a simple polygon export."""
    print(f"\n=== Testing Simple Export ===")

    try:
        from shapely.geometry import Polygon, LineString, box

        # Create simple test data
        print("Creating test data...")

        # Simple coastline (a line across the map)
        coastline = LineString([(0, 50), (100, 50)])

        # Map bounds
        map_bounds = {
            'xlim': [0, 100],
            'ylim': [0, 100]
        }

        # Simple greenery (a small polygon)
        greenery_data = [[(20, 60), (30, 60), (30, 70), (20, 70), (20, 60)]]

        print("Running export...")

        # Add the correct path to the background folder
        import sys
        import os
        background_path = os.path.dirname(os.path.abspath(__file__))  # Current directory (background)
        if background_path not in sys.path:
            sys.path.insert(0, background_path)

        # Try to import from the background directory
        from polygon_export import export_coastline_polygons_for_qgis

        result = export_coastline_polygons_for_qgis(
            [coastline],
            map_bounds,
            greenery_data,
            "D:/QGIS/gastro_map/python/output/test_polygons"
        )

        if result:
            print(f"✓ Test export successful: {result}")
            return True
        else:
            print(f"❌ Test export failed")
            return False

    except Exception as e:
        print(f"❌ Test export exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Polygon Export Debug Tool")
    print("=" * 50)

    setup_ok = test_export_setup()

    if setup_ok:
        test_simple_export()
    else:
        print("Setup failed - cannot proceed with export test")