from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib.font_manager import FontProperties, findfont

from src.outline_to_skeleton import export_debug_svg, export_robot_json, text_to_robot_paths
from modules.safety_check import validate_pose_workspace
from src.robot.fairino_path_adapter import (
    connect_nearby_pose_strokes,
    dry_run_print_pose_strokes,
    load_robot_paths,
    robot_paths_to_measured_paper_poses,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-flow test: keyboard text -> centerline path -> Fairino dry-run/apply."
    )
    parser.add_argument("--text", help="Text to write. If omitted, prompt from keyboard.")
    parser.add_argument("--font", help="Optional .ttf/.otf font path. Defaults to DejaVu Sans.")
    parser.add_argument("--config", default=str(ROOT / "config" / "robot_config.json"))
    parser.add_argument("--out", default=str(ROOT / "output" / "keyboard_robot_path.json"))
    parser.add_argument("--debug-svg", default=str(ROOT / "output" / "keyboard_centerline.svg"))
    parser.add_argument("--font-size", type=int, default=200)
    parser.add_argument("--resolution", type=float, default=2.0)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--safe-z", type=float, help="Pen lift height between strokes.")
    parser.add_argument("--margin", type=float, help="Paper margin in mm. Defaults to config paper.margin_mm.")
    parser.add_argument("--fit-width", type=float, default=90.0, help="Target text width on paper in mm.")
    parser.add_argument("--fit-height", type=float, default=80.0, help="Target text height on paper in mm.")
    parser.add_argument("--invert-y", dest="invert_y", action="store_true", help="Flip fitted text vertically on the paper.")
    parser.add_argument("--no-flip-y", dest="invert_y", action="store_false", help="Disable vertical flip.")
    parser.add_argument("--vel", type=float, help="Writing velocity.")
    parser.add_argument("--travel-vel", type=float, help="Travel velocity while pen is lifted.")
    parser.add_argument("--connect-gap", type=float, default=8.0, help="Connect stroke endpoints closer than this many mm.")
    parser.add_argument("--no-connect", action="store_true", help="Disable nearby stroke connection.")
    parser.add_argument("--apply", action="store_true", help="Send motion to robot. Without this, only dry-run.")
    parser.add_argument("--yes", action="store_true", help="Skip RUN confirmation when --apply is used.")
    parser.add_argument("--verbose", action="store_true", help="Print every planned MoveL during dry-run.")
    parser.add_argument(
        "--return-start-only",
        action="store_true",
        help="Only move to the lifted first pose for this text path; do not write.",
    )
    parser.add_argument(
        "--no-return-start",
        action="store_true",
        help="Do not return to after_draw.return_pose after finishing.",
    )
    parser.set_defaults(invert_y=True)
    args = parser.parse_args()

    text = args.text
    if text is None:
        text = input("Nhap chu can robot viet: ").strip()
    if not text:
        raise ValueError("Text must not be empty")

    font_path = Path(args.font) if args.font else Path(findfont(FontProperties(family="DejaVu Sans")))
    if not font_path.is_file():
        raise FileNotFoundError(f"Font not found: {font_path}")

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    paper = config["paper"]
    smooth = config.get("smooth_writing", {})
    orientation = paper.get("draw_orientation", [0.0, 0.0, 0.0])
    safe_z = float(args.safe_z if args.safe_z is not None else config.get("text_demo", {}).get("travel_z_offset", 20.0))
    vel = float(args.vel if args.vel is not None else smooth.get("writing_speed_mm_s", config.get("default_vel", 10.0)))
    travel_vel = float(args.travel_vel if args.travel_vel is not None else smooth.get("travel_speed_mm_s", vel))

    print("[1/3] Converting text outline to centerline robot path...")
    robot_paths = text_to_robot_paths(
        text,
        str(font_path),
        font_size=args.font_size,
        resolution=args.resolution,
        z_light=args.z_light,
        z_heavy=args.z_heavy,
    )
    export_robot_json(robot_paths, args.out)
    export_debug_svg(robot_paths, args.debug_svg)

    print("[2/3] Converting centerline x/y/z to Fairino poses...")
    loaded_paths = load_robot_paths(args.out)
    pose_strokes = robot_paths_to_measured_paper_poses(
        loaded_paths,
        paper,
        margin_mm=args.margin,
        orientation=orientation,
        invert_y=args.invert_y,
        fit_width_mm=args.fit_width,
        fit_height_mm=args.fit_height,
    )
    raw_stroke_count = len(pose_strokes)
    if not args.no_connect:
        pose_strokes = connect_nearby_pose_strokes(pose_strokes, args.connect_gap)
    point_count = sum(len(stroke) for stroke in pose_strokes)
    poses = [pose for stroke in pose_strokes for pose in stroke]
    for pose in poses:
        validate_pose_workspace(pose, config["robot_workspace"])
        lifted = list(pose)
        lifted[2] = round(float(lifted[2]) + safe_z, 3)
        validate_pose_workspace(lifted, config["robot_workspace"])
    return_pose = None
    if not args.no_return_start:
        configured_return = config.get("after_draw", {}).get("return_pose")
        if configured_return is not None:
            return_pose = [float(value) for value in configured_return]
        else:
            return_pose = list(pose_strokes[0][0])
            return_pose[2] = round(float(return_pose[2]) + safe_z, 3)
        validate_pose_workspace(return_pose, config["robot_workspace"])
    print(f"Text: {text}")
    print(f"Font: {font_path}")
    print(f"Debug SVG: {args.debug_svg}")
    print(f"Robot JSON: {args.out}")
    print(f"Robot strokes: {len(pose_strokes)} connected from {raw_stroke_count}")
    print(f"Robot points: {point_count}")
    print("Paper mapping: measured corners")
    print(f"Orientation: {orientation}")
    print(f"Margin: {float(args.margin if args.margin is not None else paper.get('margin_mm', 0.0))}mm")
    print(f"Fit size: width={args.fit_width}mm, height={args.fit_height}mm")
    print(f"Flip Y: {args.invert_y}")
    print(f"Connect gap: {'disabled' if args.no_connect else str(args.connect_gap) + 'mm'}")
    print(f"Safe lift: {safe_z}mm")
    print(f"Velocity: write={vel}, travel={travel_vel}")
    print(f"First pose: {pose_strokes[0][0]}")
    print(f"Last pose: {pose_strokes[-1][-1]}")
    print(f"Return pose: {return_pose if return_pose is not None else 'disabled'}")

    print("[3/3] Robot execution mode...")
    if args.return_start_only:
        if return_pose is None:
            raise RuntimeError("--return-start-only requires return pose; remove --no-return-start")
        if not args.apply:
            print(f"Dry-run return start only. MoveL return pose: {return_pose}")
            return

        enable_move = bool(config.get("enable_robot_move", False))
        allow_raw_motion = bool(config.get("connection_policy", {}).get("allow_raw_xmlrpc_motion", False))
        if not enable_move or not allow_raw_motion:
            raise RuntimeError(
                "Robot motion is blocked by config. Set enable_robot_move=true and "
                "connection_policy.allow_raw_xmlrpc_motion=true only after safety checks."
            )
        if not args.yes:
            confirm = input("Type RUN to move robot back to lifted start pose: ").strip()
            if confirm != "RUN":
                print("Cancelled.")
                return

        from modules.fairino_raw_controller import FairinoRawXmlRpcController

        controller = FairinoRawXmlRpcController(
            robot_ip=str(config["robot_ip"]),
            tool=int(config.get("tool", 0)),
            user=int(config.get("user", 0)),
        )
        try:
            controller.connect()
            controller.move_l(
                return_pose,
                vel=travel_vel,
                enable_move=enable_move,
                allow_raw_xmlrpc_motion=allow_raw_motion,
            )
        finally:
            controller.disconnect()
        return

    if not args.apply:
        if args.verbose:
            dry_run_print_pose_strokes(pose_strokes, safe_z)
        else:
            print("Dry-run only. Add --verbose to print every MoveL, or --apply to send motion.")
        return

    enable_move = bool(config.get("enable_robot_move", False))
    allow_raw_motion = bool(config.get("connection_policy", {}).get("allow_raw_xmlrpc_motion", False))
    if not enable_move or not allow_raw_motion:
        raise RuntimeError(
            "Robot motion is blocked by config. Set enable_robot_move=true and "
            "connection_policy.allow_raw_xmlrpc_motion=true only after safety checks."
        )

    if not args.yes:
        confirm = input("Type RUN to send this centerline path to the robot: ").strip()
        if confirm != "RUN":
            print("Cancelled.")
            return

    from modules.fairino_raw_controller import FairinoRawXmlRpcController

    controller = FairinoRawXmlRpcController(
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
    )
    try:
        controller.connect()
        controller.draw_pose_strokes(
            strokes=pose_strokes,
            return_pose=return_pose,
            vel=vel,
            travel_vel=travel_vel,
            travel_z_offset=safe_z,
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
