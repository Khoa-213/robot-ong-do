from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("convert_to_robot_motion_format")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge one or more motion JSONL files into final dataset formats.")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output_jsonl", type=Path, default=ROOT / "data" / "processed" / "robot_motion_dataset" / "final_dataset.jsonl")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from src.dataset.schema import MotionDataset

    episodes = []
    for input_path in args.inputs:
        if input_path.exists():
            episodes.extend(MotionDataset.from_jsonl(input_path).episodes)
        else:
            LOGGER.warning("Skipping missing input %s", input_path)
    dataset = MotionDataset(episodes, metadata={"fps": 20})
    dataset.validate()
    dataset.to_jsonl(args.output_jsonl)
    dataset.to_csv(args.output_jsonl.with_suffix(".csv"))
    dataset.to_npz(args.output_jsonl.with_suffix(".npz"))
    LOGGER.info("Wrote %s episodes to %s", len(episodes), args.output_jsonl)


if __name__ == "__main__":
    main()
