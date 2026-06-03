from __future__ import annotations

import argparse

from .export_robot_path import export_robot_json
from .export_svg import export_debug_svg
from .pipeline import svg_outline_to_robot_paths, text_to_robot_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert text/font or SVG outline to centerline robot paths with Z-depth.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to convert, for example 'Tâm'")
    group.add_argument("--input-svg", help="Closed outline SVG to convert")
    parser.add_argument("--font", help="Font file for --text")
    parser.add_argument("--font-size", type=int, default=200)
    parser.add_argument("--resolution", type=float, default=2.0)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--output-scale", type=float, default=1.0)
    parser.add_argument("--min-branch-length", type=float, default=2.0, help="Minimum length of a stroke in world units to be kept")
    parser.add_argument("--out", required=True, help="Output robot JSON path")
    parser.add_argument("--debug-svg", help="Output centerline-only debug SVG path")
    parser.add_argument("--show-radius", action="store_true", help="Draw debug radius markers on centerline SVG")
    args = parser.parse_args()
 
    if args.text is not None:
        if not args.font:
            parser.error("--font is required when using --text")
        robot_paths = text_to_robot_paths(
            args.text,
            args.font,
            font_size=args.font_size,
            resolution=args.resolution,
            z_light=args.z_light,
            z_heavy=args.z_heavy,
            output_scale=args.output_scale,
            min_branch_length=args.min_branch_length,
        )
    else:
        robot_paths = svg_outline_to_robot_paths(
            args.input_svg,
            resolution=args.resolution,
            z_light=args.z_light,
            z_heavy=args.z_heavy,
            output_scale=args.output_scale,
            min_branch_length=args.min_branch_length,
        )

    export_robot_json(robot_paths, args.out)
    if args.debug_svg:
        export_debug_svg(robot_paths, args.debug_svg, show_radius=args.show_radius)
    print(f"Wrote {len(robot_paths)} centerline strokes to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
