from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.safety_service import validate_pose, validate_poses, validate_start_end_in_corners

router = APIRouter()


class PoseRequest(BaseModel):
    pose: list[float] = Field(..., min_length=6, max_length=6)

    class Config:
        json_schema_extra = {
            "example": {"pose": [300.0, 0.0, 300.0, 180.0, 0.0, 90.0]}
        }


class PosesRequest(BaseModel):
    poses: list[list[float]]

    class Config:
        json_schema_extra = {
            "example": {"poses": [[300.0, 0.0, 300.0, 180.0, 0.0, 90.0]]}
        }


class PaperPointRequest(BaseModel):
    corners: list[list[float]] = Field(..., min_length=4, max_length=4)
    start_pose: list[float] = Field(..., min_length=6, max_length=6)
    end_pose: list[float] = Field(..., min_length=6, max_length=6)

    class Config:
        json_schema_extra = {
            "example": {
                "corners": [
                    [-72.905, 566.026, 254.059, 178.105, 6.628, -117.259],
                    [57.222, 563.859, 254.065, 178.438, 5.884, -130.427],
                    [54.994, 376.268, 254.059, -179.927, 2.518, -137.905],
                    [-75.305, 379.196, 254.069, 179.554, 1.428, -118.339],
                ],
                "start_pose": [82.858, -229.638, 752.628, 12.552, -0.323, 143.515],
                "end_pose": [132.858, -229.638, 752.628, 12.552, -0.323, 143.515],
            }
        }


@router.post(
    "/validate_pose",
    summary="Validate single pose",
    responses={200: {"content": {"application/json": {"example": {"ok": True}}}}},
)
def safety_validate_pose(payload: PoseRequest) -> dict[str, Any]:
    validate_pose(payload.pose)
    return {"ok": True}


@router.post(
    "/validate_poses",
    summary="Validate pose list",
    responses={200: {"content": {"application/json": {"example": {"ok": True}}}}},
)
def safety_validate_poses(payload: PosesRequest) -> dict[str, Any]:
    validate_poses(payload.poses)
    return {"ok": True}


@router.post(
    "/validate_paper_point",
    summary="Validate start/end points inside 4 paper corners",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {"ok": True, "start_inside": True, "end_inside": True}
                }
            }
        }
    },
)
def safety_validate_paper_point(payload: PaperPointRequest) -> dict[str, Any]:
    result = validate_start_end_in_corners(payload.corners, payload.start_pose, payload.end_pose)
    return {"ok": True, **result}
