from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .executor import RobotTrajectoryExecutor
from .pipeline import FontSkeletonPipeline, list_hershey_fonts


def main() -> int:
    parser = argparse.ArgumentParser(description="Font outline to skeleton robot trajectory preview/execution.")
    parser.add_argument("--text", help="Keyboard text to render into a skeleton trajectory.")
    parser.add_argument("--text-file", help="UTF-8 text file to render; useful for Vietnamese diacritics on Windows shells.")
    parser.add_argument("--font", help="TTF/OTF font path.")
    parser.add_argument("--hershey-font", help="Built-in Hershey stroke font name, for example scripts or cursive.")
    parser.add_argument("--list-hershey-fonts", action="store_true", help="List built-in Hershey stroke fonts.")
    parser.add_argument("--font-size", type=int, default=None)
    parser.add_argument("--output-width-mm", type=float, default=None)
    parser.add_argument("--output-height-mm", type=float, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--trajectory", help="Existing robot_trajectory.json.")
    parser.add_argument("--preview-only", action="store_true", help="Generate or replay without robot motion.")
    parser.add_argument("--approve", action="store_true", help="Mark a safe trajectory JSON as reviewed.")
    parser.add_argument("--execute", action="store_true", help="Execute an approved trajectory.")
    parser.add_argument("--mock", action="store_true", help="Use mock robot execution.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(message)s")

    input_text = args.text
    if args.text_file:
        input_text = Path(args.text_file).read_text(encoding="utf-8").strip()

    if args.list_hershey_fonts:
        for name in list_hershey_fonts():
            print(name)
        return 0

    if input_text:
        if args.hershey_font:
            result = FontSkeletonPipeline().run_hershey(
                text=input_text,
                hershey_font=args.hershey_font,
                output_width_mm=args.output_width_mm,
                output_height_mm=args.output_height_mm,
                output_root=args.output_root,
            )
        else:
            if not args.font:
                parser.error("--font or --hershey-font is required with --text or --text-file")
            result = FontSkeletonPipeline().run(
                text=input_text,
                font_path=args.font,
                font_size=args.font_size,
                output_width_mm=args.output_width_mm,
                output_height_mm=args.output_height_mm,
                output_root=args.output_root,
            )
        print("[PREVIEW] Trajectory generated and not sent to robot.")
        print("Preview PNG:", result["preview_png"])
        print("Preview SVG:", result["preview_svg"])
        print("CSV:", result["trajectory_csv"])
        print("JSON:", result["trajectory_json"])
        print("Validation safe:", result["validation"]["is_safe"])
        return 0

    if args.trajectory and args.approve:
        path = Path(args.trajectory)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("validation", {}).get("is_safe", False):
            raise RuntimeError("Cannot approve a trajectory that failed validation.")
        answer = input("Type REVIEWED to mark this trajectory as approved: ").strip()
        if answer != "REVIEWED":
            print("[SAFETY] Approval canceled.")
            return 1
        payload["approved"] = True
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[SAFETY] Trajectory marked approved:", path)
        return 0

    if args.trajectory:
        if args.execute:
            confirm = input("Type EXECUTE to send this reviewed trajectory to the robot: ").strip()
            result = RobotTrajectoryExecutor().execute_previewed_trajectory(
                args.trajectory,
                execute=True,
                require_confirmation=True,
                confirmation_text=confirm,
                use_mock=bool(args.mock),
            )
            print("[ROBOT] Execution result:", result)
        else:
            result = RobotTrajectoryExecutor().execute_previewed_trajectory(args.trajectory, execute=False, use_mock=True)
            print("[MOCK] Command count:", len(result))
        return 0

    parser.error("Use --text with --font, or --trajectory")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
