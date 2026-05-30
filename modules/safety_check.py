from numbers import Real
from typing import Any

from modules.paper_zone import validate_pose_inside_paper_corners


SAFE_MIN_Z = 200.0
SAFE_MAX_Z = 900.0
SAFE_X_MIN = -500.0
SAFE_X_MAX = 500.0
SAFE_Y_MIN = -600.0
SAFE_Y_MAX = 600.0


def validate_pose(pose: list[float]) -> None:
    default_workspace = {
        "x_min": SAFE_X_MIN,
        "x_max": SAFE_X_MAX,
        "y_min": SAFE_Y_MIN,
        "y_max": SAFE_Y_MAX,
        "z_min": SAFE_MIN_Z,
        "z_max": SAFE_MAX_Z,
    }
    validate_pose_workspace(pose, default_workspace)


def validate_line(start_pose: list[float], end_pose: list[float]) -> None:
    validate_pose(start_pose)
    validate_pose(end_pose)


def _ensure_pose_format(pose: list[float]) -> None:
    if not isinstance(pose, list):
        raise ValueError(f"Pose must be a list, got {type(pose).__name__}")
    if len(pose) != 6:
        raise ValueError(f"Pose must have exactly 6 values [x, y, z, rx, ry, rz], got {len(pose)}")
    for index, value in enumerate(pose[:3]):
        if not isinstance(value, Real):
            raise ValueError(f"Pose value at index {index} must be numeric, got {value!r}")


def validate_pose_workspace(pose: list[float], workspace: dict[str, Any]) -> None:
    _ensure_pose_format(pose)
    x, y, z = pose[:3]

    checks = [
        ("x", x, workspace["x_min"], workspace["x_max"]),
        ("y", y, workspace["y_min"], workspace["y_max"]),
        ("z", z, workspace["z_min"], workspace["z_max"]),
    ]
    for axis, value, min_value, max_value in checks:
        if value < min_value or value > max_value:
            raise ValueError(
                f"Pose {axis}={value} is outside robot workspace "
                f"[{min_value}, {max_value}]"
            )


def validate_pose_above_min_z(pose: list[float], z_min_allowed: float) -> None:
    _ensure_pose_format(pose)
    z = pose[2]
    if z < z_min_allowed:
        raise ValueError(f"Pose z={z} is below safe minimum z={z_min_allowed}")


def validate_point_inside_paper(x: float, y: float, paper: dict[str, Any]) -> None:
    if not paper.get("enabled", False):
        return

    origin_x = float(paper["origin_x"])
    origin_y = float(paper["origin_y"])
    width = float(paper["width_mm"])
    height = float(paper["height_mm"])
    margin = float(paper["margin_mm"])

    x_min = origin_x + margin
    x_max = origin_x + width - margin
    y_min = origin_y + margin
    y_max = origin_y + height - margin

    if x < x_min or x > x_max or y < y_min or y > y_max:
        raise ValueError(
            f"Point ({x}, {y}) is outside paper safezone "
            f"x=[{x_min}, {x_max}], y=[{y_min}, {y_max}]"
        )


def validate_line_inside_paper(
    start_pose: list[float],
    end_pose: list[float],
    paper: dict[str, Any],
) -> None:
    validate_point_inside_paper(start_pose[0], start_pose[1], paper)
    validate_point_inside_paper(end_pose[0], end_pose[1], paper)


def validate_line_demo(
    start_pose: list[float],
    end_pose: list[float],
    config: dict[str, Any],
) -> None:
    workspace = config["robot_workspace"]
    paper = config["paper"]
    z_safety = config["z_safety"]

    validate_pose_workspace(start_pose, workspace)
    validate_pose_workspace(end_pose, workspace)

    if paper.get("enabled", False):
        z_min_allowed = float(paper["paper_z"]) + float(z_safety["z_min_allowed_offset"])
        expected_lift_z = float(paper["paper_z"]) + float(z_safety["z_lift_offset"])

        validate_line_inside_paper(start_pose, end_pose, paper)
        validate_pose_above_min_z(start_pose, z_min_allowed)
        validate_pose_above_min_z(end_pose, z_min_allowed)

        for name, pose in [("start_pose", start_pose), ("end_pose", end_pose)]:
            if abs(float(pose[2]) - expected_lift_z) > 0.001:
                raise ValueError(
                    f"{name} z={pose[2]} must equal paper_z + z_lift_offset "
                    f"({expected_lift_z}) for the air-line demo"
                )


def validate_measured_paper_line_demo(
    start_pose: list[float],
    end_pose: list[float],
    config: dict[str, Any],
) -> None:
    workspace = config["robot_workspace"]
    paper = config["paper"]
    z_safety = config["z_safety"]

    validate_pose_workspace(start_pose, workspace)
    validate_pose_workspace(end_pose, workspace)

    z_min_allowed = float(paper["paper_z"]) + float(z_safety["z_min_allowed_offset"])
    expected_lift_z = float(paper["paper_z"]) + float(z_safety["z_lift_offset"])

    validate_pose_above_min_z(start_pose, z_min_allowed)
    validate_pose_above_min_z(end_pose, z_min_allowed)
    validate_pose_inside_paper_corners(start_pose, config)
    validate_pose_inside_paper_corners(end_pose, config)

    for name, pose in [("start_pose", start_pose), ("end_pose", end_pose)]:
        if abs(float(pose[2]) - expected_lift_z) > 0.001:
            raise ValueError(
                f"{name} z={pose[2]} must equal paper_z + z_lift_offset "
                f"({expected_lift_z}) for the measured-paper air-line demo"
            )


def validate_measured_paper_poses(
    poses: list[list[float]],
    config: dict[str, Any],
) -> None:
    if not poses:
        raise ValueError("Pose list must not be empty")

    workspace = config["robot_workspace"]
    paper = config["paper"]
    z_safety = config["z_safety"]
    z_min_allowed = float(paper["paper_z"]) + float(z_safety["z_min_allowed_offset"])
    expected_lift_z = float(paper["paper_z"]) + float(z_safety["z_lift_offset"])
    pressure = config.get("calligraphy_pressure", {})
    pressure_enabled = bool(pressure.get("enabled", False))
    z_max_allowed = expected_lift_z
    if pressure_enabled:
        z_max_allowed = expected_lift_z + max(
            float(z_safety.get("z_write_light_offset", 0.0)),
            float(pressure.get("z_thin_offset", 0.0)),
            0.0,
        )

    for index, pose in enumerate(poses):
        validate_pose_workspace(pose, workspace)
        validate_pose_above_min_z(pose, z_min_allowed)
        validate_pose_inside_paper_corners(pose, config)
        if pressure_enabled:
            if float(pose[2]) > z_max_allowed + 0.001:
                raise ValueError(
                    f"pose[{index}] z={pose[2]} must be <= paper_z + allowed light/pressure offset "
                    f"({round(z_max_allowed, 3)})"
                )
            continue
        if abs(float(pose[2]) - expected_lift_z) > 0.001:
            raise ValueError(
                f"pose[{index}] z={pose[2]} must equal paper_z + z_lift_offset "
                f"({expected_lift_z})"
            )
