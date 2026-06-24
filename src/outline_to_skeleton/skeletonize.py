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

    # Apply split-and-merge optimization on raw Voronoi strokes
    split_strokes = []
    for s in voronoi_strokes:
        split_strokes.extend(_split_stroke_at_sharp_turns(s, angle_threshold_deg=50, k=4))
    voronoi_strokes = _merge_collinear_strokes(split_strokes, dist_threshold=5.0, angle_threshold_deg=35, k=4)

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

    strokes = _sort_calligraphy_strokes(strokes)
    if not strokes:
        raise RobotPathError("Output robot path is empty")
    _validate_robot_paths(strokes, z_heavy)
    return strokes


def _angle_between_vectors(v1: tuple[float, float], v2: tuple[float, float]) -> float:
    from math import atan2
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[2-2] - v1[2-2]*v2[0] # det = v1[0]*v2[1] - v1[1]*v2[0]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    return abs(atan2(det, dot))


def _split_stroke_at_sharp_turns(stroke: list[tuple[float, float, float]], angle_threshold_deg: float = 50, k: int = 4) -> list[list[tuple[float, float, float]]]:
    from math import pi, hypot
    if len(stroke) <= 2 * k:
        return [stroke]
    
    threshold_rad = angle_threshold_deg * pi / 180.0
    splits = [0]
    
    for i in range(k, len(stroke) - k):
        v1 = (stroke[i][0] - stroke[i-k][0], stroke[i][1] - stroke[i-k][1])
        v2 = (stroke[i+k][0] - stroke[i][0], stroke[i+k][1] - stroke[i][1])
        
        len1 = hypot(*v1)
        len2 = hypot(*v2)
        if len1 < 1e-6 or len2 < 1e-6:
            continue
            
        angle = _angle_between_vectors(v1, v2)
        if angle > threshold_rad:
            splits.append(i)
            
    splits.append(len(stroke))
    
    parts = []
    for start, end in zip(splits, splits[1:]):
        part = stroke[start:end]
        if start > 0 and len(parts) > 0:
            parts[-1] = parts[-1] + [stroke[start]]
        if len(part) >= 2:
            parts.append(part)
            
    return parts if parts else [stroke]


def _merge_collinear_strokes(strokes: list[list[tuple[float, float, float]]], dist_threshold: float = 5.0, angle_threshold_deg: float = 35, k: int = 4) -> list[list[tuple[float, float, float]]]:
    from math import pi, hypot
    remaining = [list(s) for s in strokes if len(s) >= 2]
    merged_any = True
    threshold_rad = angle_threshold_deg * pi / 180.0
    
    while merged_any:
        merged_any = False
        n = len(remaining)
        best_pair = None
        best_score = float('inf')
        best_merge_type = None
        
        for i in range(n):
            for j in range(i + 1, n):
                s1 = remaining[i]
                s2 = remaining[j]
                
                endpoints = [
                    (s1[-1], s2[0], 'end-start', s1, s2, False, False),
                    (s1[0], s2[-1], 'start-end', s1, s2, True, True),
                    (s1[-1], s2[-1], 'end-end', s1, s2, False, True),
                    (s1[0], s2[0], 'start-start', s1, s2, True, False)
                ]
                
                for p1, p2, mtype, stroke1, stroke2, rev1, rev2 in endpoints:
                    d = hypot(p1[0] - p2[0], p1[1] - p2[1])
                    if d < dist_threshold:
                        if not rev1:
                            t1 = (stroke1[-1][0] - stroke1[-min(len(stroke1), k)][0], stroke1[-1][1] - stroke1[-min(len(stroke1), k)][1])
                        else:
                            t1 = (stroke1[0][0] - stroke1[min(len(stroke1), k)-1][0], stroke1[0][1] - stroke1[min(len(stroke1), k)-1][1])
                            
                        if not rev2:
                            t2 = (stroke2[min(len(stroke2), k)-1][0] - stroke2[0][0], stroke2[min(len(stroke2), k)-1][1] - stroke2[0][1])
                        else:
                            t2 = (stroke2[-1][0] - stroke2[-min(len(stroke2), k)][0], stroke2[-1][1] - stroke2[-min(len(stroke2), k)][1])
                            t2 = (-t2[0], -t2[1])
                            
                        l1 = hypot(*t1)
                        l2 = hypot(*t2)
                        if l1 < 1e-6 or l2 < 1e-6:
                            continue
                            
                        len1 = sum(hypot(stroke1[a+1][0]-stroke1[a][0], stroke1[a+1][1]-stroke1[a][1]) for a in range(len(stroke1)-1))
                        len2 = sum(hypot(stroke2[a+1][0]-stroke2[a][0], stroke2[a+1][1]-stroke2[a][1]) for a in range(len(stroke2)-1))
                        is_serif = len1 < 25.0 or len2 < 25.0
                        
                        angle = _angle_between_vectors(t1, t2)
                        effective_angle_threshold = threshold_rad
                        if d < 2.0:
                            effective_angle_threshold = 95 * pi / 180.0
                        elif is_serif:
                            effective_angle_threshold = 75 * pi / 180.0
                            
                        if angle < effective_angle_threshold:
                            score = d + angle * 5.0
                            if score < best_score:
                                best_score = score
                                best_pair = (i, j, rev1, rev2)
                                best_merge_type = mtype
                                
        if best_pair is not None:
            i, j, rev1, rev2 = best_pair
            s1 = remaining[i]
            s2 = remaining[j]
            
            part1 = list(reversed(s1)) if rev1 else list(s1)
            part2 = list(reversed(s2)) if rev2 else list(s2)
            
            merged = part1 + part2[1:]
            remaining.pop(max(i, j))
            remaining.pop(min(i, j))
            remaining.append(merged)
            merged_any = True
            
    return remaining


