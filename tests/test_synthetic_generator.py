from __future__ import annotations

from src.dataset.synthetic_generator import TASKS, generate_synthetic_dataset


def test_synthetic_generator_creates_required_tasks() -> None:
    dataset = generate_synthetic_dataset(episodes_per_task=2, seed=1)
    dataset.validate()
    assert len(dataset.episodes) == len(TASKS) * 2
    assert {episode.task.replace(" ", "_") for episode in dataset.episodes} == set(TASKS)
    assert all(50 <= len(episode.frames) <= 200 for episode in dataset.episodes)
    assert all(len(frame.action) == 7 for episode in dataset.episodes for frame in episode.frames)
