from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.font_skeleton_pipeline.executor import RobotTrajectoryExecutor
from src.font_skeleton_pipeline.pipeline import FontSkeletonPipeline


DEFAULT_FONT = PROJECT_ROOT / "assets" / "fonts" / "UTM ThuPhap Thien An.ttf"


def main() -> int:
    text = input("Text [Tam]: ").strip() or "Tam"
    font = input(f"Font [{DEFAULT_FONT}]: ").strip() or str(DEFAULT_FONT)
    font_size = _read_int("Font size [220]: ", 220)
    width = _read_float("Output width mm [90]: ", 90.0)
    height = _read_float("Output height mm [80]: ", 80.0)

    result = FontSkeletonPipeline().run(text, font, font_size, width, height)
    summary = _load_summary(result["trajectory_json"])
    print()
    print("[PREVIEW] Generated:", result["run_dir"])
    print("Preview PNG:", result["preview_png"])
    print("Preview SVG:", result["preview_svg"])
    print("CSV:", result["trajectory_csv"])
    print("JSON:", result["trajectory_json"])
    print()
    print("Glyph/stroke count:", len(summary.get("strokes", [])))
    print("Point count:", len(summary.get("points", [])))
    print("PEN_DOWN:", sum(1 for point in summary.get("points", []) if point["pen_state"] == "PEN_DOWN"))
    print("PEN_UP/PEN_TRANSITION:", sum(1 for point in summary.get("points", []) if point["pen_state"] != "PEN_DOWN"))
    print("Font similarity:", summary.get("font_similarity", {}))
    print("Validation safe:", summary.get("validation", {}).get("is_safe"))

    answer = input("Run mock robot command stream? [Y/N]: ").strip().upper()
    if answer == "Y":
        commands = RobotTrajectoryExecutor().execute_previewed_trajectory(result["trajectory_json"], execute=False)
        print("[MOCK] Command count:", len(commands))

    real = input("Approve and run real robot? Type EXECUTE to continue, anything else cancels: ").strip()
    if real != "EXECUTE":
        print("[SAFETY] Real robot execution canceled.")
        return 0

    payload = _load_summary(result["trajectory_json"])
    if not payload.get("validation", {}).get("is_safe", False):
        raise RuntimeError("Validation failed; refusing to approve trajectory.")
    payload["approved"] = True
    Path(result["trajectory_json"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    RobotTrajectoryExecutor().execute_previewed_trajectory(
        result["trajectory_json"],
        execute=True,
        confirmation_text="EXECUTE",
        require_confirmation=True,
        use_mock=False,
    )
    return 0


def _load_summary(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_int(prompt: str, default: int) -> int:
    value = input(prompt).strip()
    return default if not value else int(value)


def _read_float(prompt: str, default: float) -> float:
    value = input(prompt).strip()
    return default if not value else float(value)


if __name__ == "__main__":
    raise SystemExit(main())
