from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("generate_synthetic_motion_dataset")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes_per_task", type=int, default=20)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed" / "robot_motion_dataset" / "synthetic_dataset.jsonl")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from src.dataset.synthetic_generator import generate_synthetic_dataset

    dataset = generate_synthetic_dataset(args.episodes_per_task)
    dataset.to_jsonl(args.output)
    LOGGER.info("Wrote %s synthetic episodes to %s", len(dataset.episodes), args.output)


if __name__ == "__main__":
    main()
