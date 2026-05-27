import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import (
    build_circle_demo_poses,
    build_lifted_corner_pose,
    get_paper_corners,
    paper_size_from_corners,
)
from modules.safety_check import validate_measured_paper_poses


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})
    circle = config["circle_demo"]
    after_draw = config.get("after_draw", {})

    poses = build_circle_demo_poses(config)
    return_pose = None
    if after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))

    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)
    enable_move = bool(config["enable_robot_move"])
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))

    print("[RAW_CIRCLE] Config:", CONFIG_PATH)
    print("[RAW_CIRCLE] Measured paper width/height:", round(width, 3), round(height, 3))
    print("[RAW_CIRCLE] Circle demo:", circle)
    print("[RAW_CIRCLE] Pose count:", len(poses))
    print("[RAW_CIRCLE] First pose:", poses[0])
    print("[RAW_CIRCLE] Mid pose:", poses[len(poses) // 2])
    print("[RAW_CIRCLE] Last pose:", poses[-1])
    print("[RAW_CIRCLE] Return pose:", return_pose)
    print("[RAW_CIRCLE] enable_robot_move:", enable_move)
    print("[RAW_CIRCLE] allow_raw_xmlrpc_motion:", allow_raw_motion)
    print("[RAW_CIRCLE] motion_strategy:", motion_strategy)

    validate_measured_paper_poses(poses, config)
    if return_pose is not None:
        validate_measured_paper_poses([return_pose], config)
    print("[RAW_CIRCLE] Safety validation OK")

    if not enable_move or not allow_raw_motion:
        print("[RAW_CIRCLE] SAFETY LOCK: raw XML-RPC movement disabled")
        print("[RAW_CIRCLE] This script will connect and check IK, but will NOT send MoveL")

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )

    try:
        controller.connect()
        controller.draw_polyline_air(
            poses=poses,
            return_pose=return_pose,
            vel=float(circle.get("vel", config["default_vel"])),
            return_vel=float(after_draw.get("return_vel", config["default_vel"])),
            approach_with_move_j=bool(motion_strategy.get("approach_with_move_j", False)),
            approach_vel=float(motion_strategy.get("approach_vel", config["default_vel"])),
            enable_move=enable_move,
            allow_raw_xmlrpc_motion=allow_raw_motion,
        )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
