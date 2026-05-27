from math import cos, pi, sin, sqrt
from typing import Any


CORNER_KEYS = ("top_left", "top_right", "bottom_right", "bottom_left")


def get_paper_corners(config: dict[str, Any]) -> dict[str, list[float]]:
    paper = config["paper"]
    corners = paper.get("corners")
    if not isinstance(corners, dict):
        raise ValueError("paper.corners must be configured")

    missing = [key for key in CORNER_KEYS if key not in corners]
    if missing:
        raise ValueError(f"paper.corners missing keys: {missing}")

    return {key: list(corners[key]) for key in CORNER_KEYS}


def distance_xy(a: list[float], b: list[float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def paper_size_from_corners(corners: dict[str, list[float]]) -> tuple[float, float]:
    top_width = distance_xy(corners["top_left"], corners["top_right"])
    bottom_width = distance_xy(corners["bottom_left"], corners["bottom_right"])
    left_height = distance_xy(corners["top_left"], corners["bottom_left"])
    right_height = distance_xy(corners["top_right"], corners["bottom_right"])
    return (top_width + bottom_width) / 2.0, (left_height + right_height) / 2.0


def normalized_margin(config: dict[str, Any]) -> tuple[float, float]:
    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)
    margin = float(config["paper"].get("margin_mm", 0.0))
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Paper width/height from corners must be positive")
    return margin / width, margin / height


def bilinear_xyz(corners: dict[str, list[float]], u: float, v: float) -> list[float]:
    tl = corners["top_left"]
    tr = corners["top_right"]
    br = corners["bottom_right"]
    bl = corners["bottom_left"]
    weights = (
        (1.0 - u) * (1.0 - v),
        u * (1.0 - v),
        u * v,
        (1.0 - u) * v,
    )
    points = (tl, tr, br, bl)
    return [
        sum(weight * point[index] for weight, point in zip(weights, points))
        for index in range(3)
    ]


def build_pose_in_paper(config: dict[str, Any], u: float, v: float) -> list[float]:
    margin_u, margin_v = normalized_margin(config)
    if not (margin_u <= u <= 1.0 - margin_u):
        raise ValueError(f"u={u} is outside paper safe margin [{margin_u}, {1.0 - margin_u}]")
    if not (margin_v <= v <= 1.0 - margin_v):
        raise ValueError(f"v={v} is outside paper safe margin [{margin_v}, {1.0 - margin_v}]")

    corners = get_paper_corners(config)
    x, y, _paper_z = bilinear_xyz(corners, u, v)
    z = float(config["paper"]["paper_z"]) + float(config["z_safety"]["z_lift_offset"])
    rx, ry, rz = config["paper"]["draw_orientation"]
    return [round(x, 3), round(y, 3), round(z, 3), float(rx), float(ry), float(rz)]


def build_line_demo_poses(config: dict[str, Any]) -> tuple[list[float], list[float]]:
    demo = config["paper_line_demo"]
    start_u = float(demo["start_u"])
    end_u = float(demo["end_u"])
    line_v = float(demo["line_v"])
    return (
        build_pose_in_paper(config, start_u, line_v),
        build_pose_in_paper(config, end_u, line_v),
    )


def build_circle_demo_poses(config: dict[str, Any]) -> list[list[float]]:
    demo = config["circle_demo"]
    center_u = float(demo.get("center_u", 0.5))
    center_v = float(demo.get("center_v", 0.5))
    radius_u = float(demo.get("radius_u", 0.15))
    radius_v = float(demo.get("radius_v", radius_u))
    segments = int(demo.get("segments", 24))

    if segments < 8:
        raise ValueError("circle_demo.segments must be at least 8")

    poses = []
    for index in range(segments + 1):
        angle = 2.0 * pi * index / segments
        u = center_u + radius_u * cos(angle)
        v = center_v + radius_v * sin(angle)
        poses.append(build_pose_in_paper(config, u, v))
    return poses


def build_lifted_corner_pose(config: dict[str, Any], corner_name: str) -> list[float]:
    corners = get_paper_corners(config)
    if corner_name not in corners:
        raise ValueError(f"Unknown paper corner: {corner_name}")

    corner = corners[corner_name]
    z = float(config["paper"]["paper_z"]) + float(config["z_safety"]["z_lift_offset"])
    rx, ry, rz = config["paper"]["draw_orientation"]
    return [round(float(corner[0]), 3), round(float(corner[1]), 3), round(z, 3), float(rx), float(ry), float(rz)]


def build_measured_corner_pose(config: dict[str, Any], corner_name: str) -> list[float]:
    corners = get_paper_corners(config)
    if corner_name not in corners:
        raise ValueError(f"Unknown paper corner: {corner_name}")

    corner = corners[corner_name]
    if len(corner) >= 6:
        return [
            round(float(corner[0]), 3),
            round(float(corner[1]), 3),
            round(float(corner[2]), 3),
            float(corner[3]),
            float(corner[4]),
            float(corner[5]),
        ]

    z = float(config["paper"]["paper_z"]) + float(config["z_safety"]["z_lift_offset"])
    rx, ry, rz = config["paper"]["draw_orientation"]
    return [round(float(corner[0]), 3), round(float(corner[1]), 3), round(z, 3), float(rx), float(ry), float(rz)]


def build_measured_corner_test_poses(config: dict[str, Any]) -> list[list[float]]:
    return [build_measured_corner_pose(config, corner_name) for corner_name in CORNER_KEYS]


def point_inside_convex_polygon_xy(point: list[float], polygon: list[list[float]]) -> bool:
    x, y = point[0], point[1]
    sign = 0
    for index, current in enumerate(polygon):
        nxt = polygon[(index + 1) % len(polygon)]
        cross = (nxt[0] - current[0]) * (y - current[1]) - (nxt[1] - current[1]) * (x - current[0])
        if abs(cross) < 1e-9:
            continue
        current_sign = 1 if cross > 0 else -1
        if sign == 0:
            sign = current_sign
        elif sign != current_sign:
            return False
    return True


def validate_pose_inside_paper_corners(pose: list[float], config: dict[str, Any]) -> None:
    corners = get_paper_corners(config)
    polygon = [corners[key] for key in CORNER_KEYS]
    if not point_inside_convex_polygon_xy(pose, polygon):
        raise ValueError(f"Pose XY ({pose[0]}, {pose[1]}) is outside measured paper polygon")
