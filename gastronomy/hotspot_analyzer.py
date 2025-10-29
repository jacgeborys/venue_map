# In gastronomy/hotspot_analyzer.py

import numpy as np
from sklearn.cluster import DBSCAN
from collections import Counter


class HotspotAnalyzer:
    def __init__(self, venues_by_category):
        self.venues_by_category = venues_by_category
        self.all_venues_np = self._prepare_data()

    def _prepare_data(self):
        """Combine all venue coordinates into a single NumPy array for clustering."""
        all_venues_list = []
        for category, venues in self.venues_by_category.items():
            all_venues_list.extend(venues)

        # Convert to a NumPy array of shape (n_venues, 2)
        return np.array(all_venues_list)

    def find_hotspots(self, max_distance_m=150, min_venues_in_hotspot=10):
        """
        Performs DBSCAN clustering to find gastronomy hotspots.

        Args:
            max_distance_m (int): The maximum distance (in meters) between two venues
                                  for one to be considered as in the neighborhood of the other.
            min_venues_in_hotspot (int): The number of venues in a neighborhood for a
                                         point to be considered as a core point (a hotspot center).

        Returns:
            A dictionary containing the clustered labels, the number of hotspots,
            and a summary of each hotspot.
        """
        if self.all_venues_np.shape[0] < min_venues_in_hotspot:
            print("    Not enough venues to perform hotspot analysis.")
            return None

        print(
            f"    Running DBSCAN to find hotspots (max_dist={max_distance_m}m, min_venues={min_venues_in_hotspot})...")

        # DBSCAN works with the actual coordinates (which are in meters thanks to your UTM projection)
        db = DBSCAN(eps=max_distance_m, min_samples=min_venues_in_hotspot).fit(self.all_venues_np)

        # The 'labels_' attribute contains the cluster ID for each point.
        # -1 indicates a "noise" point (not part of any cluster).
        labels = db.labels_

        # Calculate summary statistics
        num_hotspots = len(set(labels)) - (1 if -1 in labels else 0)
        print(f"    ✓ Found {num_hotspots} distinct gastronomy hotspots.")

        # Analyze the composition of each hotspot
        hotspot_summary = {}
        if num_hotspots > 0:
            for i in range(num_hotspots):
                cluster_points = self.all_venues_np[labels == i]
                # You could extend this to analyze the type of venues in each cluster
                hotspot_summary[i] = {
                    'venue_count': len(cluster_points),
                    'centroid': np.mean(cluster_points, axis=0)
                }

        return {
            'labels': labels,
            'num_hotspots': num_hotspots,
            'summary': hotspot_summary,
            'noise_points': self.all_venues_np[labels == -1],
            'clustered_points': self.all_venues_np[labels != -1]
        }