from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from svgpathtools import CubicBezier, Line, QuadraticBezier, parse_path


Point2D = tuple[float, float]
Point3D = list[float]
Matrix = tuple[float, float, float, float, float, float]
StrokeDict = dict[str, Any]

IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class SvgStrokeConfig:
    sample_step_mm: float = 1.0
    max_point_distance_mm: float = 1.0
    min_point_distance_mm: float = 0.05
    smoothing_enabled: bool = False
    smoothing_window: int = 3
    curve_sample_resolution: int = 24
    simplify_tolerance: float = 0.2
    min_stroke_length: float = 0.01
    preserve_aspect_ratio: bool = True
    center_on_paper: bool = True
    invert_y: bool = True
    max_strokes: int = 0
    max_points_per_stroke: int = 0
    allow_closed_paths: bool = True

    @property
    def point_spacing_mm(self) -> float:
        return self.max_point_distance_mm

    @property
    def min_point_distance(self) -> float:
        return self.min_point_distance_mm

    @property
    def flip_y(self) -> bool:
        return self.invert_y


def load_svg_as_strokes(svg_path: str | Path, config: dict[str, Any] | SvgStrokeConfig | None = None) -> list[StrokeDict]:
    """Load robot-friendly single-stroke SVG elements into 2D stroke dictionaries."""
    cfg = _coerce_config(config)
    warnings: list[str] = []
    try:
        strokes, bounds = _load_svg_document(Path(svg_path), cfg, warnings)
    except Exception:
        if isinstance(config, dict):
            config["svg_warnings"] = warnings
        raise
    if isinstance(config, dict):
        config["svg_bounds"] = list(bounds)
        config["svg_drawable_bounds"] = list(_bounds_from_strokes(strokes))
        config["svg_warnings"] = warnings
    return strokes


def svg_strokes_to_robot_strokes(
    strokes: list[StrokeDict],
    paper_origin: Iterable[float],
    paper_width_mm: float,
    paper_height_mm: float,
    writing_z: float,
    preserve_aspect_ratio: bool = True,
    flip_y: bool = True,
    center_on_paper: bool = True,
    svg_bounds: Iterable[float] | None = None,
    fit_width: bool = True,
    fit_height: bool = True,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    invert_y: bool | None = None,
) -> list[list[Point3D]]:
    """Map SVG stroke points to paper-relative robot XYZ waypoints in millimeters."""
    if invert_y is not None:
        flip_y = bool(invert_y)
    if paper_width_mm <= 0.0 or paper_height_mm <= 0.0:
        raise ValueError("paper_width_mm and paper_height_mm must be positive")
    origin = [float(value) for value in paper_origin]
    if len(origin) < 2:
        raise ValueError("paper_origin must contain at least [x, y]")

    min_x, min_y, max_x, max_y = _bounds_from_strokes(strokes, svg_bounds)
    src_w = max_x - min_x
    src_h = max_y - min_y
    if src_w <= 0.0 or src_h <= 0.0:
        raise ValueError("SVG bounds must have positive width and height")

    if preserve_aspect_ratio:
        scale_options = []
        if fit_width:
            scale_options.append(float(paper_width_mm) / src_w)
        if fit_height:
            scale_options.append(float(paper_height_mm) / src_h)
        if not scale_options:
            scale_options.append(1.0)
        scale = min(scale_options)
        scale_x = scale_y = scale
        fitted_w = src_w * scale
        fitted_h = src_h * scale
    else:
        scale_x = float(paper_width_mm) / src_w
        scale_y = float(paper_height_mm) / src_h
        fitted_w = float(paper_width_mm)
        fitted_h = float(paper_height_mm)

    offset_x = ((float(paper_width_mm) - fitted_w) / 2.0 if center_on_paper else 0.0) + float(offset_x_mm)
    offset_y = ((float(paper_height_mm) - fitted_h) / 2.0 if center_on_paper else 0.0) + float(offset_y_mm)

    robot_strokes: list[list[Point3D]] = []
    for stroke in strokes:
        robot_points: list[Point3D] = []
        for point in stroke.get("points", []):
            x = (float(point[0]) - min_x) * scale_x + offset_x
            y = (float(point[1]) - min_y) * scale_y + offset_y
            if flip_y:
                y = float(paper_height_mm) - y
            robot_points.append([round(origin[0] + x, 3), round(origin[1] + y, 3), round(float(writing_z), 3)])
        if len(robot_points) >= 2:
            robot_strokes.append(robot_points)
    return robot_strokes


