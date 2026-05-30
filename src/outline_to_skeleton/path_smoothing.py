from __future__ import annotations

from math import hypot


Point3 = tuple[float, float, float]


def order_strokes_nearest(strokes: list[list[Point3]]) -> list[list[Point3]]:
    remaining = [list(stroke) for stroke in strokes if len(stroke) >= 2]
    ordered: list[list[Point3]] = []
    cursor: Point3 | None = None
    while remaining:
        if cursor is None:
            index = min(range(len(remaining)), key=lambda item: (min(remaining[item][0][1], remaining[item][-1][1]), min(remaining[item][0][0], remaining[item][-1][0])))
            stroke = remaining.pop(index)
            if (stroke[-1][1], stroke[-1][0]) < (stroke[0][1], stroke[0][0]):
                stroke.reverse()
        else:
            options = []
            for index, stroke in enumerate(remaining):
                options.append((distance_xy(cursor, stroke[0]), index, False))
                options.append((distance_xy(cursor, stroke[-1]), index, True))
            _, index, reverse = min(options, key=lambda item: item[0])
            stroke = remaining.pop(index)
            if reverse:
                stroke.reverse()
        ordered.append(stroke)
        cursor = stroke[-1]
    return ordered


def moving_average_stroke(stroke: list[Point3], window: int = 3) -> list[Point3]:
    if window < 3 or len(stroke) <= 2:
        return list(stroke)
    if window % 2 == 0:
        window += 1
    radius = window // 2
    out = [stroke[0]]
    for index in range(1, len(stroke) - 1):
        start = max(0, index - radius)
        end = min(len(stroke), index + radius + 1)
        segment = stroke[start:end]
        out.append(tuple(sum(point[axis] for point in segment) / len(segment) for axis in range(3)))
    out.append(stroke[-1])
    return out


def resample_stroke(stroke: list[Point3], spacing: float = 1.0) -> list[Point3]:
    if spacing <= 0 or len(stroke) < 2:
        return list(stroke)
    out = [stroke[0]]
    current = stroke[0]
    carried = 0.0
    for target in stroke[1:]:
        segment_length = distance_xy(current, target)
        if segment_length <= 1e-9:
            continue
        while carried + segment_length >= spacing:
            remain = spacing - carried
            t = remain / segment_length
            current = interpolate(current, target, t)
            out.append(current)
            segment_length = distance_xy(current, target)
            carried = 0.0
            if segment_length <= 1e-9:
                break
        carried += segment_length
        current = target
    if distance_xy(out[-1], stroke[-1]) > 1e-6:
        out.append(stroke[-1])
    return out


def rdp_stroke(stroke: list[Point3], tolerance: float = 0.05) -> list[Point3]:
    if tolerance <= 0 or len(stroke) <= 2:
        return list(stroke)
    index = 0
    max_distance = 0.0
    for i in range(1, len(stroke) - 1):
        value = perpendicular_distance_xy(stroke[i], stroke[0], stroke[-1])
        if value > max_distance:
            index = i
            max_distance = value
    if max_distance > tolerance:
        return rdp_stroke(stroke[: index + 1], tolerance)[:-1] + rdp_stroke(stroke[index:], tolerance)
    return [stroke[0], stroke[-1]]


def downsample_keep_ends(stroke: list[Point3], max_points: int) -> list[Point3]:
    if max_points <= 1 or len(stroke) <= max_points:
        return list(stroke)
    step = (len(stroke) - 1) / (max_points - 1)
    return [stroke[round(index * step)] for index in range(max_points)]


def distance_xy(a: Point3, b: Point3) -> float:
    return hypot(b[0] - a[0], b[1] - a[1])


def interpolate(a: Point3, b: Point3, t: float) -> Point3:
    return tuple(a[axis] + (b[axis] - a[axis]) * t for axis in range(3))  # type: ignore[return-value]


def perpendicular_distance_xy(point: Point3, start: Point3, end: Point3) -> float:
    base = distance_xy(start, end)
    if base <= 1e-9:
        return distance_xy(point, start)
    return abs((end[0] - start[0]) * (start[1] - point[1]) - (start[0] - point[0]) * (end[1] - start[1])) / base
