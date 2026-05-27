import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from modules.paper_zone import build_pose_in_paper


Point = tuple[float, float]
Matrix = tuple[float, float, float, float, float, float]


IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def build_svg_poses(config: dict[str, Any], svg_path: Path) -> list[list[float]]:
    demo = config["svg_demo"]
    points = sample_svg_points(
        svg_path=svg_path,
        samples_per_path=int(demo.get("samples_per_path", 120)),
    )
    normalized_points = fit_points_to_uv(
        points,
        u_min=float(demo.get("u_min", 0.25)),
        u_max=float(demo.get("u_max", 0.75)),
        v_min=float(demo.get("v_min", 0.25)),
        v_max=float(demo.get("v_max", 0.75)),
    )
    return [build_pose_in_paper(config, u, v) for u, v in normalized_points]


def sample_svg_points(svg_path: Path, samples_per_path: int = 120) -> list[Point]:
    if samples_per_path < 8:
        raise ValueError("samples_per_path must be at least 8")
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    root = ET.parse(svg_path).getroot()
    points: list[Point] = []

    for element, matrix in _walk_svg(root, IDENTITY):
        if _strip_namespace(element.tag) != "path":
            continue
        path_data = element.attrib.get("d")
        if not path_data:
            continue
        local_points = _sample_path_data(path_data, samples_per_path)
        points.extend(_apply_matrix(matrix, point) for point in local_points)

    if not points:
        raise ValueError(f"No SVG path points found in {svg_path}")
    return points


def fit_points_to_uv(
    points: list[Point],
    u_min: float,
    u_max: float,
    v_min: float,
    v_max: float,
) -> list[Point]:
    if not (0.0 <= u_min < u_max <= 1.0):
        raise ValueError("u_min/u_max must be inside [0, 1]")
    if not (0.0 <= v_min < v_max <= 1.0):
        raise ValueError("v_min/v_max must be inside [0, 1]")

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0.0 or height <= 0.0:
        raise ValueError("SVG point bounds must have positive width and height")

    u_span = u_max - u_min
    v_span = v_max - v_min
    scale = min(u_span / width, v_span / height)
    fitted_width = width * scale
    fitted_height = height * scale
    u_offset = u_min + (u_span - fitted_width) / 2.0
    v_offset = v_min + (v_span - fitted_height) / 2.0

    return [
        (
            u_offset + (x - min_x) * scale,
            v_offset + (y - min_y) * scale,
        )
        for x, y in points
    ]


def _walk_svg(element: ET.Element, parent_matrix: Matrix):
    local_matrix = _parse_transform(element.attrib.get("transform", ""))
    matrix = _multiply_matrix(parent_matrix, local_matrix)
    yield element, matrix
    for child in list(element):
        yield from _walk_svg(child, matrix)


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _parse_transform(transform: str) -> Matrix:
    matrix = IDENTITY
    for name, raw_values in re.findall(r"([a-zA-Z]+)\(([^)]*)\)", transform):
        values = [float(value) for value in re.split(r"[,\s]+", raw_values.strip()) if value]
        name = name.lower()
        if name == "translate":
            tx = values[0]
            ty = values[1] if len(values) > 1 else 0.0
            current = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif name == "scale":
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            current = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "matrix":
            if len(values) != 6:
                raise ValueError(f"matrix() transform must have 6 values: {transform}")
            current = tuple(values)  # type: ignore[assignment]
        else:
            raise ValueError(f"Unsupported SVG transform '{name}' in {transform}")
        matrix = _multiply_matrix(matrix, current)
    return matrix


def _multiply_matrix(left: Matrix, right: Matrix) -> Matrix:
    la, lb, lc, ld, le, lf = left
    ra, rb, rc, rd, re, rf = right
    return (
        la * ra + lc * rb,
        lb * ra + ld * rb,
        la * rc + lc * rd,
        lb * rc + ld * rd,
        la * re + lc * rf + le,
        lb * re + ld * rf + lf,
    )


def _apply_matrix(matrix: Matrix, point: Point) -> Point:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _sample_path_data(path_data: str, samples_per_path: int) -> list[Point]:
    tokens = re.findall(r"[MmLlHhVvCcZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", path_data)
    index = 0
    command = ""
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    points: list[Point] = []

    def has_number() -> bool:
        return index < len(tokens) and not re.match(r"^[A-Za-z]$", tokens[index])

    def read_number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    while index < len(tokens):
        if re.match(r"^[A-Za-z]$", tokens[index]):
            command = tokens[index]
            index += 1

        if command in ("M", "m"):
            first = True
            while has_number():
                x = read_number()
                y = read_number()
                if command == "m":
                    x += current[0]
                    y += current[1]
                current = (x, y)
                if first:
                    start = current
                    points.append(current)
                    first = False
                else:
                    points.extend(_sample_line(points[-1], current, 2)[1:])
            command = "L" if command == "M" else "l"
        elif command in ("L", "l"):
            while has_number():
                x = read_number()
                y = read_number()
                if command == "l":
                    x += current[0]
                    y += current[1]
                nxt = (x, y)
                points.extend(_sample_line(current, nxt, 2)[1:])
                current = nxt
        elif command in ("H", "h"):
            while has_number():
                x = read_number()
                if command == "h":
                    x += current[0]
                nxt = (x, current[1])
                points.extend(_sample_line(current, nxt, 2)[1:])
                current = nxt
        elif command in ("V", "v"):
            while has_number():
                y = read_number()
                if command == "v":
                    y += current[1]
                nxt = (current[0], y)
                points.extend(_sample_line(current, nxt, 2)[1:])
                current = nxt
        elif command in ("C", "c"):
            curve_count = max(samples_per_path // 8, 6)
            while has_number():
                c1 = (read_number(), read_number())
                c2 = (read_number(), read_number())
                end = (read_number(), read_number())
                if command == "c":
                    c1 = (c1[0] + current[0], c1[1] + current[1])
                    c2 = (c2[0] + current[0], c2[1] + current[1])
                    end = (end[0] + current[0], end[1] + current[1])
                points.extend(_sample_cubic(current, c1, c2, end, curve_count)[1:])
                current = end
        elif command in ("Z", "z"):
            if current != start:
                points.extend(_sample_line(current, start, 2)[1:])
            current = start
            command = ""
        else:
            raise ValueError(f"Unsupported SVG path command: {command}")

    if len(points) > samples_per_path:
        step = max(len(points) / samples_per_path, 1.0)
        points = [points[int(i * step)] for i in range(samples_per_path)]
    return points


def _sample_line(start: Point, end: Point, count: int) -> list[Point]:
    return [
        (
            start[0] + (end[0] - start[0]) * index / max(count - 1, 1),
            start[1] + (end[1] - start[1]) * index / max(count - 1, 1),
        )
        for index in range(count)
    ]


def _sample_cubic(start: Point, c1: Point, c2: Point, end: Point, count: int) -> list[Point]:
    points = []
    for index in range(count):
        t = index / max(count - 1, 1)
        mt = 1.0 - t
        x = mt**3 * start[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * end[0]
        y = mt**3 * start[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * end[1]
        points.append((x, y))
    return points
