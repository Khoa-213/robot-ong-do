from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.config_service import get_config, reload_config, update_config

router = APIRouter()


class ConnectionPolicyPatch(BaseModel):
    command_port: int | None = None
    legacy_state_port: int | None = None
    cnde_port: int | None = None
    allow_xmlrpc_motion_when_cnde_unavailable: bool | None = None
    allow_raw_xmlrpc_motion: bool | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "command_port": 20003,
                "legacy_state_port": 20004,
                "cnde_port": 20005,
                "allow_xmlrpc_motion_when_cnde_unavailable": False,
                "allow_raw_xmlrpc_motion": True,
            }
        }


class RobotWorkspacePatch(BaseModel):
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    z_min: float | None = None
    z_max: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "x_min": -500.0,
                "x_max": 500.0,
                "y_min": -600.0,
                "y_max": 600.0,
                "z_min": 100.0,
                "z_max": 900.0,
            }
        }


class PaperPatch(BaseModel):
    enabled: bool | None = None
    origin_x: float | None = None
    origin_y: float | None = None
    paper_z: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    margin_mm: float | None = None
    coordinate_mode: str | None = None
    draw_orientation: list[float] | None = Field(default=None, min_length=3, max_length=3)
    corners: dict[str, list[float]] | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "origin_x": -72.905,
                "origin_y": 566.026,
                "paper_z": 254.063,
                "width_mm": 130.134,
                "height_mm": 187.6,
                "margin_mm": 20.0,
                "coordinate_mode": "measured_corners",
                "draw_orientation": [179.554, 1.428, -118.339],
                "corners": {
                    "top_left": [-72.905, 566.026, 254.059, 178.105, 6.628, -117.259],
                    "top_right": [57.222, 563.859, 254.065, 178.438, 5.884, -130.427],
                    "bottom_right": [54.994, 376.268, 254.059, -179.927, 2.518, -137.905],
                    "bottom_left": [-75.305, 379.196, 254.069, 179.554, 1.428, -118.339],
                },
            }
        }


class ZSafetyPatch(BaseModel):
    z_lift_offset: float | None = None
    z_write_light_offset: float | None = None
    z_write_normal_offset: float | None = None
    z_write_bold_offset: float | None = None
    z_min_allowed_offset: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "z_lift_offset": 0.0,
                "z_write_light_offset": 2.0,
                "z_write_normal_offset": 0.0,
                "z_write_bold_offset": -1.5,
                "z_min_allowed_offset": -3.0,
            }
        }


class LineDemoPatch(BaseModel):
    start_pose: list[float] | None = Field(default=None, min_length=6, max_length=6)
    end_pose: list[float] | None = Field(default=None, min_length=6, max_length=6)

    class Config:
        json_schema_extra = {
            "example": {
                "start_pose": [82.858, -229.638, 752.628, 12.552, -0.323, 143.515],
                "end_pose": [132.858, -229.638, 752.628, 12.552, -0.323, 143.515],
            }
        }


class PaperLineDemoPatch(BaseModel):
    start_u: float | None = None
    end_u: float | None = None
    line_v: float | None = None

    class Config:
        json_schema_extra = {"example": {"start_u": 0.25, "end_u": 0.75, "line_v": 0.5}}


class CircleDemoPatch(BaseModel):
    center_u: float | None = None
    center_v: float | None = None
    radius_u: float | None = None
    radius_v: float | None = None
    segments: int | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "center_u": 0.5,
                "center_v": 0.5,
                "radius_u": 0.16,
                "radius_v": 0.16,
                "segments": 24,
                "vel": 50,
            }
        }


class ShapeDemoPatch(BaseModel):
    default_shape: str | None = None
    center_u: float | None = None
    center_v: float | None = None
    radius_u: float | None = None
    radius_v: float | None = None
    square_half_u: float | None = None
    square_half_v: float | None = None
    triangle_radius_u: float | None = None
    triangle_radius_v: float | None = None
    segments: int | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "default_shape": "circle",
                "center_u": 0.5,
                "center_v": 0.5,
                "radius_u": 0.16,
                "radius_v": 0.16,
                "square_half_u": 0.16,
                "square_half_v": 0.16,
                "triangle_radius_u": 0.18,
                "triangle_radius_v": 0.18,
                "segments": 24,
                "vel": 50,
            }
        }


