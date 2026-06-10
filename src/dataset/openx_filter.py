from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from .schema import MotionEpisode, MotionFrame

TASK_KEYWORDS = {
    "left to right": "move left to right",
    "right to left": "move right to left",
    "up": "move up",
    "down": "move down",
    "forward": "move forward",
    "backward": "move backward",
    "open": "open gripper",
    "close": "close gripper",
}


def normalize_action(action: Any) -> list[float]:
    values = np.asarray(action, dtype=float).reshape(-1).tolist()
    if len(values) >= 7:
        return values[:7]
    return values + [0.0] * (7 - len(values))


def classify_task(states: list[list[float]], language_instruction: str | None = None) -> str:
    text = (language_instruction or "").lower()
    for keyword, task in TASK_KEYWORDS.items():
        if keyword in text:
            return task
    if len(states) < 2:
        return "unknown"
    delta = np.asarray(states[-1][:3]) - np.asarray(states[0][:3])
    axis = int(np.argmax(np.abs(delta)))
    if axis == 0:
        return "move forward" if delta[0] >= 0 else "move backward"
    if axis == 1:
        return "move left to right" if delta[1] >= 0 else "move right to left"
    return "move up" if delta[2] >= 0 else "move down"


def episode_from_actions(
    episode_id: str,
    actions: Iterable[Any],
    language_instruction: str | None = None,
    fps: int = 20,
    source: str = "openx",
) -> MotionEpisode | None:
    normalized = [normalize_action(action) for action in actions]
    if len(normalized) < 2:
        return None
    states: list[list[float]] = []
    current = [0.0] * 7
    for action in normalized:
        current = [current[i] + action[i] for i in range(6)] + [action[6]]
        states.append(current[:])
    frames = [MotionFrame(t=index / fps, state=state, action=normalized[index]) for index, state in enumerate(states)]
    return MotionEpisode(
        episode_id=episode_id,
        source=source,
        robot="open_x_embodiment",
        task=classify_task(states, language_instruction),
        control_mode="cartesian_delta",
        fps=fps,
        frames=frames,
        metadata={"language_instruction": language_instruction} if language_instruction else {},
    )
