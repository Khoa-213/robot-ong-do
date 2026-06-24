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

print(f"Checking {len(strokes)} strokes for middle of h stem (X:[140,170], Y:[20,60]):")
for i, stroke in enumerate(strokes):
    in_box = []
    for p in stroke:
        if 140 <= p[0] <= 170 and 20 <= p[1] <= 60:
            in_box.append(p)
    if in_box:
        print(f"Stroke {i} has {len(in_box)} points in box. Sample points: {in_box[:3]}")
