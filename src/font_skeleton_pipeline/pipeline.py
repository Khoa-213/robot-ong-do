from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, MultiLineString, MultiPolygon
from skimage.morphology import medial_axis

from modules.trajectory_planner import config_from_robot_config, plan_pose_strokes
from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.pipeline import text_to_robot_paths
from src.outline_to_skeleton.rasterize import rasterize_polygons
from src.robot.fairino_path_adapter import robot_paths_to_measured_paper_poses
from src.services.config_service import get_config

from .models import FontSimilarityMetrics, Stroke, TrajectoryPoint
from .validator import TrajectoryValidator


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FontSkeletonPipeline:
    """Build preview-only robot trajectories from keyboard text and a TTF/OTF font."""

    def __init__(self, config: dict[str, Any] | None = None, project_root: Path | None = None) -> None:
        self.config = config if config is not None else get_config()
        self.project_root = project_root or PROJECT_ROOT

    def run(
        self,
        text: str,
        font_path: str,
        font_size: int | None = None,
        output_width_mm: float | None = None,
        output_height_mm: float | None = None,
        output_root: str | Path | None = None,
    ) -> dict[str, Any]:
        cfg = self.config.get("font_skeleton_pipeline", {})
        font_size = int(font_size if font_size is not None else cfg.get("font_size", 220))
        output_width_mm = float(output_width_mm if output_width_mm is not None else cfg.get("output_width_mm", 90.0))
        output_height_mm = float(output_height_mm if output_height_mm is not None else cfg.get("output_height_mm", 80.0))
        font = self._project_path(font_path)
        if not font.is_file():
            raise FileNotFoundError(f"Font not found: {font}")
        if font.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
            raise ValueError(f"Unsupported font extension: {font.suffix}")

        run_dir = self._create_run_dir(output_root)
        LOGGER.info("[FONT] Rendering text %r with font %s", text, font)
        polygons = text_to_outline_polygons(text, str(font), font_size)
        geometry = MultiPolygon(polygons)

        resolution = float(cfg.get("resolution", 2.0))
        mask, _info = rasterize_polygons(polygons, resolution=resolution)
        raw_skeleton = medial_axis(mask)
        _save_binary_image(mask, run_dir / "original_font_render.png")
        _save_binary_image(raw_skeleton, run_dir / "raw_skeleton.png")
        _render_original_font(text, font, font_size, run_dir / "original_font_render.png")

        LOGGER.info("[SKELETON] Extracting centerlines")
        robot_paths = text_to_robot_paths(
            text=text,
            font_path=str(font),
            font_size=font_size,
            resolution=resolution,
            z_light=float(cfg.get("z_light", -0.5)),
            z_heavy=float(cfg.get("z_heavy", -3.0)),
            output_scale=float(cfg.get("output_scale", 1.0)),
            point_spacing=float(cfg.get("point_spacing_mm", 1.0)),
            min_branch_length=float(cfg.get("min_branch_length", 4.0)),
            smoothing_window=int(cfg.get("smoothing_window", 3)),
            simplify_tolerance=float(cfg.get("simplification_tolerance", 0.05)),
            max_points_per_stroke=int(cfg.get("max_points_per_stroke", 600)),
            theta=float(cfg.get("spur_prune_threshold", 1.5)),
        )

        strokes = _build_stroke_models(robot_paths)
        _save_stroke_preview(strokes, run_dir / "cleaned_skeleton.png", "Cleaned skeleton")
        _save_stroke_preview(strokes, run_dir / "stroke_order_preview.png", "Stroke order", label_strokes=True)
        font_metrics = _font_similarity(geometry, robot_paths, self.config)
        LOGGER.info("[VALIDATION] Outside glyph ratio: %.3f", font_metrics.outside_ratio)

        paper = self.config.get("paper", {})
        pose_strokes = robot_paths_to_measured_paper_poses(
            robot_paths,
            paper_config=paper,
            margin_mm=float(paper.get("margin_mm", 20.0)),
            orientation=paper.get("draw_orientation", [0.0, 0.0, 0.0]),
            preserve_aspect_ratio=True,
            invert_y=bool(cfg.get("invert_y", True)),
            fit_width_mm=output_width_mm,
            fit_height_mm=output_height_mm,
        )
        planned_pose_strokes = plan_pose_strokes(pose_strokes, config_from_robot_config(self.config))
        trajectory = _build_trajectory_points(planned_pose_strokes, self.config)
        validation = TrajectoryValidator().validate(trajectory, self.config, font_metrics)
        trajectory_hash = _hash_trajectory(trajectory)

        payload = {
            "text": text,
            "font": str(font),
            "font_size": font_size,
            "output_width_mm": output_width_mm,
            "output_height_mm": output_height_mm,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "trajectory_id": trajectory_hash,
            "approved": False,
            "preview_only": True,
            "parameters": dict(cfg),
            "strokes": [stroke.to_dict() for stroke in strokes],
            "font_similarity": font_metrics.to_dict(),
            "validation": validation.to_dict(),
            "points": [point.to_dict() for point in trajectory],
        }

        _write_outputs(run_dir, text, payload, trajectory, validation.to_dict())
        _render_robot_preview(run_dir / "robot_trajectory_preview.png", trajectory, strokes, self.config, font_metrics)
        _write_preview_svg(run_dir / "robot_trajectory_preview.svg", trajectory, self.config)
        _write_summary(run_dir, payload, trajectory)
        LOGGER.info("[PREVIEW] Saved robot trajectory preview in %s", run_dir)

        return {
            "run_dir": str(run_dir),
            "trajectory_json": str(run_dir / "robot_trajectory.json"),
            "trajectory_csv": str(run_dir / "robot_trajectory.csv"),
            "preview_png": str(run_dir / "robot_trajectory_preview.png"),
            "preview_svg": str(run_dir / "robot_trajectory_preview.svg"),
            "validation": validation.to_dict(),
            "font_similarity": font_metrics.to_dict(),
            "approved": False,
        }

    def run_hershey(
        self,
        text: str,
        hershey_font: str = "scripts",
        output_width_mm: float | None = None,
        output_height_mm: float | None = None,
        output_root: str | Path | None = None,
    ) -> dict[str, Any]:
        cfg = self.config.get("font_skeleton_pipeline", {})
        output_width_mm = float(output_width_mm if output_width_mm is not None else cfg.get("output_width_mm", 90.0))
        output_height_mm = float(output_height_mm if output_height_mm is not None else cfg.get("output_height_mm", 80.0))

        LOGGER.info("[FONT] Rendering Hershey text %r with font %s", text, hershey_font)
        robot_paths = _hershey_text_to_robot_paths(text, hershey_font)
        run_dir = self._create_run_dir(output_root)
        strokes = _build_stroke_models(robot_paths)
        _save_stroke_preview(strokes, run_dir / "original_font_render.png", f"Hershey {hershey_font}", label_strokes=False)
        _save_stroke_preview(strokes, run_dir / "raw_skeleton.png", "Hershey raw strokes")
        _save_stroke_preview(strokes, run_dir / "cleaned_skeleton.png", "Hershey cleaned strokes")
        _save_stroke_preview(strokes, run_dir / "stroke_order_preview.png", "Stroke order", label_strokes=True)

        font_metrics = FontSimilarityMetrics(
            iou=1.0,
            chamfer_distance=0.0,
            hausdorff_distance=0.0,
            coverage_ratio=1.0,
            outside_ratio=0.0,
            is_valid=True,
            warnings=["Hershey is a native single-line stroke font; outline similarity is not applicable."],
        )

        paper = self.config.get("paper", {})
        pose_strokes = robot_paths_to_measured_paper_poses(
            robot_paths,
            paper_config=paper,
            margin_mm=float(paper.get("margin_mm", 20.0)),
            orientation=paper.get("draw_orientation", [0.0, 0.0, 0.0]),
            preserve_aspect_ratio=True,
            invert_y=bool(cfg.get("invert_y", True)),
            fit_width_mm=output_width_mm,
            fit_height_mm=output_height_mm,
        )
        planned_pose_strokes = plan_pose_strokes(pose_strokes, config_from_robot_config(self.config))
        trajectory = _build_trajectory_points(planned_pose_strokes, self.config)
        validation = TrajectoryValidator().validate(trajectory, self.config, font_metrics)
        trajectory_hash = _hash_trajectory(trajectory)

        payload = {
            "text": text,
            "font": f"hershey:{hershey_font}",
            "font_size": None,
            "output_width_mm": output_width_mm,
            "output_height_mm": output_height_mm,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "trajectory_id": trajectory_hash,
            "approved": False,
            "preview_only": True,
            "parameters": {**dict(cfg), "hershey_font": hershey_font},
            "strokes": [stroke.to_dict() for stroke in strokes],
            "font_similarity": font_metrics.to_dict(),
            "validation": validation.to_dict(),
            "points": [point.to_dict() for point in trajectory],
        }

        _write_outputs(run_dir, text, payload, trajectory, validation.to_dict())
        _render_robot_preview(run_dir / "robot_trajectory_preview.png", trajectory, strokes, self.config, font_metrics)
        _write_preview_svg(run_dir / "robot_trajectory_preview.svg", trajectory, self.config)
        _write_summary(run_dir, payload, trajectory)
        LOGGER.info("[PREVIEW] Saved Hershey robot trajectory preview in %s", run_dir)

        return {
            "run_dir": str(run_dir),
            "trajectory_json": str(run_dir / "robot_trajectory.json"),
            "trajectory_csv": str(run_dir / "robot_trajectory.csv"),
            "preview_png": str(run_dir / "robot_trajectory_preview.png"),
            "preview_svg": str(run_dir / "robot_trajectory_preview.svg"),
            "validation": validation.to_dict(),
            "font_similarity": font_metrics.to_dict(),
            "approved": False,
        }

    def _project_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def _create_run_dir(self, output_root: str | Path | None) -> Path:
        root = Path(output_root) if output_root is not None else self.project_root / "outputs"
        stamp = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        run_dir = root / stamp
        suffix = 1
        while run_dir.exists():
            run_dir = root / f"{stamp}_{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True)
        return run_dir


