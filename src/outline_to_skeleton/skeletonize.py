from __future__ import annotations

from math import hypot
import numpy as np
import scipy.spatial
import networkx as nx
from shapely.geometry import MultiPolygon, Polygon, Point, LineString
from shapely.prepared import prep

from .errors import RobotPathError, SkeletonExtractionError, ZDepthError
from .path_smoothing import downsample_keep_ends, moving_average_stroke, order_strokes_nearest, rdp_stroke, resample_stroke
from .z_depth import enforce_max_z_step, map_radius_to_z, smooth_z_values


def _sample_polygon_boundary(polygon: Polygon | MultiPolygon, spacing: float) -> np.ndarray:
    points = []

    def sample_ring(ring) -> None:
        length = ring.length
        if length == 0:
            return
        num_samples = max(10, int(np.ceil(length / spacing)))
        for i in range(num_samples):
            t = (i / num_samples) * length
            pt = ring.interpolate(t)
            points.append((pt.x, pt.y))

    if isinstance(polygon, Polygon):
        sample_ring(polygon.exterior)
        for interior in polygon.interiors:
            sample_ring(interior)
    elif isinstance(polygon, MultiPolygon):
        for poly in polygon.geoms:
            sample_ring(poly.exterior)
            for interior in poly.interiors:
                sample_ring(interior)
    return np.array(points)


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


def _voronoi_skeleton(
    polygon: Polygon | MultiPolygon,
    spacing: float = 2.0,
    min_branch_length: float = 5.0,
    theta: float = 1.5,
) -> list[list[tuple[float, float, float]]]:
    # 1. Sample boundary points
    boundary_pts = _sample_polygon_boundary(polygon, spacing)
    if len(boundary_pts) < 4:
        return []

    # 2. Compute Voronoi
    vor = scipy.spatial.Voronoi(boundary_pts)

    # 3. Filter Voronoi vertices inside the polygon
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

    # 4. Filter edges and build graph
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

    # 4.5 Prune spurs
    G_pruned = _prune_spurs(G, theta)

    # 5. Extract longest paths (naturally prunes spurious branches)
    return _extract_longest_paths(G_pruned, min_branch_length)


def _extract_longest_paths(G: nx.Graph, min_branch_length: float) -> list[list[tuple[float, float, float]]]:
    strokes = []
    
    # Process each connected component independently
    for component in nx.connected_components(G):
        comp_graph = G.subgraph(component).copy()
        while comp_graph.number_of_edges() > 0:
            # Find the connected components of the REMAINING comp_graph
            sub_components = list(nx.connected_components(comp_graph))
            best_path = None
            best_path_len = 0.0
            
            for sub_comp in sub_components:
                sub_graph = comp_graph.subgraph(sub_comp)
                if sub_graph.number_of_edges() == 0:
                    continue
                
                # Find furthest pair of nodes in this sub-component
                degrees = dict(sub_graph.degree())
                leaves = [n for n, d in degrees.items() if d == 1]
                start = leaves[0] if leaves else list(sub_graph.nodes())[0]
                
                lengths = nx.single_source_dijkstra_path_length(sub_graph, start, weight='weight')
                if not lengths:
                    continue
                furthest_node_1 = max(lengths, key=lengths.get)
                
                lengths_2 = nx.single_source_dijkstra_path_length(sub_graph, furthest_node_1, weight='weight')
                if not lengths_2:
                    continue
                furthest_node_2 = max(lengths_2, key=lengths_2.get)
                path_len = lengths_2[furthest_node_2]
                
                if path_len > best_path_len:
                    best_path_len = path_len
                    best_path = nx.shortest_path(sub_graph, furthest_node_1, furthest_node_2, weight='weight')
            
            # If the longest path among all remaining sub-components is too short, we stop
            if best_path is None or best_path_len < min_branch_length:
                break
                
            # Extract the stroke
            stroke = []
            for node in best_path:
                node_data = G.nodes[node]
                stroke.append((node_data['pos'][0], node_data['pos'][1], node_data['radius']))
            strokes.append(stroke)
            
            # Remove the edges of the extracted path from comp_graph
            for u, v in zip(best_path, best_path[1:]):
                comp_graph.remove_edge(u, v)
                
            # Clean up isolated nodes (degree 0)
            isolated = [n for n, d in comp_graph.degree() if d == 0]
            for n in isolated:
                comp_graph.remove_node(n)
                
    return strokes


