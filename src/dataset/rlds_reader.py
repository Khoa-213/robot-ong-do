from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator

LOGGER = logging.getLogger(__name__)


def load_tfds_dataset(
    dataset_name: str,
    data_dir: str | Path | None = None,
    split: str = "train",
    download: bool = False,
) -> Any:
    missing = _missing_openx_dependencies()
    if missing:
        packages = " ".join(missing)
        raise RuntimeError(
            "Missing optional Open X/TFDS dependencies: "
            f"{packages}. Install them with: pip install -r requirements-openx.txt"
        )
    try:
        import tensorflow_datasets as tfds
    except ImportError as exc:
        raise RuntimeError("TensorFlow Datasets is optional. Install tensorflow-datasets to read Open X samples.") from exc
    kwargs: dict[str, Any] = {"split": split, "download": download}
    if data_dir:
        kwargs["data_dir"] = str(data_dir)
    return tfds.load(dataset_name, **kwargs)


def iter_episode_steps(dataset: Any, max_episodes: int | None = None) -> Iterator[tuple[int, list[Any], str | None]]:
    for episode_index, episode in enumerate(dataset):
        if max_episodes is not None and episode_index >= max_episodes:
            break
        language = _to_text(episode.get("language_instruction") if hasattr(episode, "get") else None)
        steps = episode.get("steps") if hasattr(episode, "get") else episode["steps"]
        actions: list[Any] = []
        for step in steps:
            if hasattr(step, "get") and "action" in step:
                action = step["action"]
            else:
                action = step.get("action")
            actions.append(action.numpy() if hasattr(action, "numpy") else action)
        yield episode_index, actions, language


def inspect_dataset_schema(dataset: Any, max_steps: int = 3) -> dict[str, Any]:
    episode = next(iter(dataset))
    report: dict[str, Any] = {"episode_keys": _keys(episode)}
    steps = episode.get("steps") if hasattr(episode, "get") else episode["steps"]
    first_step = next(iter(steps))
    report["step_keys"] = _keys(first_step)
    observation = first_step.get("observation") if hasattr(first_step, "get") else None
    report["observation_keys"] = _keys(observation) if observation is not None else []
    action = first_step.get("action") if hasattr(first_step, "get") else None
    action_value = action.numpy() if hasattr(action, "numpy") else action
    report["action_shape"] = list(getattr(action_value, "shape", []))
    report["language_instruction"] = _to_text(episode.get("language_instruction") if hasattr(episode, "get") else None)
    report["sampled_steps"] = max_steps
    return report


def _keys(value: Any) -> list[str]:
    try:
        return sorted(str(key) for key in value.keys())
    except Exception:
        return []


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "numpy"):
        value = value.numpy()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _missing_openx_dependencies() -> list[str]:
    missing: list[str] = []
    imports = {
        "tensorflow": "tensorflow",
        "tensorflow_datasets": "tensorflow-datasets",
        "importlib_resources": "importlib_resources",
        "apache_beam": "apache-beam",
    }
    for module_name, package_name in imports.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package_name)
    return missing