def build_font_skeleton_preview(
    text: str,
    font_path: str,
    font_size: int = 220,
    output_width_mm: float = 90.0,
    output_height_mm: float = 80.0,
) -> dict[str, Any]:
    return FontSkeletonPipeline().run(text, font_path, font_size, output_width_mm, output_height_mm)


def list_hershey_fonts() -> list[str]:
    try:
        from HersheyFonts import HersheyFonts
    except ImportError as exc:
        raise ImportError("Hershey-Fonts is not installed in this Python environment") from exc
    font = HersheyFonts()
    return sorted(font.default_font_names)


def _hershey_text_to_robot_paths(text: str, hershey_font: str) -> list[list[tuple[float, float, float]]]:
    try:
        from HersheyFonts import HersheyFonts
    except ImportError as exc:
        raise ImportError("Hershey-Fonts is not installed. Use .venv\\Scripts\\python.exe for this project.") from exc

    font = HersheyFonts()
    font.load_default_font(hershey_font)
    font.normalize_rendering(100.0)
    strokes = []
    for stroke in font.strokes_for_text(text):
        points = [(round(float(x), 3), round(float(y), 3), 0.0) for x, y in stroke]
        if len(points) >= 2:
            strokes.append(points)
    if not strokes:
        raise ValueError(f"Hershey font {hershey_font!r} produced no strokes for text {text!r}")
    return strokes


