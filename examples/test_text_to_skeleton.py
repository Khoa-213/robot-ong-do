from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib.font_manager import FontProperties, findfont

from src.outline_to_skeleton import export_debug_svg, export_robot_json, text_to_robot_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert keyboard text to centerline robot paths.")
    parser.add_argument("--text", help="Text to convert. If omitted, prompt from keyboard.")
    parser.add_argument("--font", help="Optional .ttf/.otf font path. Defaults to DejaVu Sans.")
    parser.add_argument("--font-size", type=int, default=200)
    parser.add_argument("--resolution", type=float, default=2.0)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--out", default=str(ROOT / "output" / "keyboard_robot_path.json"))
    parser.add_argument("--debug-svg", default=str(ROOT / "output" / "keyboard_centerline.svg"))
    args = parser.parse_args()

    text = args.text
    if text is None:
        text = input("Nhap chu can test: ").strip()
    if not text:
        raise ValueError("Text must not be empty")

    font_path = Path(args.font) if args.font else Path(findfont(FontProperties(family="DejaVu Sans")))
    if not font_path.is_file():
        raise FileNotFoundError(f"Font not found: {font_path}")

    robot_paths = text_to_robot_paths(
        text,
        str(font_path),
        font_size=args.font_size,
        resolution=args.resolution,
        z_light=args.z_light,
        z_heavy=args.z_heavy,
    )
    export_debug_svg(robot_paths, args.debug_svg)
    export_robot_json(robot_paths, args.out)
    print(f"Text: {text}")
    print(f"Font: {font_path}")
    print(f"Debug SVG: {args.debug_svg}")
    print(f"Robot JSON: {args.out}")
    print(f"Generated {sum(len(stroke) for stroke in robot_paths)} points in {len(robot_paths)} centerline strokes")


if __name__ == "__main__":
    main()
