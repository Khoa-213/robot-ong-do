from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.font_skeleton_pipeline.executor import RobotTrajectoryExecutor
from src.font_skeleton_pipeline.pipeline import FontSkeletonPipeline


FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "UTM ThuPhap Thien An.ttf"


def _test_config() -> dict:
    return {
        "robot_ip": "127.0.0.1",
        "tool": 0,
        "user": 0,
        "default_vel": 10,
        "enable_robot_move": False,
        "connection_policy": {"allow_raw_xmlrpc_motion": False},
        "robot_workspace": {
            "x_min": -500.0,
            "x_max": 500.0,
            "y_min": -600.0,
            "y_max": 700.0,
            "z_min": 100.0,
            "z_max": 900.0,
        },
        "paper": {
            "paper_z": 292.206,
            "width_mm": 210.0,
            "height_mm": 297.0,
            "margin_mm": 20.0,
            "draw_orientation": [-179.07, -0.108, -109.105],
            "corners": {
                "top_left": [-129.426, 608.78, 292.206, -179.07, -0.108, -109.105],
                "top_right": [80.574, 608.78, 292.206, -179.07, -0.108, -109.105],
                "bottom_right": [80.574, 311.78, 292.206, -179.07, -0.108, -109.105],
                "bottom_left": [-129.426, 311.78, 292.206, -179.07, -0.108, -109.105],
            },
        },
        "z_safety": {"z_min_allowed_offset": -3.0},
        "text_demo": {"travel_z_offset": 20.0},
        "motion_strategy": {"blend_radius": 1.0},
        "smooth_writing": {
            "writing_speed_mm_s": 12,
            "travel_speed_mm_s": 18,
            "safe_z": 371.442,
            "point_spacing_mm": 1.0,
            "smoothing_tolerance": 0.35,
            "min_point_distance_mm": 0.25,
            "moving_average_window": 3,
            "blend_radius_mm": 1.0,
            "acceleration": 0.0,
            "max_points_per_stroke": 220,
        },
        "font_skeleton_pipeline": {
            "font_size": 160,
            "output_width_mm": 60.0,
            "output_height_mm": 50.0,
            "resolution": 1.4,
            "z_light": -0.5,
            "z_heavy": -2.5,
            "point_spacing_mm": 1.5,
            "min_branch_length": 4.0,
            "simplification_tolerance": 0.1,
            "max_points_per_stroke": 200,
            "max_outside_ratio": 0.2,
            "min_coverage_ratio": 0.05,
            "max_step_distance_mm": 8.0,
            "max_velocity_mm_s": 100.0,
            "max_acceleration_mm_s2": 500.0,
            "invert_y": True,
        },
    }


def test_font_skeleton_pipeline_writes_required_artifacts(tmp_path: Path) -> None:
    result = FontSkeletonPipeline(config=_test_config(), project_root=PROJECT_ROOT).run(
        "Tam",
        str(FONT_PATH),
        output_root=tmp_path,
    )
    run_dir = Path(result["run_dir"])
    for name in [
        "input_text.txt",
        "original_font_render.png",
        "raw_skeleton.png",
        "cleaned_skeleton.png",
        "stroke_order_preview.png",
        "robot_trajectory_preview.png",
        "robot_trajectory_preview.svg",
        "robot_trajectory.csv",
        "robot_trajectory.json",
        "validation_report.json",
        "summary.txt",
    ]:
        assert (run_dir / name).exists(), name

    payload = json.loads((run_dir / "robot_trajectory.json").read_text(encoding="utf-8"))
    assert payload["approved"] is False
    assert payload["preview_only"] is True
    assert payload["points"]
    assert any(point["pen_state"] == "PEN_DOWN" for point in payload["points"])
    assert any(point["motion_type"] == "TRAVEL" or point["motion_type"] == "APPROACH" for point in payload["points"])


def test_missing_font_fails_before_robot_work(tmp_path: Path) -> None:
    try:
        FontSkeletonPipeline(config=_test_config(), project_root=PROJECT_ROOT).run(
            "Tam",
            str(tmp_path / "missing.ttf"),
            output_root=tmp_path,
        )
    except FileNotFoundError:
        return
    raise AssertionError("Expected FileNotFoundError")


def test_executor_blocks_unapproved_trajectory(tmp_path: Path) -> None:
    result = FontSkeletonPipeline(config=_test_config(), project_root=PROJECT_ROOT).run(
        "I",
        str(FONT_PATH),
        output_root=tmp_path,
    )
    try:
        RobotTrajectoryExecutor(config=_test_config()).execute_previewed_trajectory(
            result["trajectory_json"],
            execute=True,
            confirmation_text="EXECUTE",
            use_mock=True,
        )
    except PermissionError:
        return
    raise AssertionError("Expected PermissionError")


def test_mock_executor_replays_preview_without_approval(tmp_path: Path) -> None:
    result = FontSkeletonPipeline(config=_test_config(), project_root=PROJECT_ROOT).run(
        "L",
        str(FONT_PATH),
        output_root=tmp_path,
    )
    commands = RobotTrajectoryExecutor(config=_test_config()).execute_previewed_trajectory(result["trajectory_json"])
    assert commands
    assert all("pose" in command for command in commands)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        test_font_skeleton_pipeline_writes_required_artifacts(base / "artifacts")
        test_missing_font_fails_before_robot_work(base / "missing")
        test_executor_blocks_unapproved_trajectory(base / "blocked")
        test_mock_executor_replays_preview_without_approval(base / "mock")
    print("font skeleton pipeline tests passed")
