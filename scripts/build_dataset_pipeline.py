from __future__ import annotations

import argparse
import logging
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("build_dataset_pipeline")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic_only", action="store_true")
    parser.add_argument("--dataset_name")
    parser.add_argument("--max_openx_episodes", type=int, default=100)
    parser.add_argument("--synthetic_episodes_per_task", type=int, default=20)
    parser.add_argument("--skip_clone", action="store_true")
    parser.add_argument(
        "--allow_download_prepare",
        action="store_true",
        help="Allow TFDS to download/prepare the Open X dataset. This can be very large.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from src.dataset.isaac_exporter import export_isaac
    from src.dataset.openx_filter import episode_from_actions
    from src.dataset.rlds_reader import iter_episode_steps, load_tfds_dataset
    from src.dataset.schema import MotionDataset, save_json
    from src.dataset.synthetic_generator import generate_synthetic_dataset
    from src.dataset.unity_exporter import export_unity

    processed_dir = ROOT / "data" / "processed" / "robot_motion_dataset"
    exports_unity = ROOT / "data" / "exports" / "unity" / "unity_motion_dataset.json"
    exports_isaac = ROOT / "data" / "exports" / "isaac" / "isaac_motion_dataset.json"
    final_jsonl = processed_dir / "final_dataset.jsonl"

    if not args.skip_clone and not args.synthetic_only:
        try:
            from clone_openx_repo import clone_or_update_openx

            clone_or_update_openx()
        except Exception as exc:
            LOGGER.warning("Skipping Open X repo clone/update: %s", exc)

    openx_episodes = []
    if args.dataset_name and not args.synthetic_only:
        try:
            tfds_dataset = load_tfds_dataset(args.dataset_name, download=args.allow_download_prepare)
            for episode_index, actions, language in iter_episode_steps(tfds_dataset, args.max_openx_episodes):
                episode = episode_from_actions(f"openx_{args.dataset_name}_{episode_index:05d}", actions, language)
                if episode is not None:
                    openx_episodes.append(episode)
            LOGGER.info("Loaded %s Open X episodes", len(openx_episodes))
        except Exception as exc:
            LOGGER.warning("Open X sample unavailable, continuing with synthetic data: %s", exc)
            LOGGER.info("Open X loading reads prepared TFDS cache by default. Use --allow_download_prepare only intentionally.")

    synthetic = generate_synthetic_dataset(args.synthetic_episodes_per_task)
    episodes = [*openx_episodes, *synthetic.episodes]
    dataset = MotionDataset(
        episodes,
        metadata={
            "fps": 20,
            "sources": ["openx_optional", "synthetic"],
            "openx_episode_count": len(openx_episodes),
            "synthetic_episode_count": len(synthetic.episodes),
        },
    )
    dataset.validate()
    dataset.to_jsonl(final_jsonl)
    dataset.to_csv(final_jsonl.with_suffix(".csv"))
    dataset.to_npz(final_jsonl.with_suffix(".npz"))
    export_unity(dataset, exports_unity)
    export_isaac(dataset, exports_isaac, ROOT / "data" / "exports" / "isaac" / "isaac_motion_dataset.npz")
    _make_previews(final_jsonl)
    save_json(
        processed_dir / "pipeline_report.json",
        {
            "dataset_name": args.dataset_name,
            "openx_episode_count": len(openx_episodes),
            "synthetic_episode_count": len(synthetic.episodes),
            "total_episode_count": len(dataset.episodes),
            "used_openx_data": bool(openx_episodes),
            "final_jsonl": str(final_jsonl),
            "unity_export": str(exports_unity),
            "isaac_export": str(exports_isaac),
        },
    )
    LOGGER.info("Pipeline complete: %s episodes", len(dataset.episodes))
    LOGGER.info("Open X episodes: %s", len(openx_episodes))
    LOGGER.info("Synthetic episodes: %s", len(synthetic.episodes))
    LOGGER.info("Final JSONL: %s", final_jsonl)
    LOGGER.info("Unity export: %s", exports_unity)
    LOGGER.info("Isaac export: %s", exports_isaac)


def _make_previews(final_jsonl: Path) -> None:
    try:
        from visualize_trajectory import _load_episodes, _plot_episode

        for episode in _load_episodes(final_jsonl)[:3]:
            _plot_episode(episode, ROOT / "data" / "processed" / "trajectory_preview" / f"{episode['episode_id']}.png")
    except Exception as exc:
        LOGGER.warning("Could not create trajectory previews: %s", exc)


if __name__ == "__main__":
    main()