def validate_robot_strokes_safe_zone(
    robot_strokes: list[list[Point3D]],
    paper_origin: Iterable[float],
    paper_width_mm: float,
    paper_height_mm: float,
    z_min: float | None = None,
    z_max: float | None = None,
    margin_mm: float = 0.0,
) -> None:
    origin = [float(value) for value in paper_origin]
    x_min = origin[0] + margin_mm
    x_max = origin[0] + float(paper_width_mm) - margin_mm
    y_min = origin[1] + margin_mm
    y_max = origin[1] + float(paper_height_mm) - margin_mm
    for stroke_index, stroke in enumerate(robot_strokes, start=1):
        for point_index, point in enumerate(stroke, start=1):
            x, y, z = point
            z_bad = (z_min is not None and z < z_min) or (z_max is not None and z > z_max)
            if x < x_min or x > x_max or y < y_min or y > y_max or z_bad:
                raise ValueError(f"Waypoint out of safe zone at stroke {stroke_index} point {point_index}: {point}")


def export_strokes_json(path: str | Path, strokes: list[StrokeDict], robot_strokes: list[list[Point3D]] | None = None) -> None:
    payload: dict[str, Any] = {"strokes": strokes}
    if robot_strokes is not None:
        payload["robot_strokes"] = robot_strokes
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_stroke_preview(strokes: list[StrokeDict], output_path: str | Path, title: str | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    for index, stroke in enumerate(strokes, start=1):
        points = stroke.get("points", [])
        if len(points) < 2:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        ax.plot(xs, ys, linewidth=1.5)
        ax.scatter(xs[0], ys[0], c="green", s=25, zorder=3)
        ax.scatter(xs[-1], ys[-1], c="red", s=25, zorder=3)
        if len(strokes) <= 40:
            ax.text(xs[0], ys[0], str(index), fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()
    ax.grid(True, alpha=0.25)
    ax.set_title(title or "SVG stroke order")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def _load_svg_document(svg_path: Path, cfg: SvgStrokeConfig, warnings: list[str]) -> tuple[list[StrokeDict], tuple[float, float, float, float]]:
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SVG XML in {svg_path}: {exc}") from exc

    strokes: list[StrokeDict] = []
    for element, matrix in _walk_svg(root, IDENTITY):
        tag = _strip_namespace(element.tag)
        try:
            local_strokes = _element_to_strokes(element, tag, cfg, warnings)
        except Exception as exc:
            element_id = element.attrib.get("id", "<no id>")
            raise ValueError(f"Failed to parse SVG {tag} element {element_id}: {exc}") from exc
        for source, points, closed in local_strokes:
            transformed = [_apply_matrix(matrix, point) for point in points]
            cleaned = clean_svg_points(transformed, cfg)
            if len(cleaned) >= 2 and _stroke_length(cleaned) >= cfg.min_stroke_length:
                strokes.append(
                    {
                        "id": f"stroke_{len(strokes) + 1:03d}",
                        "source": source,
                        "points": [[round(x, 6), round(y, 6)] for x, y in cleaned],
                        "closed": bool(closed),
                        "requires_pen_lift": True,
                    }
                )
                if cfg.max_strokes > 0 and len(strokes) >= cfg.max_strokes:
                    break
        if cfg.max_strokes > 0 and len(strokes) >= cfg.max_strokes:
            break

    if not strokes:
        detail = "; ".join(warnings[-6:])
        suffix = f" Warnings: {detail}" if detail else ""
        raise ValueError(f"No robot-friendly single-stroke path/polyline/line elements found in {svg_path}.{suffix}")
    return strokes, _svg_bounds(root, strokes)


def _element_to_strokes(
    element: ET.Element,
    tag: str,
    cfg: SvgStrokeConfig,
    warnings: list[str],
) -> list[tuple[str, list[Point2D], bool]]:
    if tag == "path":
        if _has_non_none_fill(element):
            warnings.append(_element_warning(element, "ignored path with fill; single-stroke SVG must use fill='none'"))
            return []
        path_data = element.attrib.get("d", "")
        if not path_data.strip():
            return []
        if _path_has_close_command(path_data):
            message = "path contains Z/z close command"
            if not cfg.allow_closed_paths:
                warnings.append(_element_warning(element, f"ignored {message}"))
                return []
            warnings.append(_element_warning(element, f"accepted {message}; verify this is an intentional closed stroke"))
        return [("path", points, closed) for points, closed in _sample_path_data(path_data, cfg)]
    if tag == "polyline":
        points = _parse_points_attr(element.attrib.get("points", ""))
        return [(tag, points, False)]
    if tag == "line":
        return [
            (
                "line",
                [
                    (_float_attr(element, "x1"), _float_attr(element, "y1")),
                    (_float_attr(element, "x2"), _float_attr(element, "y2")),
                ],
                False,
            )
        ]
    if tag in ("text", "rect", "circle", "ellipse", "polygon"):
        warnings.append(_element_warning(element, f"ignored <{tag}>; use path/polyline/line centerline strokes only"))
    return []


def clean_svg_points(points: list[Point2D], cfg: SvgStrokeConfig) -> list[Point2D]:
    cleaned = _remove_near_duplicate_points(points, cfg.min_point_distance)
    simplified = _rdp_points(cleaned, cfg.simplify_tolerance)
    smoothed = _moving_average_points(simplified, cfg.smoothing_window) if cfg.smoothing_enabled else simplified
    resampled = _resample_points(smoothed, cfg.max_point_distance_mm) if cfg.max_point_distance_mm > 0.0 else smoothed
    if cfg.max_points_per_stroke > 0 and len(resampled) > cfg.max_points_per_stroke:
        resampled = _downsample_keep_ends(resampled, cfg.max_points_per_stroke)
    return resampled


def _sample_path_data(path_data: str, cfg: SvgStrokeConfig) -> list[tuple[list[Point2D], bool]]:
    path = parse_path(path_data)
    if len(path) == 0:
        return []
    strokes: list[tuple[list[Point2D], bool]] = []
    current_points: list[Point2D] = []
    previous_end: complex | None = None
    for segment in path:
        if previous_end is None or abs(segment.start - previous_end) > 1e-9:
            if len(current_points) >= 2:
                strokes.append((current_points, _points_closed(current_points)))
            current_points = [_complex_to_point(segment.start)]
        samples = _sample_segment(segment, cfg)
        current_points.extend(samples[1:] if current_points else samples)
        previous_end = segment.end
    if len(current_points) >= 2:
        strokes.append((current_points, _points_closed(current_points)))
    return strokes


def _sample_segment(segment: Any, cfg: SvgStrokeConfig) -> list[Point2D]:
    if isinstance(segment, Line):
        count = 2
    elif isinstance(segment, (CubicBezier, QuadraticBezier)):
        count = max(_segment_sample_count(segment, cfg.sample_step_mm), int(cfg.curve_sample_resolution), 4)
    else:
        count = max(_segment_sample_count(segment, cfg.sample_step_mm), int(cfg.curve_sample_resolution), 8)
    return [_complex_to_point(segment.point(index / max(count - 1, 1))) for index in range(count)]


def _segment_sample_count(segment: Any, sample_step_mm: float) -> int:
    if sample_step_mm <= 0.0:
        return 2
    try:
        length = float(segment.length(error=1e-4))
    except Exception:
        length = abs(segment.end - segment.start)
    return max(2, min(1000, int(math.ceil(length / sample_step_mm)) + 1))


def _walk_svg(element: ET.Element, parent_matrix: Matrix):
    local_matrix = _parse_transform(element.attrib.get("transform", ""))
    matrix = _multiply_matrix(parent_matrix, local_matrix)
    yield element, matrix
    for child in list(element):
        yield from _walk_svg(child, matrix)


def _parse_transform(transform: str) -> Matrix:
    matrix = IDENTITY
    for name, raw_values in re.findall(r"([a-zA-Z]+)\(([^)]*)\)", transform):
        values = [float(value) for value in re.split(r"[,\s]+", raw_values.strip()) if value]
        current = _transform_to_matrix(name.lower(), values)
        matrix = _multiply_matrix(matrix, current)
    return matrix


def _transform_to_matrix(name: str, values: list[float]) -> Matrix:
    if name == "translate":
        return (1.0, 0.0, 0.0, 1.0, values[0], values[1] if len(values) > 1 else 0.0)
    if name == "scale":
        sx = values[0]
        sy = values[1] if len(values) > 1 else sx
        return (sx, 0.0, 0.0, sy, 0.0, 0.0)
    if name == "rotate":
        angle = math.radians(values[0])
        c = math.cos(angle)
        s = math.sin(angle)
        rot = (c, s, -s, c, 0.0, 0.0)
        if len(values) >= 3:
            cx, cy = values[1], values[2]
            return _multiply_matrix(_multiply_matrix((1.0, 0.0, 0.0, 1.0, cx, cy), rot), (1.0, 0.0, 0.0, 1.0, -cx, -cy))
        return rot
    if name == "matrix":
        if len(values) != 6:
            raise ValueError("matrix() transform must have 6 values")
        return tuple(values)  # type: ignore[return-value]
    if name == "skewx":
        return (1.0, 0.0, math.tan(math.radians(values[0])), 1.0, 0.0, 0.0)
    if name == "skewy":
        return (1.0, math.tan(math.radians(values[0])), 0.0, 1.0, 0.0, 0.0)
    raise ValueError(f"Unsupported SVG transform '{name}'")


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


def _apply_matrix(matrix: Matrix, point: Point2D) -> Point2D:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _svg_bounds(root: ET.Element, strokes: list[StrokeDict]) -> tuple[float, float, float, float]:
    viewbox = root.attrib.get("viewBox", "").strip()
    if viewbox:
        values = [float(value) for value in re.split(r"[,\s]+", viewbox) if value]
        if len(values) == 4 and values[2] > 0.0 and values[3] > 0.0:
            return values[0], values[1], values[0] + values[2], values[1] + values[3]
    width = _parse_svg_length(root.attrib.get("width", "0"))
    height = _parse_svg_length(root.attrib.get("height", "0"))
    if width > 0.0 and height > 0.0:
        return 0.0, 0.0, width, height
    return _bounds_from_strokes(strokes)


def _bounds_from_strokes(strokes: list[StrokeDict], svg_bounds: Iterable[float] | None = None) -> tuple[float, float, float, float]:
    if svg_bounds is not None:
        values = [float(value) for value in svg_bounds]
        if len(values) == 4:
            return values[0], values[1], values[2], values[3]
    points = [point for stroke in strokes for point in stroke.get("points", [])]
    if not points:
        raise ValueError("No stroke points available for bounds")
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _coerce_config(config: dict[str, Any] | SvgStrokeConfig | None) -> SvgStrokeConfig:
    if isinstance(config, SvgStrokeConfig):
        return config
    data = config or {}
    sample_step = float(data.get("sample_step_mm", data.get("point_spacing_mm", data.get("point_spacing", 1.0))))
    max_point_distance = float(data.get("max_point_distance_mm", data.get("point_spacing_mm", data.get("point_spacing", sample_step))))
    return SvgStrokeConfig(
        sample_step_mm=sample_step,
        max_point_distance_mm=max_point_distance,
        min_point_distance_mm=float(data.get("min_point_distance_mm", data.get("min_point_distance", 0.05))),
        smoothing_enabled=bool(data.get("smoothing_enabled", data.get("smooth_points", False))),
        smoothing_window=int(data.get("smoothing_window", data.get("moving_average_window", 3))),
        curve_sample_resolution=int(data.get("curve_sample_resolution", data.get("samples_per_path", 24))),
        simplify_tolerance=float(data.get("simplify_tolerance", data.get("smoothing_tolerance", 0.2))),
        min_stroke_length=float(data.get("min_stroke_length", 0.01)),
        preserve_aspect_ratio=bool(data.get("preserve_aspect_ratio", True)),
        center_on_paper=bool(data.get("center_on_paper", True)),
        invert_y=bool(data.get("invert_y", data.get("flip_y", True))),
        max_strokes=int(data.get("max_strokes", 0)),
        max_points_per_stroke=int(data.get("max_points_per_stroke", 0)),
        allow_closed_paths=bool(data.get("allow_closed_paths", True)),
    )


def _parse_points_attr(points_data: str) -> list[Point2D]:
    values = [float(value) for value in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", points_data)]
    return [(values[index], values[index + 1]) for index in range(0, len(values) - 1, 2)]


def _sample_ellipse(cx: float, cy: float, rx: float, ry: float, resolution: int) -> list[Point2D]:
    if rx <= 0.0 or ry <= 0.0:
        return []
    count = max(int(resolution), 16)
    return [(cx + rx * math.cos(2.0 * math.pi * i / count), cy + ry * math.sin(2.0 * math.pi * i / count)) for i in range(count + 1)]


def _has_non_none_fill(element: ET.Element) -> bool:
    fill = _style_value(element, "fill")
    if fill is None:
        fill = element.attrib.get("fill")
    if fill is None:
        return False
    fill = fill.strip().lower()
    return bool(fill) and fill not in ("none", "transparent")


def _style_value(element: ET.Element, name: str) -> str | None:
    for item in element.attrib.get("style", "").split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        if key.strip().lower() == name:
            return value.strip()
    return None


def _path_has_close_command(path_data: str) -> bool:
    return re.search(r"[Zz]", path_data) is not None


def _element_warning(element: ET.Element, message: str) -> str:
    element_id = element.attrib.get("id")
    suffix = f" id='{element_id}'" if element_id else ""
    return f"{message}{suffix}"


def _remove_near_duplicate_points(points: list[Point2D], min_distance: float) -> list[Point2D]:
    if not points:
        return []
    cleaned = [points[0]]
    for point in points[1:]:
        if _distance(cleaned[-1], point) >= min_distance:
            cleaned.append(point)
    if len(cleaned) == 1 and len(points) > 1:
        cleaned.append(points[-1])
    return cleaned


def _rdp_points(points: list[Point2D], tolerance: float) -> list[Point2D]:
    if tolerance <= 0.0 or len(points) <= 2:
        return list(points)
    index = 0
    max_distance = 0.0
    for i in range(1, len(points) - 1):
        distance = _perpendicular_distance(points[i], points[0], points[-1])
        if distance > max_distance:
            index = i
            max_distance = distance
    if max_distance > tolerance:
        return _rdp_points(points[: index + 1], tolerance)[:-1] + _rdp_points(points[index:], tolerance)
    return [points[0], points[-1]]


def _resample_points(points: list[Point2D], spacing: float) -> list[Point2D]:
    if spacing <= 0.0 or len(points) < 2:
        return list(points)
    resampled = [points[0]]
    carried = 0.0
    current = points[0]
    for target in points[1:]:
        segment_length = _distance(current, target)
        if segment_length <= 1e-9:
            continue
        while carried + segment_length >= spacing:
            remain = spacing - carried
            t = remain / segment_length
            current = (current[0] + (target[0] - current[0]) * t, current[1] + (target[1] - current[1]) * t)
            resampled.append(current)
            segment_length = _distance(current, target)
            carried = 0.0
            if segment_length <= 1e-9:
                break
        carried += segment_length
        current = target
    if _distance(resampled[-1], points[-1]) > 1e-6:
        resampled.append(points[-1])
    return resampled


def _downsample_keep_ends(points: list[Point2D], max_points: int) -> list[Point2D]:
    if max_points < 2 or len(points) <= max_points:
        return list(points)
    step = (len(points) - 1) / (max_points - 1)
    return [points[round(i * step)] for i in range(max_points)]


def _moving_average_points(points: list[Point2D], window: int) -> list[Point2D]:
    if window < 3 or len(points) <= 2:
        return list(points)
    if window % 2 == 0:
        window += 1
    radius = window // 2
    smoothed = [points[0]]
    for index in range(1, len(points) - 1):
        start = max(0, index - radius)
        end = min(len(points), index + radius + 1)
        segment = points[start:end]
        smoothed.append(
            (
                sum(point[0] for point in segment) / len(segment),
                sum(point[1] for point in segment) / len(segment),
            )
        )
    smoothed.append(points[-1])
    return smoothed


def _stroke_length(points: list[Point2D]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _perpendicular_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    base = _distance(start, end)
    if base <= 1e-9:
        return _distance(point, start)
    return abs((end[0] - start[0]) * (start[1] - point[1]) - (start[0] - point[0]) * (end[1] - start[1])) / base


def _points_closed(points: list[Point2D]) -> bool:
    return len(points) >= 2 and _distance(points[0], points[-1]) <= 1e-6


def _complex_to_point(value: complex) -> Point2D:
    return float(value.real), float(value.imag)


def _float_attr(element: ET.Element, name: str, default: float = 0.0) -> float:
    return _parse_svg_length(element.attrib.get(name, str(default)))


def _parse_svg_length(value: str) -> float:
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", str(value))
    return float(match.group(0)) if match else 0.0


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse an SVG into robot-ready stroke waypoints.")
    parser.add_argument("--input", required=True, help="Input SVG path.")
    parser.add_argument("--output", default="outputs", help="Output directory for generated preview/json files.")
    parser.add_argument("--dry-run", action="store_true", help="Parse, scale, validate, and print summary only.")
    parser.add_argument("--preview", action="store_true", help="Save a PNG preview of stroke order.")
    parser.add_argument("--export-json", help="Write parsed strokes and robot strokes JSON to this path.")
    parser.add_argument("--paper-width", type=float, default=100.0, help="Paper width in mm.")
    parser.add_argument("--paper-height", type=float, default=100.0, help="Paper height in mm.")
    parser.add_argument("--point-spacing", type=float, default=1.0, help="Resample spacing in SVG units before paper scaling.")
    parser.add_argument("--flip-y", action=argparse.BooleanOptionalAction, default=True, help="Flip SVG Y axis when mapping to robot paper.")
    parser.add_argument("--center", action=argparse.BooleanOptionalAction, default=True, help="Center drawing on paper.")
    parser.add_argument(
        "--fit-drawable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fit drawable stroke bounds instead of the full SVG page/viewBox.",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    config: dict[str, Any] = {
        "point_spacing_mm": args.point_spacing,
        "curve_sample_resolution": 32,
        "simplify_tolerance": 0.05,
    }
    try:
        strokes = load_svg_as_strokes(args.input, config)
        robot_strokes = svg_strokes_to_robot_strokes(
            strokes,
            paper_origin=(0.0, 0.0),
            paper_width_mm=args.paper_width,
            paper_height_mm=args.paper_height,
            writing_z=0.0,
            preserve_aspect_ratio=True,
            flip_y=args.flip_y,
            center_on_paper=args.center,
            svg_bounds=config.get("svg_drawable_bounds" if args.fit_drawable else "svg_bounds"),
        )
        validate_robot_strokes_safe_zone(robot_strokes, (0.0, 0.0), args.paper_width, args.paper_height)
    except Exception as exc:
        raise SystemExit(f"[SVG] ERROR: {exc}") from exc

    total_points = sum(len(stroke["points"]) for stroke in strokes)
    robot_points = sum(len(stroke) for stroke in robot_strokes)
    print("[SVG] Input:", args.input)
    print("[SVG] Stroke count:", len(strokes))
    print("[SVG] SVG point count:", total_points)
    print("[SVG] Robot point count:", robot_points)
    print("[SVG] Page bounds:", config.get("svg_bounds"))
    print("[SVG] Drawable bounds:", config.get("svg_drawable_bounds"))
    for warning in config.get("svg_warnings", []):
        print("[SVG] Warning:", warning)
    print("[SVG] Fit drawable:", bool(args.fit_drawable))
    print("[SVG] Dry run:", bool(args.dry_run))

    if args.preview:
        stem = Path(args.input).stem
        preview_path = Path(args.output) / f"preview_{stem}.png"
        save_stroke_preview(strokes, preview_path, title=f"SVG stroke order: {stem}")
        print("[SVG] Preview:", preview_path)

    if args.export_json:
        export_strokes_json(args.export_json, strokes, robot_strokes)
        print("[SVG] JSON:", args.export_json)


if __name__ == "__main__":
    main()
