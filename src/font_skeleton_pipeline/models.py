from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FontSimilarityMetrics:
    iou: float
    chamfer_distance: float
    hausdorff_distance: float
    coverage_ratio: float
    outside_ratio: float
    is_valid: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Stroke:
    stroke_id: int
    component_id: int
    raw_points: list[tuple[float, float, float]]
    smooth_points: list[tuple[float, float, float]]
    start_point: tuple[float, float]
    end_point: tuple[float, float]
    is_closed: bool
    draw_direction: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raw_points"] = [list(point) for point in self.raw_points]
        data["smooth_points"] = [list(point) for point in self.smooth_points]
        return data


@dataclass(frozen=True)
class TrajectoryPoint:
    index: int
    stroke_id: int
    x: float
    y: float
    z: float
    rx: float | None
    ry: float | None
    rz: float | None
    velocity: float
    acceleration: float
    blend_radius: float
    pen_state: str
    motion_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    point_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    is_safe: bool
    issues: list[ValidationIssue]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": dict(self.metrics),
        }
