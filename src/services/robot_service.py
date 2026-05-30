import json
import socket
from pathlib import Path
from typing import Any

from modules.fairino_controller import FairinoController
from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import (
    build_circle_demo_poses,
    build_lifted_corner_pose,
    build_line_demo_poses,
    build_pose_in_paper,
    get_paper_corners,
    paper_size_from_corners,
)
from modules.safety_check import validate_measured_paper_poses, validate_pose_workspace
from modules.shape_api import build_shape_pose_strokes
from modules.svg_trajectory import build_svg_pose_strokes, fit_points_to_uv, sample_svg_strokes
from modules.text_trajectory import build_text_pose_strokes
from modules.trajectory_planner import config_from_robot_config, plan_pose_strokes

from src.services.config_service import get_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORD_LIBRARY_PATH = PROJECT_ROOT / "config" / "word_library.json"


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


def get_raw_robot_status() -> dict[str, Any]:
    config = get_config()
    status: dict[str, Any] = {
        "robot_ip": config["robot_ip"],
        "connected": False,
        "controller_ip": None,
        "tcp_pose": None,
        "error_code": None,
    }

    controller = _raw_controller(config)
    try:
        status["connected"] = controller.connect()
        if status["connected"]:
            status["controller_ip"] = _safe_raw_call(controller.get_controller_ip)
            status["tcp_pose"] = _safe_raw_call(controller.get_actual_tcp_pose)
            status["error_code"] = _safe_raw_call(controller.get_robot_error_code)
    finally:
        controller.disconnect()
    return status


def resolve_ik_for_pose(pose: list[float]) -> dict[str, Any]:
    config = get_config()
    validate_pose_workspace(pose, config["robot_workspace"])

    controller = _raw_controller(config)
    try:
        connected = controller.connect()
        joint = controller.resolve_joint_for_pose(pose)
    finally:
        controller.disconnect()

    return {"pose": pose, "connected": connected, "joint": joint}


def move_to_start(vel: float | None) -> dict[str, Any]:
    config = get_config()
    before_draw = config.get("before_draw", {})
    start_pose = before_draw.get("start_pose")
    if start_pose is None:
        raise ValueError("before_draw.start_pose is not configured")

    validate_pose_workspace(start_pose, config["robot_workspace"])
    velocity = float(vel) if vel is not None else float(before_draw.get("start_vel", config.get("default_vel", 10)))
    result = _raw_move_l(config, start_pose, velocity)
    return {"pose": start_pose, **result}


def draw_line_demo(vel: float | None) -> dict[str, Any]:
    config = get_config()
    motion_strategy = config.get("motion_strategy", {})
    start_pose, end_pose = build_line_demo_poses(config)
    return_pose, return_pose_uses_paper_corner = _configured_return_pose(config)
    poses = [start_pose, end_pose]

    validate_measured_paper_poses(poses, config)
    _validate_return_pose(config, return_pose, return_pose_uses_paper_corner)

    velocity = float(vel) if vel is not None else float(config.get("default_vel", 10))
    enable_move, allow_raw_motion = _motion_flags(config)
    controller = _raw_controller(config)
    try:
        controller.connect()
        results = controller.draw_line_air(
            start_pose=start_pose,
            end_pose=end_pose,
            return_pose=return_pose,
            vel=velocity,
            return_vel=float(config.get("after_draw", {}).get("return_vel", config.get("default_vel", 10))),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()

    return {
        "pose_count": len(poses),
        "return_pose": return_pose,
        "enable_move": enable_move,
        "allow_raw_xmlrpc_motion": allow_raw_motion,
        "result": results,
    }


def draw_circle_demo(vel: float | None) -> dict[str, Any]:
    config = get_config()
    circle_config = config.get("circle_demo", {})
    poses = build_circle_demo_poses(config)
    return _draw_polyline(config, poses, vel, float(circle_config.get("vel", config.get("default_vel", 10))))


def draw_svg(
    svg_path: str | None,
    word_key: str | None,
    svg_paths: list[str] | None,
    vel: float | None,
) -> dict[str, Any]:
    config = get_config()
    paths = _resolve_svg_paths(svg_path, word_key, svg_paths)
    if len(paths) == 1:
        strokes = build_svg_pose_strokes(config, paths[0])
    else:
        strokes = _build_combined_svg_pose_strokes(config, paths)
    return _draw_pose_strokes(
        config,
        strokes,
        vel,
        default_vel=float(config.get("svg_demo", {}).get("vel", config.get("default_vel", 10))),
        source=[str(path) for path in paths],
    )


def draw_text(text: str, vel: float | None, continuous: bool | None) -> dict[str, Any]:
    config = get_config()
    text_config = config.get("text_demo", {})
    raw_strokes = build_text_pose_strokes(config, text)
    continuous_mode = continuous if continuous is not None else bool(text_config.get("continuous", True))
    strokes = [[pose for stroke in raw_strokes for pose in stroke]] if continuous_mode else raw_strokes
    result = _draw_pose_strokes(
        config,
        strokes,
        vel,
        default_vel=float(text_config.get("vel", config.get("default_vel", 10))),
        source=text,
    )
    result["continuous"] = continuous_mode
    return result


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


def _raw_controller(config: dict[str, Any]) -> FairinoRawXmlRpcController:
    return FairinoRawXmlRpcController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
    )


