from typing import Any

from modules.paper_zone import CORNER_KEYS, get_paper_corners, point_inside_convex_polygon_xy
from modules.safety_check import validate_pose as validate_pose_workspace
from modules.safety_check import validate_measured_paper_poses

from src.services.config_service import get_config


def validate_pose(pose: list[float]) -> None:
    validate_pose_workspace(pose)


def validate_poses(poses: list[list[float]]) -> None:
    config = get_config()
    validate_measured_paper_poses(poses, config)


def validate_point_in_corners(corners: list[list[float]], point: list[float]) -> bool:
    if len(corners) != 4:
        raise ValueError("corners must have exactly 4 points")
    for index, corner in enumerate(corners):
        if len(corner) < 6:
            raise ValueError(f"corner[{index}] must have at least 6 values [x, y, z, rx, ry, rz]")

    if len(point) < 6:
        raise ValueError("point must have at least 6 values [x, y, z, rx, ry, rz]")

    polygon = [[float(c[0]), float(c[1])] for c in corners]
    xy_point = [float(point[0]), float(point[1])]
    return point_inside_convex_polygon_xy(xy_point, polygon)


def validate_start_end_in_corners(
    corners: list[list[float]],
    start_pose: list[float],
    end_pose: list[float],
) -> dict[str, bool]:
    return {
        "start_inside": validate_point_in_corners(corners, start_pose),
        "end_inside": validate_point_in_corners(corners, end_pose),
    }


def validate_start_end_in_current_corners(
    start_pose: list[float],
    end_pose: list[float],
) -> dict[str, Any]:
    config = get_config()
    corners_by_name = get_paper_corners(config)
    corners = [corners_by_name[key] for key in CORNER_KEYS]
    return {
        "corners": corners_by_name,
        "start_inside": validate_point_in_corners(corners, start_pose),
        "end_inside": validate_point_in_corners(corners, end_pose),
    }