def _build_stroke_models(robot_paths: list[list[tuple[float, float, float]]]) -> list[Stroke]:
    strokes: list[Stroke] = []
    for index, points in enumerate(robot_paths, start=1):
        if len(points) < 2:
            continue
        start = points[0]
        end = points[-1]
        closed = ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5 <= 1.0
        strokes.append(
            Stroke(
                stroke_id=index,
                component_id=index,
                raw_points=list(points),
                smooth_points=list(points),
                start_point=(start[0], start[1]),
                end_point=(end[0], end[1]),
                is_closed=closed,
                draw_direction="forward",
                confidence=0.85,
            )
        )
    LOGGER.info("[STROKE] Extracted %d valid strokes", len(strokes))
    return strokes


def _build_trajectory_points(strokes: list[list[list[float]]], config: dict[str, Any]) -> list[TrajectoryPoint]:
    smooth = config.get("smooth_writing", {})
    text_cfg = config.get("text_demo", {})
    draw_velocity = float(smooth.get("writing_speed_mm_s", text_cfg.get("vel", config.get("default_vel", 10))))
    travel_velocity = float(smooth.get("travel_speed_mm_s", text_cfg.get("travel_vel", config.get("default_vel", 10))))
    acceleration = float(smooth.get("acceleration", 0.0))
    blend = float(smooth.get("blend_radius_mm", config.get("motion_strategy", {}).get("blend_radius", 0.0)))
    paper_z = float(config.get("paper", {}).get("paper_z", smooth.get("writing_z", 0.0)))
    safe_z = float(smooth.get("safe_z", paper_z + float(text_cfg.get("travel_z_offset", 20.0))))

    points: list[TrajectoryPoint] = []

    def add(stroke_id: int, pose: list[float], z: float, velocity: float, pen_state: str, motion_type: str, blend_radius: float) -> None:
        points.append(
            TrajectoryPoint(
                index=len(points),
                stroke_id=stroke_id,
                x=round(float(pose[0]), 3),
                y=round(float(pose[1]), 3),
                z=round(float(z), 3),
                rx=round(float(pose[3]), 3) if len(pose) > 3 else None,
                ry=round(float(pose[4]), 3) if len(pose) > 4 else None,
                rz=round(float(pose[5]), 3) if len(pose) > 5 else None,
                velocity=round(float(velocity), 3),
                acceleration=round(float(acceleration), 3),
                blend_radius=round(float(blend_radius), 3),
                pen_state=pen_state,
                motion_type=motion_type,
            )
        )

    for stroke_id, stroke in enumerate(strokes, start=1):
        if len(stroke) < 2:
            continue
        first = stroke[0]
        add(stroke_id, first, safe_z, travel_velocity, "PEN_UP", "APPROACH", 0.0)
        add(stroke_id, first, first[2], travel_velocity, "PEN_TRANSITION", "LIFT", 0.0)
        for point_index, pose in enumerate(stroke):
            point_blend = blend if point_index < len(stroke) - 1 else 0.0
            add(stroke_id, pose, pose[2], draw_velocity, "PEN_DOWN", "DRAW", point_blend)
        add(stroke_id, stroke[-1], safe_z, travel_velocity, "PEN_TRANSITION", "LIFT", 0.0)
    return points


