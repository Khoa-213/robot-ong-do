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

    print("[TEST_GRIPPER_485_DIAG] Config:", CONFIG_PATH)
    print("[TEST_GRIPPER_485_DIAG] Robot IP:", config["robot_ip"])
    print("[TEST_GRIPPER_485_DIAG] Gripper model:", gripper.get("model"))
    print("[TEST_GRIPPER_485_DIAG] This test is read-only")
    print("[TEST_GRIPPER_485_DIAG] No ActGripper, MoveGripper, or Set* command will be sent")

    controller = FairinoGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            print("[TEST_GRIPPER_485_DIAG] Raw XML-RPC connection failed")
            return

        controller.get_controller_ip()
        controller.get_robot_error_code()
        controller.get_config()
        controller.get_tool_end_communication_param()
        controller.get_tool_end_lua_enable_status()
        controller.get_tool_end_lua_device_type()
        controller.get_tool_end_lua_enabled_device()
        controller.get_tool_end_lua_gripper_func(int(gripper.get("index", 1)))
        controller.get_gripper_status_snapshot()
    except Exception as exc:
        print("[TEST_GRIPPER_485_DIAG] ERROR:", repr(exc))
    finally:
        controller.disconnect()

    print("[TEST_GRIPPER_485_DIAG] If WebApp still shows Gripper 485 timeout:")
    print("  1. Clear alarm in WebApp after fixing wiring/config")
    print("  2. Confirm tool-end 24V power is enabled")
    print("  3. Confirm gripper RS485 A/B pins are wired correctly, not reversed")
    print("  4. Confirm baud rate/protocol/vendor-device match JODELL EPG40-050")
    print("  5. Keep gripper.enable_gripper_motion=false until diagnostics are clean")


if __name__ == "__main__":
    main()
