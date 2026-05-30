import socket
from typing import Any

from modules.fairino_controller import FairinoController
from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import build_lifted_corner_pose
from modules.safety_check import validate_measured_paper_poses, validate_pose_workspace
from modules.shape_api import build_shape_pose_strokes

from src.services.config_service import get_config


def check_ports(robot_ip: str, ports: list[int]) -> dict[str, Any]:
    results: dict[str, Any] = {"robot_ip": robot_ip, "ports": {}}
    for port in ports:
        key = str(port)
        try:
            with socket.create_connection((robot_ip, port), timeout=2.0):
                results["ports"][key] = True
        except OSError as exc:
            results["ports"][key] = False
            results.setdefault("errors", {})[key] = str(exc)
    return results


def get_robot_status() -> dict[str, Any]:
    config = get_config()
    policy = config.get("connection_policy", {})
    controller = FairinoController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
        allow_xmlrpc_motion_when_cnde_unavailable=bool(
            policy.get("allow_xmlrpc_motion_when_cnde_unavailable", False)
        ),
    )

    status: dict[str, Any] = {
        "robot_ip": config["robot_ip"],
        "connected": False,
        "xmlrpc_ok": False,
        "tcp_pose": None,
        "error_code": None,
    }

    try:
        status["connected"] = controller.connect()
        status["xmlrpc_ok"] = controller.check_xmlrpc_status()
        if controller.robot is not None and hasattr(controller.robot, "GetActualTCPPose"):
            status["tcp_pose"] = controller.robot.GetActualTCPPose(0)
        if controller.robot is not None and hasattr(controller.robot, "GetRobotErrorCode"):
            status["error_code"] = controller.robot.GetRobotErrorCode()
    finally:
        controller.disconnect()
    return status


def move_l(pose: list[float], vel: float | None) -> dict[str, Any]:
    config = get_config()
    policy = config.get("connection_policy", {})
    controller = FairinoController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
        allow_xmlrpc_motion_when_cnde_unavailable=bool(
            policy.get("allow_xmlrpc_motion_when_cnde_unavailable", False)
        ),
    )

    enable_move = bool(config.get("enable_robot_move", False))
    velocity = float(vel) if vel is not None else float(config.get("default_vel", 10))

    try:
        controller.connect()
        result = controller.move_l(pose, vel=velocity, enable_move=enable_move)
    finally:
        controller.disconnect()

    return {"enable_move": enable_move, "result": result}


def draw_shape(shape_name: str, vel: float | None) -> dict[str, Any]:
    config = get_config()
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})
    shape_config = config.get("shape_demo", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})

    strokes = build_shape_pose_strokes(config, shape_name)
    poses = [pose for stroke in strokes for pose in stroke]
    start_pose = before_draw.get("start_pose")
    return_pose = None
    return_pose_uses_paper_corner = False
    if after_draw.get("return_pose") is not None:
        return_pose = after_draw["return_pose"]
    elif after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))
        return_pose_uses_paper_corner = True

    enable_move = bool(config.get("enable_robot_move", False))
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))
    velocity = float(vel) if vel is not None else float(shape_config.get("vel", config.get("default_vel", 10)))

    validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    if return_pose is not None:
        if return_pose_uses_paper_corner:
            validate_measured_paper_poses([return_pose], config)
        else:
            validate_pose_workspace(return_pose, config["robot_workspace"])

    controller = FairinoRawXmlRpcController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
    )

    try:
        controller.connect()
        results = controller.draw_pose_strokes(
            strokes=strokes,
            start_pose=start_pose,
            return_pose=return_pose,
            vel=velocity,
            travel_vel=float(shape_config.get("travel_vel", config.get("default_vel", 10))),
            travel_z_offset=float(config.get("text_demo", {}).get("travel_z_offset", 20.0)),
            start_vel=float(before_draw.get("start_vel", config.get("default_vel", 10))),
            return_vel=float(after_draw.get("return_vel", config.get("default_vel", 10))),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()

    return {
        "shape": shape_name,
        "pose_count": len(poses),
        "enable_move": enable_move,
        "allow_raw_xmlrpc_motion": allow_raw_motion,
        "result": results,
    }


def draw_paper_corners(corners: list[list[float]], vel: float | None) -> dict[str, Any]:
    if len(corners) != 4:
        raise ValueError("corners must have exactly 4 points")

    config = get_config()
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})

    poses = [list(corner) for corner in corners]
    for index, pose in enumerate(poses):
        if len(pose) < 6:
            raise ValueError(f"corner[{index}] must have 6 values [x, y, z, rx, ry, rz]")

    for pose in poses:
        validate_pose_workspace(pose, config["robot_workspace"])

    enable_move = bool(config.get("enable_robot_move", False))
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))
    velocity = float(vel) if vel is not None else float(config.get("default_vel", 10))

    controller = FairinoRawXmlRpcController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
    )

    try:
        controller.connect()
        results = controller.draw_polyline_air(
            poses=poses,
            vel=velocity,
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()

    return {
        "pose_count": len(poses),
        "enable_move": enable_move,
        "allow_raw_xmlrpc_motion": allow_raw_motion,
        "result": results,
    }
