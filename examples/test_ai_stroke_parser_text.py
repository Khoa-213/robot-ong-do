from __future__ import annotations

import argparse
import json
from math import atan2, degrees, hypot
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import imageio.v3 as iio
import numpy as np
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties, findfont
from skimage.morphology import medial_axis

from modules.safety_check import validate_pose_workspace
from src.outline_to_skeleton.export_robot_path import export_robot_json
from src.outline_to_skeleton.export_svg import export_debug_svg
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.graph_trace import trace_skeleton_pixels
from src.outline_to_skeleton.path_smoothing import moving_average_stroke, resample_stroke, rdp_stroke
from src.outline_to_skeleton.rasterize import pixel_to_world, rasterize_polygons
from src.outline_to_skeleton.z_depth import enforce_max_z_step, map_radius_to_z, smooth_z_values
from src.robot.fairino_path_adapter import (
    dry_run_print_pose_strokes,
    export_pose_strokes_json,
    load_robot_paths,
    robot_paths_to_measured_paper_poses,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-style test: text -> outline -> skeleton image -> stroke parser -> robot path."
    )
    parser.add_argument("--text", help="Text to write. If omitted, prompt from keyboard.")
    parser.add_argument("--font", help="Optional .ttf/.otf font path.")
    parser.add_argument("--font-family", default="", help="Font family when --font is omitted.")
    parser.add_argument("--config", default=str(ROOT / "config" / "robot_config.json"))
    parser.add_argument("--out", default=str(ROOT / "output" / "ai_parser_robot_path.json"))
    parser.add_argument("--debug-svg", default=str(ROOT / "output" / "ai_parser_centerline.svg"))
    parser.add_argument("--pose-json", default=str(ROOT / "output" / "ai_parser_robot_poses.json"))
    parser.add_argument("--skeleton-png", default=str(ROOT / "output" / "ai_parser_skeleton.png"))
    parser.add_argument(
        "--parser",
        choices=("onnx", "heuristic"),
        default="onnx",
        help="Use a real ONNX stroke parser model, or explicit heuristic fallback.",
    )
    parser.add_argument("--onnx-model", help="Path to pretrained ONNX stroke parser model.")
    parser.add_argument("--font-size", type=int, default=220)
    parser.add_argument("--resolution", type=float, default=2.0)
    parser.add_argument("--z-light", type=float, default=-0.5)
    parser.add_argument("--z-heavy", type=float, default=-3.0)
    parser.add_argument("--path-spacing", type=float, default=1.0)
    parser.add_argument("--min-branch", type=float, default=6.0)
    parser.add_argument("--smooth-window", type=int, default=5)
    parser.add_argument("--simplify", type=float, default=0.08)
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
    args = parser.parse_args()

    text = args.text if args.text is not None else input("Nhap chu can AI parser viet: ").strip()
    if not text:
        raise ValueError("Text must not be empty")

    font_family = args.font_family.strip() or _default_parser_font_family()
    font_path = Path(args.font) if args.font else Path(findfont(FontProperties(family=font_family)))
    if not font_path.is_file():
        raise FileNotFoundError(f"Font not found: {font_path}")

    print("[1/4] Text outline -> static skeleton image...")
    polygons = text_to_outline_polygons(text, str(font_path), args.font_size)
    mask, raster_info = rasterize_polygons(polygons, args.resolution)
    skeleton, distance = medial_axis(mask, return_distance=True)
    if not np.any(skeleton):
        raise RuntimeError("Skeleton image is empty")
    _write_skeleton_png(skeleton, args.skeleton_png)

    print("[2/4] AI parser predicts stroke order and direction...")
    pixel_strokes = trace_skeleton_pixels(
        skeleton,
        min_branch_length_px=max(2.0, args.min_branch * raster_info.scale),
    )
    if args.parser == "onnx":
        parser_result = OnnxStrokeParser(args.onnx_model).parse(skeleton)
    else:
        parser_result = HeuristicStrokeParser().parse(pixel_strokes)
    robot_paths = _pixel_strokes_to_robot_paths(
        parser_result.strokes,
        distance,
        raster_info,
        z_light=args.z_light,
        z_heavy=args.z_heavy,
        path_spacing=args.path_spacing,
        smooth_window=args.smooth_window,
        simplify=args.simplify,
    )
    export_robot_json(robot_paths, args.out)
    export_debug_svg(robot_paths, args.debug_svg)

    print("[3/4] Centerline x/y/z -> measured paper robot poses...")
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
    print(f"Parser: {args.parser}")
    print(f"Model: {args.onnx_model if args.parser == 'onnx' else 'none'}")
    print(f"Raw skeleton branches: {len(pixel_strokes)}")
    print(f"Predicted strokes: {len(robot_paths)}")
    print(f"Robot points: {sum(len(stroke) for stroke in pose_strokes)}")
    print(f"Skeleton PNG: {args.skeleton_png}")
    print(f"Debug SVG: {args.debug_svg}")
    print(f"Robot path JSON: {args.out}")
    print(f"Robot pose JSON: {args.pose_json}")
    print(f"First pose: {pose_strokes[0][0]}")
    print(f"Last pose: {pose_strokes[-1][-1]}")
    print(f"Return pose: {return_pose if return_pose is not None else 'disabled'}")

    print("[4/4] Robot execution mode...")
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
        confirm = input("Type RUN to send this AI-parser path to the robot: ").strip()
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