def _font_similarity(
    geometry: MultiPolygon,
    robot_paths: list[list[tuple[float, float, float]]],
    config: dict[str, Any],
) -> FontSimilarityMetrics:
    cfg = config.get("font_skeleton_pipeline", {})
    lines = []
    total_length = 0.0
    for stroke in robot_paths:
        if len(stroke) >= 2:
            line = LineString([(x, y) for x, y, _z in stroke])
            if line.length > 0:
                lines.append(line)
                total_length += line.length
    if not lines:
        return FontSimilarityMetrics(0.0, 0.0, 999999.0, 0.0, 1.0, False, ["No centerline strokes were generated"])

    centerlines = MultiLineString(lines)
    configured_width = float(cfg.get("similarity_stroke_width", 3.0))
    area_width = geometry.area / total_length if total_length > 0 else configured_width
    estimated_width = max(0.5, configured_width, area_width)
    reconstructed = centerlines.buffer(estimated_width / 2.0, cap_style=2, join_style=2)
    union_area = geometry.union(reconstructed).area
    intersection_area = geometry.intersection(reconstructed).area
    iou = intersection_area / union_area if union_area > 0 else 0.0
    coverage = intersection_area / geometry.area if geometry.area > 0 else 0.0
    outside_length = sum(line.difference(geometry).length for line in lines)
    outside_ratio = outside_length / total_length if total_length > 0 else 1.0
    hausdorff = float(geometry.boundary.hausdorff_distance(centerlines))
    chamfer = float(centerlines.distance(geometry.boundary))

    max_outside = float(cfg.get("max_outside_ratio", config.get("validation", {}).get("max_outside_ratio", 0.03)))
    min_coverage = float(cfg.get("min_coverage_ratio", config.get("validation", {}).get("min_coverage_ratio", 0.3)))
    warnings = []
    if outside_ratio > max_outside:
        warnings.append(f"Centerline outside glyph ratio {outside_ratio:.3f} exceeds {max_outside:.3f}")
    if coverage < min_coverage:
        warnings.append(f"Reconstructed coverage {coverage:.3f} is below {min_coverage:.3f}")
    return FontSimilarityMetrics(
        iou=round(iou, 5),
        chamfer_distance=round(chamfer, 5),
        hausdorff_distance=round(hausdorff, 5),
        coverage_ratio=round(coverage, 5),
        outside_ratio=round(outside_ratio, 5),
        is_valid=not warnings,
        warnings=warnings,
    )


