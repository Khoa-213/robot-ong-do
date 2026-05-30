from __future__ import annotations

from .font_outline import text_to_outline_polygons
from .skeletonize import polygons_to_robot_paths
from .svg_outline import svg_to_outline_polygons


def text_to_robot_paths(
    text: str,
    font_path: str,
    font_size: int = 200,
    resolution: float = 2.0,
    z_light: float = -0.5,
    z_heavy: float = -3.0,
    output_scale: float = 1.0,
    *,
    point_spacing: float = 1.0,
    min_branch_length: float = 2.0,
    smoothing_window: int = 3,
    simplify_tolerance: float = 0.05,
    max_points_per_stroke: int = 600,
) -> list[list[tuple[float, float, float]]]:
    """
    Convert text outline into centerline robot paths with Z-depth.
    Return only robot paths, not outline.
    """
    polygons = text_to_outline_polygons(text, font_path, font_size)
    return polygons_to_robot_paths(
        polygons,
        resolution,
        z_light,
        z_heavy,
        output_scale,
        point_spacing=point_spacing,
        min_branch_length=min_branch_length,
        smoothing_window=smoothing_window,
        simplify_tolerance=simplify_tolerance,
        max_points_per_stroke=max_points_per_stroke,
    )


def svg_outline_to_robot_paths(
    svg_path: str,
    resolution: float = 2.0,
    z_light: float = -0.5,
    z_heavy: float = -3.0,
    output_scale: float = 1.0,
    *,
    point_spacing: float = 1.0,
    min_branch_length: float = 2.0,
    smoothing_window: int = 3,
    simplify_tolerance: float = 0.05,
    max_points_per_stroke: int = 600,
) -> list[list[tuple[float, float, float]]]:
    """
    Convert SVG outline into centerline robot paths with Z-depth.
    Return only robot paths, not outline.
    """
    polygons = svg_to_outline_polygons(svg_path)
    return polygons_to_robot_paths(
        polygons,
        resolution,
        z_light,
        z_heavy,
        output_scale,
        point_spacing=point_spacing,
        min_branch_length=min_branch_length,
        smoothing_window=smoothing_window,
        simplify_tolerance=simplify_tolerance,
        max_points_per_stroke=max_points_per_stroke,
    )
