from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, sqrt
from typing import Any


Pose = list[float]
Stroke = list[Pose]


@dataclass(frozen=True)
class SmoothMotionConfig:
    point_spacing_mm: float = 1.0
    smoothing_tolerance_mm: float = 0.35
    min_point_distance_mm: float = 0.25
    moving_average_window: int = 3
    corner_slowdown_angle_deg: float = 55.0
    min_corner_speed_factor: float = 0.45
    max_points_per_stroke: int = 220


def config_from_robot_config(config: dict[str, Any]) -> SmoothMotionConfig:
    motion = config.get("motion_strategy", {})
    smooth = config.get("smooth_writing", {})
    return SmoothMotionConfig(
        point_spacing_mm=float(smooth.get("point_spacing_mm", motion.get("point_spacing_mm", motion.get("point_spacing", 1.0)))),
        smoothing_tolerance_mm=float(
            smooth.get("smoothing_tolerance", motion.get("smoothing_tolerance", motion.get("smoothing_tolerance_mm", 0.35)))
        ),
        min_point_distance_mm=float(smooth.get("min_point_distance_mm", motion.get("min_point_distance_mm", 0.25))),
        moving_average_window=int(smooth.get("moving_average_window", motion.get("moving_average_window", 3))),
        corner_slowdown_angle_deg=float(smooth.get("corner_slowdown_angle_deg", motion.get("corner_slowdown_angle_deg", 55.0))),
        min_corner_speed_factor=float(smooth.get("min_corner_speed_factor", motion.get("min_corner_speed_factor", 0.45))),
        max_points_per_stroke=int(smooth.get("max_points_per_stroke", motion.get("max_points_per_stroke", 220))),
    )


def plan_pose_strokes(strokes: list[Stroke], config: SmoothMotionConfig) -> list[Stroke]:
    planned: list[Stroke] = []
    for stroke in strokes:
        planned_stroke = plan_pose_stroke(stroke, config)
        if len(planned_stroke) >= 2:
            planned.append(planned_stroke)
    return planned


def plan_pose_stroke(stroke: Stroke, config: SmoothMotionConfig) -> Stroke:
    if len(stroke) < 2:
        return [list(pose) for pose in stroke]

    cleaned = remove_near_duplicate_poses(stroke, config.min_point_distance_mm)
    simplified = rdp_poses(cleaned, config.smoothing_tolerance_mm)
    smoothed = moving_average_poses(simplified, config.moving_average_window)
    resampled = resample_pose_path(smoothed, config.point_spacing_mm)
    if config.max_points_per_stroke > 0 and len(resampled) > config.max_points_per_stroke:
        resampled = downsample_keep_ends(resampled, config.max_points_per_stroke)
    return resampled


def stroke_speed_factors(stroke: Stroke, config: SmoothMotionConfig) -> list[float]:
    if len(stroke) < 3:
        return [1.0 for _ in stroke]

    factors = [1.0]
    for prev_pose, pose, next_pose in zip(stroke, stroke[1:], stroke[2:]):
        angle = turn_angle_deg(prev_pose, pose, next_pose)
        if angle >= config.corner_slowdown_angle_deg:
            ratio = min(angle / 160.0, 1.0)
            factor = 1.0 - ratio * (1.0 - config.min_corner_speed_factor)
            factors.append(max(config.min_corner_speed_factor, min(1.0, factor)))
        else:
            factors.append(1.0)
    factors.append(1.0)
    return factors


def remove_near_duplicate_poses(stroke: Stroke, min_distance_mm: float) -> Stroke:
    if not stroke:
        return []
    cleaned = [list(stroke[0])]
    for pose in stroke[1:]:
        if distance_xyz(cleaned[-1], pose) >= min_distance_mm:
            cleaned.append(list(pose))
    if len(cleaned) == 1 and len(stroke) > 1:
        cleaned.append(list(stroke[-1]))
    return cleaned


