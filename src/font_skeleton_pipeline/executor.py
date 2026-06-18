from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.trajectory_planner import config_from_robot_config
from src.services.config_service import get_config

from .models import TrajectoryPoint, ValidationIssue, ValidationResult


class MockRobot:
    """Record the command stream that would be sent to a robot."""

    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute(self, trajectory: list[TrajectoryPoint]) -> list[dict[str, Any]]:
        for point in trajectory:
            command = {
                "command": point.motion_type,
                "stroke_id": point.stroke_id,
                "pose": [point.x, point.y, point.z, point.rx, point.ry, point.rz],
                "pen_state": point.pen_state,
                "velocity": point.velocity,
                "blend_radius": point.blend_radius,
            }
            self.commands.append(command)
        return self.commands


class RobotTrajectoryExecutor:
    """Execute only reviewed and validated font-skeleton trajectories."""

    def __init__(self, config: dict[str, Any] | None = None, robot: Any | None = None) -> None:
        self.config = config if config is not None else get_config()
        self.robot = robot

    def validate_capabilities(self) -> dict[str, bool]:
        return {
            "new_spline": True,
            "blended_movel": True,
            "servo_stream": False,
            "mock": isinstance(self.robot, MockRobot),
        }

    def execute_previewed_trajectory(
        self,
        trajectory_json: str | Path,
        *,
        execute: bool = False,
        require_confirmation: bool = True,
        confirmation_text: str | None = None,
        use_mock: bool = True,
    ) -> Any:
        payload = json.loads(Path(trajectory_json).read_text(encoding="utf-8"))
        points = [_point_from_dict(item) for item in payload.get("points", [])]
        validation = _validation_from_payload(payload)

        if not execute:
            robot = self.robot if self.robot is not None else MockRobot()
            return robot.execute(points)

        if not payload.get("approved", False):
            raise PermissionError("Trajectory has not been reviewed and approved.")
        if not validation.is_safe:
            raise RuntimeError("Trajectory failed safety validation.")
        if require_confirmation and confirmation_text != "EXECUTE":
            raise PermissionError("Robot execution requires typing EXECUTE.")

        if use_mock:
            robot = self.robot if self.robot is not None else MockRobot()
            return robot.execute(points)

        return self.execute_spline(points)

    def execute_spline(self, trajectory: list[TrajectoryPoint]) -> Any:
        strokes = _trajectory_to_pose_strokes(trajectory)
        if not strokes:
            raise ValueError("No drawable strokes found")
        policy = self.config.get("connection_policy", {})
        controller = FairinoRawXmlRpcController(
            robot_ip=str(self.config["robot_ip"]),
            tool=int(self.config.get("tool", 0)),
            user=int(self.config.get("user", 0)),
        )
        controller.set_paper_guard(self.config, allowed_poses=[self.config.get("before_draw", {}).get("start_pose")])
        try:
            controller.connect()
            return controller.draw_pose_strokes_smooth(
                strokes=strokes,
                vel=float(self.config.get("smooth_writing", {}).get("writing_speed_mm_s", 10)),
                travel_vel=float(self.config.get("smooth_writing", {}).get("travel_speed_mm_s", 18)),
                travel_z_offset=float(self.config.get("text_demo", {}).get("travel_z_offset", 20.0)),
                enable_move=bool(self.config.get("enable_robot_move", False)),
                allow_raw_xmlrpc_motion=bool(policy.get("allow_raw_xmlrpc_motion", False)),
                blend_radius=float(self.config.get("smooth_writing", {}).get("blend_radius_mm", 0.0)),
                acceleration=float(self.config.get("smooth_writing", {}).get("acceleration", 0.0)),
                planner_config=config_from_robot_config(self.config),
            )
        finally:
            controller.disconnect()

    def execute_servo_stream(self, trajectory: list[TrajectoryPoint]) -> Any:
        raise NotImplementedError("Servo streaming is not enabled for this pipeline yet")

    def execute_blended_linear_path(self, trajectory: list[TrajectoryPoint]) -> Any:
        return self.execute_spline(trajectory)


def _point_from_dict(data: dict[str, Any]) -> TrajectoryPoint:
    return TrajectoryPoint(
        index=int(data["index"]),
        stroke_id=int(data["stroke_id"]),
        x=float(data["x"]),
        y=float(data["y"]),
        z=float(data["z"]),
        rx=None if data.get("rx") is None else float(data["rx"]),
        ry=None if data.get("ry") is None else float(data["ry"]),
        rz=None if data.get("rz") is None else float(data["rz"]),
        velocity=float(data["velocity"]),
        acceleration=float(data["acceleration"]),
        blend_radius=float(data["blend_radius"]),
        pen_state=str(data["pen_state"]),
        motion_type=str(data["motion_type"]),
    )


def _validation_from_payload(payload: dict[str, Any]) -> ValidationResult:
    validation = payload.get("validation", {})
    issues = [
        ValidationIssue(
            severity=str(item.get("severity", "error")),
            code=str(item.get("code", "unknown")),
            message=str(item.get("message", "")),
            point_index=item.get("point_index"),
        )
        for item in validation.get("issues", [])
    ]
    return ValidationResult(bool(validation.get("is_safe", False)), issues, validation.get("metrics", {}))


def _trajectory_to_pose_strokes(trajectory: list[TrajectoryPoint]) -> list[list[list[float]]]:
    strokes: dict[int, list[list[float]]] = {}
    for point in trajectory:
        if point.motion_type != "DRAW" or point.pen_state != "PEN_DOWN":
            continue
        strokes.setdefault(point.stroke_id, []).append(
            [
                point.x,
                point.y,
                point.z,
                float(point.rx or 0.0),
                float(point.ry or 0.0),
                float(point.rz or 0.0),
            ]
        )
    return [stroke for _stroke_id, stroke in sorted(strokes.items()) if len(stroke) >= 2]
