import argparse
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
    parser = argparse.ArgumentParser(
        description="Setup Fairino tool-end RS485/Lua path for gripper. No gripper motion is sent."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually send SetAxleCommunicationParam, SetAxleLuaEnable, SetAxleLuaEnableDeviceType.",
    )
    args = parser.parse_args()

    config = load_config()
    gripper = config.get("gripper", {})
    tool_end_lua = gripper.get("tool_end_lua", {})

    print("[TEST_GRIPPER_SETUP_TOOL_END] Config:", CONFIG_PATH)
    print("[TEST_GRIPPER_SETUP_TOOL_END] Robot IP:", config["robot_ip"])
    print("[TEST_GRIPPER_SETUP_TOOL_END] Gripper model:", gripper.get("model"))
    print("[TEST_GRIPPER_SETUP_TOOL_END] apply:", args.apply)
    print("[TEST_GRIPPER_SETUP_TOOL_END] No ActGripper or MoveGripper command will be sent")
    print("[TEST_GRIPPER_SETUP_TOOL_END] Planned tool-end setup:", tool_end_lua)

    if bool(gripper.get("enable_gripper_motion", False)):
        print("[TEST_GRIPPER_SETUP_TOOL_END] WARNING: enable_gripper_motion is true in config")
        print("[TEST_GRIPPER_SETUP_TOOL_END] This setup script still will not move the gripper")

    controller = FairinoGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            print("[TEST_GRIPPER_SETUP_TOOL_END] Raw XML-RPC connection failed")
            return

        print("[TEST_GRIPPER_SETUP_TOOL_END] Before setup:")
        controller.get_controller_ip()
        controller.get_tool_end_communication_param()
        controller.get_tool_end_lua_enable_status()
        controller.get_tool_end_lua_device_type()

        controller.setup_tool_end_gripper(tool_end_lua, apply_setup=args.apply)

        print("[TEST_GRIPPER_SETUP_TOOL_END] After setup/readback:")
        controller.get_tool_end_communication_param()
        controller.get_tool_end_lua_enable_status()
        controller.get_tool_end_lua_device_type()
    except Exception as exc:
        print("[TEST_GRIPPER_SETUP_TOOL_END] ERROR:", repr(exc))
    finally:
        controller.disconnect()

    if not args.apply:
        print("[TEST_GRIPPER_SETUP_TOOL_END] Preview finished.")
        print("[TEST_GRIPPER_SETUP_TOOL_END] To apply setup:")
        print("  python tests\\test_gripper_setup_tool_end.py --apply")
    else:
        print("[TEST_GRIPPER_SETUP_TOOL_END] Setup command finished.")
        print("[TEST_GRIPPER_SETUP_TOOL_END] Now run:")
        print("  python tests\\test_gripper_485_diagnostics.py")


if __name__ == "__main__":
    main()
