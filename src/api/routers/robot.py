from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.robot_service import check_ports, get_robot_status, move_l, draw_shape, draw_paper_corners
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


class PaperCornersDrawRequest(BaseModel):
    corners: list[list[float]] = Field(..., min_length=4, max_length=4)
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "corners": [
                    [-72.905, 566.026, 254.059, 178.105, 6.628, -117.259],
                    [57.222, 563.859, 254.065, 178.438, 5.884, -130.427],
                    [54.994, 376.268, 254.059, -179.927, 2.518, -137.905],
                    [-75.305, 379.196, 254.069, 179.554, 1.428, -118.339],
                ],
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
