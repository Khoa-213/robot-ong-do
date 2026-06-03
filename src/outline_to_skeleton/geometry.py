from __future__ import annotations

from collections.abc import Iterable

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from .errors import PolygonRepairError


def repair_geometry(geometry) -> MultiPolygon:
    if geometry is None or geometry.is_empty:
        raise PolygonRepairError("Polygon is empty before repair")
    try:
        from shapely.validation import make_valid

        repaired = make_valid(geometry)
    except Exception:
        repaired = geometry.buffer(0)

    if repaired.is_empty:
        raise PolygonRepairError("Polygon is empty after repair")
    if not repaired.is_valid:
        repaired = repaired.buffer(0)
    if repaired.is_empty or not repaired.is_valid:
        raise PolygonRepairError("Polygon self-intersection could not be repaired")

    polygons = []
    if isinstance(repaired, Polygon):
        polygons = [repaired]
    elif isinstance(repaired, MultiPolygon):
        polygons = list(repaired.geoms)
    elif hasattr(repaired, "geoms"):
        for item in repaired.geoms:
            if isinstance(item, Polygon):
                polygons.append(item)
            elif isinstance(item, MultiPolygon):
                polygons.extend(item.geoms)

    polygons = [poly for poly in polygons if poly.area > 1e-9]
    if not polygons:
        raise PolygonRepairError("No polygonal area remains after repair")
    return MultiPolygon(polygons)


def rings_to_polygons(rings: Iterable[list[tuple[float, float]]]) -> list[Polygon]:
    cleaned = []
    for ring in rings:
        if len(ring) < 3:
            continue
        points = [(float(x), float(y)) for x, y in ring]
        if points[0] != points[-1]:
            points.append(points[0])
        poly = Polygon(points)
        if poly.area > 1e-9:
            cleaned.append((points, abs(poly.area), poly))

    if not cleaned:
        raise PolygonRepairError("No closed contours were found in outline")

    cleaned.sort(key=lambda item: item[1], reverse=True)
    containers: list[int | None] = []
    for index, (_, _, poly) in enumerate(cleaned):
        probe = poly.representative_point()
        parent = None
        parent_area = None
        for candidate_index, (_, area, candidate) in enumerate(cleaned[:index]):
            if candidate.contains(probe):
                if parent_area is None or area < parent_area:
                    parent = candidate_index
                    parent_area = area
        containers.append(parent)

    children: dict[int, list[int]] = {index: [] for index in range(len(cleaned))}
    for index, parent in enumerate(containers):
        if parent is not None:
            children[parent].append(index)

    polygons = []
    for index, (ring, _, poly) in enumerate(cleaned):
        depth = 0
        parent = containers[index]
        while parent is not None:
            depth += 1
            parent = containers[parent]
        if depth % 2 == 1:
            continue
        holes = [cleaned[child][0] for child in children[index] if _depth(child, containers) == depth + 1]
        candidate = repair_geometry(Polygon(ring, holes))
        for geom in candidate.geoms:
            if geom.area > 1e-9:
                polygons.append(geom)

    try:
        merged = unary_union(polygons)
    except Exception:
        merged = unary_union([poly.buffer(0) for poly in polygons])
    return list(repair_geometry(merged).geoms)


def _depth(index: int, containers: list[int | None]) -> int:
    depth = 0
    parent = containers[index]
    while parent is not None:
        depth += 1
        parent = containers[parent]
    return depth


def geometry_boundary_distance(geometry, x: float, y: float) -> float:
    return float(geometry.boundary.distance(Point(float(x), float(y))))
