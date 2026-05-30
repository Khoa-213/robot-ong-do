import re
import xml.etree.ElementTree as ET
from pathlib import Path
from math import cos, pi, sin
from typing import Any

from modules.paper_zone import build_pose_in_paper
from modules.calligraphy_pressure_controller import (
    apply_calligraphy_pressure_to_strokes,
    config_from_robot_config as pressure_config_from_robot_config,
)
from src.svg.svg_to_strokes import load_svg_as_strokes


Point = tuple[float, float]
Matrix = tuple[float, float, float, float, float, float]


IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def build_svg_poses(config: dict[str, Any], svg_path: Path) -> list[list[float]]:
    return [pose for stroke in build_svg_pose_strokes(config, svg_path) for pose in stroke]


def build_svg_pose_strokes(config: dict[str, Any], svg_path: Path) -> list[list[list[float]]]:
    return build_custom_svg_pose_strokes(config, svg_path)


def build_custom_svg_pose_strokes(config: dict[str, Any], svg_path: Path) -> list[list[list[float]]]:
    """Parse a generic SVG and map each drawable stroke into measured paper poses."""
    demo = config.get("svg_demo", {})
    svg_config = {
        **config.get("svg_pipeline", {}),
        "samples_per_path": int(demo.get("samples_per_path", 120)),
        "point_spacing_mm": config.get("svg_pipeline", {}).get(
            "point_spacing_mm",
            config.get("smooth_writing", {}).get("point_spacing_mm", 1.0),
        ),
        "max_points_per_stroke": config.get("svg_pipeline", {}).get(
            "max_points_per_stroke",
            config.get("smooth_writing", {}).get("max_points_per_stroke", 220),
        ),
    }
    parsed_strokes = load_svg_as_strokes(svg_path, svg_config)
    if bool(svg_config.get("align_text_baseline", False)):
        parsed_strokes = _align_svg_text_baseline(
            parsed_strokes,
            candidate_ratio=float(svg_config.get("baseline_candidate_ratio", 0.45)),
            target=str(svg_config.get("baseline_target", "median")),
        )
    fit_to_drawable_bounds = bool(svg_config.get("fit_to_drawable_bounds", True))
    svg_bounds = svg_config.get("svg_drawable_bounds" if fit_to_drawable_bounds else "svg_bounds")
    if bool(svg_config.get("align_text_baseline", False)) and fit_to_drawable_bounds:
        svg_bounds = _stroke_dict_bounds(parsed_strokes)
    uv_strokes = _svg_strokes_to_uv_strokes(
        parsed_strokes,
        bounds=svg_bounds,
        u_min=float(demo.get("u_min", 0.25)),
        u_max=float(demo.get("u_max", 0.75)),
        v_min=float(demo.get("v_min", 0.25)),
        v_max=float(demo.get("v_max", 0.75)),
        preserve_aspect_ratio=bool(svg_config.get("preserve_aspect_ratio", True)),
        center_on_paper=bool(svg_config.get("center_on_paper", True)),
        flip_y=bool(svg_config.get("invert_y", svg_config.get("flip_y", False))),
        fit_width=bool(svg_config.get("fit_width", True)),
        fit_height=bool(svg_config.get("fit_height", True)),
        offset_u=float(svg_config.get("offset_x", svg_config.get("offset_u", 0.0))),
        offset_v=float(svg_config.get("offset_y", svg_config.get("offset_v", 0.0))),
    )
    pose_strokes = [[build_pose_in_paper(config, u, v) for u, v in stroke] for stroke in uv_strokes]
    return apply_calligraphy_pressure_to_strokes(pose_strokes, pressure_config_from_robot_config(config))


