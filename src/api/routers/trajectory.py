from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.trajectory_service import (
    build_line_preview,
    build_shape_preview,
    build_svg_preview,
    build_text_outline_times_preview,
    build_text_preview,
    build_text_skeleton_times_preview,
)

router = APIRouter()


class ShapeRequest(BaseModel):
    shape_name: str

    class Config:
        json_schema_extra = {"example": {"shape_name": "circle"}}


class SvgRequest(BaseModel):
    svg_path: str | None = None
    word_key: str | None = None

    class Config:
        json_schema_extra = {"example": {"word_key": "Tam"}}


class TextRequest(BaseModel):
    text: str
    continuous: bool | None = None

    class Config:
        json_schema_extra = {"example": {"text": "Tam", "continuous": True}}


class TextOutlineRequest(BaseModel):
    text: str
    continuous: bool | None = None

    class Config:
        json_schema_extra = {"example": {"text": "Happy New Year", "continuous": False}}


@router.post(
    "/line/preview",
    summary="Preview line demo poses",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "start_pose": [0, 0, 0, 0, 0, 0],
                        "end_pose": [1, 1, 1, 0, 0, 0],
                        "return_pose": None,
                        "use_measured_paper": True,
                    }
                }
            }
        }
    },
)
def preview_line() -> dict[str, Any]:
    return build_line_preview()


@router.post(
    "/shape/preview",
    summary="Preview shape poses",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "shape": "circle",
                        "poses": [[0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0]],
                    }
                }
            }
        }
    },
)
def preview_shape(payload: ShapeRequest) -> dict[str, Any]:
    return build_shape_preview(payload.shape_name)


@router.post(
    "/svg/preview",
    summary="Preview SVG poses",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "svg_path": "assets/svg/tam.svg",
                        "poses": [[0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0]],
                    }
                }
            }
        }
    },
)
def preview_svg(payload: SvgRequest) -> dict[str, Any]:
    return build_svg_preview(payload.svg_path, payload.word_key)


@router.post(
    "/text/preview",
    summary="Preview text poses",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "text": "Tam",
                        "continuous": True,
                        "stroke_count": 2,
                        "poses": [[0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0]],
                    }
                }
            }
        }
    },
)
def preview_text(payload: TextRequest) -> dict[str, Any]:
    return build_text_preview(payload.text, payload.continuous)


@router.post(
    "/text/outline/preview",
    summary="Preview keyboard text as Times New Roman outline poses",
)
def preview_text_outline(payload: TextOutlineRequest) -> dict[str, Any]:
    return build_text_outline_times_preview(payload.text, payload.continuous)


@router.post(
    "/text/skeleton/preview",
    summary="Preview keyboard text as Times New Roman skeleton poses",
)
def preview_text_skeleton(payload: TextOutlineRequest) -> dict[str, Any]:
    return build_text_skeleton_times_preview(payload.text, payload.continuous)