class BeforeDrawPatch(BaseModel):
    start_pose: list[float] | None = Field(default=None, min_length=6, max_length=6)
    start_vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "start_pose": [-79.006, 386.988, 326.726, 179.446, 3.677, -117.524],
                "start_vel": 20,
            }
        }


class SvgDemoPatch(BaseModel):
    svg_path: str | None = None
    u_min: float | None = None
    u_max: float | None = None
    v_min: float | None = None
    v_max: float | None = None
    samples_per_path: int | None = None
    vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "svg_path": "assets/svg/tâm.svg",
                "u_min": 0.25,
                "u_max": 0.75,
                "v_min": 0.25,
                "v_max": 0.75,
                "samples_per_path": 120,
                "vel": 50,
            }
        }


class TextDemoPatch(BaseModel):
    mode: str | None = None
    continuous: bool | None = None
    u_min: float | None = None
    u_max: float | None = None
    v_min: float | None = None
    v_max: float | None = None
    font_family: str | None = None
    font_size: float | None = None
    invert_y: bool | None = None
    max_points_per_stroke: int | None = None
    vel: float | None = None
    travel_vel: float | None = None
    travel_z_offset: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "single_line",
                "continuous": False,
                "u_min": 0.2,
                "u_max": 0.8,
                "v_min": 0.2,
                "v_max": 0.8,
                "font_family": "DejaVu Sans",
                "font_size": 1.0,
                "invert_y": True,
                "max_points_per_stroke": 48,
                "vel": 20,
                "travel_vel": 20,
                "travel_z_offset": 20.0,
            }
        }


class AfterDrawPatch(BaseModel):
    return_to_bottom_left: bool | None = None
    return_corner: str | None = None
    return_pose: list[float] | None = Field(default=None, min_length=6, max_length=6)
    return_vel: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "return_to_bottom_left": True,
                "return_corner": "bottom_left",
                "return_pose": [-79.006, 386.988, 326.726, 179.446, 3.677, -117.524],
                "return_vel": 20,
            }
        }


class MotionStrategyPatch(BaseModel):
    approach_with_move_j: bool | None = None
    approach_vel: float | None = None
    draw_with_move_l: bool | None = None

    class Config:
        json_schema_extra = {
            "example": {"approach_with_move_j": True, "approach_vel": 20, "draw_with_move_l": True}
        }


class ToolDoGripperPatch(BaseModel):
    enabled: bool | None = None
    enable_tool_do_gripper: bool | None = None
    do_id: int | None = None
    open_status: int | None = None
    close_status: int | None = None
    smooth: int | None = None
    block: int | None = None
    cycle_count: int | None = None
    hold_seconds: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": False,
                "enable_tool_do_gripper": False,
                "do_id": 1,
                "open_status": 0,
                "close_status": 1,
                "smooth": 0,
                "block": 1,
                "cycle_count": 5,
                "hold_seconds": 1.0,
            }
        }


class ToolEndLuaPatch(BaseModel):
    configure_before_test: bool | None = None
    baud_rate_code: int | None = None
    data_bit: int | None = None
    stop_bit: int | None = None
    verify: int | None = None
    timeout_ms: int | None = None
    timeout_times: int | None = None
    period_ms: int | None = None
    enable_lua: bool | None = None
    force_sensor_enable: int | None = None
    gripper_enable: int | None = None
    io_enable: int | None = None
    enable_gripper_func: bool | None = None
    gripper_func: list[int] | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "configure_before_test": False,
                "baud_rate_code": 7,
                "data_bit": 8,
                "stop_bit": 1,
                "verify": 0,
                "timeout_ms": 5,
                "timeout_times": 3,
                "period_ms": 1000,
                "enable_lua": True,
                "force_sensor_enable": 0,
                "gripper_enable": 1,
                "io_enable": 0,
                "enable_gripper_func": True,
                "gripper_func": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            }
        }


