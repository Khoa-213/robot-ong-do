import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_raw_controller import FairinoRawXmlRpcController
from modules.paper_zone import (
    build_lifted_corner_pose,
    build_line_demo_poses,
    get_paper_corners,
    paper_size_from_corners,
)
from modules.safety_check import validate_measured_paper_line_demo


CONFIG_PATH = PROJECT_ROOT / "config" / "robot_config.json"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy = config.get("connection_policy", {})
    motion_strategy = config.get("motion_strategy", {})

    start_pose, end_pose = build_line_demo_poses(config)
    after_draw = config.get("after_draw", {})
    return_pose = None
    if after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))
    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)
    enable_move = bool(config["enable_robot_move"])
    allow_raw_motion = bool(policy.get("allow_raw_xmlrpc_motion", False))

    print("[RAW_DEMO] Config:", CONFIG_PATH)
    print("[RAW_DEMO] Measured paper width/height:", round(width, 3), round(height, 3))
    print("[RAW_DEMO] Paper line demo UV:", config["paper_line_demo"])
    print("[RAW_DEMO] Start pose:", start_pose)
    print("[RAW_DEMO] End pose:", end_pose)
    print("[RAW_DEMO] Return pose:", return_pose)
    print("[RAW_DEMO] enable_robot_move:", enable_move)
    print("[RAW_DEMO] allow_raw_xmlrpc_motion:", allow_raw_motion)
    print("[RAW_DEMO] motion_strategy:", motion_strategy)

    validate_measured_paper_line_demo(start_pose, end_pose, config)
    if return_pose is not None:
        validate_measured_paper_line_demo(return_pose, return_pose, config)
    print("[RAW_DEMO] Safety validation OK")

    if not enable_move or not allow_raw_motion:
        print("[RAW_DEMO] SAFETY LOCK: raw XML-RPC movement disabled")
        print("[RAW_DEMO] This script will connect and check IK, but will NOT send MoveL")

    controller = FairinoRawXmlRpcController(
        robot_ip=config["robot_ip"],
        tool=int(config["tool"]),
        user=int(config["user"]),
    )

    try:
        controller.connect()
        controller.draw_line_air(
            start_pose=start_pose,
            end_pose=end_pose,
            return_pose=return_pose,
            vel=float(config["default_vel"]),
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
