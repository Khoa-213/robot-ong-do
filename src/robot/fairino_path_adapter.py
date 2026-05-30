from __future__ import annotations

import json
from pathlib import Path
from math import hypot
from typing import Any

from modules.fairino_raw_controller import FairinoRawXmlRpcController


Point3 = tuple[float, float, float]
Pose = list[float]


def load_robot_paths(json_path: str) -> list[list[Point3]]:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    strokes: list[list[Point3]] = []
    for stroke in data:
        points = stroke.get("points", [])
        strokes.append([(float(point["x"]), float(point["y"]), float(point["z"])) for point in points])
    return [stroke for stroke in strokes if len(stroke) >= 2]


def robot_paths_to_poses(
    robot_paths: list[list[Point3]],
    paper_origin: dict[str, float],
    scale: float = 1.0,
    orientation: list[float] | tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> list[list[Pose]]:
    if not robot_paths:
        raise ValueError("robot_paths is empty")
    if len(orientation) != 3:
        raise ValueError("orientation must be [rx, ry, rz]")

    ox = float(paper_origin["x"])
    oy = float(paper_origin["y"])
    oz = float(paper_origin["z"])
    strokes: list[list[Pose]] = []
    for stroke in robot_paths:
        poses = []
        for x, y, z in stroke:
            poses.append(
                [
                    round(ox + float(x) * scale, 3),
                    round(oy + float(y) * scale, 3),
                    round(oz + float(z), 3),
                    round(float(orientation[0]), 3),
                    round(float(orientation[1]), 3),
                    round(float(orientation[2]), 3),
                ]
            )
        if len(poses) >= 2:
            strokes.append(poses)
    if not strokes:
        raise ValueError("No usable strokes after converting robot paths to poses")
    return strokes


def robot_paths_to_measured_paper_poses(
    robot_paths: list[list[Point3]],
    paper_config: dict[str, Any],
    margin_mm: float | None = None,
    orientation: list[float] | tuple[float, float, float] | None = None,
    preserve_aspect_ratio: bool = True,
    invert_y: bool = False,
    fit_width_mm: float | None = None,
    fit_height_mm: float | None = None,
) -> list[list[Pose]]:
    if not robot_paths:
        raise ValueError("robot_paths is empty")
    corners = paper_config.get("corners", {})
    required = ("top_left", "top_right", "bottom_left")
    if not all(name in corners for name in required):
        raise ValueError("paper_config.corners.top_left/top_right/bottom_left are required")

    top_left = [float(value) for value in corners["top_left"][:3]]
    top_right = [float(value) for value in corners["top_right"][:3]]
    bottom_left = [float(value) for value in corners["bottom_left"][:3]]
    orient = orientation if orientation is not None else paper_config.get("draw_orientation", corners["bottom_left"][3:6])
    if len(orient) != 3:
        raise ValueError("orientation must be [rx, ry, rz]")

    points = [point for stroke in robot_paths for point in stroke]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("robot_paths bounds must have positive width and height")

    paper_width = float(paper_config.get("width_mm", 1.0))
    paper_height = float(paper_config.get("height_mm", 1.0))
    margin = float(margin_mm if margin_mm is not None else paper_config.get("margin_mm", 0.0))
    drawable_width = max(1.0, paper_width - margin * 2.0)
    drawable_height = max(1.0, paper_height - margin * 2.0)
    target_width = min(drawable_width, float(fit_width_mm)) if fit_width_mm is not None and fit_width_mm > 0 else drawable_width
    target_height = min(drawable_height, float(fit_height_mm)) if fit_height_mm is not None and fit_height_mm > 0 else drawable_height

    if preserve_aspect_ratio:
        scale = min(target_width / width, target_height / height)
        fitted_width = width * scale
        fitted_height = height * scale
        offset_x = margin + (drawable_width - fitted_width) / 2.0
        offset_y = margin + (drawable_height - fitted_height) / 2.0
    else:
        scale = 1.0
        fitted_width = target_width
        fitted_height = target_height
        offset_x = margin
        offset_y = margin

    strokes: list[list[Pose]] = []
    for stroke in robot_paths:
        poses = []
        for x, y, z in stroke:
            if preserve_aspect_ratio:
                local_x = offset_x + (float(x) - min_x) * scale
                local_y = offset_y + (float(y) - min_y) * scale
            else:
                local_x = offset_x + (float(x) - min_x) / width * fitted_width
                local_y = offset_y + (float(y) - min_y) / height * fitted_height
            if invert_y:
                local_y = paper_height - local_y
            u = local_x / paper_width
            v = local_y / paper_height
            base = [
                top_left[axis]
                + u * (top_right[axis] - top_left[axis])
                + v * (bottom_left[axis] - top_left[axis])
                for axis in range(3)
            ]
            poses.append(
                [
                    round(base[0], 3),
                    round(base[1], 3),
                    round(base[2] + float(z), 3),
                    round(float(orient[0]), 3),
                    round(float(orient[1]), 3),
                    round(float(orient[2]), 3),
                ]
            )
        if len(poses) >= 2:
            strokes.append(poses)
    if not strokes:
        raise ValueError("No usable strokes after converting robot paths to measured paper poses")
    return strokes


def dry_run_print_pose_strokes(strokes: list[list[Pose]], safe_z: float = 20.0) -> None:
    for stroke_index, stroke in enumerate(strokes, start=1):
        first = stroke[0]
        print(f"[DRY_RUN] stroke {stroke_index}: safe start {[first[0], first[1], round(first[2] + safe_z, 3), *first[3:]]}")
        print(f"[DRY_RUN] stroke {stroke_index}: pen down {first}")
        for point_index, pose in enumerate(stroke, start=1):
            print(f"[DRY_RUN] stroke {stroke_index} point {point_index}/{len(stroke)} MoveL {pose}")
        print(f"[DRY_RUN] stroke {stroke_index}: pen up {[first[0], first[1], round(first[2] + safe_z, 3), *first[3:]]}")


def connect_nearby_pose_strokes(strokes: list[list[Pose]], max_gap_mm: float = 8.0) -> list[list[Pose]]:
    if max_gap_mm <= 0 or len(strokes) <= 1:
        return [[list(pose) for pose in stroke] for stroke in strokes]

    remaining = [[list(pose) for pose in stroke] for stroke in strokes if len(stroke) >= 2]
    connected: list[list[Pose]] = []
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed and remaining:
            changed = False
            best_index = -1
            best_reverse = False
            best_distance = max_gap_mm
            for index, stroke in enumerate(remaining):
                start_distance = _pose_xy_distance(current[-1], stroke[0])
                end_distance = _pose_xy_distance(current[-1], stroke[-1])
                if start_distance <= best_distance:
                    best_index = index
                    best_reverse = False
                    best_distance = start_distance
                if end_distance <= best_distance:
                    best_index = index
                    best_reverse = True
                    best_distance = end_distance
            if best_index >= 0:
                next_stroke = remaining.pop(best_index)
                if best_reverse:
                    next_stroke.reverse()
                current.extend(next_stroke)
                changed = True
        connected.append(current)
    return connected


def _pose_xy_distance(a: Pose, b: Pose) -> float:
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def execute_robot_path_json(
    json_path: str,
    paper_origin: dict[str, float],
    scale: float = 1.0,
    safe_z: float = 20.0,
    orientation: list[float] | tuple[float, float, float] = (0.0, 0.0, 0.0),
    robot_ip: str | None = None,
    tool: int = 0,
    user: int = 0,
    vel: float = 10.0,
    travel_vel: float | None = None,
    dry_run: bool = True,
    enable_move: bool = False,
    allow_raw_xmlrpc_motion: bool = False,
    controller: Any | None = None,
):
    robot_paths = load_robot_paths(json_path)
    pose_strokes = robot_paths_to_poses(robot_paths, paper_origin, scale, orientation)
    if dry_run:
        dry_run_print_pose_strokes(pose_strokes, safe_z)
        return pose_strokes

    if controller is None:
        if not robot_ip:
            raise ValueError("robot_ip is required when dry_run=False and controller is not provided")
        controller = FairinoRawXmlRpcController(robot_ip=robot_ip, tool=tool, user=user)
        owns_controller = True
    else:
        owns_controller = False

    try:
        if owns_controller:
            controller.connect()
        return controller.draw_pose_strokes(
            strokes=pose_strokes,
            vel=vel,
            travel_vel=travel_vel if travel_vel is not None else vel,
            travel_z_offset=safe_z,
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_xmlrpc_motion,
        )
    finally:
        if owns_controller:
            controller.disconnect()
