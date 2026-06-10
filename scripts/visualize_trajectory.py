from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("visualize_trajectory")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "processed" / "robot_motion_dataset" / "final_dataset.jsonl")
    parser.add_argument("--episode_id")
    parser.add_argument("--max_episodes", type=int, default=3)
    parser.add_argument("--output_dir", type=Path, default=ROOT / "data" / "processed" / "trajectory_preview")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    episodes = _load_episodes(args.input)
    selected = [episode for episode in episodes if args.episode_id in (None, episode["episode_id"])]
    for episode in selected[: args.max_episodes]:
        output = args.output_dir / f"{episode['episode_id']}.png"
        _plot_episode(episode, output)
        LOGGER.info("Wrote preview %s", output)


def _load_episodes(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    if "episodes" in data:
        episodes = []
        for episode in data["episodes"]:
            if "frames" in episode:
                states = [
                    [
                        frame["position"]["x"],
                        frame["position"]["y"],
                        frame["position"]["z"],
                        frame["rotation_euler"]["x"],
                        frame["rotation_euler"]["y"],
                        frame["rotation_euler"]["z"],
                        frame["gripper"],
                    ]
                    for frame in episode["frames"]
                ]
            else:
                states = [
                    [
                        target["position"]["x"],
                        target["position"]["y"],
                        target["position"]["z"],
                        target["rotation_euler"]["x"],
                        target["rotation_euler"]["y"],
                        target["rotation_euler"]["z"],
                        target["gripper"],
                    ]
                    for target in episode["end_effector_targets"]
                ]
            episodes.append({"episode_id": episode["episode_id"], "task": episode.get("task", ""), "frames": [{"state": state} for state in states]})
        return episodes
    return data


def _plot_episode(episode: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    states = [frame["state"] for frame in episode["frames"]]
    xs = [state[0] for state in states]
    ys = [state[1] for state in states]
    zs = [state[2] for state in states]
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(6, 5))
    axis = fig.add_subplot(111, projection="3d")
    axis.plot(xs, ys, zs, linewidth=2)
    axis.scatter(xs[0], ys[0], zs[0], c="green", label="start")
    axis.scatter(xs[-1], ys[-1], zs[-1], c="red", label="end")
    axis.set_title(f"{episode['episode_id']} - {episode.get('task', '')}")
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_zlabel("z")
    _set_stable_axes(axis, xs, ys, zs)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=140)
    plt.close(fig)


def _set_stable_axes(axis, xs: list[float], ys: list[float], zs: list[float]) -> None:
    centers = [
        (min(xs) + max(xs)) / 2.0,
        (min(ys) + max(ys)) / 2.0,
        (min(zs) + max(zs)) / 2.0,
    ]
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.12)
    half = span / 2.0
    axis.set_xlim(centers[0] - half, centers[0] + half)
    axis.set_ylim(centers[1] - half, centers[1] + half)
    axis.set_zlim(centers[2] - half, centers[2] + half)


if __name__ == "__main__":
    main()
