import argparse
import json
import sys
from math import cos, pi, sin
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import build_pose_in_paper, get_paper_corners, paper_size_from_corners
from modules.safety_check import validate_measured_paper_poses, validate_pose_workspace
from modules.text_trajectory import build_text_pose_strokes, flatten_strokes
from modules.trajectory_planner import config_from_robot_config, plan_pose_strokes


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
TESTS = ("line_50mm", "oval", "bezier", "tam", "phuc")


def choose_test(default_name: str) -> str:
    print("[SMOOTH_MENU] Available tests:")
    for index, name in enumerate(TESTS, start=1):
        default_mark = " (default)" if name == default_name else ""
        print(f"  {index}. {name}{default_mark}")
    raw = input(f"Select test [default: {default_name}]: ").strip()
    if not raw:
        return default_name
    if raw.isdigit():
        index = int(raw)
        if 1 <= index <= len(TESTS):
            return TESTS[index - 1]
    if raw not in TESTS:
        raise ValueError(f"Unknown smooth test: {raw}")
    return raw


def build_test_strokes(config: dict, test_name: str) -> list[list[list[float]]]:
    if test_name == "line_50mm":
        corners = get_paper_corners(config)
        width, _height = paper_size_from_corners(corners)
        half_u = 25.0 / width
        return [[build_pose_in_paper(config, 0.5 - half_u, 0.5), build_pose_in_paper(config, 0.5 + half_u, 0.5)]]

    if test_name == "oval":
        points = []
        for index in range(97):
            angle = 2.0 * pi * index / 96
            points.append(build_pose_in_paper(config, 0.5 + 0.18 * cos(angle), 0.5 + 0.11 * sin(angle)))
        return [points]

    if test_name == "bezier":
        control = ((0.25, 0.65), (0.38, 0.15), (0.68, 0.85), (0.78, 0.35))
        points = []
        for index in range(80):
            t = index / 79
            mt = 1.0 - t
            u = mt**3 * control[0][0] + 3 * mt**2 * t * control[1][0] + 3 * mt * t**2 * control[2][0] + t**3 * control[3][0]
            v = mt**3 * control[0][1] + 3 * mt**2 * t * control[1][1] + 3 * mt * t**2 * control[2][1] + t**3 * control[3][1]
            points.append(build_pose_in_paper(config, u, v))
        return [points]

    if test_name == "tam":
        return build_text_pose_strokes(config, "Tam")
    if test_name == "phuc":
        return build_text_pose_strokes(config, "Phuc")
    raise ValueError(f"Unknown smooth test: {test_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smooth Fairino writing tests with dry-run by default.")
    parser.add_argument("--test", choices=TESTS, help="Smooth writing test to run.")
    parser.add_argument("--apply", action="store_true", help="Send real robot motion after confirmation.")
    parser.add_argument("--yes", action="store_true", help="Skip the final motion confirmation prompt.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})
    motion_strategy = config.get("motion_strategy", {})
    smooth_config = config.get("smooth_writing", {})
    text_config = config.get("text_demo", {})

    test_name = args.test or choose_test("line_50mm")
    strokes = build_test_strokes(config, test_name)
    planner_config = config_from_robot_config(config)
    planned_strokes = plan_pose_strokes(strokes, planner_config)
    poses = flatten_strokes(planned_strokes)

    start_pose = before_draw.get("start_pose")
    return_pose = after_draw.get("return_pose")
    enable_move = bool(config["enable_robot_move"]) and args.apply
    allow_motion = bool(policy.get("allow_raw_xmlrpc_motion", False)) and args.apply
    blend_radius = float(smooth_config.get("blend_radius_mm", motion_strategy.get("blend_radius", 0.0)))

    print("[SMOOTH_MENU] Config:", CONFIG_PATH)
    print("[SMOOTH_MENU] Test:", test_name)
    print("[SMOOTH_MENU] Raw stroke count:", len(strokes))
    print("[SMOOTH_MENU] Planned stroke count:", len(planned_strokes))
    print("[SMOOTH_MENU] Planned pose count:", len(poses))
    print("[SMOOTH_MENU] First pose:", poses[0])
    print("[SMOOTH_MENU] Last pose:", poses[-1])
    print("[SMOOTH_MENU] apply:", args.apply)
    print("[SMOOTH_MENU] blend_radius:", blend_radius)

    validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    if return_pose is not None:
        validate_pose_workspace(return_pose, config["robot_workspace"])
    print("[SMOOTH_MENU] Safety validation OK")

    if not enable_move or not allow_motion:
        print("[SMOOTH_MENU] DRY RUN: no robot motion will be sent")
        if not args.apply:
            print("[SMOOTH_MENU] DRY RUN complete")
            return
    elif not args.yes:
        confirmation = input("Type RUN to start real robot motion: ").strip()
        if confirmation != "RUN":
            print("[SMOOTH_MENU] Motion cancelled by user")
            return

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )

    try:
        controller.connect()
        controller.draw_pose_strokes_smooth(
            strokes=planned_strokes,
            start_pose=start_pose,
            return_pose=return_pose,
            vel=float(smooth_config.get("writing_speed_mm_s", text_config.get("vel", config["default_vel"]))),
            travel_vel=float(smooth_config.get("travel_speed_mm_s", text_config.get("travel_vel", config["default_vel"]))),
            travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
            start_vel=float(before_draw.get("start_vel", config["default_vel"])),
            return_vel=float(after_draw.get("return_vel", config["default_vel"])),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config["default_vel"])),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_motion,
            blend_radius=blend_radius,
            acceleration=float(smooth_config.get("acceleration", motion_strategy.get("acceleration", 0.0))),
            spline_type=int(motion_strategy.get("spline_type", 1)),
            spline_average_time_ms=int(motion_strategy.get("spline_average_time_ms", 2000)),
            planner_config=planner_config,
            fallback_to_blended_movel=bool(motion_strategy.get("fallback_to_blended_movel", True)),
        )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
