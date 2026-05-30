from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton import export_debug_svg, export_robot_json, svg_outline_to_robot_paths



def main() -> None:
    svg_path = ROOT / "assets" / "input" / "tam_outline.svg"
    robot_paths = svg_outline_to_robot_paths(str(svg_path), resolution=2.0, z_light=-0.5, z_heavy=-3.0)
    export_debug_svg(robot_paths, str(ROOT / "output" / "tam_svg_centerline.svg"))
    export_robot_json(robot_paths, str(ROOT / "output" / "tam_svg_robot_path.json"))
    print(f"Generated {sum(len(stroke) for stroke in robot_paths)} points in {len(robot_paths)} centerline strokes")


if __name__ == "__main__":
    main()
