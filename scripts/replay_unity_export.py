from __future__ import annotations

import argparse
import json
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "exports" / "unity" / "unity_motion_dataset.json")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    for episode in data.get("episodes", []):
        if not episode.get("frames"):
            raise ValueError(f"{episode.get('episode_id')} has no frames")
        for frame in episode["frames"]:
            if "position" not in frame or "rotation_euler" not in frame:
                raise ValueError(f"Invalid Unity frame in {episode.get('episode_id')}")
    print(f"Unity export OK: {len(data.get('episodes', []))} episodes")


if __name__ == "__main__":
    main()
