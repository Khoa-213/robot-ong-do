import sys
from pathlib import Path
from shapely.geometry import MultiPolygon
from math import hypot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths

polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
geom = MultiPolygon(polys)
paths = polygons_to_robot_paths(geom, resolution=2.0)

# Import split & merge from test_split_merge
from scratch.test_split_merge import split_stroke_at_sharp_turns, merge_collinear_strokes

split_paths = []
for p in paths:
    split_paths.extend(split_stroke_at_sharp_turns(p, angle_threshold_deg=50, k=2))
merged_paths = merge_collinear_strokes(split_paths, dist_threshold=5.0, angle_threshold_deg=35, k=2)

# Calculate bounds
all_pts = [p for s in merged_paths for p in s]
all_ys = [p[1] for p in all_pts]
min_y_all, max_y_all = min(all_ys), max(all_ys)
text_height = max_y_all - min_y_all

# Candidate classification first by Y coordinates
candidates = []
for idx, stroke in enumerate(merged_paths):
    xs = [pt[0] for pt in stroke]
    ys = [pt[1] for pt in stroke]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    mid_y = sum(ys) / len(ys)
    
    stroke_len = sum(hypot(xs[i+1]-xs[i], ys[i+1]-ys[i]) for i in range(len(stroke)-1))
    
    is_base = min_y < min_y_all + 0.3 * text_height
    # Check if dot below
    if is_base and max_y < min_y_all + 0.2 * text_height and stroke_len < 0.1 * text_height:
        is_base = False
        
    candidates.append({
        'stroke': stroke,
        'min_x': min_x,
        'min_y': min_y,
        'max_y': max_y,
        'mid_y': mid_y,
        'is_base': is_base,
        'stroke_len': stroke_len
    })

# Identify base strokes first
base_strokes = [c for c in candidates if c['is_base']]

# For non-base candidates, check minimum distance to any base stroke
non_base = [c for c in candidates if not c['is_base']]

# Final categories
final_base = [c['stroke'] for c in base_strokes]
final_diacritics = []
final_tones = []

for c in non_base:
    stroke = c['stroke']
    # Compute min distance to any point in final_base
    min_dist = float('inf')
    for base_stroke in final_base:
        for p1 in stroke:
            for p2 in base_stroke:
                d = hypot(p1[0] - p2[0], p1[1] - p2[1])
                if d < min_dist:
                    min_dist = d
                    
    # If it is touching/very close to a base stroke, it is a serif, so reclassify as BASE!
    if min_dist < 8.0:
        final_base.append(stroke)
    else:
        # Floating! Classify as diacritic or tone mark
        if c['mid_y'] >= min_y_all + 0.72 * text_height:
            final_tones.append(stroke)
        elif c['max_y'] < min_y_all + 0.2 * text_height:
            # lower tone dot
            final_tones.append(stroke)
        else:
            final_diacritics.append(stroke)

# Print sorted results
print("\n--- BASE STROKES ---")
for s in sorted(final_base, key=lambda x: min(pt[0] for pt in x)):
    xs = [pt[0] for pt in s]
    ys = [pt[1] for pt in s]
    print(f"BASE: X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]")

print("\n--- LETTER DIACRITICS ---")
for s in sorted(final_diacritics, key=lambda x: min(pt[0] for pt in x)):
    xs = [pt[0] for pt in s]
    ys = [pt[1] for pt in s]
    print(f"DIACRITIC: X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]")

print("\n--- TONE MARKS ---")
for s in sorted(final_tones, key=lambda x: min(pt[0] for pt in x)):
    xs = [pt[0] for pt in s]
    ys = [pt[1] for pt in s]
    print(f"TONE: X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]")
