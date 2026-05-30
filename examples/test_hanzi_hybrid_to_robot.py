from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import font_manager
from matplotlib.font_manager import FontProperties, findfont
from shapely.geometry import MultiPolygon, Point
from shapely.ops import unary_union
from svgpathtools import parse_path

from modules.safety_check import validate_pose_workspace
from src.outline_to_skeleton.export_robot_path import export_robot_json
from src.outline_to_skeleton.export_svg import export_debug_svg
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.path_smoothing import moving_average_stroke, resample_stroke
from src.outline_to_skeleton.z_depth import enforce_max_z_step, map_radius_to_z, smooth_z_values
from src.robot.fairino_path_adapter import (
    dry_run_print_pose_strokes,
    export_pose_strokes_json,
    load_robot_paths,
    robot_paths_to_measured_paper_poses,
)


# Normalized, human-authored stroke-order paths. Coordinates are top-left origin.
# This is intentionally not auto-skeletonized; it mimics KanjiVG-style ordered strokes.
ORDERED_HANZI_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    "永": [
        [(0.51, 0.07), (0.45, 0.17)],
        [(0.51, 0.16), (0.51, 0.63), (0.47, 0.75), (0.35, 0.82)],
        [(0.38, 0.31), (0.25, 0.42), (0.15, 0.55)],
        [(0.57, 0.32), (0.71, 0.42), (0.84, 0.55)],
        [(0.49, 0.48), (0.38, 0.58), (0.25, 0.72), (0.12, 0.86)],
        [(0.55, 0.47), (0.64, 0.60), (0.76, 0.74), (0.90, 0.88)],
    ],
    "大": [
        [(0.22, 0.32), (0.78, 0.32)],
        [(0.52, 0.12), (0.50, 0.42), (0.40, 0.66), (0.20, 0.88)],
        [(0.52, 0.42), (0.64, 0.62), (0.82, 0.86)],
    ],
    "人": [
        [(0.56, 0.16), (0.48, 0.40), (0.34, 0.66), (0.18, 0.88)],
        [(0.51, 0.43), (0.64, 0.64), (0.82, 0.88)],
    ],
    "中": [
        [(0.28, 0.25), (0.76, 0.25), (0.76, 0.70), (0.28, 0.70), (0.28, 0.25)],
        [(0.52, 0.10), (0.52, 0.88)],
    ],
}


