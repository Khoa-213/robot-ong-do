from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any


Pose = list[float]
Stroke = list[Pose]


@dataclass(frozen=True)
class CalligraphyPressureConfig:
    enabled: bool = False
    z_safe: float = 80.0
    z_pen_touch: float = 20.0
    z_thin_offset: float = 0.3
    z_normal_offset: float = 0.0
    z_thick_offset: float = -0.4
    downward_dy_threshold: float = 0.3
    upward_dy_threshold: float = -0.3
    horizontal_dy_threshold: float = 0.2
    invert_y: bool = False
    pressure_smoothing: bool = True
    max_z_change_per_mm: float = 0.05


def config_from_robot_config(config: dict[str, Any]) -> CalligraphyPressureConfig:
    pressure = config.get("calligraphy_pressure", {})
    smooth = config.get("smooth_writing", {})
    return CalligraphyPressureConfig(
        enabled=bool(pressure.get("enabled", False)),
        z_safe=float(pressure.get("z_safe", smooth.get("safe_z", 80.0))),
        z_pen_touch=float(pressure.get("z_pen_touch", smooth.get("writing_z", 20.0))),
        z_thin_offset=float(pressure.get("z_thin_offset", 0.3)),
        z_normal_offset=float(pressure.get("z_normal_offset", 0.0)),
        z_thick_offset=float(pressure.get("z_thick_offset", -0.4)),
        downward_dy_threshold=float(pressure.get("downward_dy_threshold", 0.3)),
        upward_dy_threshold=float(pressure.get("upward_dy_threshold", -0.3)),
        horizontal_dy_threshold=float(pressure.get("horizontal_dy_threshold", 0.2)),
        invert_y=bool(pressure.get("invert_y", config.get("svg_pipeline", {}).get("invert_y", config.get("svg_pipeline", {}).get("flip_y", False)))),
        pressure_smoothing=bool(pressure.get("pressure_smoothing", True)),
        max_z_change_per_mm=float(pressure.get("max_z_change_per_mm", 0.05)),
    )


def apply_calligraphy_pressure_to_strokes(strokes: list[Stroke], config: CalligraphyPressureConfig) -> list[Stroke]:
    if not config.enabled:
        return [[list(pose) for pose in stroke] for stroke in strokes]
    return [apply_calligraphy_pressure_to_stroke(stroke, config) for stroke in strokes]


def apply_calligraphy_pressure_to_stroke(stroke: Stroke, config: CalligraphyPressureConfig) -> Stroke:
    if len(stroke) < 2:
        return [list(pose) for pose in stroke]

    target_z = _target_z_values(stroke, config)
    if config.pressure_smoothing:
        target_z = _smooth_values(target_z)
    limited_z = _limit_z_rate(stroke, target_z, config.max_z_change_per_mm)

    adjusted: Stroke = []
    for pose, z in zip(stroke, limited_z):
        next_pose = list(pose)
        next_pose[2] = round(z, 3)
        adjusted.append(next_pose)
    return adjusted


def _target_z_values(stroke: Stroke, config: CalligraphyPressureConfig) -> list[float]:
    values: list[float] = []
    for index, pose in enumerate(stroke):
        if index < len(stroke) - 1:
            nxt = stroke[index + 1]
            dx = float(nxt[0]) - float(pose[0])
            dy = float(nxt[1]) - float(pose[1])
        else:
            prev = stroke[index - 1]
            dx = float(pose[0]) - float(prev[0])
            dy = float(pose[1]) - float(prev[1])
        if config.invert_y:
            dy = -dy
        values.append(float(pose[2]) + _offset_for_delta(dx, dy, config))
    return values


def _offset_for_delta(dx: float, dy: float, config: CalligraphyPressureConfig) -> float:
    if dy > config.downward_dy_threshold:
        return config.z_thick_offset
    if dy < config.upward_dy_threshold:
        return config.z_thin_offset
    if abs(dy) <= config.horizontal_dy_threshold and abs(dx) > abs(dy):
        return config.z_normal_offset
    return config.z_normal_offset


def _smooth_values(values: list[float]) -> list[float]:
    if len(values) <= 2:
        return list(values)
    smoothed = [values[0]]
    for prev_value, value, next_value in zip(values, values[1:], values[2:]):
        smoothed.append((prev_value + value + next_value) / 3.0)
    smoothed.append(values[-1])
    return smoothed


def _limit_z_rate(stroke: Stroke, values: list[float], max_z_change_per_mm: float) -> list[float]:
    if max_z_change_per_mm <= 0.0 or len(values) <= 1:
        return list(values)
    limited = [values[0]]
    for prev_pose, pose, target_z in zip(stroke, stroke[1:], values[1:]):
        distance = hypot(float(pose[0]) - float(prev_pose[0]), float(pose[1]) - float(prev_pose[1]))
        max_delta = max_z_change_per_mm * max(distance, 1e-6)
        delta = target_z - limited[-1]
        if delta > max_delta:
            target_z = limited[-1] + max_delta
        elif delta < -max_delta:
            target_z = limited[-1] - max_delta
        limited.append(target_z)
    return limited
