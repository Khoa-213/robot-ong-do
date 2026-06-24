import sys
from pathlib import Path
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _voronoi_skeleton

polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
geom = MultiPolygon(polys)
strokes = _voronoi_skeleton(geom, spacing=1.0, min_branch_length=2.0, theta=1.5)

# Find the stroke that has X: [140, 170], Y: [20, 60]
for i, stroke in enumerate(strokes):
    in_box = [p for p in stroke if 140 <= p[0] <= 170 and 20 <= p[1] <= 60]
    if len(in_box) > 10:
        print(f"Stroke {i}: total_points={len(stroke)}")
        print(f"Start point: {stroke[0]}")
        print(f"End point: {stroke[-1]}")
        # Print some intermediate points
        step = len(stroke) // 10
        for j in range(0, len(stroke), step):
            print(f"  Point {j}: {stroke[j]}")
