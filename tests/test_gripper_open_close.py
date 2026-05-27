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

    enable_gripper_motion = bool(gripper.get("enable_gripper_motion", False))
    allow_raw_xmlrpc_gripper = bool(gripper.get("allow_raw_xmlrpc_gripper", False))
    index = int(gripper.get("index", 1))
    open_pos = int(gripper.get("open_pos", 100))
    close_pos = int(gripper.get("close_pos", 20))
    vel = int(gripper.get("test_vel", 20))
    force = int(gripper.get("test_force", 20))
    max_time_ms = int(gripper.get("max_time_ms", 5000))
    block = int(gripper.get("block", 0))
    gripper_type = int(gripper.get("type", 0))

    print("[TEST_GRIPPER_OPEN_CLOSE] Config:", CONFIG_PATH)
    print("[TEST_GRIPPER_OPEN_CLOSE] Robot IP:", config["robot_ip"])
    print("[TEST_GRIPPER_OPEN_CLOSE] Gripper model:", gripper.get("model"))
    print("[TEST_GRIPPER_OPEN_CLOSE] index:", index)
    print("[TEST_GRIPPER_OPEN_CLOSE] open_pos:", open_pos)
    print("[TEST_GRIPPER_OPEN_CLOSE] close_pos:", close_pos)
    print("[TEST_GRIPPER_OPEN_CLOSE] vel:", vel)
    print("[TEST_GRIPPER_OPEN_CLOSE] force:", force)
    print("[TEST_GRIPPER_OPEN_CLOSE] enable_gripper_motion:", enable_gripper_motion)
    print("[TEST_GRIPPER_OPEN_CLOSE] allow_raw_xmlrpc_gripper:", allow_raw_xmlrpc_gripper)

    if not enable_gripper_motion or not allow_raw_xmlrpc_gripper:
        print("[TEST_GRIPPER_OPEN_CLOSE] SAFETY LOCK: gripper movement disabled")
        print("[TEST_GRIPPER_OPEN_CLOSE] Preview only, robot will not connect and gripper will not move")
        preview = FairinoGripperController(config["robot_ip"])
        preview.preview_move("open", open_pos, vel, force)
        preview.preview_move("close", close_pos, vel, force)
        return

    controller = FairinoGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            print("[TEST_GRIPPER_OPEN_CLOSE] Raw XML-RPC connection failed")
            return

        controller.get_controller_ip()

        tool_end_lua = gripper.get("tool_end_lua", {})
        if bool(tool_end_lua.get("configure_before_test", False)):
            controller.configure_tool_end_lua(
                tool_end_lua,
                enable_gripper_motion=enable_gripper_motion,
                allow_raw_xmlrpc_gripper=allow_raw_xmlrpc_gripper,
            )

        controller.set_config(
            company=int(gripper.get("company", 3)),
            device=int(gripper.get("device", 0)),
            softversion=int(gripper.get("softversion", 0)),
            bus=int(gripper.get("bus", 0)),
            enable_gripper_motion=enable_gripper_motion,
            allow_raw_xmlrpc_gripper=allow_raw_xmlrpc_gripper,
        )
        controller.get_config()
        controller.activate(
            index=index,
            enable_gripper_motion=enable_gripper_motion,
            allow_raw_xmlrpc_gripper=allow_raw_xmlrpc_gripper,
        )

        controller.move(
            index=index,
            pos=open_pos,
            vel=vel,
            force=force,
            maxtime=max_time_ms,
            block=block,
            gripper_type=gripper_type,
            enable_gripper_motion=enable_gripper_motion,
            allow_raw_xmlrpc_gripper=allow_raw_xmlrpc_gripper,
        )
        controller.get_motion_done()

        controller.move(
            index=index,
            pos=close_pos,
            vel=vel,
            force=force,
            maxtime=max_time_ms,
            block=block,
            gripper_type=gripper_type,
            enable_gripper_motion=enable_gripper_motion,
            allow_raw_xmlrpc_gripper=allow_raw_xmlrpc_gripper,
        )
        controller.get_motion_done()
    except Exception as exc:
        print("[TEST_GRIPPER_OPEN_CLOSE] ERROR:", repr(exc))
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
