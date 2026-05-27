from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.gripper_service import (
    get_gripper_status,
    open_gripper,
    close_gripper,
)

router = APIRouter()


class GripperMoveRequest(BaseModel):
    pos: int | None = None
    vel: int | None = None
    force: int | None = None

    class Config:
        json_schema_extra = {"example": {"pos": 100, "vel": 20, "force": 20}}


@router.get(
    "/status",
    summary="Read gripper status",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "connected": True,
                        "config": [0, 4, 0, 0, 0],
                        "snapshot": {"position": [0, 0, 50]},
                    }
                }
            }
        }
    },
)
def gripper_status() -> dict[str, Any]:
    return get_gripper_status()


@router.post(
    "/open",
    summary="Open gripper (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "enable_gripper_motion": False,
                        "allow_raw_xmlrpc_gripper": False,
                        "result": None,
                    }
                }
            }
        }
    },
)
def gripper_open(payload: GripperMoveRequest) -> dict[str, Any]:
    return open_gripper(payload.pos, payload.vel, payload.force)


@router.post(
    "/close",
    summary="Close gripper (guarded by config)",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "enable_gripper_motion": False,
                        "allow_raw_xmlrpc_gripper": False,
                        "result": None,
                    }
                }
            }
        }
    },
)
def gripper_close(payload: GripperMoveRequest) -> dict[str, Any]:
    return close_gripper(payload.pos, payload.vel, payload.force)
