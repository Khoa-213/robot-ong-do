import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.sdk_path import setup_fairino_sdk_path


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"


def call_raw(server, method_name: str, *args):
    print(f"[RAW_XMLRPC] Calling {method_name}{args}")
    try:
        method = getattr(server, method_name)
        result = method(*args)
        print(f"[RAW_XMLRPC] {method_name} -> {result}")
        return result
    except Exception as exc:
        print(f"[RAW_XMLRPC] {method_name} FAILED: {exc}")
        return None


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    robot_ip = config["robot_ip"]

    setup_fairino_sdk_path()
    from fairino import Robot

    print("[TEST_RAW_XMLRPC] Creating Robot.RPC object:", robot_ip)
    robot = Robot.RPC(robot_ip)
    print("[TEST_RAW_XMLRPC] SDK robot.is_connect:", getattr(robot, "is_connect", None))

    raw_server = getattr(robot, "robot", None)
    if raw_server is None:
        print("[TEST_RAW_XMLRPC] Cannot find raw XML-RPC server object at robot.robot")
        return

    print("[TEST_RAW_XMLRPC] Raw XML-RPC server:", raw_server)
    call_raw(raw_server, "GetControllerIP")
    call_raw(raw_server, "GetActualTCPPose", 0)
    call_raw(raw_server, "GetRobotEmergencyStopState")
    call_raw(raw_server, "GetRobotErrorCode")
    call_raw(raw_server, "GetSafetyStopState")
    print("[TEST_RAW_XMLRPC] No robot motion command was sent")

    if hasattr(robot, "CloseRPC"):
        robot.CloseRPC()


if __name__ == "__main__":
    main()
