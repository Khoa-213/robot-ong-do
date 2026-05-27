import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
DEFAULT_LUA_PATH = PROJECT_ROOT / "config" / "lua" / "AXLE_LUA_End_DaHuan.lua"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.sdk_path import setup_fairino_sdk_path


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Fairino tool-end Lua gripper protocol file.")
    parser.add_argument("--lua", default=str(DEFAULT_LUA_PATH), help="Path to AXLE_LUA_End_*.lua file.")
    parser.add_argument(
        "--allow-demo-lua",
        action="store_true",
        help="Allow uploading a demo Lua file that directly calls ActGripper/MoveGripper.",
    )
    args = parser.parse_args()

    lua_path = Path(args.lua).resolve()
    if not lua_path.exists():
        print("[GRIPPER_UPLOAD_LUA] Lua file not found:", lua_path)
        print("[GRIPPER_UPLOAD_LUA] Put the vendor/Fairino Lua file here or pass --lua <path>.")
        return

    lua_text = lua_path.read_text(encoding="utf-8", errors="ignore")
    if not args.allow_demo_lua and ("ActGripper(" in lua_text or "MoveGripper(" in lua_text):
        print("[GRIPPER_UPLOAD_LUA] Refusing to upload demo Lua:", lua_path)
        print("[GRIPPER_UPLOAD_LUA] This file calls ActGripper/MoveGripper directly.")
        print("[GRIPPER_UPLOAD_LUA] Fairino tool-end RS485 needs a vendor open-protocol Lua file instead.")
        print("[GRIPPER_UPLOAD_LUA] Expected file name is usually like AXLE_LUA_End_DaHuan_WeiHang.lua.")
        print("[GRIPPER_UPLOAD_LUA] Use --allow-demo-lua only if you intentionally want to upload this demo file.")
        return

    config = load_config()
    setup_fairino_sdk_path()
    from fairino import Robot

    print("[GRIPPER_UPLOAD_LUA] Robot IP:", config["robot_ip"])
    print("[GRIPPER_UPLOAD_LUA] Lua file:", lua_path)
    Robot.RPC.is_connect = True
    robot = Robot.RPC(config["robot_ip"])
    Robot.RPC.is_connect = True
    try:
        print("[GRIPPER_UPLOAD_LUA] AxleLuaUpload:", robot.AxleLuaUpload(str(lua_path)))
        print("[GRIPPER_UPLOAD_LUA] SetAxleCommunicationParam:", robot.robot.SetAxleCommunicationParam(7, 8, 1, 0, 5, 3, 1))
        print("[GRIPPER_UPLOAD_LUA] SetAxleLuaEnable:", robot.robot.SetAxleLuaEnable(1))
        print("[GRIPPER_UPLOAD_LUA] SetAxleLuaEnableDeviceType:", robot.robot.SetAxleLuaEnableDeviceType(0, 1, 0))
        print("[GRIPPER_UPLOAD_LUA] SetAxleLuaGripperFunc(1):", robot.robot.SetAxleLuaGripperFunc(1, [1] * 16))
        print("[GRIPPER_UPLOAD_LUA] GetAxleLuaGripperFunc(1):", robot.robot.GetAxleLuaGripperFunc(1))
        print("[GRIPPER_UPLOAD_LUA] GetAxleLuaEnableDevice:", robot.robot.GetAxleLuaEnableDevice())
        print("[GRIPPER_UPLOAD_LUA] GetRobotErrorCode:", robot.robot.GetRobotErrorCode())
    finally:
        if hasattr(robot, "CloseRPC"):
            robot.CloseRPC()


if __name__ == "__main__":
    main()