class GripperPatch(BaseModel):
    enabled: bool | None = None
    model: str | None = None
    model_code: str | None = None
    voltage_v: float | None = None
    max_current_a: float | None = None
    communication_protocol: str | None = None
    matching_cable: str | None = None
    interface: str | None = None
    enable_gripper_motion: bool | None = None
    allow_raw_xmlrpc_gripper: bool | None = None
    index: int | None = None
    company: int | None = None
    device: int | None = None
    softversion: int | None = None
    bus: int | None = None
    open_pos: int | None = None
    close_pos: int | None = None
    test_vel: int | None = None
    test_force: int | None = None
    max_time_ms: int | None = None
    block: int | None = None
    type: int | None = None
    rot_num: float | None = None
    rot_vel: int | None = None
    rot_torque: int | None = None
    tool_end_lua: ToolEndLuaPatch | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "model": "JODELL EPG40-050",
                "model_code": "EPG40-050-0PF-L200-C7-N-A-P40-S00",
                "voltage_v": 24,
                "max_current_a": 0.85,
                "communication_protocol": "RS485",
                "matching_cable": "M12-5FA-S5-5000-P",
                "interface": "tool_end",
                "enable_gripper_motion": True,
                "allow_raw_xmlrpc_gripper": True,
                "index": 1,
                "company": 1,
                "device": 5,
                "softversion": 0,
                "bus": 0,
                "open_pos": 100,
                "close_pos": 20,
                "test_vel": 10,
                "test_force": 10,
                "max_time_ms": 5000,
                "block": 0,
                "type": 0,
                "rot_num": 0,
                "rot_vel": 0,
                "rot_torque": 0,
                "tool_end_lua": {
                    "configure_before_test": False,
                    "baud_rate_code": 7,
                    "data_bit": 8,
                    "stop_bit": 1,
                    "verify": 0,
                    "timeout_ms": 5,
                    "timeout_times": 3,
                    "period_ms": 1000,
                    "enable_lua": True,
                    "force_sensor_enable": 0,
                    "gripper_enable": 1,
                    "io_enable": 0,
                    "enable_gripper_func": True,
                    "gripper_func": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                },
            }
        }


class ConfigPatchData(BaseModel):
    robot_ip: str | None = None
    tool: int | None = None
    user: int | None = None
    default_vel: float | None = None
    enable_robot_move: bool | None = None
    connection_policy: ConnectionPolicyPatch | None = None
    robot_workspace: RobotWorkspacePatch | None = None
    paper: PaperPatch | None = None
    z_safety: ZSafetyPatch | None = None
    line_demo: LineDemoPatch | None = None
    paper_line_demo: PaperLineDemoPatch | None = None
    circle_demo: CircleDemoPatch | None = None
    shape_demo: ShapeDemoPatch | None = None
    before_draw: BeforeDrawPatch | None = None
    svg_demo: SvgDemoPatch | None = None
    text_demo: TextDemoPatch | None = None
    after_draw: AfterDrawPatch | None = None
    motion_strategy: MotionStrategyPatch | None = None
    tool_do_gripper: ToolDoGripperPatch | None = None
    gripper: GripperPatch | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "robot_ip": "192.168.58.2",
                "tool": 0,
                "user": 0,
                "default_vel": 20,
                "enable_robot_move": True,
                "connection_policy": {
                    "command_port": 20003,
                    "legacy_state_port": 20004,
                    "cnde_port": 20005,
                    "allow_xmlrpc_motion_when_cnde_unavailable": False,
                    "allow_raw_xmlrpc_motion": True,
                },
            }
        }


class ConfigPatch(BaseModel):
    data: ConfigPatchData

    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "default_vel": 20,
                    "enable_robot_move": True,
                    "paper": {"margin_mm": 20.0},
                }
            }
        }


@router.get(
    "",
    summary="Read config",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "default_vel": 20,
                        "enable_robot_move": False,
                    }
                }
            }
        }
    },
)
def read_config() -> dict[str, Any]:
    return get_config()


@router.post(
    "/reload",
    summary="Reload config from disk",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "default_vel": 20,
                        "enable_robot_move": False,
                    }
                }
            }
        }
    },
)
def reload_config_file() -> dict[str, Any]:
    return reload_config()


@router.patch(
    "",
    summary="Patch config",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "robot_ip": "192.168.58.2",
                        "default_vel": 15,
                        "enable_robot_move": False,
                        "paper": {"margin_mm": 15.0},
                    }
                }
            }
        }
    },
)
def patch_config(payload: ConfigPatch) -> dict[str, Any]:
    return update_config(payload.data)
