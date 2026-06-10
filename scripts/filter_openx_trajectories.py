from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("filter_openx_trajectories")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", required=True)
    parser.add_argument("--max_episodes", type=int, default=100)
    parser.add_argument("--data_dir", type=Path, default=Path.home() / "tensorflow_datasets")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed" / "robot_motion_dataset" / "openx_filtered.jsonl")
    parser.add_argument(
        "--allow_download_prepare",
        action="store_true",
        help="Allow TFDS to download/prepare the dataset. This can be very large and is not limited by --max_episodes.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from src.dataset.openx_filter import episode_from_actions
        from src.dataset.rlds_reader import iter_episode_steps, load_tfds_dataset
        from src.dataset.schema import MotionDataset

        dataset = load_tfds_dataset(args.dataset_name, data_dir=args.data_dir, download=args.allow_download_prepare)
        episodes = []
        for episode_index, actions, language in iter_episode_steps(dataset, args.max_episodes):
            episode = episode_from_actions(f"openx_{args.dataset_name}_{episode_index:05d}", actions, language)
            if episode is not None:
                episodes.append(episode)
        MotionDataset(episodes).to_jsonl(args.output)
        LOGGER.info("Wrote %s filtered episodes to %s", len(episodes), args.output)
    except Exception as exc:
        LOGGER.error("Could not filter Open X trajectories: %s", exc)
        LOGGER.info("Filtering only samples from an already prepared TFDS cache unless --allow_download_prepare is set.")


if __name__ == "__main__":
    main()
