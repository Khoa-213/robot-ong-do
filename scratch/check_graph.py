import sys
sys.path.insert(0, ".")
from shapely.geometry import MultiPolygon
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _voronoi_skeleton

polys = text_to_outline_polygons('h', 'assets/fonts/UTM ThuPhap Thien An.ttf', 200)
geom = MultiPolygon(polys)
strokes = _voronoi_skeleton(geom, spacing=1.0, min_branch_length=4.0)
print("Number of strokes:", len(strokes))
for i, stroke in enumerate(strokes):
    print(f"Stroke {i}: length {len(stroke)}")
    # Print the first 5 coordinates
    print("  First 5:", [(round(x,1), round(y,1), round(r,1)) for x, y, r in stroke[:5]])
    # Print the last 5 coordinates
    print("  Last 5:", [(round(x,1), round(y,1), round(r,1)) for x, y, r in stroke[-5:]])
