# In gastronomy/hotspot_analyzer.py

import numpy as np
from sklearn.cluster import DBSCAN
from shapely.geometry import MultiPoint


class HotspotAnalyzer:
    """
    Implements a "Best-of-Each-Category" analysis to guarantee a balanced
    representation of all significant specialist hubs.
    """

    def __init__(self, venues_by_category):
        self.venues_by_category = venues_by_category

    def find_hubs(self):
        """
        Discovers all clusters for each category and curates the top N from each,
        ensuring every category gets represented.
        """
        print("    Running 'Best-of-Each-Category' analysis...")

        # --- PHASE 1: DISCOVERY ---
        all_discovered_clusters = []

        # We use the balanced and adaptive thresholds
        threshold_config = [
            # ("Restaurants", ["restaurants"], 8, 0.25, 15),
            ("Cafes", ["cafes"], 5, 0.4, 8),
            ("Nightlife", ["bars", "clubs"], 5, 0.5, 5)
        ]

        for character, categories, base, sqrt_factor, abs_min in threshold_config:
            points_list = [v for cat in categories for v in self.venues_by_category.get(cat, [])]
            points = np.array(points_list)
            total_venues = len(points)
            if total_venues == 0: continue

            min_samples = max(abs_min, int(base + (total_venues ** 0.5) * sqrt_factor))
            print(f"    - {character}: {total_venues} venues. Dynamic threshold set to {min_samples}.")
            if total_venues < min_samples: continue

            # Run DBSCAN with our balanced eps (search radius)
            db = DBSCAN(eps=200, min_samples=min_samples).fit(points)

            found_count = 0
            for label in set(db.labels_) - {-1}:
                found_count += 1
                cluster_points = points[db.labels_ == label]
                all_discovered_clusters.append({
                    'count': len(cluster_points),
                    'hull': MultiPoint(cluster_points).convex_hull,
                    'character': character
                })

            if found_count > 0:
                print(f"      -> Found {found_count} cluster(s).")

        print(f"    Discovery Phase: Found {len(all_discovered_clusters)} total clusters across all categories.")

        # --- PHASE 2: GUARANTEED CURATION ---
        if not all_discovered_clusters:
            return []

        # Separate all discovered clusters by their category
        by_category = {"Restaurants": [], "Cafes": [], "Nightlife": []}
        for cluster in all_discovered_clusters:
            by_category[cluster['character']].append(cluster)

        # For each category, sort its clusters by size
        for cat in by_category:
            by_category[cat].sort(key=lambda x: x['count'], reverse=True)

        # Build the final list by taking the top N from each category
        final_selection = []
        # final_selection.extend(by_category["Restaurants"][:4])
        final_selection.extend(by_category["Nightlife"][:4])
        final_selection.extend(by_category["Cafes"][:2])

        # Sort the final combined list by count for a clean drawing order
        final_selection.sort(key=lambda x: x['count'], reverse=True)

        print(
            f"    Curation Phase: Selected the top hubs from each category, resulting in {len(final_selection)} annotations.")
        return final_selection