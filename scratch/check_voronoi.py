from shapely.geometry import MultiPolygon, Point
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _sample_polygon_boundary
import scipy.spatial

polys = text_to_outline_polygons('h', 'assets/fonts/UTM ThuPhap Thien An.ttf', 200)
geom = MultiPolygon(polys)
boundary_pts = _sample_polygon_boundary(geom, 1.0)
vor = scipy.spatial.Voronoi(boundary_pts)

inside_count = 0
close_count = 0
total_vertices = len(vor.vertices)

for v in vor.vertices:
    pt = Point(v[0], v[1])
    if geom.contains(pt):
        inside_count += 1
        d = geom.boundary.distance(pt)
        if d < 1.0:
            close_count += 1

print(f"Total vertices: {total_vertices}")
print(f"Inside: {inside_count}")
print(f"Close to boundary (< 1.0): {close_count}")
