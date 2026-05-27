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
    tool_end_lua = gripper.get("tool_end_lua", {})
    func = [int(value) for value in tool_end_lua.get("gripper_func", [1] * 16)]

    print("[GRIPPER_ENABLE_FUNCS] Config:", CONFIG_PATH)
    print("[GRIPPER_ENABLE_FUNCS] Robot IP:", config["robot_ip"])
    print("[GRIPPER_ENABLE_FUNCS] Function map:", func)

    controller = FairinoGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            print("[GRIPPER_ENABLE_FUNCS] Raw XML-RPC connection failed")
            return

        controller.get_controller_ip()
        controller.get_robot_error_code()

        print("[GRIPPER_ENABLE_FUNCS] Enable tool-end communication/Lua/device type")
        print(
            "[GRIPPER_ENABLE_FUNCS] SetAxleCommunicationParam:",
            controller.raw.SetAxleCommunicationParam(
                int(tool_end_lua.get("baud_rate_code", 7)),
                int(tool_end_lua.get("data_bit", 8)),
                int(tool_end_lua.get("stop_bit", 1)),
                int(tool_end_lua.get("verify", 0)),
                int(tool_end_lua.get("timeout_ms", 5)),
                int(tool_end_lua.get("timeout_times", 3)),
                int(tool_end_lua.get("period_ms", 1)),
            ),
        )
        print("[GRIPPER_ENABLE_FUNCS] SetAxleLuaEnable:", controller.raw.SetAxleLuaEnable(1))
        print(
            "[GRIPPER_ENABLE_FUNCS] SetAxleLuaEnableDeviceType:",
            controller.raw.SetAxleLuaEnableDeviceType(0, 1, 0),
        )

        for gripper_id in (0, 1):
            print(
                f"[GRIPPER_ENABLE_FUNCS] SetAxleLuaGripperFunc({gripper_id}):",
                controller.raw.SetAxleLuaGripperFunc(gripper_id, func),
            )
            print(
                f"[GRIPPER_ENABLE_FUNCS] GetAxleLuaGripperFunc({gripper_id}):",
                controller.raw.GetAxleLuaGripperFunc(gripper_id),
            )

        print("[GRIPPER_ENABLE_FUNCS] GetAxleLuaEnableDevice:", controller.raw.GetAxleLuaEnableDevice())
        print("[GRIPPER_ENABLE_FUNCS] GetRobotErrorCode:", controller.raw.GetRobotErrorCode())
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