def _write_outputs(
    run_dir: Path,
    text: str,
    payload: dict[str, Any],
    trajectory: list[TrajectoryPoint],
    validation: dict[str, Any],
) -> None:
    (run_dir / "input_text.txt").write_text(text, encoding="utf-8")
    (run_dir / "robot_trajectory.json").write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "validation_report.json").write_text(
        json.dumps(_json_ready(validation), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (run_dir / "robot_trajectory.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "index",
                "stroke_id",
                "motion_type",
                "pen_state",
                "x_mm",
                "y_mm",
                "z_mm",
                "rx_deg",
                "ry_deg",
                "rz_deg",
                "velocity_mm_s",
                "acceleration_mm_s2",
                "blend_radius_mm",
            ],
        )
        writer.writeheader()
        for point in trajectory:
            writer.writerow(
                {
                    "index": point.index,
                    "stroke_id": point.stroke_id,
                    "motion_type": point.motion_type,
                    "pen_state": point.pen_state,
                    "x_mm": point.x,
                    "y_mm": point.y,
                    "z_mm": point.z,
                    "rx_deg": point.rx,
                    "ry_deg": point.ry,
                    "rz_deg": point.rz,
                    "velocity_mm_s": point.velocity,
                    "acceleration_mm_s2": point.acceleration,
                    "blend_radius_mm": point.blend_radius,
                }
            )


def _render_original_font(text: str, font_path: Path, font_size: int, output: Path) -> None:
    font = ImageFont.truetype(str(font_path), max(12, int(font_size)))
    bbox = font.getbbox(text)
    width = max(64, bbox[2] - bbox[0] + 40)
    height = max(64, bbox[3] - bbox[1] + 40)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20 - bbox[0], 20 - bbox[1]), text, font=font, fill="black")
    image.save(output)


def _save_binary_image(mask, output: Path) -> None:
    image = Image.fromarray((mask.astype("uint8") * 255))
    image.save(output)