class ParserResult:
    def __init__(self, strokes: list[list[tuple[int, int]]]):
        self.strokes = strokes


class OnnxStrokeParser:
    """
    Adapter for a real pretrained stroke parser.

    Expected model contract:
    - input: skeleton image tensor [1, 1, H, W], float32, values 0..1
    - output option A: [N, T, 2] normalized points x/y in 0..1, padded with negative values
    - output option B: [N, 4] normalized line segments x1/y1/x2/y2 in 0..1
    """

    def __init__(self, model_path: str | None):
        if not model_path:
            raise RuntimeError(
                "--parser onnx requires --onnx-model path. No pretrained stroke-order model is bundled in this repo."
            )
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"ONNX model not found: {self.model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "onnxruntime is not installed in .venv. Install it with: "
                ".\\.venv\\Scripts\\python.exe -m pip install onnxruntime"
            ) from exc
        self.ort = ort
        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])

    def parse(self, skeleton: np.ndarray) -> ParserResult:
        image = skeleton.astype(np.float32)
        image = image[None, None, :, :]
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: image})
        strokes = self._decode_outputs(outputs[0], skeleton.shape)
        if not strokes:
            raise RuntimeError("ONNX stroke parser returned no strokes")
        return ParserResult(strokes)

    def _decode_outputs(self, raw_output, image_shape: tuple[int, int]) -> list[list[tuple[int, int]]]:
        output = np.asarray(raw_output)
        if output.ndim == 3 and output.shape[-1] >= 2:
            return self._decode_polyline_output(output, image_shape)
        if output.ndim == 2 and output.shape[-1] >= 4:
            return self._decode_segment_output(output, image_shape)
        raise RuntimeError(
            f"Unsupported ONNX output shape {output.shape}. Expected [N,T,2] polylines or [N,4] segments."
        )

    def _decode_polyline_output(self, output: np.ndarray, image_shape: tuple[int, int]) -> list[list[tuple[int, int]]]:
        rows, cols = image_shape
        strokes = []
        for item in output:
            stroke = []
            for x_norm, y_norm, *_ in item:
                if x_norm < 0 or y_norm < 0:
                    continue
                col = int(round(float(x_norm) * (cols - 1)))
                row = int(round(float(y_norm) * (rows - 1)))
                stroke.append((max(0, min(rows - 1, row)), max(0, min(cols - 1, col))))
            if len(stroke) >= 2:
                strokes.append(stroke)
        return strokes

    def _decode_segment_output(self, output: np.ndarray, image_shape: tuple[int, int]) -> list[list[tuple[int, int]]]:
        rows, cols = image_shape
        strokes = []
        for item in output:
            x1, y1, x2, y2 = [float(value) for value in item[:4]]
            if min(x1, y1, x2, y2) < 0:
                continue
            start = (int(round(y1 * (rows - 1))), int(round(x1 * (cols - 1))))
            end = (int(round(y2 * (rows - 1))), int(round(x2 * (cols - 1))))
            strokes.append(_interpolate_pixel_line(start, end))
        return strokes


