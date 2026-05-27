import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"

_config_cache: dict[str, Any] | None = None


def load_config(force: bool = False) -> dict[str, Any]:
    global _config_cache
    if _config_cache is not None and not force:
        return _config_cache
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    _config_cache = data
    return data


def get_config() -> dict[str, Any]:
    return load_config()


def reload_config() -> dict[str, Any]:
    return load_config(force=True)


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    data = load_config(force=True)
    merged = _merge_dicts(data, patch)
    CONFIG_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return reload_config()


def _merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
