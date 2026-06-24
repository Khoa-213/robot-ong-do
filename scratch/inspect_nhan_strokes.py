import sys
from pathlib import Path
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths

polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
geom = MultiPolygon(polys)
paths = polygons_to_robot_paths(
    geom,
    resolution=2.0,
    z_light=-0.5,
    z_heavy=-3.0,
    point_spacing=1.0,
    min_branch_length=4.0,
    simplify_tolerance=0.05,
    theta=1.5,
)

print(f"Total strokes: {len(paths)}")
for i, stroke in enumerate(paths):
    xs = [p[0] for p in stroke]
    ys = [p[1] for p in stroke]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    print(f"Stroke {i}: points={len(stroke)} X:[{min_x:.1f}, {max_x:.1f}] Y:[{min_y:.1f}, {max_y:.1f}]")