def _motion_flags(config: dict[str, Any]) -> tuple[bool, bool]:
    policy = config.get("connection_policy", {})
    return bool(config.get("enable_robot_move", False)), bool(policy.get("allow_raw_xmlrpc_motion", False))


def _raw_move_l(config: dict[str, Any], pose: list[float], vel: float) -> dict[str, Any]:
    enable_move, allow_raw_motion = _motion_flags(config)
    controller = _raw_controller(config)
    try:
        controller.connect()
        result = controller.move_l(
            pose=pose,
            vel=vel,
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()
    return {"enable_move": enable_move, "allow_raw_xmlrpc_motion": allow_raw_motion, "result": result}


def _configured_return_pose(config: dict[str, Any]) -> tuple[list[float] | None, bool]:
    after_draw = config.get("after_draw", {})
    if after_draw.get("return_pose") is not None:
        return list(after_draw["return_pose"]), False
    if after_draw.get("return_to_bottom_left", False):
        return build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left"))), True
    return None, False


def _validate_return_pose(config: dict[str, Any], return_pose: list[float] | None, uses_paper_corner: bool) -> None:
    if return_pose is None:
        return
    if uses_paper_corner:
        validate_measured_paper_poses([return_pose], config)
    else:
        validate_pose_workspace(return_pose, config["robot_workspace"])


def _draw_polyline(config: dict[str, Any], poses: list[list[float]], vel: float | None, default_vel: float) -> dict[str, Any]:
    motion_strategy = config.get("motion_strategy", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})
    start_pose = before_draw.get("start_pose")
    return_pose, return_pose_uses_paper_corner = _configured_return_pose(config)

    validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    _validate_return_pose(config, return_pose, return_pose_uses_paper_corner)

    enable_move, allow_raw_motion = _motion_flags(config)
    velocity = float(vel) if vel is not None else default_vel
    controller = _raw_controller(config)
    try:
        controller.connect()
        results = controller.draw_polyline_air(
            poses=poses,
            start_pose=start_pose,
            return_pose=return_pose,
            vel=velocity,
            start_vel=float(before_draw.get("start_vel", config.get("default_vel", 10))),
            return_vel=float(after_draw.get("return_vel", config.get("default_vel", 10))),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
            blend_radius=float(motion_strategy.get("blend_radius", -1.0)),
        )
    finally:
        controller.disconnect()

    return {
        "pose_count": len(poses),
        "start_pose": start_pose,
        "return_pose": return_pose,
        "enable_move": enable_move,
        "allow_raw_xmlrpc_motion": allow_raw_motion,
        "result": results,
    }