def _save_stroke_preview(strokes: list[Stroke], output: Path, title: str, label_strokes: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for stroke in strokes:
        xs = [point[0] for point in stroke.smooth_points]
        ys = [point[1] for point in stroke.smooth_points]
        ax.plot(xs, ys, linewidth=1.5)
        ax.scatter([xs[0]], [ys[0]], s=18, c="green")
        ax.scatter([xs[-1]], [ys[-1]], s=18, c="red")
        if label_strokes:
            ax.text(xs[0], ys[0], str(stroke.stroke_id), fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.grid(True, linewidth=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _render_robot_preview(
    output: Path,
    trajectory: list[TrajectoryPoint],
    strokes: list[Stroke],
    config: dict[str, Any],
    metrics: FontSimilarityMetrics,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))
    draw_points = [point for point in trajectory if point.motion_type == "DRAW"]
    travel_points = [point for point in trajectory if point.motion_type != "DRAW"]
    _plot_grouped(ax, draw_points, "-", "#0b6bcb", "PEN_DOWN draw")
    _plot_travel(ax, trajectory)
    if travel_points:
        ax.scatter([p.x for p in travel_points], [p.y for p in travel_points], s=8, c="#888888", alpha=0.25)
    starts = {}
    ends = {}
    for point in draw_points:
        starts.setdefault(point.stroke_id, point)
        ends[point.stroke_id] = point
    for stroke_id, point in starts.items():
        ax.scatter([point.x], [point.y], s=42, c="green", marker="o")
        ax.text(point.x, point.y, f"S{stroke_id}", fontsize=8)
    for stroke_id, point in ends.items():
        ax.scatter([point.x], [point.y], s=42, c="red", marker="x")
    _plot_paper(ax, config)
    ax.set_title(
        "Robot trajectory preview "
        f"(safe={metrics.is_valid}, outside={metrics.outside_ratio:.3f}, coverage={metrics.coverage_ratio:.3f})"
    )
    ax.set_xlabel("Robot X mm")
    ax.set_ylabel("Robot Y mm")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linewidth=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_grouped(ax, points: list[TrajectoryPoint], style: str, color: str, label: str) -> None:
    by_stroke: dict[int, list[TrajectoryPoint]] = {}
    for point in points:
        by_stroke.setdefault(point.stroke_id, []).append(point)
    first = True
    for stroke_points in by_stroke.values():
        ax.plot(
            [point.x for point in stroke_points],
            [point.y for point in stroke_points],
            style,
            color=color,
            linewidth=1.4,
            label=label if first else None,
        )
        first = False


def _plot_travel(ax, trajectory: list[TrajectoryPoint]) -> None:
    first = True
    for previous, point in zip(trajectory, trajectory[1:]):
        if point.motion_type == "DRAW" and previous.motion_type == "DRAW" and point.stroke_id == previous.stroke_id:
            continue
        ax.plot(
            [previous.x, point.x],
            [previous.y, point.y],
            "--",
            color="#666666",
            linewidth=0.9,
            alpha=0.65,
            label="PEN_UP travel" if first else None,
        )
        first = False
        if point.index % 12 == 0:
            ax.annotate("", xy=(point.x, point.y), xytext=(previous.x, previous.y), arrowprops={"arrowstyle": "->", "lw": 0.5})


def _plot_paper(ax, config: dict[str, Any]) -> None:
    corners = config.get("paper", {}).get("corners", {})
    if not all(key in corners for key in ("top_left", "top_right", "bottom_right", "bottom_left")):
        return
    polygon = [corners[key] for key in ("top_left", "top_right", "bottom_right", "bottom_left", "top_left")]
    ax.plot([p[0] for p in polygon], [p[1] for p in polygon], color="#111111", linewidth=1.2, label="paper bounds")


def _write_preview_svg(output: Path, trajectory: list[TrajectoryPoint], config: dict[str, Any]) -> None:
    xs = [point.x for point in trajectory]
    ys = [point.y for point in trajectory]
    min_x, max_x = min(xs) - 10, max(xs) + 10
    min_y, max_y = min(ys) - 10, max(ys) + 10
    height = max_y - min_y

    def pt(point: TrajectoryPoint) -> str:
        return f"{point.x - min_x:.3f},{max_y - point.y:.3f}"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {max_x - min_x:.3f} {height:.3f}">',
        '<g id="original-font"></g>',
        '<g id="cleaned-skeleton"></g>',
        '<g id="pen-down-path" fill="none" stroke="#0b6bcb" stroke-width="0.8">',
    ]
    by_stroke: dict[int, list[TrajectoryPoint]] = {}
    for point in trajectory:
        if point.motion_type == "DRAW":
            by_stroke.setdefault(point.stroke_id, []).append(point)
    for stroke_points in by_stroke.values():
        d = " ".join(("M" if index == 0 else "L") + pt(point) for index, point in enumerate(stroke_points))
        lines.append(f'<path d="{d}"/>')
    lines.extend(['</g>', '<g id="pen-up-path" fill="none" stroke="#666" stroke-width="0.5" stroke-dasharray="2 2">'])
    for previous, point in zip(trajectory, trajectory[1:]):
        if point.motion_type == "DRAW" and previous.motion_type == "DRAW" and point.stroke_id == previous.stroke_id:
            continue
        lines.append(f'<path d="M{pt(previous)} L{pt(point)}"/>')
    lines.extend(['</g>', '<g id="stroke-labels" font-size="4" fill="green">'])
    for stroke_id, stroke_points in by_stroke.items():
        point = stroke_points[0]
        lines.append(f'<text x="{point.x - min_x:.3f}" y="{max_y - point.y:.3f}">{stroke_id}</text>')
    lines.extend(['</g>', '<g id="coordinate-labels" font-size="3" fill="#333">'])
    for point in trajectory[:: max(1, len(trajectory) // 12)]:
        lines.append(
            f'<text x="{point.x - min_x:.3f}" y="{max_y - point.y:.3f}">'
            f'{point.x:.1f},{point.y:.1f},Z{point.z:.1f} {point.pen_state}</text>'
        )
    lines.extend(['</g>', '<g id="paper-bounds" fill="none" stroke="#111" stroke-width="0.7">'])
    corners = config.get("paper", {}).get("corners", {})
    if all(key in corners for key in ("top_left", "top_right", "bottom_right", "bottom_left")):
        values = [corners[key] for key in ("top_left", "top_right", "bottom_right", "bottom_left")]
        d = " ".join(("M" if index == 0 else "L") + f"{p[0] - min_x:.3f},{max_y - p[1]:.3f}" for index, p in enumerate(values))
        lines.append(f'<path d="{d} Z"/>')
    lines.extend(['</g>', '<g id="safe-zone"></g>', '</svg>'])
    output.write_text("\n".join(lines), encoding="utf-8")


def _write_summary(run_dir: Path, payload: dict[str, Any], trajectory: list[TrajectoryPoint]) -> None:
    draw_points = [point for point in trajectory if point.pen_state == "PEN_DOWN"]
    up_points = [point for point in trajectory if point.pen_state != "PEN_DOWN"]
    xs = [point.x for point in trajectory]
    ys = [point.y for point in trajectory]
    zs = [point.z for point in trajectory]
    validation = payload["validation"]
    metrics = payload["font_similarity"]
    lines = [
        "Font skeleton trajectory summary",
        f"Text: {payload['text']}",
        f"Font: {payload['font']}",
        f"Trajectory ID: {payload['trajectory_id']}",
        f"Approved: {payload['approved']}",
        f"Stroke count: {len(payload['strokes'])}",
        f"Point count: {len(trajectory)}",
        f"PEN_DOWN points: {len(draw_points)}",
        f"PEN_UP/PEN_TRANSITION points: {len(up_points)}",
        f"X min/max: {min(xs):.3f}/{max(xs):.3f}",
        f"Y min/max: {min(ys):.3f}/{max(ys):.3f}",
        f"Z min/max: {min(zs):.3f}/{max(zs):.3f}",
        f"Font IoU: {metrics['iou']}",
        f"Font outside ratio: {metrics['outside_ratio']}",
        f"Validation safe: {validation['is_safe']}",
        "Robot execution is locked until this JSON is reviewed and approved.",
    ]
    (run_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hash_trajectory(trajectory: list[TrajectoryPoint]) -> str:
    body = json.dumps([asdict(point) for point in trajectory], sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()[:16]


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value
