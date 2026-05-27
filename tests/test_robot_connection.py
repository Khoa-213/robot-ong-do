import json
import socket
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_controller import FairinoController


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            print(f"[PORT] {host}:{port} is open")
            return True
    except OSError as exc:
        print(f"[PORT] {host}:{port} is not reachable: {exc}")
        return False


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    robot_ip = config["robot_ip"]

    print("[TEST_CONNECT] Config:", CONFIG_PATH)
    print("[TEST_CONNECT] Robot IP:", robot_ip)
    policy = config.get("connection_policy", {})
    command_port = int(policy.get("command_port", 20003))
    legacy_state_port = int(policy.get("legacy_state_port", 20004))
    cnde_port = int(policy.get("cnde_port", 20005))

    port_20003 = check_port(robot_ip, command_port)
    port_20004 = check_port(robot_ip, legacy_state_port)
    port_20005 = check_port(robot_ip, cnde_port)

    if port_20003 and port_20004 and not port_20005:
        print("[DIAG] XML-RPC port 20003 is open")
        print("[DIAG] Legacy realtime/status port 20004 is open")
        print("[DIAG] CNDE port 20005 is closed")
        print("[DIAG] This SDK build expects CNDE on 20005, so robot.is_connect may stay False")
        print("[DIAG] Do not enable robot movement until the SDK/controller compatibility is resolved")

    controller = FairinoController(
        robot_ip=robot_ip,
        tool=int(config["tool"]),
        user=int(config["user"]),
        allow_xmlrpc_motion_when_cnde_unavailable=bool(
            policy.get("allow_xmlrpc_motion_when_cnde_unavailable", False)
        ),
    )
    connected = controller.connect()
    print("[TEST_CONNECT] Connected:", connected)
    controller.disconnect()


if __name__ == "__main__":
    main()
