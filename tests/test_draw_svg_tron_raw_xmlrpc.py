import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import build_lifted_corner_pose, get_paper_corners, paper_size_from_corners
from modules.safety_check import validate_measured_paper_poses, validate_pose_workspace
from modules.svg_trajectory import build_svg_pose_strokes
from modules.trajectory_planner import config_from_robot_config, plan_pose_strokes


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
DEFAULT_SVG_PATH = PROJECT_ROOT / "assets" / "svg" / "tron.svg"
LOG_PREFIX = "[RAW_SVG_TRON]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw assets/svg/tron.svg as separate SVG strokes.")
    parser.add_argument("--svg", default=str(DEFAULT_SVG_PATH), help="SVG path to draw.")
    parser.add_argument("--dry-run", action="store_true", help="Print/validate trajectory without sending motion.")
    parser.add_argument("--yes", action="store_true", help="Skip the final motion confirmation prompt.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})
    smooth_config = config.get("smooth_writing", {})
    svg_demo = config.get("svg_demo", {})
    text_config = config.get("text_demo", {})
    before_draw = config.get("before_draw", {})
    after_draw = config.get("after_draw", {})

    svg_path = Path(args.svg)
    if not svg_path.is_absolute():
        svg_path = PROJECT_ROOT / svg_path

    strokes = build_svg_pose_strokes(config, svg_path)
    poses = [pose for stroke in strokes for pose in stroke]

    planner_config = config_from_robot_config(config)
    planned_strokes = plan_pose_strokes(strokes, planner_config)
    planned_pose_count = sum(len(stroke) for stroke in planned_strokes)

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
    enable_move = bool(config.get("enable_robot_move", False)) and not args.dry_run
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))
    if args.dry_run:
        allow_raw_motion = False

    blend_radius = float(smooth_config.get("blend_radius_mm", motion_strategy.get("blend_radius", 0.0)))
    writing_vel = float(smooth_config.get("writing_speed_mm_s", svg_demo.get("vel", config.get("default_vel", 10))))
    travel_vel = float(smooth_config.get("travel_speed_mm_s", text_config.get("travel_vel", config.get("default_vel", 10))))

    print(LOG_PREFIX, "Config:", CONFIG_PATH)
    print(LOG_PREFIX, "SVG:", svg_path)
    print(LOG_PREFIX, "Raw stroke count:", len(strokes))
    print(LOG_PREFIX, "Raw pose count:", len(poses))
    print(LOG_PREFIX, "Planned stroke count:", len(planned_strokes))
    print(LOG_PREFIX, "Planned pose count:", planned_pose_count)
    print(LOG_PREFIX, "Measured paper width/height:", round(width, 3), round(height, 3))
    print(LOG_PREFIX, "First pose:", poses[0])
    print(LOG_PREFIX, "Last pose:", poses[-1])
    print(LOG_PREFIX, "Start pose:", start_pose)
    print(LOG_PREFIX, "Return pose:", return_pose)
    print(LOG_PREFIX, "enable_robot_move:", enable_move)
    print(LOG_PREFIX, "allow_raw_xmlrpc_motion:", allow_raw_motion)
    print(LOG_PREFIX, "blend_radius:", blend_radius)
    print(LOG_PREFIX, "dry_run:", args.dry_run)

    validate_measured_paper_poses(poses, config)
    if start_pose is not None:
        validate_pose_workspace(start_pose, config["robot_workspace"])
    if return_pose is not None:
        if return_pose_uses_paper_corner:
            validate_measured_paper_poses([return_pose], config)
        else:
            validate_pose_workspace(return_pose, config["robot_workspace"])
    print(LOG_PREFIX, "Safety validation OK")

    if not enable_move or not allow_raw_motion:
        print(LOG_PREFIX, "SAFETY LOCK: raw XML-RPC movement disabled")
        print(LOG_PREFIX, "This script will not send robot motion")
        if args.dry_run:
            print(LOG_PREFIX, "DRY RUN complete")
            return
    elif not args.yes:
        confirmation = input("Type RUN to start real robot motion: ").strip()
        if confirmation != "RUN":
            print(LOG_PREFIX, "Motion cancelled by user")
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
            vel=writing_vel,
            travel_vel=travel_vel,
            travel_z_offset=float(text_config.get("travel_z_offset", 20.0)),
            start_vel=float(before_draw.get("start_vel", config.get("default_vel", 10))),
            return_vel=float(after_draw.get("return_vel", config.get("default_vel", 10))),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config.get("default_vel", 10))),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
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
