import sys
sys.path.insert(0, ".")
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon, Point
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _sample_polygon_boundary, _extract_longest_paths
import scipy.spatial
import networkx as nx
from math import hypot

def _prune_spurs(G: nx.Graph, theta: float = 1.5) -> nx.Graph:
    G_pruned = G.copy()
    while True:
        leaves = [n for n, d in G_pruned.degree() if d == 1]
        if not leaves:
            break
        edges_to_remove = []
        for leaf in leaves:
            path = [leaf]
            current = leaf
            visited = {leaf}
            while True:
                neighbors = [n for n in G_pruned.neighbors(current) if n not in visited]
                if len(neighbors) == 1:
                    next_node = neighbors[0]
                    path.append(next_node)
                    visited.add(next_node)
                    if G_pruned.degree(next_node) >= 3:
                        break
                    current = next_node
                else:
                    break
            if len(path) > 1:
                end_node = path[-1]
                if G_pruned.degree(end_node) >= 3:
                    path_len = 0.0
                    for u, v in zip(path, path[1:]):
                        path_len += G_pruned[u][v]['weight']
                    junction_radius = G_pruned.nodes[end_node].get('radius', 1.0)
                    if path_len < theta * junction_radius:
                        for u, v in zip(path, path[1:]):
                            edges_to_remove.append((u, v))
        if not edges_to_remove:
            break
        G_pruned.remove_edges_from(edges_to_remove)
        isolated = [n for n, d in G_pruned.degree() if d == 0]
        G_pruned.remove_nodes_from(isolated)
    return G_pruned

def get_skeleton_pruned(polygon, spacing=1.0, theta=1.5, min_branch_length=4.0):
    boundary_pts = _sample_polygon_boundary(polygon, spacing)
    if len(boundary_pts) < 4:
        return []
    vor = scipy.spatial.Voronoi(boundary_pts)
    
    from shapely.prepared import prep
    prep_poly = prep(polygon)
    vertices_inside = {}
    for idx, vertex in enumerate(vor.vertices):
        pt = Point(vertex[0], vertex[1])
        if prep_poly.contains(pt):
            vertices_inside[idx] = vertex

    vertex_radii = {}
    def get_radius(v_idx, pt) -> float:
        if v_idx not in vertex_radii:
            vertex_radii[v_idx] = float(polygon.boundary.distance(pt))
        return vertex_radii[v_idx]

    G = nx.Graph()
    for v1, v2 in vor.ridge_vertices:
        if v1 in vertices_inside and v2 in vertices_inside:
            p1 = vertices_inside[v1]
            p2 = vertices_inside[v2]
            midpoint = Point((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
            if prep_poly.contains(midpoint):
                dist = hypot(p2[0] - p1[0], p2[1] - p1[1])
                pt1 = Point(p1[0], p1[1])
                pt2 = Point(p2[0], p2[1])
                r1 = get_radius(v1, pt1)
                r2 = get_radius(v2, pt2)
                G.add_node(v1, pos=tuple(p1), radius=r1)
                G.add_node(v2, pos=tuple(p2), radius=r2)
                G.add_edge(v1, v2, weight=dist)

    G_pruned = _prune_spurs(G, theta)
    return _extract_longest_paths(G_pruned, min_branch_length)

def plot_times_text(text, filename):
    polys = text_to_outline_polygons(text, "C:/Windows/Fonts/times.ttf", 200)
    geom = MultiPolygon(polys)
    strokes = get_skeleton_pruned(geom, spacing=1.0, theta=1.5, min_branch_length=4.0)

    fig, ax = plt.subplots(figsize=(10, 6))
    for poly in polys:
        x, y = poly.exterior.xy
        ax.plot(x, y, color="#ccc", linestyle="--", linewidth=1.5)
        for interior in poly.interiors:
            xi, yi = interior.xy
            ax.plot(xi, yi, color="#ccc", linestyle="--", linewidth=1.5)

    for idx, stroke in enumerate(strokes):
        xs = [pt[0] for pt in stroke]
        ys = [pt[1] for pt in stroke]
        ax.plot(xs, ys, linewidth=2.5, label=f"Stroke {idx+1}")
        ax.scatter(xs, ys, s=15, zorder=3)

    ax.set_aspect("equal")
    ax.set_title(f"Times New Roman Skeleton: '{text}'")
    ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.0))
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Successfully saved to {filename}")

if __name__ == "__main__":
    plot_times_text("Nhẫn", "output/nhan_times_skeleton.png")