def rdp_poses(stroke: Stroke, tolerance_mm: float) -> Stroke:
    if tolerance_mm <= 0.0 or len(stroke) <= 2:
        return [list(pose) for pose in stroke]

    index = 0
    max_distance = 0.0
    for i in range(1, len(stroke) - 1):
        distance = perpendicular_distance_xyz(stroke[i], stroke[0], stroke[-1])
        if distance > max_distance:
            index = i
            max_distance = distance

    if max_distance > tolerance_mm:
        left = rdp_poses(stroke[: index + 1], tolerance_mm)
        right = rdp_poses(stroke[index:], tolerance_mm)
        return left[:-1] + right
    return [list(stroke[0]), list(stroke[-1])]


def moving_average_poses(stroke: Stroke, window: int) -> Stroke:
    if window < 3 or len(stroke) <= 2:
        return [list(pose) for pose in stroke]
    if window % 2 == 0:
        window += 1

    radius = window // 2
    smoothed = [list(stroke[0])]
    for index in range(1, len(stroke) - 1):
        start = max(0, index - radius)
        end = min(len(stroke), index + radius + 1)
        segment = stroke[start:end]
        pose = list(stroke[index])
        for axis in range(3):
            pose[axis] = round(sum(item[axis] for item in segment) / len(segment), 3)
        smoothed.append(pose)
    smoothed.append(list(stroke[-1]))
    return smoothed


def resample_pose_path(stroke: Stroke, spacing_mm: float) -> Stroke:
    if spacing_mm <= 0.0 or len(stroke) < 2:
        return [list(pose) for pose in stroke]

    resampled = [list(stroke[0])]
    carried = 0.0
    current = list(stroke[0])
    for target in stroke[1:]:
        segment_length = distance_xyz(current, target)
        if segment_length <= 1e-9:
            continue
        while carried + segment_length >= spacing_mm:
            remain = spacing_mm - carried
            t = remain / segment_length
            current = interpolate_pose(current, target, t)
            resampled.append(current)
            segment_length = distance_xyz(current, target)
            carried = 0.0
            if segment_length <= 1e-9:
                break
        carried += segment_length
        current = list(target)

    if distance_xyz(resampled[-1], stroke[-1]) > 1e-6:
        resampled.append(list(stroke[-1]))
    return resampled


def downsample_keep_ends(stroke: Stroke, max_points: int) -> Stroke:
    if max_points < 2 or len(stroke) <= max_points:
        return [list(pose) for pose in stroke]
    step = (len(stroke) - 1) / (max_points - 1)
    return [list(stroke[round(index * step)]) for index in range(max_points)]


def interpolate_pose(start: Pose, end: Pose, t: float) -> Pose:
    return [round(start[i] + (end[i] - start[i]) * t, 3) for i in range(6)]


def distance_xyz(a: Pose, b: Pose) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def perpendicular_distance_xyz(point: Pose, start: Pose, end: Pose) -> float:
    ax, ay, az = point[0] - start[0], point[1] - start[1], point[2] - start[2]
    bx, by, bz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
    base_len = sqrt(bx * bx + by * by + bz * bz)
    if base_len <= 1e-9:
        return distance_xyz(point, start)
    cross_x = ay * bz - az * by
    cross_y = az * bx - ax * bz
    cross_z = ax * by - ay * bx
    return sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z) / base_len


def turn_angle_deg(prev_pose: Pose, pose: Pose, next_pose: Pose) -> float:
    a = (prev_pose[0] - pose[0], prev_pose[1] - pose[1], prev_pose[2] - pose[2])
    b = (next_pose[0] - pose[0], next_pose[1] - pose[1], next_pose[2] - pose[2])
    len_a = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    len_b = sqrt(b[0] * b[0] + b[1] * b[1] + b[2] * b[2])
    if len_a <= 1e-9 or len_b <= 1e-9:
        return 0.0
    dot = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (len_a * len_b)
    dot = max(-1.0, min(1.0, dot))
    return degrees(acos(dot))
