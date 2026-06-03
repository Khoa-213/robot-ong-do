from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import font_manager
from matplotlib.font_manager import FontProperties, findfont

from modules.safety_check import validate_pose_workspace
from src.outline_to_skeleton import export_debug_svg, export_robot_json
from src.outline_to_skeleton.template_match import TemplateMatchConfig, text_to_template_match_debug
from src.robot.fairino_path_adapter import (
    dry_run_print_pose_strokes,
    export_pose_strokes_json,
    load_robot_paths,
    robot_paths_to_measured_paper_poses,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Template matching test: keyboard text -> ordered template skeleton -> relaxed centerline -> robot."
    )
    parser.add_argument("--text", help="Text to write. If omitted, prompt from keyboard.")
    parser.add_argument("--font", help="Optional target outline .ttf/.otf font path.")
    parser.add_argument("--font-family", default="", help="Target outline font family when --font is omitted.")
    parser.add_argument("--config", default=str(ROOT / "config" / "robot_config.json"))
    parser.add_argument("--out", default=str(ROOT / "output" / "template_robot_path.json"))
    parser.add_argument("--debug-svg", default=str(ROOT / "output" / "template_centerline.svg"))
    parser.add_argument("--pose-json", default=str(ROOT / "output" / "template_robot_poses.json"))
    parser.add_argument("--font-size", type=int, default=220)
    parser.add_argument("--resolution", type=float, default=2.0)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--template-spacing", type=float, default=2.0)
    parser.add_argument("--output-spacing", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--search-radius", type=int, default=6)
    parser.add_argument("--initial-snap-radius", type=int, default=45)
    parser.add_argument(
        "--template-inset-scale",
        type=float,
        default=0.82,
        help="Shrink affine-aligned template around each glyph center before snake relaxation.",
    )
    parser.add_argument("--spring-weight", type=float, default=0.22)
    parser.add_argument("--smooth-window", type=int, default=3)
    parser.add_argument("--simplify", type=float, default=0.0)
    parser.add_argument("--fit-width", type=float, default=120.0)
    parser.add_argument("--fit-height", type=float, default=90.0)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--invert-y", dest="invert_y", action="store_true")
    parser.add_argument("--no-flip-y", dest="invert_y", action="store_false")
    parser.set_defaults(invert_y=True)
    parser.add_argument("--vel", type=float)
    parser.add_argument("--travel-vel", type=float)
    parser.add_argument("--safe-z", type=float)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--preview", action="store_true", help="Show matplotlib preview of outline/template/snake.")
    parser.add_argument("--preview-save", help="Save matplotlib preview PNG instead of or in addition to showing it.")
    args = parser.parse_args()

    text = args.text if args.text is not None else input("Nhap chu template matching viet: ").strip()
    if not text:
        raise ValueError("Text must not be empty")

    font_family = args.font_family.strip() or _default_outline_font_family()
    font_path = Path(args.font) if args.font else Path(findfont(FontProperties(family=font_family)))
    if not font_path.is_file():
        raise FileNotFoundError(f"Font not found: {font_path}")

    print("[1/3] Template skeleton -> spring relaxation inside target outline...")
    cfg = TemplateMatchConfig(
        font_size=args.font_size,
        resolution=args.resolution,
        z_light=args.z_light,
        z_heavy=args.z_heavy,
        template_spacing=args.template_spacing,
        output_spacing=args.output_spacing,
        iterations=args.iterations,
        search_radius_px=args.search_radius,
        initial_snap_radius_px=args.initial_snap_radius,
        template_inset_scale=args.template_inset_scale,
        spring_weight=args.spring_weight,
        simplify_tolerance=args.simplify,
        smooth_window=args.smooth_window,
    )
    debug = text_to_template_match_debug(text, str(font_path), cfg)
    robot_paths = debug.robot_paths
    export_robot_json(robot_paths, args.out)
    export_debug_svg(robot_paths, args.debug_svg)
    if args.preview or args.preview_save:
        _plot_template_match_preview(debug, args.preview_save, show=args.preview)

    print("[2/3] Centerline x/y/z -> measured paper robot poses...")
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

    print(f"Text: {text}")
    print(f"Target outline font: {font_path}")
    print(f"Font family: {font_family if not args.font else '(file path)'}")
    print(f"Template strokes: {len(robot_paths)}")
    print(f"Robot points: {sum(len(stroke) for stroke in pose_strokes)}")
    print(f"Debug SVG: {args.debug_svg}")
    print(f"Robot path JSON: {args.out}")
    print(f"Robot pose JSON: {args.pose_json}")
    print(
        "Relax tuning: "
        f"iterations={args.iterations}, search_radius={args.search_radius}px, "
        f"initial_snap={args.initial_snap_radius}px, inset={args.template_inset_scale}, "
        f"spring={args.spring_weight}"
    )
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
        confirm = input("Type RUN to send this template-matched path to the robot: ").strip()
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


def _default_outline_font_family() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for family in ("Segoe Print", "Ink Free", "Comic Sans MS", "Arial Rounded MT Bold", "Segoe UI"):
        if family in available:
            return family
    return "DejaVu Sans"


def _plot_template_match_preview(debug, output_path: str | None, show: bool) -> None:
    if not show:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 7))
    for polygon in debug.outlines:
        x, y = polygon.exterior.xy
        ax.fill(x, y, facecolor="#dddddd", edgecolor="#222222", linewidth=1.0, alpha=0.55)
        for interior in polygon.interiors:
            hx, hy = interior.xy
            ax.fill(hx, hy, facecolor="white", edgecolor="#555555", linewidth=0.8)

    for index, stroke in enumerate(debug.fitted_template, start=1):
        xs = [point[0] for point in stroke]
        ys = [point[1] for point in stroke]
        ax.plot(xs, ys, "--", color="#d96c00", linewidth=1.2, alpha=0.75)
        ax.text(xs[0], ys[0], str(index), color="#d96c00", fontsize=9)

    for index, stroke in enumerate(debug.relaxed_template, start=1):
        xs = [point[0] for point in stroke]
        ys = [point[1] for point in stroke]
        ax.plot(xs, ys, "-", color="#0066cc", linewidth=2.0)
        ax.scatter([xs[0]], [ys[0]], color="#008800", s=18)
        ax.scatter([xs[-1]], [ys[-1]], color="#cc0000", s=18)
        ax.text(xs[0], ys[0], str(index), color="#004c99", fontsize=10, weight="bold")

    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()
    ax.set_title("Template Matching Preview: outline gray, source dashed orange, snake blue")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        print(f"Preview PNG: {path}")
    if show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