def _orient_stroke(stroke: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    if len(stroke) < 2:
        return stroke
    p1 = stroke[0]
    pn = stroke[-1]
    dx = pn[0] - p1[0]
    dy = pn[1] - p1[1]
    if abs(dx) >= abs(dy):
        # horizontal-ish: left-to-right
        if dx < 0:
            return list(reversed(stroke))
    else:
        # vertical-ish: top-to-bottom (Y increases upwards)
        if dy > 0:
            return list(reversed(stroke))
    return stroke


def _sort_calligraphy_strokes(strokes: list[list[tuple[float, float, float]]]) -> list[list[tuple[float, float, float]]]:
    from math import hypot
    if not strokes:
        return strokes

    all_pts = [p for s in strokes for p in s]
    all_ys = [p[1] for p in all_pts]
    min_y_all, max_y_all = min(all_ys), max(all_ys)
    text_height = max_y_all - min_y_all if max_y_all > min_y_all else 1.0
    gap_threshold = 0.45 * text_height

    # Calculate stroke boundaries and sort by min_x
    stroke_data = []
    for s in strokes:
        xs = [pt[0] for pt in s]
        ys = [pt[1] for pt in s]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        mid_y = sum(ys) / len(ys)
        stroke_len = sum(hypot(xs[i+1]-xs[i], ys[i+1]-ys[i]) for i in range(len(s)-1))
        
        stroke_data.append({
            'stroke': s,
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'mid_y': mid_y,
            'stroke_len': stroke_len
        })
        
    stroke_data.sort(key=lambda x: x['min_x'])

    # Group into words based on horizontal gaps
    word_groups: list[list[dict]] = []
    for sd in stroke_data:
        if not word_groups:
            word_groups.append([sd])
        else:
            last_group = word_groups[-1]
            group_max_x = max(item['max_x'] for item in last_group)
            if sd['min_x'] <= group_max_x + gap_threshold:
                last_group.append(sd)
            else:
                word_groups.append([sd])

    sorted_strokes = []
    
    # Process each word group independently
    for group in word_groups:
        # Step 1: Initial classification of BASE candidate strokes
        base_candidates = []
        non_base_candidates = []
        
        for item in group:
            min_y = item['min_y']
            max_y = item['max_y']
            stroke_len = item['stroke_len']
            
            is_base = min_y < min_y_all + 0.3 * text_height
            # If dot below (very small and low), it is classified as a tone mark
            if is_base and max_y < min_y_all + 0.2 * text_height and stroke_len < 0.1 * text_height:
                is_base = False
                
            if is_base:
                base_candidates.append(item)
            else:
                non_base_candidates.append(item)
                
        # Get list of base stroke geometries
        word_base_strokes = [c['stroke'] for c in base_candidates]
        word_diacritic_strokes = []
        word_tone_strokes = []
        
        # Step 2: Check distance to base strokes for non-base candidates to reclassify serifs
        for item in non_base_candidates:
            stroke = item['stroke']
            min_dist = float('inf')
            
            for b_stroke in word_base_strokes:
                for p1 in stroke:
                    for p2 in b_stroke:
                        d = hypot(p1[0] - p2[0], p1[1] - p2[1])
                        if d < min_dist:
                            min_dist = d
                            
            if min_dist < 8.0:
                # Serif/connected stroke, reclassify as base
                word_base_strokes.append(stroke)
            else:
                # Floating diacritic or tone mark
                if item['mid_y'] >= min_y_all + 0.72 * text_height:
                    word_tone_strokes.append(stroke)
                elif item['max_y'] < min_y_all + 0.2 * text_height:
                    # lower tone dot
                    word_tone_strokes.append(stroke)
                else:
                    word_diacritic_strokes.append(stroke)
                    
        # Step 3: Sort each layer from left to right and orient strokes naturally
        sorted_base = [_orient_stroke(s) for s in sorted(word_base_strokes, key=lambda s: min(p[0] for p in s))]
        sorted_diacritics = [_orient_stroke(s) for s in sorted(word_diacritic_strokes, key=lambda s: min(p[0] for p in s))]
        sorted_tones = [_orient_stroke(s) for s in sorted(word_tone_strokes, key=lambda s: min(p[0] for p in s))]
        
        # Concatenate in calligraphy order: Base -> Letter Diacritics -> Tone Marks
        sorted_strokes.extend(sorted_base + sorted_diacritics + sorted_tones)
        
    return sorted_strokes



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
