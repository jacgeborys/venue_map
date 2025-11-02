# In gastronomy/cluster_annotator.py

import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import MultiPoint, Point, box
from scipy.interpolate import splprep, splev
import matplotlib.patheffects as path_effects
from utils.color_utils import tint_color_with_white


class ClusterAnnotator:
    """
    Takes a list of curated top clusters and draws them on the map with a
    refined, professional aesthetic and non-clashing, on-screen labels.
    """

    def __init__(self, top_clusters, all_city_venues):
        self.top_clusters = top_clusters
        self.all_city_venues_np = np.array(all_city_venues)

    def draw_annotations(self, ax, palette, font_helper):
        """
        Draws smoothed boundaries, leader lines, and intelligently placed text.
        """
        if not self.top_clusters: return

        drawn_label_boxes = []

        for hotspot in self.top_clusters:
            # (Color selection and shape smoothing logic is unchanged)
            base_color_tuple = (1.0, 1.0, 1.0)
            if "Nightlife" in hotspot['character']:
                base_color_tuple = plt.cm.colors.to_rgb(palette['gastronomy']['clubs'])
            elif "Restaurant" in hotspot['character']:
                base_color_tuple = plt.cm.colors.to_rgb(palette['gastronomy']['restaurants'])
            elif "Cafe" in hotspot['character']:
                base_color_tuple = plt.cm.colors.to_rgb(palette['gastronomy']['cafes'])

            line_color = tint_color_with_white(base_color_tuple, factor=0.4)

            hull = hotspot['hull']
            x, y = hull.exterior.xy
            points = np.array([x, y]).T
            smoothing_factor = len(points) * 150
            tck, u = splprep([points[:, 0], points[:, 1]], s=smoothing_factor, per=1)
            unew = np.linspace(u.min(), u.max(), 150)
            smooth_x, smooth_y = splev(unew, tck, der=0)

            ax.plot(smooth_x, smooth_y, color=line_color, linewidth=1.25, alpha=0.8, zorder=10)

            best_pos, label_box = self._find_best_label_position(ax, hull, drawn_label_boxes)
            drawn_label_boxes.append(label_box)

            label_text = f"{hotspot['character']}\n({hotspot['count']})"
            font_props = font_helper('regular', 10)

            hull_line = hull.exterior
            closest_point_on_hull = hull_line.interpolate(hull_line.project(best_pos))

            ax.plot([closest_point_on_hull.x, best_pos.x], [closest_point_on_hull.y, best_pos.y],
                    color=line_color, linewidth=1.0, alpha=0.9, zorder=10)

            text_element = ax.text(best_pos.x, best_pos.y, label_text,
                                   ha='center', va='center', color='white',
                                   fontproperties=font_props, zorder=11)
            text_element.set_path_effects(
                [path_effects.Stroke(linewidth=3, foreground=palette['background']), path_effects.Normal()])

    def _find_best_label_position(self, ax, hull, previously_drawn_boxes):
        """
        Tests candidate positions, avoiding data points, other labels, and off-map areas.
        """
        map_xlim = ax.get_xlim()
        map_ylim = ax.get_ylim()
        map_height = map_ylim[1] - map_ylim[0]

        label_width, label_height = map_height * 0.20, map_height * 0.06
        base_offset = map_height * 0.04
        all_candidates = []
        distance_multipliers = [1.0, 1.5, 2.0, 2.5]
        angles = np.linspace(0, 360, 16, endpoint=False)

        for multiplier in distance_multipliers:
            offset_distance = base_offset * multiplier
            for angle in angles:
                rad = np.deg2rad(angle)
                search_point = Point(hull.centroid.x + np.cos(rad) * 1e6, hull.centroid.y + np.sin(rad) * 1e6)
                intersect_point = hull.exterior.interpolate(hull.exterior.project(search_point))
                pos_x = intersect_point.x + np.cos(rad) * offset_distance
                pos_y = intersect_point.y + np.sin(rad) * offset_distance

                # --- START OF BUG FIX: The Bounds Check ---
                # Give an enormous penalty if the label position is off the map
                on_map_penalty = 0
                if not (map_xlim[0] < pos_x < map_xlim[1] and map_ylim[0] < pos_y < map_ylim[1]):
                    on_map_penalty = 1e9  # Effectively disqualifies this position
                # --- END OF BUG FIX ---

                candidate_box = box(pos_x - label_width / 2, pos_y - label_height / 2, pos_x + label_width / 2,
                                    pos_y + label_height / 2)

                label_clutter = 0
                for drawn_box in previously_drawn_boxes:
                    if candidate_box.intersects(drawn_box):
                        label_clutter = 1000
                        break

                poi_clutter = 0
                for p in self.all_city_venues_np:
                    if candidate_box.contains(Point(p)):
                        poi_clutter += 1

                total_clutter = on_map_penalty + label_clutter + poi_clutter + (multiplier * 5)
                all_candidates.append({'score': total_clutter, 'pos': Point(pos_x, pos_y), 'box': candidate_box})

        best_candidate = min(all_candidates, key=lambda c: c['score'])
        return best_candidate['pos'], best_candidate['box']