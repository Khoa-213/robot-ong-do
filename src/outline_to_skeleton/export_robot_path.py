from __future__ import annotations

import json
from pathlib import Path


def export_robot_json(robot_paths, output_path: str):
    """
    Save robot paths as JSON with only stroke id and x/y/z points.
    """
    data = []
    for stroke_index, stroke in enumerate(robot_paths, start=1):
        data.append(
            {
                "stroke_id": stroke_index,
                "points": [
                    {"x": float(point[0]), "y": float(point[1]), "z": float(point[2])}
                    for point in stroke
                ],
            }
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
