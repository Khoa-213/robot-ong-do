from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Iterable

ACTION_DIM = 7


@dataclass
class MotionFrame:
    t: float
    state: list[float]
    action: list[float]

    def validate(self) -> None:
        _validate_vector("state", self.state, ACTION_DIM)
        _validate_vector("action", self.action, ACTION_DIM)
        if not math.isfinite(self.t):
            raise ValueError("frame time must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {"t": self.t, "state": self.state, "action": self.action}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotionFrame":
        frame = cls(t=float(data["t"]), state=_float_list(data["state"]), action=_float_list(data["action"]))
        frame.validate()
        return frame


@dataclass
class MotionEpisode:
    episode_id: str
    source: str
    robot: str
    task: str
    control_mode: str
    fps: int
    frames: list[MotionFrame] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, min_frames: int = 2) -> None:
        if not self.episode_id:
            raise ValueError("episode_id is required")
        if len(self.frames) < min_frames:
            raise ValueError(f"{self.episode_id} has fewer than {min_frames} frames")
        previous_t = -math.inf
        for frame in self.frames:
            frame.validate()
            if frame.t <= previous_t:
                raise ValueError(f"{self.episode_id} frame times must increase")
            previous_t = frame.t

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "source": self.source,
            "robot": self.robot,
            "task": self.task,
            "control_mode": self.control_mode,
            "fps": self.fps,
            "frames": [frame.to_dict() for frame in self.frames],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotionEpisode":
        episode = cls(
            episode_id=str(data["episode_id"]),
            source=str(data.get("source", "unknown")),
            robot=str(data.get("robot", "generic_6dof_arm")),
            task=str(data.get("task", "unknown")),
            control_mode=str(data.get("control_mode", "cartesian_delta")),
            fps=int(data.get("fps", 20)),
            frames=[MotionFrame.from_dict(item) for item in data.get("frames", [])],
            metadata=dict(data.get("metadata", {})),
        )
        episode.validate(min_frames=1)
        return episode


@dataclass
class MotionDataset:
    episodes: list[MotionEpisode]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, min_frames: int = 2) -> None:
        for episode in self.episodes:
            episode.validate(min_frames=min_frames)

    def to_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            for episode in self.episodes:
                file.write(json.dumps(episode.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "MotionDataset":
        episodes: list[MotionEpisode] = []
        with Path(path).open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    episodes.append(MotionEpisode.from_dict(json.loads(line)))
        return cls(episodes=episodes)

    def to_npz(self, path: str | Path) -> None:
        import numpy as np

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            episode_ids=np.array([episode.episode_id for episode in self.episodes], dtype=object),
            tasks=np.array([episode.task for episode in self.episodes], dtype=object),
            states=np.array([[frame.state for frame in episode.frames] for episode in self.episodes], dtype=object),
            actions=np.array([[frame.action for frame in episode.frames] for episode in self.episodes], dtype=object),
        )

    def to_csv(self, path: str | Path) -> None:
        import pandas as pd

        rows: list[dict[str, Any]] = []
        for episode in self.episodes:
            for frame_index, frame in enumerate(episode.frames):
                row = {
                    "episode_id": episode.episode_id,
                    "task": episode.task,
                    "frame_index": frame_index,
                    "t": frame.t,
                }
                row.update({f"state_{index}": value for index, value in enumerate(frame.state)})
                row.update({f"action_{index}": value for index, value in enumerate(frame.action)})
                rows.append(row)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(path, index=False)


def load_motion_dataset(path: str | Path) -> MotionDataset:
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        return MotionDataset.from_jsonl(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = data.get("episodes", data if isinstance(data, list) else [])
    return MotionDataset([MotionEpisode.from_dict(item) for item in episodes], metadata=data.get("metadata", {}))


def save_json(path: str | Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _float_list(values: Iterable[Any]) -> list[float]:
    return [float(value) for value in values]


def _validate_vector(name: str, values: list[float], expected_dim: int) -> None:
    if len(values) != expected_dim:
        raise ValueError(f"{name} must have dimension {expected_dim}, got {len(values)}")
    if any(not math.isfinite(value) for value in values):
        raise ValueError(f"{name} contains NaN or Inf")
