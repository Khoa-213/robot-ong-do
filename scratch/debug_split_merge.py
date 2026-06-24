import sys
from pathlib import Path
import numpy as np
from math import atan2, pi, hypot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths
from shapely.geometry import MultiPolygon

def angle_between_vectors(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    return abs(atan2(det, dot))

# Load strokes
polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
geom = MultiPolygon(polys)
paths = polygons_to_robot_paths(geom, resolution=2.0)

# Import splitting logic from test_split_merge
from scratch.test_split_merge import split_stroke_at_sharp_turns

split_paths = []
for p in paths:
    split_paths.extend(split_stroke_at_sharp_turns(p, angle_threshold_deg=50, k=2))

# Let's inspect the two candidate strokes for left stem
# Find Stroke 17 (top part of left stem) and Stroke 2 (bottom part of left stem)
# Stroke 17 in previous print: points=17 X:[148.2, 169.2] Y:[70.6, 128.9]
# Stroke 2 in previous print: points=16 X:[168.8, 189.6] Y:[1.8, 69.3]

s17 = None
s2 = None
for s in split_paths:
    xs = [pt[0] for pt in s]
    ys = [pt[1] for pt in s]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if 148 <= min_x <= 150 and 70 <= min_y <= 71:
        s17 = s
    if 168 <= min_x <= 169 and 1.8 <= min_y <= 2.0:
        s2 = s

if s17 and s2:
    print("Found candidate strokes!")
    # Check endpoints
    print(f"s17 endpoints: Start={s17[0]} End={s17[-1]}")
    print(f"s2 endpoints: Start={s2[0]} End={s2[-1]}")
    
    # Distance between s17[-1] and s2[-1] (or whichever is closer)
    for p1_idx, p1 in [(-1, s17[-1]), (0, s17[0])]:
        for p2_idx, p2 in [(-1, s2[-1]), (0, s2[0])]:
            d = hypot(p1[0] - p2[0], p1[1] - p2[1])
            print(f"Distance between s17[{p1_idx}] and s2[{p2_idx}] is {d:.3f}")
            if d < 10.0:
                # Tangent vectors
                k = 3
                # Tangent 1
                if p1_idx == -1:
                    t1 = (s17[-1][0] - s17[-k][0], s17[-1][1] - s17[-k][1])
                else:
                    t1 = (s17[0][0] - s17[k-1][0], s17[0][1] - s17[k-1][1])
                # Tangent 2 (corrected index mapping)
                if p2_idx == 0:
                    t2 = (s2[k-1][0] - s2[0][0], s2[k-1][1] - s2[0][1])
                else:
                    t2 = (s2[-1][0] - s2[-k][0], s2[-1][1] - s2[-k][1])
                
                # Check sign/flow direction:
                # If connecting end-end, we need to reverse one flow so they align.
                # So we flip the sign of one vector.
                if p1_idx == -1 and p2_idx == -1:
                    t2 = (-t2[0], -t2[1])
                elif p1_idx == 0 and p2_idx == 0:
                    t2 = (-t2[0], -t2[1])
                    
                print(f"  t1={t1} t2={t2}")
                angle = angle_between_vectors(t1, t2)
                print(f"  Angle={angle*180/pi:.1f} deg")

else:
    print("Could not find s17 or s2 candidates")
