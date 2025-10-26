"""
Venue Data Processor
"""
class VenueProcessor:
    def process_venues(self, osm_data, transformer):
        """Extract and transform venue coordinates from both nodes and ways (using centroids)."""
        venues = []

        for element in osm_data.get('elements', []):
            if element['type'] == 'node':
                # Handle point venues
                lon, lat = element['lon'], element['lat']
                x, y = transformer.transform(lon, lat)
                venues.append((x, y))

            elif element['type'] == 'way' and 'geometry' in element:
                # Handle building/area venues - calculate centroid
                coords = []
                for node in element['geometry']:
                    lon, lat = node['lon'], node['lat']
                    coords.append((lon, lat))

                if len(coords) >= 1:
                    # Calculate centroid of the way
                    if len(coords) == 1:
                        # Single point
                        centroid_lon, centroid_lat = coords[0]
                    else:
                        # Calculate average position as centroid
                        centroid_lon = sum(coord[0] for coord in coords) / len(coords)
                        centroid_lat = sum(coord[1] for coord in coords) / len(coords)

                    # Transform centroid to map coordinates
                    x, y = transformer.transform(centroid_lon, centroid_lat)
                    venues.append((x, y))

        return venues