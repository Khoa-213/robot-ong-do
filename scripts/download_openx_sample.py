from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("download_openx_sample")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", required=True)
    parser.add_argument("--max_episodes", type=int, default=100)
    parser.add_argument("--data_dir", type=Path, default=Path.home() / "tensorflow_datasets")
    parser.add_argument("--split", default="train")
    parser.add_argument(
        "--allow_download_prepare",
        action="store_true",
        help="Allow TFDS to download/prepare the dataset. This can be very large and is not limited by --max_episodes.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from src.dataset.rlds_reader import iter_episode_steps, load_tfds_dataset

        dataset = load_tfds_dataset(args.dataset_name, data_dir=args.data_dir, split=args.split, download=args.allow_download_prepare)
        count = sum(1 for _ in iter_episode_steps(dataset, args.max_episodes))
        LOGGER.info("Loaded %s episode samples from %s", count, args.dataset_name)
    except Exception as exc:
        LOGGER.error("Could not load dataset sample: %s", exc)
        LOGGER.info("Open X datasets are large and are not cloned from GitHub.")
        LOGGER.info("By default this script reads an existing TFDS cache only.")
        LOGGER.info("Use --allow_download_prepare only if you intentionally want TFDS to prepare the dataset.")
        LOGGER.info("If you already downloaded data, pass --data_dir pointing at your TFDS directory.")
        LOGGER.info("Cloud copy pattern:")
        LOGGER.info("  gsutil -m cp -r gs://gdm-robotics-open-x-embodiment/%s ~/tensorflow_datasets/", args.dataset_name)


if __name__ == "__main__":
    main()
