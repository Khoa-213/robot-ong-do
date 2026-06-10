from __future__ import annotations

from pathlib import Path
from typing import Any

from .coordinate_converter import robot_to_isaac_position, robot_to_isaac_rotation
from .schema import MotionDataset, save_json


def export_isaac(dataset: MotionDataset, output_path: str | Path, npz_path: str | Path | None = None, unit_scale: float = 1.0) -> dict[str, Any]:
    payload = {
        "metadata": {"format": "robot_motion_isaac_v1", "unit": "meters", "fps": dataset.metadata.get("fps", 20)},
        "episodes": [],
    }
    for episode in dataset.episodes:
        payload["episodes"].append(
            {
                "episode_id": episode.episode_id,
                "task": episode.task,
                "coordinate_system": "isaac_usd",
                "end_effector_targets": [
                    {
                        "t": frame.t,
                        "position": robot_to_isaac_position(*(value * unit_scale for value in frame.state[:3])),
                        "rotation_euler": robot_to_isaac_rotation(*frame.state[3:6]),
                        "gripper": frame.state[6],
                    }
                    for frame in episode.frames
                ],
            }
        )
    save_json(output_path, payload)
    if npz_path:
        dataset.to_npz(npz_path)
    return payload