def _align_svg_text_baseline(
    strokes: list[dict[str, Any]],
    candidate_ratio: float = 0.45,
    target: str = "median",
) -> list[dict[str, Any]]:
    """Align main text strokes to one SVG-space baseline while leaving upper marks alone."""
    if len(strokes) < 2:
        return [dict(stroke) for stroke in strokes]

    bounds = [_stroke_dict_bounds([stroke]) for stroke in strokes]
    bottoms = [item[3] for item in bounds]
    min_bottom = min(bottoms)
    max_bottom = max(bottoms)
    if max_bottom - min_bottom <= 1e-9:
        return [dict(stroke) for stroke in strokes]

    ratio = max(0.0, min(1.0, float(candidate_ratio)))
    candidate_floor = min_bottom + (max_bottom - min_bottom) * ratio
    candidate_indexes = [index for index, bottom in enumerate(bottoms) if bottom >= candidate_floor]
    if len(candidate_indexes) < 2:
        return [dict(stroke) for stroke in strokes]

    candidate_bottoms = [bottoms[index] for index in candidate_indexes]
    if target.lower() == "max":
        target_bottom = max(candidate_bottoms)
    elif target.lower() == "min":
        target_bottom = min(candidate_bottoms)
    else:
        ordered = sorted(candidate_bottoms)
        middle = len(ordered) // 2
        target_bottom = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0

    aligned: list[dict[str, Any]] = []
    for index, stroke in enumerate(strokes):
        next_stroke = dict(stroke)
        points = stroke.get("points", [])
        if index in candidate_indexes:
            dy = target_bottom - bottoms[index]
            next_stroke["points"] = [[round(float(x), 6), round(float(y) + dy, 6)] for x, y in points]
            next_stroke["baseline_aligned"] = True
        else:
            next_stroke["points"] = [[float(x), float(y)] for x, y in points]
            next_stroke["baseline_aligned"] = False
        aligned.append(next_stroke)
    return aligned


