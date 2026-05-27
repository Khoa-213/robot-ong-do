import argparse
import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.tool_do_gripper import ToolDOGripperController


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test gripper wired to Fairino tool DO0. Default is preview only."
    )
    parser.add_argument("--apply", action="store_true", help="Actually send SetToolDO open/close commands.")
    parser.add_argument("--cycles", type=int, default=None, help="Override cycle count.")
    args = parser.parse_args()

    config = load_config()
    do_config = config.get("tool_do_gripper", {})

    do_id = int(do_config.get("do_id", 0))
    open_status = int(do_config.get("open_status", 0))
    close_status = int(do_config.get("close_status", 1))
    smooth = int(do_config.get("smooth", 0))
    block = int(do_config.get("block", 1))
    hold_seconds = float(do_config.get("hold_seconds", 1.0))
    cycles = int(args.cycles if args.cycles is not None else do_config.get("cycle_count", 5))

    enable_tool_do_gripper = bool(do_config.get("enable_tool_do_gripper", False)) and args.apply

    print("[TEST_TOOL_DO0_GRIPPER] Config:", CONFIG_PATH)
    print("[TEST_TOOL_DO0_GRIPPER] Robot IP:", config["robot_ip"])
    print("[TEST_TOOL_DO0_GRIPPER] Tool DO gripper config:", do_config)
    print("[TEST_TOOL_DO0_GRIPPER] apply:", args.apply)
    print("[TEST_TOOL_DO0_GRIPPER] effective enable_tool_do_gripper:", enable_tool_do_gripper)
    print("[TEST_TOOL_DO0_GRIPPER] DO mapping:")
    print(f"  OPEN  -> SetToolDO(id={do_id}, status={open_status}, block={block})")
    print(f"  CLOSE -> SetToolDO(id={do_id}, status={close_status}, block={block})")

    if args.apply and not bool(do_config.get("enable_tool_do_gripper", False)):
        print("[TEST_TOOL_DO0_GRIPPER] SAFETY LOCK: config tool_do_gripper.enable_tool_do_gripper is false")
        print("[TEST_TOOL_DO0_GRIPPER] Set it true only when the gripper area is clear")

    controller = ToolDOGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            print("[TEST_TOOL_DO0_GRIPPER] Raw XML-RPC connection failed")
            return

        controller.get_controller_ip()
        controller.get_robot_error_code()

        for index in range(cycles):
            print(f"[TEST_TOOL_DO0_GRIPPER] Cycle {index + 1}/{cycles}")
            controller.close(
                do_id=do_id,
                close_status=close_status,
                smooth=smooth,
                block=block,
                enable_tool_do_gripper=enable_tool_do_gripper,
            )
            time.sleep(hold_seconds)
            controller.open(
                do_id=do_id,
                open_status=open_status,
                smooth=smooth,
                block=block,
                enable_tool_do_gripper=enable_tool_do_gripper,
            )
            time.sleep(hold_seconds)
    except Exception as exc:
        print("[TEST_TOOL_DO0_GRIPPER] ERROR:", repr(exc))
    finally:
        controller.disconnect()

    if not enable_tool_do_gripper:
        print("[TEST_TOOL_DO0_GRIPPER] Preview finished. No SetToolDO command was sent.")
        print("[TEST_TOOL_DO0_GRIPPER] To run for real:")
        print("  1. Set config tool_do_gripper.enable_tool_do_gripper = true")
        print("  2. Run python tests\\test_tool_do0_gripper.py --apply")


if __name__ == "__main__":
    main()
