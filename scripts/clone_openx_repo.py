from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

from _path_setup import add_project_root

ROOT = add_project_root()
LOGGER = logging.getLogger("clone_openx_repo")
OPENX_URL = "https://github.com/google-deepmind/open_x_embodiment"


def clone_or_update_openx(target: Path = ROOT / "external" / "open_x_embodiment", pull: bool = False) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        LOGGER.info("Open X-Embodiment repo already exists at %s", target)
        if pull:
            subprocess.run(["git", "-C", str(target), "pull", "--ff-only"], check=False)
        return target
    LOGGER.info("Cloning %s to %s", OPENX_URL, target)
    subprocess.run(["git", "clone", OPENX_URL, str(target)], check=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=ROOT / "external" / "open_x_embodiment")
    parser.add_argument("--pull", action="store_true", help="Run git pull --ff-only if repo already exists.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    clone_or_update_openx(args.target, args.pull)


if __name__ == "__main__":
    main()
