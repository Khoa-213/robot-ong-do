import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.sdk_path import LIB_PATH, SDK_ROOT, setup_fairino_sdk_path


def main() -> None:
    try:
        setup_fairino_sdk_path()
        from fairino import Robot

        print("[TEST_IMPORT] Fairino SDK import OK")
        print("[TEST_IMPORT] SDK_ROOT:", SDK_ROOT)
        print("[TEST_IMPORT] LIB_PATH:", LIB_PATH)
        print("[TEST_IMPORT] Robot module:", Robot)
    except Exception as exc:
        print("[TEST_IMPORT] Fairino SDK import FAILED:", exc)
        raise


if __name__ == "__main__":
    main()