def _draw_pose_strokes(
    config: dict[str, Any],
    strokes: list[list[list[float]]],
    vel: float | None,
    default_vel: float,
    source: Any,
) -> dict[str, Any]:
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})
    motion_strategy = config.get("motion_strategy", {})
    smooth_config = config.get("smooth_writing", {})
    text_config = config.get("text_demo", {})
    poses = [pose for stroke in strokes for pose in stroke]
    start_pose = before_draw.get("start_pose")
    return_pose, return_pose_uses_paper_corner = _configured_return_pose(config)

    validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    _validate_return_pose(config, return_pose, return_pose_uses_paper_corner)

    planner_config = config_from_robot_config(config)
    planned_strokes = plan_pose_strokes(strokes, planner_config)
    planned_pose_count = sum(len(stroke) for stroke in planned_strokes)
    use_smooth = str(motion_strategy.get("mode", "new_spline")).strip().lower() in ("new_spline", "spline", "smooth")
    motion_strokes = planned_strokes if use_smooth else strokes

    enable_move, allow_raw_motion = _motion_flags(config)
    writing_vel = float(vel) if vel is not None else float(smooth_config.get("writing_speed_mm_s", default_vel))
    travel_vel = float(smooth_config.get("travel_speed_mm_s", text_config.get("travel_vel", config.get("default_vel", 10))))
    blend_radius = float(smooth_config.get("blend_radius_mm", motion_strategy.get("blend_radius", 0.0)))

    controller = _raw_controller(config)
    try:
        controller.connect()
        if use_smooth:
            results = controller.draw_pose_strokes_smooth(
                strokes=motion_strokes,
                start_pose=start_pose,
                return_pose=return_pose,
                vel=writing_vel,
                travel_vel=travel_vel,
                travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
                start_vel=float(before_draw.get("start_vel", config.get("default_vel", 10))),
                return_vel=float(after_draw.get("return_vel", config.get("default_vel", 10))),
                approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
                approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
                blend_radius=blend_radius,
                acceleration=float(smooth_config.get("acceleration", motion_strategy.get("acceleration", 0.0))),
                spline_type=int(motion_strategy.get("spline_type", 1)),
                spline_average_time_ms=int(motion_strategy.get("spline_average_time_ms", 2000)),
                planner_config=planner_config,
                fallback_to_blended_movel=bool(motion_strategy.get("fallback_to_blended_movel", True)),
            )
        else:
            results = controller.draw_pose_strokes(
                strokes=motion_strokes,
                start_pose=start_pose,
                return_pose=return_pose,
                vel=writing_vel,
                travel_vel=travel_vel,
                travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
                start_vel=float(before_draw.get("start_vel", config.get("default_vel", 10))),
                return_vel=float(after_draw.get("return_vel", config.get("default_vel", 10))),
                approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
                approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
                blend_radius=blend_radius,
            )
    finally:
        controller.disconnect()

    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)
    return {
        "source": source,
        "stroke_count": len(strokes),
        "pose_count": len(poses),
        "planned_stroke_count": len(planned_strokes),
        "planned_pose_count": planned_pose_count,
        "paper_width": round(width, 3),
        "paper_height": round(height, 3),
        "start_pose": start_pose,
        "return_pose": return_pose,
        "motion_mode": "smooth" if use_smooth else "movel_strokes",
        "enable_move": enable_move,
        "allow_raw_xmlrpc_motion": allow_raw_motion,
        "result": results,
    }


def _resolve_svg_paths(svg_path: str | None, word_key: str | None, svg_paths: list[str] | None) -> list[Path]:
    if svg_paths:
        return [_project_path(path) for path in svg_paths]
    if svg_path:
        return [_project_path(svg_path)]
    if word_key:
        library = json.loads(WORD_LIBRARY_PATH.read_text(encoding="utf-8"))
        if word_key not in library:
            raise ValueError(f"Unknown word_key: {word_key}")
        return [_project_path(str(library[word_key]))]
    config = get_config()
    svg_demo = config.get("svg_demo", {})
    return [_project_path(str(svg_demo.get("svg_path", "assets/svg/tam.svg")))]


def _project_path(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def _build_combined_svg_pose_strokes(config: dict[str, Any], svg_paths: list[Path]) -> list[list[list[float]]]:
    demo = config.get("svg_demo", {})
    source_strokes = []
    for svg_path in svg_paths:
        source_strokes.extend(sample_svg_strokes(svg_path, int(demo.get("samples_per_path", 120))))

    point_counts = [len(stroke) for stroke in source_strokes]
    normalized_points = fit_points_to_uv(
        [point for stroke in source_strokes for point in stroke],
        u_min=float(demo.get("u_min", 0.25)),
        u_max=float(demo.get("u_max", 0.75)),
        v_min=float(demo.get("v_min", 0.25)),
        v_max=float(demo.get("v_max", 0.75)),
    )

    pose_strokes = []
    start = 0
    for count in point_counts:
        stroke_points = normalized_points[start : start + count]
        pose_strokes.append([build_pose_in_paper(config, u, v) for u, v in stroke_points])
        start += count
    return pose_strokes


def _safe_raw_call(callable_obj):
    try:
        return callable_obj()
    except Exception as exc:
        return {"error": str(exc)}
