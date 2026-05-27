from math import cos, pi, sin
from pathlib import Path
from typing import Any

from modules.paper_zone import build_pose_in_paper
from modules.svg_trajectory import build_svg_poses


SHAPE_NAMES = (
    "line_horizontal",
    "line_vertical",
    "line_diagonal_down",
    "line_diagonal_up",
    "circle",
    "square",
    "rectangle",
    "triangle",
    "tam",
    "tam1",
)


def list_shapes() -> tuple[str, ...]:
    return SHAPE_NAMES


def build_shape_poses(config: dict[str, Any], shape_name: str) -> list[list[float]]:
    shape_name = shape_name.strip().lower()
    shape_config = config.get("shape_demo", {})

    if shape_name == "line_horizontal":
        return _build_line(config, [(0.25, 0.5), (0.75, 0.5)])
    if shape_name == "line_vertical":
        return _build_line(config, [(0.5, 0.25), (0.5, 0.75)])
    if shape_name == "line_diagonal_down":
        return _build_line(config, [(0.25, 0.25), (0.75, 0.75)])
    if shape_name == "line_diagonal_up":
        return _build_line(config, [(0.25, 0.75), (0.75, 0.25)])
    if shape_name == "circle":
        return _build_circle(config, shape_config)
    if shape_name == "square":
        return _build_square(config, shape_config)
    if shape_name == "rectangle":
        return _build_rectangle(config, shape_config)
    if shape_name == "triangle":
        return _build_triangle(config, shape_config)
    if shape_name in ("tam", "tam_old"):
        return _build_configured_tam_svg(config)
    if shape_name in ("tam1", "tam_new"):
        return _build_svg_file(config, "assets/svg/tam1.svg")

    raise ValueError(f"Unknown shape '{shape_name}'. Available: {', '.join(SHAPE_NAMES)}")


def _build_line(config: dict[str, Any], points_uv: list[tuple[float, float]]) -> list[list[float]]:
    return [build_pose_in_paper(config, u, v) for u, v in points_uv]


def _build_circle(config: dict[str, Any], shape_config: dict[str, Any]) -> list[list[float]]:
    center_u = float(shape_config.get("center_u", 0.5))
    center_v = float(shape_config.get("center_v", 0.5))
    radius_u = float(shape_config.get("radius_u", 0.16))
    radius_v = float(shape_config.get("radius_v", radius_u))
    segments = int(shape_config.get("segments", 24))

    if segments < 8:
        raise ValueError("shape_demo.segments must be at least 8 for circle")

    points = []
    for index in range(segments + 1):
        angle = 2.0 * pi * index / segments
        points.append((center_u + radius_u * cos(angle), center_v + radius_v * sin(angle)))
    return _build_line(config, points)


def _build_square(config: dict[str, Any], shape_config: dict[str, Any]) -> list[list[float]]:
    center_u = float(shape_config.get("center_u", 0.5))
    center_v = float(shape_config.get("center_v", 0.5))
    half_u = float(shape_config.get("square_half_u", 0.16))
    half_v = float(shape_config.get("square_half_v", 0.16))
    points = [
        (center_u - half_u, center_v - half_v),
        (center_u + half_u, center_v - half_v),
        (center_u + half_u, center_v + half_v),
        (center_u - half_u, center_v + half_v),
        (center_u - half_u, center_v - half_v),
    ]
    return _build_line(config, points)


def _build_rectangle(config: dict[str, Any], shape_config: dict[str, Any]) -> list[list[float]]:
    center_u = float(shape_config.get("center_u", 0.5))
    center_v = float(shape_config.get("center_v", 0.5))
    half_u = float(shape_config.get("square_half_u", 0.2))
    half_v = float(shape_config.get("square_half_v", 0.12))
    points = [
        (center_u - half_u, center_v - half_v),
        (center_u + half_u, center_v - half_v),
        (center_u + half_u, center_v + half_v),
        (center_u - half_u, center_v + half_v),
        (center_u - half_u, center_v - half_v),
    ]
    return _build_line(config, points)


def _build_triangle(config: dict[str, Any], shape_config: dict[str, Any]) -> list[list[float]]:
    center_u = float(shape_config.get("center_u", 0.5))
    center_v = float(shape_config.get("center_v", 0.5))
    radius_u = float(shape_config.get("triangle_radius_u", 0.18))
    radius_v = float(shape_config.get("triangle_radius_v", 0.18))
    points = []
    for angle in (-pi / 2.0, 7.0 * pi / 6.0, 11.0 * pi / 6.0, -pi / 2.0):
        points.append((center_u + radius_u * cos(angle), center_v + radius_v * sin(angle)))
    return _build_line(config, points)


def _build_configured_tam_svg(config: dict[str, Any]) -> list[list[float]]:
    svg_demo = config["svg_demo"]
    return _build_svg_file(config, str(svg_demo.get("svg_path", "assets/svg/tam.svg")))


def _build_svg_file(config: dict[str, Any], relative_path: str) -> list[list[float]]:
    project_root = Path(__file__).resolve().parents[1]
    return build_svg_poses(config, project_root / relative_path)
