from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("inspect_openx_dataset")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", required=True)
    parser.add_argument("--data_dir", type=Path, default=Path.home() / "tensorflow_datasets")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed" / "dataset_inspection_report.json")
    parser.add_argument(
        "--allow_download_prepare",
        action="store_true",
        help="Allow TFDS to download/prepare the dataset. This can be very large.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from src.dataset.rlds_reader import inspect_dataset_schema, load_tfds_dataset
        from src.dataset.schema import save_json

        dataset = load_tfds_dataset(args.dataset_name, data_dir=args.data_dir, download=args.allow_download_prepare)
        report = inspect_dataset_schema(dataset)
        save_json(args.output, report)
        LOGGER.info("Wrote inspection report to %s", args.output)
    except Exception as exc:
        LOGGER.error("Could not inspect dataset: %s", exc)
        LOGGER.info("If the dataset is not already in TFDS cache, download it first with gsutil or rerun with --allow_download_prepare.")


if __name__ == "__main__":
    main()