ORDERED_HANZI_BEZIERS: dict[str, list[str]] = {
    "永": [
        "M 50 9 C 47 14, 44 18, 42 23",
        "M 51 21 C 51 35, 51 50, 51 63 C 50 74, 43 81, 34 86",
        "M 39 34 C 31 42, 23 50, 15 59",
        "M 59 34 C 70 41, 80 50, 88 60",
        "M 49 50 C 39 61, 27 75, 13 90",
        "M 55 49 C 63 63, 75 78, 91 91",
    ],
    "大": [
        "M 22 34 C 38 32, 62 32, 80 34",
        "M 52 13 C 51 33, 48 54, 39 70 C 32 82, 24 90, 16 95",
        "M 52 42 C 61 60, 72 78, 86 93",
    ],
    "人": [
        "M 56 14 C 52 35, 43 59, 30 77 C 24 85, 18 91, 12 96",
        "M 51 43 C 60 61, 72 80, 88 95",
    ],
    "中": [
        "M 28 26 C 42 25, 63 25, 77 26 L 76 70 C 62 72, 42 72, 28 70 Z",
        "M 52 10 C 52 31, 52 59, 52 91",
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid Hanzi test: ordered stroke path + outline-derived Z-depth + Fairino dry-run/apply."
    )
    parser.add_argument("--text", default="永", help="Single built-in Hanzi: 永, 大, 人, 中.")
    parser.add_argument("--font", help="Optional CJK .ttf/.ttc font path. Defaults to Microsoft YaHei/SimSun.")
    parser.add_argument("--font-family", default="", help="CJK font family when --font is omitted.")
    parser.add_argument("--config", default=str(ROOT / "config" / "robot_config.json"))
    parser.add_argument("--out", default=str(ROOT / "output" / "hanzi_hybrid_robot_path.json"))
    parser.add_argument("--debug-svg", default=str(ROOT / "output" / "hanzi_hybrid_centerline.svg"))
    parser.add_argument("--pose-json", default=str(ROOT / "output" / "hanzi_hybrid_robot_poses.json"))
    parser.add_argument("--font-size", type=int, default=240)
    parser.add_argument("--sample-spacing", type=float, default=0.8, help="Path spacing in source font units before paper fit.")
    parser.add_argument(
        "--stroke-source",
        choices=("bezier", "polyline"),
        default="bezier",
        help="Use curved hand-authored strokes or the older rough polylines.",
    )
    parser.add_argument("--fit-width", type=float, default=120.0)
    parser.add_argument("--fit-height", type=float, default=120.0)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--invert-y", dest="invert_y", action="store_true")
    parser.add_argument("--no-flip-y", dest="invert_y", action="store_false")
    parser.set_defaults(invert_y=True)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--vel", type=float)
    parser.add_argument("--travel-vel", type=float)
    parser.add_argument("--safe-z", type=float)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    text = args.text.strip()
    if len(text) != 1 or text not in ORDERED_HANZI_STROKES:
        raise ValueError(f"Only built-in single Hanzi are supported now: {', '.join(ORDERED_HANZI_STROKES)}")

    font_family = args.font_family.strip() or _default_cjk_font_family()
    font_path = Path(args.font) if args.font else Path(findfont(FontProperties(family=font_family)))
    if not font_path.is_file():
        raise FileNotFoundError(f"Font not found: {font_path}")

    print("[1/3] Building ordered hybrid centerline from human stroke-order paths...")
    outlines = text_to_outline_polygons(text, str(font_path), font_size=args.font_size)
    outline_geom = unary_union(outlines)
    if isinstance(outline_geom, MultiPolygon):
        bounds_geom = outline_geom
    else:
        bounds_geom = MultiPolygon([outline_geom])
    min_x, min_y, max_x, max_y = bounds_geom.bounds

    if args.stroke_source == "bezier":
        ordered_paths = _bezier_strokes_to_font_space(ORDERED_HANZI_BEZIERS[text], min_x, min_y, max_x, max_y)
    else:
        ordered_paths = _normalized_strokes_to_font_space(ORDERED_HANZI_STROKES[text], min_x, min_y, max_x, max_y)
    robot_paths = _apply_outline_z_depth(
        ordered_paths,
        outline_geom,
        sample_spacing=args.sample_spacing,
        z_light=args.z_light,
        z_heavy=args.z_heavy,
    )
    export_robot_json(robot_paths, args.out)
    export_debug_svg(robot_paths, args.debug_svg)

    print("[2/3] Fitting hybrid path to measured paper robot coordinates...")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    paper = config["paper"]
    smooth = config.get("smooth_writing", {})
    orientation = paper.get("draw_orientation", [0.0, 0.0, 0.0])
    safe_z = float(args.safe_z if args.safe_z is not None else config.get("text_demo", {}).get("travel_z_offset", 20.0))
    vel = float(args.vel if args.vel is not None else smooth.get("writing_speed_mm_s", config.get("default_vel", 10.0)))
    travel_vel = float(args.travel_vel if args.travel_vel is not None else smooth.get("travel_speed_mm_s", vel))

    pose_strokes = robot_paths_to_measured_paper_poses(
        load_robot_paths(args.out),
        paper,
        margin_mm=args.margin,
        orientation=orientation,
        invert_y=args.invert_y,
        fit_width_mm=args.fit_width,
        fit_height_mm=args.fit_height,
    )
    export_pose_strokes_json(pose_strokes, args.pose_json)

    poses = [pose for stroke in pose_strokes for pose in stroke]
    for pose in poses:
        validate_pose_workspace(pose, config["robot_workspace"])
        lifted = list(pose)
        lifted[2] = round(float(lifted[2]) + safe_z, 3)
        validate_pose_workspace(lifted, config["robot_workspace"])

    return_pose = config.get("after_draw", {}).get("return_pose")
    if return_pose is not None:
        return_pose = [float(value) for value in return_pose]
        validate_pose_workspace(return_pose, config["robot_workspace"])

    print(f"Text: {_safe_text(text)}")
    print(f"Font: {font_path}")
    print(f"Font family: {font_family if not args.font else '(file path)'}")
    print(f"Ordered strokes: {len(robot_paths)}")
    print(f"Stroke source: {args.stroke_source}")
    print(f"Robot points: {sum(len(stroke) for stroke in pose_strokes)}")
    print(f"Debug SVG: {args.debug_svg}")
    print(f"Robot path JSON: {args.out}")
    print(f"Robot pose JSON: {args.pose_json}")
    print(f"Fit size: width={args.fit_width}mm, height={args.fit_height}mm")
    print(f"Flip Y: {args.invert_y}")
    print(f"First pose: {pose_strokes[0][0]}")
    print(f"Last pose: {pose_strokes[-1][-1]}")
    print(f"Return pose: {return_pose if return_pose is not None else 'disabled'}")

    print("[3/3] Robot execution mode...")
    if not args.apply:
        if args.verbose:
            dry_run_print_pose_strokes(pose_strokes, safe_z)
        else:
            print("Dry-run only. Add --verbose to print MoveL, or --apply to send motion.")
        return

    enable_move = bool(config.get("enable_robot_move", False))
    allow_raw_motion = bool(config.get("connection_policy", {}).get("allow_raw_xmlrpc_motion", False))
    if not enable_move or not allow_raw_motion:
        raise RuntimeError("Robot motion is blocked by config safety flags")
    if not args.yes:
        confirm = input("Type RUN to send this hybrid Hanzi path to the robot: ").strip()
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


def _default_cjk_font_family() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for family in ("Microsoft YaHei", "SimSun", "Microsoft JhengHei", "MS Gothic", "Yu Gothic"):
        if family in available:
            return family
    return "DejaVu Sans"


def _safe_text(value: str) -> str:
    return value.encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(
        sys.stdout.encoding or "utf-8"
    )


def _normalized_strokes_to_font_space(
    strokes: list[list[tuple[float, float]]],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> list[list[tuple[float, float, float]]]:
    width = max_x - min_x
    height = max_y - min_y
    return [
        [
            (
                min_x + nx * width,
                max_y - ny * height,
                0.0,
            )
            for nx, ny in stroke
        ]
        for stroke in strokes
    ]


def _bezier_strokes_to_font_space(
    path_defs: list[str],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    samples_per_path: int = 80,
) -> list[list[tuple[float, float, float]]]:
    width = max_x - min_x
    height = max_y - min_y
    strokes = []
    for path_def in path_defs:
        path = parse_path(path_def)
        points = []
        for index in range(samples_per_path + 1):
            t = index / samples_per_path
            point = path.point(t)
            nx = float(point.real) / 100.0
            ny = float(point.imag) / 100.0
            points.append((min_x + nx * width, max_y - ny * height, 0.0))
        strokes.append(points)
    return strokes


def _apply_outline_z_depth(
    strokes: list[list[tuple[float, float, float]]],
    outline_geom,
    sample_spacing: float,
    z_light: float,
    z_heavy: float,
) -> list[list[tuple[float, float, float]]]:
    sampled = [resample_stroke(stroke, sample_spacing) for stroke in strokes]
    radii = []
    for stroke in sampled:
        for x, y, _ in stroke:
            point = Point(x, y)
            radius = outline_geom.boundary.distance(point) if outline_geom.contains(point) else 0.0
            radii.append(float(radius))
    min_radius = min(radii) if radii else 0.0
    max_radius = max(radii) if radii else 1.0

    output = []
    for stroke in sampled:
        z_values = []
        for x, y, _ in stroke:
            point = Point(x, y)
            radius = outline_geom.boundary.distance(point) if outline_geom.contains(point) else 0.0
            z_values.append(map_radius_to_z(float(radius), min_radius, max_radius, z_light, z_heavy))
        z_values = smooth_z_values(z_values)
        with_z = [(x, y, z) for (x, y, _), z in zip(stroke, z_values)]
        with_z = moving_average_stroke(with_z, 3)
        with_z = enforce_max_z_step(with_z)
        output.append([(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in with_z])
    return output


if __name__ == "__main__":
    main()
