import json
from pathlib import Path
from typing import Any

from modules.paper_zone import (
    build_lifted_corner_pose,
    build_line_demo_poses,
)
from modules.shape_api import build_shape_poses
from modules.svg_trajectory import build_svg_poses
from modules.text_trajectory import build_text_pose_strokes, connect_pose_strokes, flatten_strokes

from src.services.config_service import get_config
from src.services.robot_service import _times_outline_text_config
from src.outline_to_skeleton import text_to_robot_paths
from src.robot.fairino_path_adapter import (
    robot_paths_to_measured_paper_poses,
    prune_short_pose_strokes,
    connect_nearby_pose_strokes,
    trim_pose_stroke_ends,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORD_LIBRARY_PATH = PROJECT_ROOT / "config" / "word_library.json"


def build_line_preview() -> dict[str, Any]:
    config = get_config()
    use_measured_paper = "corners" in config.get("paper", {})
    if use_measured_paper:
        start_pose, end_pose = build_line_demo_poses(config)
    else:
        start_pose = config["line_demo"]["start_pose"]
        end_pose = config["line_demo"]["end_pose"]

    after_draw = config.get("after_draw", {})
    return_pose = None
    if use_measured_paper and after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))

    return {
        "start_pose": start_pose,
        "end_pose": end_pose,
        "return_pose": return_pose,
        "use_measured_paper": use_measured_paper,
    }


def build_shape_preview(shape_name: str) -> dict[str, Any]:
    config = get_config()
    poses = build_shape_poses(config, shape_name)
    return {"shape": shape_name, "poses": poses}


def build_svg_preview(svg_path: str | None, word_key: str | None) -> dict[str, Any]:
    config = get_config()
    path = _resolve_svg_path(svg_path, word_key)
    poses = build_svg_poses(config, path)
    return {"svg_path": str(path), "poses": poses}


def build_text_preview(text: str, continuous: bool | None) -> dict[str, Any]:
    config = get_config()
    strokes = build_text_pose_strokes(config, text)
    continuous_mode = continuous
    if continuous_mode is None:
        continuous_mode = bool(config.get("text_demo", {}).get("continuous", True))

    poses = connect_pose_strokes(strokes) if continuous_mode else flatten_strokes(strokes)
    return {
        "text": text,
        "continuous": continuous_mode,
        "stroke_count": len(strokes),
        "poses": poses,
    }


def build_text_outline_times_preview(text: str, continuous: bool | None) -> dict[str, Any]:
    config = _times_outline_text_config(get_config())
    strokes = build_text_pose_strokes(config, text)
    continuous_mode = continuous
    if continuous_mode is None:
        continuous_mode = bool(config.get("text_demo", {}).get("continuous", False))

    poses = connect_pose_strokes(strokes) if continuous_mode else flatten_strokes(strokes)
    return {
        "text": text,
        "continuous": continuous_mode,
        "font_family": "Times New Roman",
        "text_mode": "outline",
        "stroke_count": len(strokes),
        "poses": poses,
    }


def build_text_skeleton_times_preview(text: str, continuous: bool | None) -> dict[str, Any]:
    config = get_config()
    text_demo = config.get("text_demo", {})
    paper = config.get("paper", {})

    font_path = str(text_demo.get("times_font_path", "C:/Windows/Fonts/times.ttf"))
    if not Path(font_path).is_file():
        font_path = "C:/Windows/Fonts/times.ttf"

    # Extract skeleton centerline (x, y, z)
    robot_paths = text_to_robot_paths(
        text=text,
        font_path=font_path,
        font_size=200,
        resolution=2.0,
        z_light=-0.5,
        z_heavy=-3.0,
        point_spacing=1.0,
        min_branch_length=4.0,
        simplify_tolerance=0.05,
        theta=1.5,
    )

    orientation = paper.get("draw_orientation", [0.0, 0.0, 0.0])
    pose_strokes = robot_paths_to_measured_paper_poses(
        robot_paths=robot_paths,
        paper_config=paper,
        margin_mm=paper.get("margin_mm", 20.0),
        orientation=orientation,
        invert_y=True,
        fit_width_mm=90.0,
        fit_height_mm=80.0,
    )

    prune_tip_length = 28.0
    connect_gap = 8.0
    trim_ends = 3.0

    pose_strokes = prune_short_pose_strokes(pose_strokes, prune_tip_length)
    continuous_mode = bool(continuous)
    if not continuous_mode:
        pose_strokes = connect_nearby_pose_strokes(pose_strokes, connect_gap)
    else:
        pose_strokes = connect_nearby_pose_strokes(pose_strokes, 9999.0)

    pose_strokes = trim_pose_stroke_ends(pose_strokes, trim_ends)
    poses = [pose for stroke in pose_strokes for pose in stroke]

    return {
        "text": text,
        "continuous": continuous_mode,
        "font_family": "Times New Roman",
        "text_mode": "skeleton",
        "stroke_count": len(pose_strokes),
        "poses": poses,
    }


def _resolve_svg_path(svg_path: str | None, word_key: str | None) -> Path:
    if svg_path:
        return PROJECT_ROOT / svg_path

    if word_key:
        library = json.loads(WORD_LIBRARY_PATH.read_text(encoding="utf-8"))
        if word_key not in library:
            raise ValueError(f"Unknown word_key: {word_key}")
        return PROJECT_ROOT / library[word_key]

    config = get_config()
    svg_demo = config.get("svg_demo", {})
    return PROJECT_ROOT / str(svg_demo.get("svg_path", "assets/svg/tam.svg"))
