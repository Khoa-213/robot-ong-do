import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_gripper import FairinoGripperController


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def is_ok_response(result: Any) -> bool:
    return isinstance(result, list) and len(result) > 0 and result[0] == 0


def has_gripper_data(result: Any) -> bool:
    # Fairino gripper status calls return [error, fault, value].
    # fault=0 means a clean status; fault=1 means no-data/fault on this controller.
    return isinstance(result, list) and len(result) >= 3 and result[0] == 0 and result[1] == 0


def verdict(label: str, ok: bool, detail: Any) -> bool:
    status = "OK" if ok else "FAIL"
    print(f"[GRIPPER_PING] {label}: {status} -> {detail}")
    return ok


def main() -> None:
    config = load_config()
    gripper = config.get("gripper", {})

    print("[GRIPPER_PING] Config:", CONFIG_PATH)
    print("[GRIPPER_PING] Robot IP:", config["robot_ip"])
    print("[GRIPPER_PING] Gripper:", gripper.get("model", "unknown"))
    print("[GRIPPER_PING] Read-only ping. No Set*, ActGripper, or MoveGripper command will be sent.")

    controller = FairinoGripperController(config["robot_ip"])
    try:
        raw_connected = controller.connect()
        verdict("ROBOT XML-RPC", raw_connected, "raw ServerProxy connected" if raw_connected else "not connected")
        if not raw_connected:
            return

        controller_ip = controller.get_controller_ip()
        robot_ok = verdict("ROBOT CONTROLLER", is_ok_response(controller_ip), controller_ip)

        comm = controller.get_tool_end_communication_param()
        comm_ok = is_ok_response(comm) and len(comm) >= 8 and comm[1] != 0
        verdict("TOOL-END RS485 PARAM", comm_ok, comm)

        lua = controller.get_tool_end_lua_enable_status()
        lua_ok = is_ok_response(lua) and len(lua) >= 2 and lua[1] == 1
        verdict("TOOL-END LUA ENABLE", lua_ok, lua)

        device = controller.get_tool_end_lua_device_type()
        device_ok = is_ok_response(device) and len(device) >= 4 and device[2] == 1
        verdict("LUA GRIPPER DEVICE", device_ok, device)

        gripper_config = controller.get_config()
        config_ok = is_ok_response(gripper_config)
        verdict("GRIPPER CONFIG", config_ok, gripper_config)

        position = controller.raw.GetGripperCurPosition()
        voltage = controller.raw.GetGripperVoltage()
        current = controller.raw.GetGripperCurCurrent()
        position_ok = verdict("GRIPPER POSITION RESPONSE", has_gripper_data(position), position)
        voltage_ok = verdict("GRIPPER VOLTAGE RESPONSE", has_gripper_data(voltage), voltage)
        current_ok = verdict("GRIPPER CURRENT RESPONSE", has_gripper_data(current), current)

        gripper_response_ok = position_ok or voltage_ok or current_ok
        all_ok = robot_ok and comm_ok and lua_ok and device_ok and config_ok and gripper_response_ok
        print("[GRIPPER_PING] SUMMARY:", "PASS" if all_ok else "FAIL")

        if not gripper_response_ok:
            print("[GRIPPER_PING] NEXT:")
            print("  - Clear WebApp alarm if present")
            print("  - Check tool-end 24V/GND")
            print("  - Check RS485 A/B wiring or try swapping A/B")
            print("  - Confirm JODELL EPG40-050 baud/slave/protocol")
    except Exception as exc:
        print("[GRIPPER_PING] ERROR:", repr(exc))
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
