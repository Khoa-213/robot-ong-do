from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "processed" / "robot_motion_dataset" / "final_dataset.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "exports" / "unity" / "unity_motion_dataset.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from src.dataset.schema import MotionDataset
    from src.dataset.unity_exporter import export_unity

    export_unity(MotionDataset.from_jsonl(args.input), args.output)
    logging.info("Wrote Unity export to %s", args.output)


if __name__ == "__main__":
    main()
