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
from modules.shape_api import build_shape_poses, list_shapes
from modules.text_trajectory import build_text_pose_strokes, connect_pose_strokes, flatten_strokes


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
PAPER_CORNERS_TEST = "paper_corners"
KEYBOARD_TEXT = "keyboard_text"


def list_menu_actions() -> tuple[str, ...]:
    return (*list_shapes(), PAPER_CORNERS_TEST, KEYBOARD_TEXT)


def choose_shape(default_shape: str) -> str:
    shapes = list_menu_actions()
    print("[SHAPE_MENU] Available shapes:")
    for index, shape in enumerate(shapes, start=1):
        default_mark = " (default)" if shape == default_shape else ""
        print(f"  {index}. {shape}{default_mark}")

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
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})
    shape_config = config.get("shape_demo", {})
    text_config = config.get("text_demo", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})

    default_shape = str(shape_config.get("default_shape", "circle"))
    shape_name = args.shape or choose_shape(default_shape)
    is_corner_test = shape_name == PAPER_CORNERS_TEST
    is_keyboard_text = shape_name == KEYBOARD_TEXT
    text_strokes = None
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
    else:
        poses = build_shape_poses(config, shape_name)

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
    enable_move = bool(config["enable_robot_move"])
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))

    print("[SHAPE_MENU] Config:", CONFIG_PATH)
    print("[SHAPE_MENU] Selected shape:", shape_name)
    if is_keyboard_text:
        print("[SHAPE_MENU] Text stroke count:", len(text_strokes or []))
        print("[SHAPE_MENU] Text continuous:", bool(text_config.get("continuous", True)))
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
        print("[SHAPE_MENU] This script will connect and check IK, but will NOT send MoveL")

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )

    try:
        controller.connect()
        if text_strokes is not None and not bool(text_config.get("continuous", True)):
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
            )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
