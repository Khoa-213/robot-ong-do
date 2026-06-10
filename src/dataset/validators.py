from __future__ import annotations

from .schema import MotionDataset


def validate_motion_dataset(dataset: MotionDataset, min_frames: int = 2) -> None:
    dataset.validate(min_frames=min_frames)
