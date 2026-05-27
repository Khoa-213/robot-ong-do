import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_gripper import FairinoGripperController


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    config = load_config()
    gripper = config.get("gripper", {})

    print("[TEST_GRIPPER_CONNECTION] Config:", CONFIG_PATH)
    print("[TEST_GRIPPER_CONNECTION] Robot IP:", config["robot_ip"])
    print("[TEST_GRIPPER_CONNECTION] Gripper model:", gripper.get("model"))
    print("[TEST_GRIPPER_CONNECTION] Interface:", gripper.get("interface"))
    print("[TEST_GRIPPER_CONNECTION] enable_gripper_motion:", gripper.get("enable_gripper_motion"))
    print("[TEST_GRIPPER_CONNECTION] No gripper motion command will be sent")

    controller = FairinoGripperController(config["robot_ip"])
    try:
        connected = controller.connect()
        print("[TEST_GRIPPER_CONNECTION] Raw XML-RPC connected:", connected)
        if not connected:
            return

        controller.get_controller_ip()
        controller.get_config()
    except Exception as exc:
        print("[TEST_GRIPPER_CONNECTION] ERROR:", repr(exc))
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
