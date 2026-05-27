import sys
import os
import time
from pathlib import Path

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    SDK_ROOT = PROJECT_ROOT / "fairino-python-sdk" / "windows"
    LIB_PATH = SDK_ROOT / "libfairino"

    sys.path.append(str(SDK_ROOT))

    if LIB_PATH.exists():
        os.add_dll_directory(str(LIB_PATH))

    from fairino import Robot

    print("Fairino SDK import successfully")
    print("SDK_ROOT:", SDK_ROOT)
    print("LIB_PATH:", LIB_PATH)

except Exception as e:
    print("Fairino SDK import failed")
    print(e)
    Robot = None


ROBOT_IP = "192.168.58.2"

tool = 0
user = 0

ENABLE_MOVE = False

safe_pose = [300.0, 0.0, 300.0, 180.0, 0.0, 90.0]


def connect_robot():
    if Robot is None:
        print("Cannot connect because Fairino SDK import failed")
        return None

    try:
        print(f"Trying to connect to robot: {ROBOT_IP}")
        robot = Robot.RPC(ROBOT_IP)

        print("Robot object created:", robot)

        # Kiểm tra trạng thái connect thật sự nếu SDK có biến is_connect
        if hasattr(robot, "is_connect"):
            print("robot.is_connect =", robot.is_connect)

            if robot.is_connect is False:
                print("ERROR: Robot object was created, but SDK is_connect = False")
                print("=> Chưa kết nối thật sự với robot controller.")
                return None

        print("OK: Robot SDK connected successfully")
        return robot

    except Exception as e:
        print("Cannot connect to robot")
        print(e)
        return None


def test_movel(robot):
    if robot is None:
        print("Cannot MoveL because robot is not connected")
        return

    print("Target pose:", safe_pose)

    if not ENABLE_MOVE:
        print("SAFETY LOCK: ENABLE_MOVE = False, MoveL command not sent")
        print("After confirming the pose is safe, change ENABLE_MOVE = True")
        return

    try:
        ret = robot.MoveL(
            safe_pose,
            tool,
            user,
            vel=10
        )

        print("MoveL result:", ret)
        time.sleep(1)

    except Exception as e:
        print("MoveL failed")
        print(e)


def main():
    robot = connect_robot()

    if robot is None:
        print("Stop program because robot connection failed")
        return

    test_movel(robot)


if __name__ == "__main__":
    main()