def polygons_to_robot_paths(
    polygons: list[Polygon] | MultiPolygon,
    resolution: float = 2.0,
    z_light: float = -0.5,
    z_heavy: float = -3.0,
    output_scale: float = 1.0,
    point_spacing: float = 1.0,
    min_branch_length: float = 2.0,
    smoothing_window: int = 3,
    simplify_tolerance: float = 0.05,
    max_points_per_stroke: int = 600,
    theta: float = 1.5,
) -> list[list[tuple[float, float, float]]]:
    geom = MultiPolygon(polygons) if isinstance(polygons, list) else polygons
    if geom.is_empty:
        raise SkeletonExtractionError("Input polygons geometry is empty")

    spacing = max(0.5, min(5.0, 2.0 / resolution))
    voronoi_strokes = _voronoi_skeleton(geom, spacing=spacing, min_branch_length=min_branch_length, theta=theta)
    if not voronoi_strokes:
        raise SkeletonExtractionError("Voronoi skeleton is empty")

    all_radii = [r for stroke in voronoi_strokes for x, y, r in stroke]
    if not all_radii:
        raise SkeletonExtractionError("Skeleton has no radius samples")
    min_radius = min(all_radii)
    max_radius = max(all_radii)

    strokes: list[list[tuple[float, float, float]]] = []
    for voronoi_stroke in voronoi_strokes:
        # Simplify the raw Voronoi centerline first to reduce point density and noise
        simplified_stroke = rdp_stroke(voronoi_stroke, simplify_tolerance)
        if len(simplified_stroke) < 2:
            continue

        raw: list[tuple[float, float, float]] = []
        z_values = [
            map_radius_to_z(r, min_radius, max_radius, z_light, z_heavy)
            for x, y, r in simplified_stroke
        ]
        z_values = smooth_z_values(z_values)
        for (x, y, r), z in zip(simplified_stroke, z_values):
            raw.append((x * output_scale, y * output_scale, z))
        if len(raw) < 2:
            continue
        prepared = moving_average_stroke(raw, smoothing_window)
        prepared = resample_stroke(prepared, point_spacing)
        prepared = rdp_stroke(prepared, simplify_tolerance)
        prepared = enforce_max_z_step(prepared)
        if max_points_per_stroke > 0 and len(prepared) > max_points_per_stroke:
            prepared = downsample_keep_ends(prepared, max_points_per_stroke)
            prepared = enforce_max_z_step(prepared)
        strokes.append(_round_stroke(prepared))

    strokes = order_strokes_nearest(strokes)
    if not strokes:
        raise RobotPathError("Output robot path is empty")
    _validate_robot_paths(strokes, z_heavy)
    return strokes


def _round_stroke(stroke: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    return [(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in stroke]


def _validate_robot_paths(strokes: list[list[tuple[float, float, float]]], z_heavy: float) -> None:
    point_count = sum(len(stroke) for stroke in strokes)
    if point_count == 0:
        raise RobotPathError("Output robot path is empty")
    if point_count > 200000:
        raise RobotPathError("Output has too many points and may make the robot slow")
    deepest = min(point[2] for stroke in strokes for point in stroke)
    if deepest < z_heavy - 1e-6:
        raise ZDepthError("Z-depth is deeper than configured z_heavy")
    for stroke in strokes:
        for start, end in zip(stroke, stroke[1:]):
            if abs(end[2] - start[2]) > 0.201:
                raise ZDepthError("Z-depth changes too abruptly between adjacent points")
