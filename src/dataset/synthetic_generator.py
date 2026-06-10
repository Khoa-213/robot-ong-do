from __future__ import annotations

import math
import random
from typing import Callable

from .schema import MotionDataset, MotionEpisode, MotionFrame

TASKS = (
    "move_left_to_right",
    "move_right_to_left",
    "move_up",
    "move_down",
    "move_forward",
    "move_backward",
    "draw_line",
    "draw_square",
    "draw_circle",
    "pen_lift",
    "pen_down",
)


def generate_synthetic_dataset(episodes_per_task: int = 20, fps: int = 20, seed: int = 7) -> MotionDataset:
    rng = random.Random(seed)
    episodes: list[MotionEpisode] = []
    for task in TASKS:
        for index in range(episodes_per_task):
            frame_count = rng.randint(50, 200)
            states = _make_path(task, frame_count, rng)
            frames: list[MotionFrame] = []
            previous = states[0]
            for frame_index, state in enumerate(states):
                delta = [state[i] - previous[i] for i in range(6)] + [state[6]]
                frames.append(MotionFrame(t=frame_index / fps, state=state, action=delta))
                previous = state
            episodes.append(
                MotionEpisode(
                    episode_id=f"synthetic_{task}_{index + 1:04d}",
                    source="synthetic",
                    robot="generic_6dof_arm",
                    task=task.replace("_", " "),
                    control_mode="cartesian_delta",
                    fps=fps,
                    frames=frames,
                    metadata={"generator": "src.dataset.synthetic_generator"},
                )
            )
    dataset = MotionDataset(episodes=episodes, metadata={"source": "synthetic", "fps": fps})
    dataset.validate()
    return dataset


def _make_path(task: str, count: int, rng: random.Random) -> list[list[float]]:
    amplitude = rng.uniform(0.08, 0.18)
    base = [rng.uniform(0.25, 0.45), rng.uniform(-0.08, 0.08), rng.uniform(0.16, 0.28), 0.0, 0.0, 0.0, 0.0]
    noise_phase = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(3)]
    noise_freq = [rng.uniform(0.6, 1.4) for _ in range(3)]
    builders: dict[str, Callable[[float], tuple[float, float, float, float]]] = {
        "move_left_to_right": lambda s: (0.0, -amplitude / 2 + amplitude * s, 0.0, 0.0),
        "move_right_to_left": lambda s: (0.0, amplitude / 2 - amplitude * s, 0.0, 0.0),
        "move_up": lambda s: (0.0, 0.0, amplitude * s, 0.0),
        "move_down": lambda s: (0.0, 0.0, amplitude * (1.0 - s), 0.0),
        "move_forward": lambda s: (amplitude * s, 0.0, 0.0, 0.0),
        "move_backward": lambda s: (amplitude * (1.0 - s), 0.0, 0.0, 0.0),
        "draw_line": lambda s: (0.0, -amplitude / 2 + amplitude * s, 0.0, 0.0),
        "pen_lift": lambda s: (0.0, 0.0, 0.04 * s, 1.0),
        "pen_down": lambda s: (0.0, 0.0, 0.04 * (1.0 - s), 0.0),
    }
    states: list[list[float]] = []
    for i in range(count):
        s = i / (count - 1)
        if task == "draw_square":
            dx, dy = _square_point(s, amplitude)
            dz, gripper = 0.0, 0.0
        elif task == "draw_circle":
            dx = math.cos(2 * math.pi * s) * amplitude / 2
            dy = math.sin(2 * math.pi * s) * amplitude / 2
            dz, gripper = 0.0, 0.0
        else:
            dx, dy, dz, gripper = builders[task](s)
        noise = _smooth_position_noise(s, noise_phase, noise_freq)
        states.append([
            base[0] + dx + noise[0],
            base[1] + dy + noise[1],
            base[2] + dz + noise[2],
            base[3],
            base[4],
            base[5],
            gripper,
        ])
    return states


def _smooth_position_noise(s: float, phases: list[float], freqs: list[float]) -> list[float]:
    # Keep demo data realistic without turning simple motions into jittery paths.
    amplitude = 0.00025
    return [
        amplitude * math.sin(2.0 * math.pi * freqs[index] * s + phases[index])
        for index in range(3)
    ]


def _square_point(s: float, size: float) -> tuple[float, float]:
    edge = min(3, int(s * 4))
    local = s * 4 - edge
    half = size / 2
    if edge == 0:
        return -half + size * local, -half
    if edge == 1:
        return half, -half + size * local
    if edge == 2:
        return half - size * local, half
    return -half, half - size * local