class HeuristicStrokeParser:
    """
    Placeholder for a future CNN/RNN/ONNX parser.

    It consumes a skeleton graph, then applies simple writing priors:
    top-to-bottom, left-to-right, and choose direction by stroke geometry.
    """

    def parse(self, pixel_strokes: list[list[tuple[int, int]]]) -> ParserResult:
        cleaned = [stroke for stroke in pixel_strokes if len(stroke) >= 2]
        oriented = [self._orient_stroke(stroke) for stroke in cleaned]
        ordered = sorted(oriented, key=self._stroke_sort_key)
        return ParserResult(ordered)

    def _orient_stroke(self, stroke: list[tuple[int, int]]) -> list[tuple[int, int]]:
        start = stroke[0]
        end = stroke[-1]
        dr = end[0] - start[0]
        dc = end[1] - start[1]
        angle = abs(degrees(atan2(dr, dc)))
        if angle > 55.0:
            return stroke if start[0] <= end[0] else list(reversed(stroke))
        return stroke if start[1] <= end[1] else list(reversed(stroke))

    def _stroke_sort_key(self, stroke: list[tuple[int, int]]) -> tuple[float, float, float]:
        rows = [point[0] for point in stroke]
        cols = [point[1] for point in stroke]
        start = stroke[0]
        length = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stroke, stroke[1:]))
        return (min(rows), min(cols), -length + start[0] * 0.001)


def _interpolate_pixel_line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    dr = end[0] - start[0]
    dc = end[1] - start[1]
    steps = max(abs(dr), abs(dc), 1)
    return [
        (
            int(round(start[0] + dr * index / steps)),
            int(round(start[1] + dc * index / steps)),
        )
        for index in range(steps + 1)
    ]


def _pixel_strokes_to_robot_paths(
    pixel_strokes: list[list[tuple[int, int]]],
    distance: np.ndarray,
    raster_info,
    z_light: float,
    z_heavy: float,
    path_spacing: float,
    smooth_window: int,
    simplify: float,
) -> list[list[tuple[float, float, float]]]:
    radii = [float(distance[row, col]) / raster_info.scale for row, col in np.argwhere(distance > 0)]
    min_radius = min(radii) if radii else 0.0
    max_radius = max(radii) if radii else 1.0
    paths = []
    for pixel_stroke in pixel_strokes:
        z_values = [
            map_radius_to_z(float(distance[row, col]) / raster_info.scale, min_radius, max_radius, z_light, z_heavy)
            for row, col in pixel_stroke
        ]
        z_values = smooth_z_values(z_values)
        stroke = []
        for (row, col), z in zip(pixel_stroke, z_values):
            x, y = pixel_to_world(row, col, raster_info)
            stroke.append((x, y, z))
        stroke = moving_average_stroke(stroke, smooth_window)
        stroke = resample_stroke(stroke, path_spacing)
        stroke = rdp_stroke(stroke, simplify)
        stroke = enforce_max_z_step(stroke)
        if len(stroke) >= 2:
            paths.append([(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in stroke])
    if not paths:
        raise RuntimeError("AI parser produced no robot path")
    return paths


def _write_skeleton_png(skeleton: np.ndarray, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.where(skeleton, 0, 255).astype(np.uint8)
    iio.imwrite(path, image)


def _default_parser_font_family() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for family in ("Segoe Print", "Ink Free", "Comic Sans MS", "Microsoft YaHei", "Segoe UI"):
        if family in available:
            return family
    return "DejaVu Sans"


def _safe_text(value: str) -> str:
    return value.encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(
        sys.stdout.encoding or "utf-8"
    )


if __name__ == "__main__":
    main()
