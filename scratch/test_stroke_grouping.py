import sys
from pathlib import Path
from shapely.geometry import MultiPolygon

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

# Calculate text bounding box
all_pts = [p for s in merged_paths for p in s]
all_ys = [p[1] for p in all_pts]
min_y, max_y = min(all_ys), max(all_ys)
text_height = max_y - min_y
gap_threshold = 0.2 * text_height

# Sort strokes by min_x
stroke_data = []
for s in merged_paths:
    xs = [pt[0] for pt in s]
    ys = [pt[1] for pt in s]
    stroke_data.append({
        'stroke': s,
        'min_x': min(xs),
        'max_x': max(xs),
        'min_y': min(ys),
        'max_y': max(ys),
        'mid_x': sum(xs) / len(xs),
        'mid_y': sum(ys) / len(ys)
    })

stroke_data.sort(key=lambda x: x['min_x'])

# Group into characters
char_groups = []
for sd in stroke_data:
    if not char_groups:
        char_groups.append([sd])
    else:
        # Get span of last group
        last_group = char_groups[-1]
        group_max_x = max(item['max_x'] for item in last_group)
        if sd['min_x'] <= group_max_x + gap_threshold:
            last_group.append(sd)
        else:
            char_groups.append([sd])

print(f"Detected {len(char_groups)} character groups:")
for idx, group in enumerate(char_groups):
    group_min_x = min(item['min_x'] for item in group)
    group_max_x = max(item['max_x'] for item in group)
    print(f"Group {idx}: strokes={len(group)} X:[{group_min_x:.1f}, {group_max_x:.1f}]")
