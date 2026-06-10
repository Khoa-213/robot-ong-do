from __future__ import annotations

import argparse
import json
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "exports" / "isaac" / "isaac_motion_dataset.json")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    for episode in data.get("episodes", []):
        targets = episode.get("end_effector_targets", [])
        if not targets:
            raise ValueError(f"{episode.get('episode_id')} has no targets")
        for target in targets:
            if "position" not in target or "rotation_euler" not in target:
                raise ValueError(f"Invalid Isaac target in {episode.get('episode_id')}")
    print(f"Isaac export OK: {len(data.get('episodes', []))} episodes")


if __name__ == "__main__":
    main()
