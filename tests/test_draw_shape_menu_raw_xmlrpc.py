import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import (
    CORNER_KEYS,
    build_lifted_corner_pose,
    build_measured_corner_test_poses,
    get_paper_corners,
    paper_size_from_corners,
)
from modules.safety_check import validate_measured_paper_poses, validate_pose_workspace
from modules.shape_api import build_shape_pose_strokes, list_shapes
from modules.svg_trajectory import build_custom_svg_pose_strokes
from modules.trajectory_planner import config_from_robot_config, plan_pose_strokes
from modules.text_trajectory import build_text_pose_strokes, connect_pose_strokes, flatten_strokes
from src.svg.svg_to_strokes import load_svg_as_strokes, save_stroke_preview


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
PAPER_CORNERS_TEST = "paper_corners"
KEYBOARD_TEXT = "keyboard_text"
CUSTOM_SVG = "custom_svg"


def list_menu_actions() -> tuple[str, ...]:
    return (*list_shapes(), PAPER_CORNERS_TEST, KEYBOARD_TEXT, CUSTOM_SVG)


def choose_shape(default_shape: str) -> str:
    shapes = list_menu_actions()
    print("[SHAPE_MENU] Available shapes:")
    for index, shape in enumerate(shapes, start=1):
        default_mark = " (default)" if shape == default_shape else ""
        label = "[SVG] Load and write custom SVG" if shape == CUSTOM_SVG else shape
        print(f"  {index}. {label}{default_mark}")

    raw_choice = input(f"Select shape [default: {default_shape}]: ").strip()
    if not raw_choice:
        return default_shape

    if raw_choice.isdigit():
        index = int(raw_choice)
        if 1 <= index <= len(shapes):
            return shapes[index - 1]
        raise ValueError(f"Shape menu index out of range: {index}")

    shape = raw_choice.lower()
    if shape not in shapes:
        raise ValueError(f"Unknown shape: {shape}")
    return shape


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw a simple shape inside the measured paper zone.")
    parser.add_argument(
        "--shape",
        choices=list_menu_actions(),
        help="Shape or paper-corner test to run. If omitted, an interactive menu is shown.",
    )
    parser.add_argument("--text", help="Text to write when --shape keyboard_text is selected.")
    parser.add_argument("--svg", help="SVG path to write when --shape custom_svg is selected.")
    parser.add_argument("--preview", action="store_true", help="Save a stroke order preview for custom SVG.")
    parser.add_argument("--dry-run", action="store_true", help="Print/validate trajectory without sending motion.")
    parser.add_argument("--yes", action="store_true", help="Skip the final motion confirmation prompt.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})
    shape_config = config.get("shape_demo", {})
    text_config = config.get("text_demo", {})
    smooth_config = config.get("smooth_writing", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})

    default_shape = str(shape_config.get("default_shape", "circle"))
    shape_name = args.shape or choose_shape(default_shape)
    is_corner_test = shape_name == PAPER_CORNERS_TEST
    is_keyboard_text = shape_name == KEYBOARD_TEXT
    is_custom_svg = shape_name == CUSTOM_SVG
    text_strokes = None
    shape_strokes = None
    custom_svg_path = None
    if is_corner_test:
        poses = build_measured_corner_test_poses(config)
    elif is_keyboard_text:
        text_to_write = args.text
        if text_to_write is None:
            text_to_write = input("Text to write: ").strip()
        text_strokes = build_text_pose_strokes(config, text_to_write)
        if bool(text_config.get("continuous", True)):
            poses = connect_pose_strokes(text_strokes)
        else:
            poses = flatten_strokes(text_strokes)
    elif is_custom_svg:
        raw_svg = args.svg or input("SVG file path: ").strip()
        if not raw_svg:
            raise ValueError("SVG file path is required for custom_svg")
        custom_svg_path = Path(raw_svg)
        if not custom_svg_path.is_absolute():
            custom_svg_path = PROJECT_ROOT / custom_svg_path
        shape_strokes = build_custom_svg_pose_strokes(config, custom_svg_path)
        poses = flatten_strokes(shape_strokes)
        if args.preview:
            preview_config = dict(config.get("svg_pipeline", {}))
            parsed_svg_strokes = load_svg_as_strokes(custom_svg_path, preview_config)
            preview_path = PROJECT_ROOT / "outputs" / f"preview_{custom_svg_path.stem}.png"
            save_stroke_preview(parsed_svg_strokes, preview_path, title=f"SVG stroke order: {custom_svg_path.name}")
            print("[SHAPE_MENU] SVG preview:", preview_path)
    else:
        shape_strokes = build_shape_pose_strokes(config, shape_name)
        poses = flatten_strokes(shape_strokes)

    start_pose = before_draw.get("start_pose")
    return_pose = None
    return_pose_uses_paper_corner = False
    if after_draw.get("return_pose") is not None:
        return_pose = after_draw["return_pose"]
    elif after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))
        return_pose_uses_paper_corner = True

    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)
    enable_move = bool(config["enable_robot_move"]) and not args.dry_run
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))
    if args.dry_run:
        allow_raw_motion = False
    blend_radius = float(motion_strategy.get("blend_radius", -1.0))
    if "blend_radius_mm" in smooth_config:
        blend_radius = float(smooth_config["blend_radius_mm"])
    motion_mode = str(motion_strategy.get("mode", "new_spline")).strip().lower()
    planner_config = config_from_robot_config(config)
    writing_vel = float(smooth_config.get("writing_speed_mm_s", text_config.get("vel", shape_config.get("vel", config["default_vel"]))))
    travel_vel = float(smooth_config.get("travel_speed_mm_s", text_config.get("travel_vel", config["default_vel"])))

    if text_strokes is not None:
        motion_strokes = [poses] if bool(text_config.get("continuous", True)) else text_strokes
    elif is_corner_test:
        motion_strokes = []
    elif shape_strokes is not None:
        motion_strokes = shape_strokes
    else:
        motion_strokes = [poses]
    planned_strokes = plan_pose_strokes(motion_strokes, planner_config) if motion_strokes else []
    planned_pose_count = sum(len(stroke) for stroke in planned_strokes)

    print("[SHAPE_MENU] Config:", CONFIG_PATH)
    print("[SHAPE_MENU] Selected shape:", shape_name)
    if is_custom_svg:
        print("[SHAPE_MENU] SVG:", custom_svg_path)
        xs = [pose[0] for pose in poses]
        ys = [pose[1] for pose in poses]
        zs = [pose[2] for pose in poses]
        print("[SHAPE_MENU] SVG robot bbox:", [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3), round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)])
    if is_keyboard_text:
        print("[SHAPE_MENU] Text stroke count:", len(text_strokes or []))
        print("[SHAPE_MENU] Text continuous:", bool(text_config.get("continuous", True)))
    print("[SHAPE_MENU] Motion mode:", motion_mode)
    print("[SHAPE_MENU] Planned stroke count:", len(planned_strokes))
    print("[SHAPE_MENU] Planned pose count:", planned_pose_count)
    print("[SHAPE_MENU] Measured paper width/height:", round(width, 3), round(height, 3))
    if is_corner_test:
        for corner_name, pose in zip(CORNER_KEYS, poses):
            print(f"[SHAPE_MENU] Paper corner {corner_name}:", pose)
    print("[SHAPE_MENU] Pose count:", len(poses))
    print("[SHAPE_MENU] Start pose:", start_pose)
    print("[SHAPE_MENU] First pose:", poses[0])
    print("[SHAPE_MENU] Last pose:", poses[-1])
    print("[SHAPE_MENU] Return pose:", return_pose)
    print("[SHAPE_MENU] enable_robot_move:", enable_move)
    print("[SHAPE_MENU] allow_raw_xmlrpc_motion:", allow_raw_motion)
    print("[SHAPE_MENU] motion_strategy:", motion_strategy)
    print("[SHAPE_MENU] blend_radius:", blend_radius)
    print("[SHAPE_MENU] dry_run:", args.dry_run)

    if is_corner_test:
        for pose in poses:
            validate_pose_workspace(pose, config["robot_workspace"])
    else:
        validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    if return_pose is not None:
        if return_pose_uses_paper_corner:
            validate_measured_paper_poses([return_pose], config)
        else:
            validate_pose_workspace(return_pose, config["robot_workspace"])
    print("[SHAPE_MENU] Safety validation OK")

    if not enable_move or not allow_raw_motion:
        print("[SHAPE_MENU] SAFETY LOCK: raw XML-RPC movement disabled")
        print("[SHAPE_MENU] This script will not send robot motion")
        if args.dry_run:
            print("[SHAPE_MENU] DRY RUN complete")
            return
    elif not args.yes:
        confirmation = input("Type RUN to start real robot motion: ").strip()
        if confirmation != "RUN":
            print("[SHAPE_MENU] Motion cancelled by user")
            return

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )

    try:
        controller.connect()
        if motion_mode in ("new_spline", "spline", "smooth") and planned_strokes:
            controller.draw_pose_strokes_smooth(
                strokes=planned_strokes,
                start_pose=start_pose,
                return_pose=return_pose,
                vel=writing_vel,
                travel_vel=travel_vel,
                travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
                start_vel=float(before_draw.get("start_vel", config["default_vel"])),
                return_vel=float(after_draw.get("return_vel", config["default_vel"])),
                approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
                approach_vel=float(motion_strategy.get("approach_vel", config["default_vel"])),
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
                blend_radius=blend_radius,
                acceleration=float(smooth_config.get("acceleration", motion_strategy.get("acceleration", 0.0))),
                spline_type=int(motion_strategy.get("spline_type", 1)),
                spline_average_time_ms=int(motion_strategy.get("spline_average_time_ms", 2000)),
                planner_config=planner_config,
                fallback_to_blended_movel=bool(motion_strategy.get("fallback_to_blended_movel", True)),
            )
        elif text_strokes is not None and not bool(text_config.get("continuous", True)):
            controller.draw_pose_strokes(
                strokes=text_strokes,
                start_pose=start_pose,
                return_pose=return_pose,
                vel=float(text_config.get("vel", shape_config.get("vel", config["default_vel"]))),
                travel_vel=float(text_config.get("travel_vel", config["default_vel"])),
                travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
                start_vel=float(before_draw.get("start_vel", config["default_vel"])),
                return_vel=float(after_draw.get("return_vel", config["default_vel"])),
                approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
                approach_vel=float(motion_strategy.get("approach_vel", config["default_vel"])),
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
                blend_radius=blend_radius,
            )
        else:
            controller.draw_polyline_air(
                poses=poses,
                start_pose=start_pose,
                return_pose=return_pose,
                vel=float(text_config.get("vel", shape_config.get("vel", config["default_vel"]))),
                start_vel=float(before_draw.get("start_vel", config["default_vel"])),
                return_vel=float(after_draw.get("return_vel", config["default_vel"])),
                approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
                approach_vel=float(motion_strategy.get("approach_vel", config["default_vel"])),
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
                blend_radius=blend_radius,
            )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
