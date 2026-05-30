from __future__ import annotations

MAX_Z_STEP_PER_POINT = 0.2
MAX_ABS_Z_DEPTH = 10.0


def map_radius_to_z(
    radius: float,
    min_radius: float,
    max_radius: float,
    z_light: float = -0.5,
    z_heavy: float = -3.0,
) -> float:
    """
    Map radius to Z-depth. Small radius -> light pressure, large radius -> heavy pressure.
    """
    if z_heavy < -MAX_ABS_Z_DEPTH:
        raise ValueError(f"z_heavy={z_heavy} is too deep; limit is {-MAX_ABS_Z_DEPTH}mm")
    if max_radius <= min_radius:
        return float(z_light)
    ratio = (float(radius) - float(min_radius)) / (float(max_radius) - float(min_radius))
    ratio = max(0.0, min(1.0, ratio))
    return float(z_light) + ratio * (float(z_heavy) - float(z_light))


def smooth_z_values(values: list[float], window: int = 5) -> list[float]:
    if window < 3 or len(values) < 3:
        return list(values)
    if window % 2 == 0:
        window += 1
    radius = window // 2
    smoothed = []
    for index, value in enumerate(values):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def enforce_max_z_step(
    stroke: list[tuple[float, float, float]],
    max_step: float = MAX_Z_STEP_PER_POINT,
) -> list[tuple[float, float, float]]:
    if len(stroke) < 2 or max_step <= 0:
        return stroke
    out = [stroke[0]]
    for start, end in zip(stroke, stroke[1:]):
        dz = end[2] - start[2]
        steps = max(1, int(abs(dz) / max_step + 0.999))
        for index in range(1, steps + 1):
            t = index / steps
            out.append(
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                    start[2] + dz * t,
                )
            )
    return out
