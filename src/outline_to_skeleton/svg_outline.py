from __future__ import annotations

from pathlib import Path

from svgpathtools import Line, Path as SvgPath, svg2paths2

from .errors import OutlineExtractionError
from .geometry import rings_to_polygons


def svg_to_outline_polygons(svg_path: str, samples_per_segment: int = 24):
    path = Path(svg_path)
    if not path.is_file():
        raise OutlineExtractionError(f"SVG cannot be read: {svg_path}")

    try:
        paths, _, _ = svg2paths2(str(path))
    except Exception as exc:
        raise OutlineExtractionError(f"SVG parse failed: {svg_path}: {exc}") from exc

    rings: list[list[tuple[float, float]]] = []
    for svg_path_item in paths:
        rings.extend(_path_to_rings(svg_path_item, samples_per_segment))

    if not rings:
        raise OutlineExtractionError("SVG has no valid closed path outline")
    return rings_to_polygons(rings)


def _path_to_rings(path: SvgPath, samples_per_segment: int) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor: complex | None = None

    for segment in path:
        if cursor is None or abs(segment.start - cursor) > 1e-6:
            if _is_closed_ring(current):
                rings.append(current)
            current = [(float(segment.start.real), float(segment.start.imag))]

        count = 1 if isinstance(segment, Line) else max(4, int(samples_per_segment))
        for index in range(1, count + 1):
            point = segment.point(index / count)
            current.append((float(point.real), float(point.imag)))
        cursor = segment.end

    if _is_closed_ring(current):
        rings.append(current)
    return rings


def _is_closed_ring(points: list[tuple[float, float]]) -> bool:
    if len(points) < 4:
        return False
    start = points[0]
    end = points[-1]
    return ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5 <= 1e-4
