import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import build_lifted_corner_pose
from modules.shape_api import build_shape_poses, list_shapes


def main() -> None:
    parser = argparse.ArgumentParser(description="Check IK for shape poses without moving the robot.")
    parser.add_argument("--shape", choices=list_shapes(), default="square")
    parser.add_argument("--point", type=int, default=0, help="0-based pose index to check.")
    parser.add_argument("--return-corner", help="Check a lifted paper corner pose instead of a shape point.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.return_corner:
        pose = build_lifted_corner_pose(config, args.return_corner)
        label = f"return corner {args.return_corner}"
    else:
        poses = build_shape_poses(config, args.shape)
        pose = poses[args.point]
        label = f"{args.shape} point {args.point}"

    print("[IK_SHAPE] Config:", CONFIG_PATH)
    print("[IK_SHAPE] Target:", label)
    print("[IK_SHAPE] Pose:", pose)
    print("[IK_SHAPE] This test does not send MoveJ or MoveL")

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )
    try:
        if not controller.connect():
            print("[IK_SHAPE] Raw XML-RPC connection failed")
            return
        joint = controller.resolve_joint_for_pose(pose)
        print("[IK_SHAPE] IK joint:", joint)
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