def _stroke_dict_bounds(strokes: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    points = [point for stroke in strokes for point in stroke.get("points", [])]
    if not points:
        raise ValueError("No SVG stroke points available for bounds")
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _svg_strokes_to_uv_strokes(
    strokes: list[dict[str, Any]],
    bounds: list[float] | tuple[float, float, float, float] | None,
    u_min: float,
    u_max: float,
    v_min: float,
    v_max: float,
    preserve_aspect_ratio: bool = True,
    center_on_paper: bool = True,
    flip_y: bool = False,
    fit_width: bool = True,
    fit_height: bool = True,
    offset_u: float = 0.0,
    offset_v: float = 0.0,
) -> list[list[Point]]:
    if bounds is None:
        all_points = [point for stroke in strokes for point in stroke["points"]]
        xs = [float(point[0]) for point in all_points]
        ys = [float(point[1]) for point in all_points]
        min_x, min_y, max_x, max_y = min(xs), min(ys), max(xs), max(ys)
    else:
        min_x, min_y, max_x, max_y = [float(value) for value in bounds]
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0.0 or height <= 0.0:
        raise ValueError("SVG bounds must have positive width and height")

    u_span = u_max - u_min
    v_span = v_max - v_min
    if preserve_aspect_ratio:
        scale_options = []
        if fit_width:
            scale_options.append(u_span / width)
        if fit_height:
            scale_options.append(v_span / height)
        if not scale_options:
            scale_options.append(1.0)
        scale = min(scale_options)
        scale_x = scale_y = scale
        fitted_u = width * scale
        fitted_v = height * scale
    else:
        scale_x = u_span / width
        scale_y = v_span / height
        fitted_u = u_span
        fitted_v = v_span
    offset_u = ((u_span - fitted_u) / 2.0 if center_on_paper else 0.0) + float(offset_u)
    offset_v = ((v_span - fitted_v) / 2.0 if center_on_paper else 0.0) + float(offset_v)

    uv_strokes: list[list[Point]] = []
    for stroke in strokes:
        uv_points: list[Point] = []
        for x, y in stroke["points"]:
            u = u_min + offset_u + (float(x) - min_x) * scale_x
            v_local = offset_v + (float(y) - min_y) * scale_y
            v = v_max - v_local if flip_y else v_min + v_local
            uv_points.append((u, v))
        uv_strokes.append(uv_points)
    return uv_strokes


def build_svg_pose_strokes_in_viewbox(config: dict[str, Any], svg_path: Path) -> list[list[list[float]]]:
    demo = config["svg_demo"]
    strokes = sample_svg_strokes(
        svg_path=svg_path,
        samples_per_path=int(demo.get("samples_per_path", 120)),
    )
    root = ET.parse(svg_path).getroot()
    min_x, min_y, width, height = _svg_viewbox(root)
    if width <= 0.0 or height <= 0.0:
        raise ValueError(f"SVG viewBox must have positive width and height: {svg_path}")

    u_min = float(demo.get("u_min", 0.25))
    u_max = float(demo.get("u_max", 0.75))
    v_min = float(demo.get("v_min", 0.25))
    v_max = float(demo.get("v_max", 0.75))
    if not (0.0 <= u_min < u_max <= 1.0):
        raise ValueError("u_min/u_max must be inside [0, 1]")
    if not (0.0 <= v_min < v_max <= 1.0):
        raise ValueError("v_min/v_max must be inside [0, 1]")

    u_span = u_max - u_min
    v_span = v_max - v_min
    scale = min(u_span / width, v_span / height)
    fitted_width = width * scale
    fitted_height = height * scale
    u_offset = u_min + (u_span - fitted_width) / 2.0
    v_offset = v_min + (v_span - fitted_height) / 2.0

    pose_strokes = []
    for stroke in strokes:
        uv_stroke = [
            (
                u_offset + (x - min_x) * scale,
                v_offset + (y - min_y) * scale,
            )
            for x, y in stroke
        ]
        pose_strokes.append([build_pose_in_paper(config, u, v) for u, v in uv_stroke])
    return pose_strokes


def sample_svg_points(svg_path: Path, samples_per_path: int = 120) -> list[Point]:
    strokes = sample_svg_strokes(svg_path, samples_per_path)
    return [point for stroke in strokes for point in stroke]


def sample_svg_strokes(svg_path: Path, samples_per_path: int = 120) -> list[list[Point]]:
    if samples_per_path < 8:
        raise ValueError("samples_per_path must be at least 8")
    parsed = load_svg_as_strokes(
        svg_path,
        {
            "curve_sample_resolution": samples_per_path,
            "sample_step_mm": 1.0,
            "max_point_distance_mm": 0.0,
            "simplify_tolerance": 0.0,
            "smoothing_enabled": False,
            "min_point_distance_mm": 0.0,
        },
    )
    return [[(float(x), float(y)) for x, y in stroke["points"]] for stroke in parsed]


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


def _sample_poly_points(points_data: str, samples_per_path: int) -> list[Point]:
    values = [float(value) for value in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", points_data)]
    points = [(values[index], values[index + 1]) for index in range(0, len(values) - 1, 2)]
    if len(points) > samples_per_path:
        step = max(len(points) / samples_per_path, 1.0)
        points = [points[int(i * step)] for i in range(samples_per_path)]
    return points


def _sample_ellipse(cx: float, cy: float, rx: float, ry: float, samples_per_path: int) -> list[Point]:
    if rx <= 0.0 or ry <= 0.0:
        return []
    count = max(samples_per_path, 16)
    return [
        (
            cx + rx * cos(2.0 * pi * index / count),
            cy + ry * sin(2.0 * pi * index / count),
        )
        for index in range(count + 1)
    ]


def _svg_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    viewbox = root.attrib.get("viewBox", "").strip()
    if viewbox:
        values = [float(value) for value in re.split(r"[,\s]+", viewbox) if value]
        if len(values) == 4:
            return values[0], values[1], values[2], values[3]
    width = _parse_svg_length(root.attrib.get("width", "0"))
    height = _parse_svg_length(root.attrib.get("height", "0"))
    return 0.0, 0.0, width, height


def _parse_svg_length(value: str) -> float:
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)
    return float(match.group(0)) if match else 0.0


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
