from __future__ import annotations

import pytest

from src.dataset.schema import MotionEpisode, MotionFrame


def test_motion_episode_validates_action_dimension_and_time() -> None:
    episode = MotionEpisode(
        episode_id="episode_1",
        source="test",
        robot="generic_6dof_arm",
        task="move",
        control_mode="cartesian_delta",
        fps=20,
        frames=[
            MotionFrame(t=0.0, state=[0.0] * 7, action=[0.0] * 7),
            MotionFrame(t=0.05, state=[0.1] * 7, action=[0.1] * 7),
        ],
    )
    episode.validate()


def test_motion_episode_rejects_bad_action_dimension() -> None:
    episode = MotionEpisode(
        episode_id="bad",
        source="test",
        robot="generic_6dof_arm",
        task="move",
        control_mode="cartesian_delta",
        fps=20,
        frames=[MotionFrame(t=0.0, state=[0.0] * 7, action=[0.0] * 6)],
    )
    with pytest.raises(ValueError, match="dimension 7"):
        episode.validate(min_frames=1)
