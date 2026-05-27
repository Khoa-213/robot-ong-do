import json
import socket
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.fairino_controller import FairinoController
from modules.paper_zone import build_lifted_corner_pose, build_line_demo_poses, paper_size_from_corners, get_paper_corners
from modules.safety_check import validate_line_demo, validate_measured_paper_line_demo


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
    use_measured_paper = "corners" in config.get("paper", {})
    if use_measured_paper:
        start_pose, end_pose = build_line_demo_poses(config)
    else:
        start_pose = config["line_demo"]["start_pose"]
        end_pose = config["line_demo"]["end_pose"]
    after_draw = config.get("after_draw", {})
    return_pose = None
    if use_measured_paper and after_draw.get("return_to_bottom_left", False):
        return_pose = build_lifted_corner_pose(config, str(after_draw.get("return_corner", "bottom_left")))
    enable_move = bool(config["enable_robot_move"])
    vel = float(config["default_vel"])
    policy = config.get("connection_policy", {})

    print("[TEST_DRAW_LINE_AIR] Config:", CONFIG_PATH)
    print("[TEST_DRAW_LINE_AIR] Robot workspace:", config["robot_workspace"])
    print("[TEST_DRAW_LINE_AIR] Paper zone:", config["paper"])
    if use_measured_paper:
        corners = get_paper_corners(config)
        width, height = paper_size_from_corners(corners)
        print("[TEST_DRAW_LINE_AIR] Measured paper width/height:", round(width, 3), round(height, 3))
        print("[TEST_DRAW_LINE_AIR] Paper line demo UV:", config["paper_line_demo"])
    print("[TEST_DRAW_LINE_AIR] Z lift:", config["z_safety"]["z_lift_offset"])
    print("[TEST_DRAW_LINE_AIR] Start pose:", start_pose)
    print("[TEST_DRAW_LINE_AIR] End pose:", end_pose)
    print("[TEST_DRAW_LINE_AIR] Return pose:", return_pose)
    print("[TEST_DRAW_LINE_AIR] enable_robot_move:", enable_move)

    if use_measured_paper:
        validate_measured_paper_line_demo(start_pose, end_pose, config)
    else:
        validate_line_demo(start_pose, end_pose, config)
    print("[TEST_DRAW_LINE_AIR] Safety validation OK")

    if not enable_move:
        print("[TEST_DRAW_LINE_AIR] SAFETY LOCK: robot movement disabled")
        print("[TEST_DRAW_LINE_AIR] Preview only, robot will not connect and MoveL will not be sent")
        print("[TEST_DRAW_LINE_AIR] Planned trajectory:")
        print("  1. MoveL start_pose:", start_pose)
        print("  2. MoveL end_pose:", end_pose)
        if return_pose is not None:
            print("  3. MoveL return_pose:", return_pose)
        return

    check_port(robot_ip, 20003)
    check_port(robot_ip, 20005)

    controller = FairinoController(
        robot_ip=robot_ip,
        tool=int(config["tool"]),
        user=int(config["user"]),
        allow_xmlrpc_motion_when_cnde_unavailable=bool(
            policy.get("allow_xmlrpc_motion_when_cnde_unavailable", False)
        ),
    )
    try:
        controller.connect()
        controller.draw_line_air(
            start_pose=start_pose,
            end_pose=end_pose,
            vel=vel,
            enable_move=enable_move,
        )
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
