import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_controller import FairinoController


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})

    controller = FairinoController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
        allow_xmlrpc_motion_when_cnde_unavailable=bool(
            policy.get("allow_xmlrpc_motion_when_cnde_unavailable", False)
        ),
    )

    try:
        controller.connect()
        ok = controller.check_xmlrpc_status()
        print("[TEST_XMLRPC_STATUS] XML-RPC status OK:", ok)
        print("[TEST_XMLRPC_STATUS] No robot motion command was sent")
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
