from __future__ import annotations

from math import dist, isfinite
from typing import Any

from modules.paper_zone import CORNER_KEYS, point_inside_convex_polygon_xy

from .models import FontSimilarityMetrics, TrajectoryPoint, ValidationIssue, ValidationResult


class TrajectoryValidator:
    """Validate final robot-coordinate trajectory before preview or execution."""

    def validate(
        self,
        trajectory: list[TrajectoryPoint],
        config: dict[str, Any],
        font_metrics: FontSimilarityMetrics | None = None,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not trajectory:
            issues.append(ValidationIssue("error", "empty_trajectory", "Trajectory has no points"))
            return ValidationResult(False, issues, {})

        workspace = config.get("robot_workspace", {})
        paper = config.get("paper", {})
        z_safety = config.get("z_safety", {})
        smooth = config.get("smooth_writing", {})
        pipeline_cfg = config.get("font_skeleton_pipeline", {})
        max_step = float(pipeline_cfg.get("max_step_distance_mm", smooth.get("max_step_distance_mm", 5.0)))
        max_velocity = float(pipeline_cfg.get("max_velocity_mm_s", smooth.get("max_velocity_mm_s", 100.0)))
        max_acceleration = float(pipeline_cfg.get("max_acceleration_mm_s2", smooth.get("max_acceleration_mm_s2", 500.0)))
        min_z = float(paper.get("paper_z", 0.0)) + float(z_safety.get("z_min_allowed_offset", -3.0))

        paper_polygon = []
        corners = paper.get("corners", {})
        if isinstance(corners, dict) and all(key in corners for key in CORNER_KEYS):
            paper_polygon = [corners[key] for key in CORNER_KEYS]

        pen_up_draw_errors = 0
        pen_down_travel_errors = 0
        draw_length = 0.0
        travel_length = 0.0
        max_observed_step = 0.0

        for index, point in enumerate(trajectory):
            values = [point.x, point.y, point.z]
            if point.rx is not None:
                values.append(point.rx)
            if point.ry is not None:
                values.append(point.ry)
            if point.rz is not None:
                values.append(point.rz)
            if not all(isfinite(float(value)) for value in values):
                issues.append(ValidationIssue("error", "non_finite", "Point contains NaN or Infinity", point.index))

            _check_range(issues, point, "x", point.x, workspace.get("x_min"), workspace.get("x_max"))
            _check_range(issues, point, "y", point.y, workspace.get("y_min"), workspace.get("y_max"))
            _check_range(issues, point, "z", point.z, workspace.get("z_min"), workspace.get("z_max"))

            if point.z < min_z:
                issues.append(
                    ValidationIssue("error", "z_below_pen_limit", f"Z {point.z} is below allowed draw limit {min_z}", point.index)
                )
            if point.velocity > max_velocity:
                issues.append(
                    ValidationIssue("error", "velocity_limit", f"Velocity {point.velocity} exceeds {max_velocity}", point.index)
                )
            if point.acceleration > max_acceleration:
                issues.append(
                    ValidationIssue(
                        "error",
                        "acceleration_limit",
                        f"Acceleration {point.acceleration} exceeds {max_acceleration}",
                        point.index,
                    )
                )
            if paper_polygon and not point_inside_convex_polygon_xy([point.x, point.y], paper_polygon):
                issues.append(ValidationIssue("error", "outside_paper", "Point XY is outside measured paper polygon", point.index))
            if point.motion_type in {"TRAVEL", "APPROACH", "LIFT", "RETRACT"} and point.pen_state == "PEN_DOWN":
                pen_down_travel_errors += 1
                issues.append(ValidationIssue("error", "pen_down_travel", "Travel motion is marked PEN_DOWN", point.index))
            if point.motion_type == "DRAW" and point.pen_state != "PEN_DOWN":
                pen_up_draw_errors += 1
                issues.append(ValidationIssue("error", "pen_up_draw", "Draw motion is not marked PEN_DOWN", point.index))

            if index > 0:
                previous = trajectory[index - 1]
                step = dist((previous.x, previous.y, previous.z), (point.x, point.y, point.z))
                max_observed_step = max(max_observed_step, step)
                if (
                    previous.motion_type == "DRAW"
                    and point.motion_type == "DRAW"
                    and previous.stroke_id == point.stroke_id
                    and step > max_step
                ):
                    issues.append(
                        ValidationIssue("error", "step_distance", f"Step distance {step:.3f} exceeds {max_step}", point.index)
                    )
                if point.pen_state == "PEN_DOWN" and point.motion_type == "DRAW":
                    draw_length += step
                else:
                    travel_length += step

        if font_metrics is not None:
            if not font_metrics.is_valid:
                issues.append(ValidationIssue("error", "font_similarity", "Font similarity validation failed"))
            for warning in font_metrics.warnings:
                issues.append(ValidationIssue("warning", "font_similarity_warning", warning))

        metrics = {
            "point_count": float(len(trajectory)),
            "draw_length_mm": round(draw_length, 3),
            "travel_length_mm": round(travel_length, 3),
            "max_step_distance_mm": round(max_observed_step, 3),
            "pen_down_travel_errors": float(pen_down_travel_errors),
            "pen_up_draw_errors": float(pen_up_draw_errors),
        }
        is_safe = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(is_safe, issues, metrics)


def _check_range(
    issues: list[ValidationIssue],
    point: TrajectoryPoint,
    axis: str,
    value: float,
    lower: Any,
    upper: Any,
) -> None:
    if lower is not None and value < float(lower):
        issues.append(ValidationIssue("error", f"{axis}_below_workspace", f"{axis}={value} is below {lower}", point.index))
    if upper is not None and value > float(upper):
        issues.append(ValidationIssue("error", f"{axis}_above_workspace", f"{axis}={value} is above {upper}", point.index))
