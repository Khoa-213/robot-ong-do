from __future__ import annotations

import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from skimage.morphology import medial_axis

from .errors import RobotPathError, SkeletonExtractionError, ZDepthError
from .graph_trace import trace_skeleton_pixels
from .path_smoothing import downsample_keep_ends, moving_average_stroke, order_strokes_nearest, rdp_stroke, resample_stroke
from .rasterize import pixel_to_world, rasterize_polygons
from .z_depth import enforce_max_z_step, map_radius_to_z, smooth_z_values


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
) -> list[list[tuple[float, float, float]]]:
    mask, info = rasterize_polygons(polygons, resolution)
    if not np.any(mask):
        raise SkeletonExtractionError("Rasterized outline is empty")

    skeleton, distance = medial_axis(mask, return_distance=True)
    if not np.any(skeleton):
        raise SkeletonExtractionError("Medial axis is empty")

    min_branch_px = max(2.0, float(min_branch_length) * info.scale)
    pixel_paths = trace_skeleton_pixels(skeleton, min_branch_px)
    radii = [float(distance[row, col]) / info.scale for row, col in np.argwhere(skeleton)]
    if not radii:
        raise SkeletonExtractionError("Skeleton has no radius samples")
    min_radius = max(0.0, min(radii))
    max_radius = max(radii)

    strokes: list[list[tuple[float, float, float]]] = []
    for pixel_path in pixel_paths:
        raw: list[tuple[float, float, float]] = []
        z_values = [
            map_radius_to_z(float(distance[row, col]) / info.scale, min_radius, max_radius, z_light, z_heavy)
            for row, col in pixel_path
        ]
        z_values = smooth_z_values(z_values)
        for (row, col), z in zip(pixel_path, z_values):
            x, y = pixel_to_world(row, col, info)
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
