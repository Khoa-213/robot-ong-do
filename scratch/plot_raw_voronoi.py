import sys
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _voronoi_skeleton, polygons_to_robot_paths

polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
geom = MultiPolygon(polys)

# Let's see what raw voronoi skeleton returns
spacing = 1.0
boundary_pts = []
for poly in polys:
    # Just a simple boundary sampling
    pass

strokes = _voronoi_skeleton(geom, spacing=1.0, min_branch_length=2.0, theta=1.5)

fig, ax = plt.subplots(figsize=(10, 8))
for poly in polys:
    x, y = poly.exterior.xy
    ax.plot(x, y, color='gray', linestyle='--')

for i, stroke in enumerate(strokes):
    xs = [p[0] for p in stroke]
    ys = [p[1] for p in stroke]
    ax.plot(xs, ys, label=f"Stroke {i}")
    ax.scatter(xs, ys, s=10)

ax.set_aspect('equal')
ax.legend()
plt.savefig("output/raw_voronoi_nhan.png")
print("Saved raw voronoi to output/raw_voronoi_nhan.png")
