from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.robot.fairino_path_adapter import execute_robot_path_json, load_robot_paths, robot_paths_to_poses


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run or execute a centerline robot path JSON on Fairino.")
    parser.add_argument("--path-json", default=str(ROOT / "output" / "keyboard_robot_path.json"))
    parser.add_argument("--config", default=str(ROOT / "config" / "robot_config.json"))
    parser.add_argument("--scale", type=float, default=1.0, help="Scale path x/y units to robot mm.")
    parser.add_argument("--safe-z", type=float, help="Pen lift height between strokes.")
    parser.add_argument("--vel", type=float, help="Writing velocity.")
    parser.add_argument("--travel-vel", type=float, help="Travel velocity while pen is lifted.")
    parser.add_argument("--apply", action="store_true", help="Send motion to robot. Without this, only dry-run.")
    parser.add_argument("--yes", action="store_true", help="Skip RUN confirmation when --apply is used.")
    parser.add_argument("--verbose", action="store_true", help="Print every planned MoveL in dry-run.")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    paper = config["paper"]
    motion = config.get("motion_strategy", {})
    smooth = config.get("smooth_writing", {})

    paper_origin = {
        "x": float(paper.get("origin_x", 0.0)),
        "y": float(paper.get("origin_y", 0.0)),
        "z": float(paper.get("paper_z", smooth.get("writing_z", 0.0))),
    }
    orientation = paper.get("draw_orientation", [0.0, 0.0, 0.0])
    safe_z = float(args.safe_z if args.safe_z is not None else config.get("text_demo", {}).get("travel_z_offset", 20.0))
    vel = float(args.vel if args.vel is not None else smooth.get("writing_speed_mm_s", config.get("default_vel", 10.0)))
    travel_vel = float(args.travel_vel if args.travel_vel is not None else smooth.get("travel_speed_mm_s", vel))

    robot_paths = load_robot_paths(args.path_json)
    pose_strokes = robot_paths_to_poses(robot_paths, paper_origin, args.scale, orientation)
    point_count = sum(len(stroke) for stroke in pose_strokes)
    print(f"Path JSON: {args.path_json}")
    print(f"Robot strokes: {len(pose_strokes)}")
    print(f"Robot points: {point_count}")
    print(f"Paper origin: {paper_origin}")
    print(f"Orientation: {orientation}")
    print(f"Scale: {args.scale}")
    print(f"Safe lift: {safe_z}mm")
    print(f"Velocity: write={vel}, travel={travel_vel}")
    print(f"First pose: {pose_strokes[0][0]}")
    print(f"Last pose: {pose_strokes[-1][-1]}")

    if not args.apply:
        if args.verbose:
            execute_robot_path_json(
                args.path_json,
                paper_origin=paper_origin,
                scale=args.scale,
                safe_z=safe_z,
                orientation=orientation,
                dry_run=True,
            )
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

    execute_robot_path_json(
        args.path_json,
        paper_origin=paper_origin,
        scale=args.scale,
        safe_z=safe_z,
        orientation=orientation,
        robot_ip=str(config["robot_ip"]),
        tool=int(config.get("tool", 0)),
        user=int(config.get("user", 0)),
        vel=vel,
        travel_vel=travel_vel,
        dry_run=False,
        enable_move=enable_move,
        allow_raw_xmlrpc_motion=allow_raw_motion,
    )


if __name__ == "__main__":
    main()
