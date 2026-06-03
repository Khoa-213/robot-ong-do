from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.robot_service import (
    check_ports,
    draw_circle_demo,
    draw_line_demo,
    draw_paper_corners,
    draw_shape,
    draw_svg,
    draw_text,
    draw_text_outline_times,
    draw_text_skeleton_times,
    get_raw_robot_status,
    get_robot_status,
    move_l,
    move_to_start,
    resolve_ik_for_pose,
)
from src.services.config_service import get_config

router = APIRouter()


class PoseRequest(BaseModel):
    pose: list[float] = Field(..., min_length=6, max_length=6)
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "pose": [300.0, 0.0, 300.0, 180.0, 0.0, 90.0],
                "vel": 10.0,
            }
        }


class ShapeDrawRequest(BaseModel):
    shape_name: str
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"shape_name": "square", "vel": 20}}


class VelocityRequest(BaseModel):
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"vel": 20}}


class SvgDrawRequest(BaseModel):
    svg_path: str | None = None
    word_key: str | None = None
    svg_paths: list[str] | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"svg_path": "assets/svg/Nhan.svg", "vel": 12}}


class TextDrawRequest(BaseModel):
    text: str
    continuous: bool | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"text": "Tam", "continuous": False, "vel": 12}}


class TextOutlineDrawRequest(BaseModel):
    text: str
    continuous: bool | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"text": "Happy New Year", "continuous": False, "vel": 12}}


class TextSkeletonDrawRequest(BaseModel):
    text: str
    continuous: bool | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {"example": {"text": "Happy New Year", "continuous": False, "vel": 12}}


class PaperCornersDrawRequest(BaseModel):
    corners: list[list[float]] | None = Field(default=None, min_length=4, max_length=4)
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "vel": 20,
            }
        }


@router.get(
    "/ports",
    summary="Check robot ports",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "ports": {"20003": True, "20004": True, "20005": False},
                    }
                }
            }
        }
    },
)
def robot_ports() -> dict[str, Any]:
    config = get_config()
    robot_ip = str(config["robot_ip"])
    policy = config.get("connection_policy", {})
    ports = [
        int(policy.get("command_port", 20003)),
        int(policy.get("legacy_state_port", 20004)),
        int(policy.get("cnde_port", 20005)),
    ]
    return check_ports(robot_ip, ports)


@router.get(
    "/status",
    summary="Read robot status",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "connected": True,
                        "xmlrpc_ok": True,
                        "tcp_pose": [0, 0, 0, 0, 0, 0],
                        "error_code": [0, 0],
                    }
                }
            }
        }
    },
)
def robot_status() -> dict[str, Any]:
    return get_robot_status()


@router.get(
    "/raw_status",
    summary="Read raw XML-RPC robot status",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "connected": True,
                        "controller_ip": "192.168.58.2",
                        "tcp_pose": [0, 0, 0, 0, 0, 0],
                        "error_code": [0, 0],
                    }
                }
            }
        }
    },
)
def robot_raw_status() -> dict[str, Any]:
    return get_raw_robot_status()


@router.post(
    "/moveL",
    summary="MoveL to pose (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {"enable_move": False, "result": None}
                }
            }
        }
    },
)
def robot_move_l(payload: PoseRequest) -> dict[str, Any]:
    return move_l(payload.pose, payload.vel)


@router.post(
    "/ik",
    summary="Resolve IK for a pose without sending motion",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "pose": [300, 0, 300, 180, 0, 90],
                        "connected": True,
                        "joint": [0, -30, 90, 0, 60, 0],
                    }
                }
            }
        }
    },
)
def robot_ik(payload: PoseRequest) -> dict[str, Any]:
    return resolve_ik_for_pose(payload.pose)


@router.post(
    "/move/start",
    summary="Move robot to before_draw.start_pose (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "pose": [-105.657, 275.606, 371.442, 179.379, 8.605, -113.274],
                        "enable_move": True,
                        "allow_raw_xmlrpc_motion": True,
                        "result": 0,
                    }
                }
            }
        }
    },
)
def robot_move_start(payload: VelocityRequest) -> dict[str, Any]:
    return move_to_start(payload.vel)


@router.post(
    "/draw/shape",
    summary="Draw a simple shape (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "shape": "square",
                        "pose_count": 5,
                        "enable_move": False,
                        "allow_raw_xmlrpc_motion": False,
                        "result": None,
                    }
                }
            }
        }
    },
)
def robot_draw_shape(payload: ShapeDrawRequest) -> dict[str, Any]:
    return draw_shape(payload.shape_name, payload.vel)


@router.post(
    "/draw/line",
    summary="Draw measured paper line demo (guarded by config)",
)
def robot_draw_line(payload: VelocityRequest) -> dict[str, Any]:
    return draw_line_demo(payload.vel)


@router.post(
    "/draw/circle",
    summary="Draw measured paper circle demo (guarded by config)",
)
def robot_draw_circle(payload: VelocityRequest) -> dict[str, Any]:
    return draw_circle_demo(payload.vel)


@router.post(
    "/draw/svg",
    summary="Draw one or more SVG files as writing strokes (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "source": ["D:/robot-ong-do/assets/svg/Nhan.svg"],
                        "stroke_count": 4,
                        "pose_count": 180,
                        "planned_pose_count": 160,
                        "motion_mode": "smooth",
                        "enable_move": True,
                        "allow_raw_xmlrpc_motion": True,
                        "result": [],
                    }
                }
            }
        }
    },
)
def robot_draw_svg(payload: SvgDrawRequest) -> dict[str, Any]:
    return draw_svg(payload.svg_path, payload.word_key, payload.svg_paths, payload.vel)


@router.post(
    "/draw/text",
    summary="Draw text using configured text trajectory (guarded by config)",
)
def robot_draw_text(payload: TextDrawRequest) -> dict[str, Any]:
    return draw_text(payload.text, payload.vel, payload.continuous)


@router.post(
    "/draw/text/outline",
    summary="Draw keyboard text as Times New Roman outline strokes (guarded by config)",
)
def robot_draw_text_outline(payload: TextOutlineDrawRequest) -> dict[str, Any]:
    return draw_text_outline_times(payload.text, payload.vel, payload.continuous)


@router.post(
    "/draw/text/skeleton",
    summary="Draw keyboard text as Times New Roman skeleton strokes (guarded by config)",
)
def robot_draw_text_skeleton(payload: TextSkeletonDrawRequest) -> dict[str, Any]:
    return draw_text_skeleton_times(payload.text, payload.vel, payload.continuous)


@router.post(
    "/draw/paper_corners",
    summary="Move through 4 paper corners (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "pose_count": 4,
                        "enable_move": False,
                        "allow_raw_xmlrpc_motion": False,
                        "result": None,
                    }
                }
            }
        }
    },
)
def robot_draw_paper_corners(payload: PaperCornersDrawRequest) -> dict[str, Any]:
    return draw_paper_corners(payload.corners, payload.vel)
