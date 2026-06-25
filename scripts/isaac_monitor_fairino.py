from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
import numpy as np
import queue
from xmlrpc.server import SimpleXMLRPCServer
import threading

# This script must run with Isaac Sim's python.bat/python.sh, not the project venv.
# pyrefly: ignore [missing-import]
from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor a Fairino FR3 robot controller and mirror its joints/TCP movement in Isaac Sim."
    )
    parser.add_argument(
        "--ip",
        type=str,
        default="192.168.58.2",
        help="IP address of the Fairino robot controller or FRSim emulator.",
    )
    parser.add_argument(
        "--usd",
        type=str,
        default="D:/Capstone/fairino3.usd",
        help="Path to the fairino3.usd stage file.",
    )
    parser.add_argument("--headless", action="store_true", help="Run simulation in headless mode.")
    parser.add_argument(
        "--mock-server",
        action="store_true",
        help="Run a mock XML-RPC server inside the script to act as a virtual controller.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Clean sys.argv to prevent Isaac Sim's internal parser from exiting early on custom arguments
    import sys
    sys.argv = [sys.argv[0]]

    # Start Isaac Sim application
    simulation_app = SimulationApp({"headless": args.headless})

    # pyrefly: ignore [missing-import]
    import omni.usd
    # pyrefly: ignore [missing-import]
    import omni.kit.app
    # pyrefly: ignore [missing-import]
    from pxr import Gf, UsdGeom, UsdLux, Sdf

    # Try importing using Isaac Sim namespaces
    try:
        # pyrefly: ignore [missing-import]
        from isaacsim.core.api.world import World
        # pyrefly: ignore [missing-import]
        from isaacsim.core.api.robots import Robot
        # pyrefly: ignore [missing-import]
        from isaacsim.core.api.objects import VisualSphere
        # pyrefly: ignore [missing-import]
        from isaacsim.core.prims import SingleRigidPrim
    except ImportError:
        # pyrefly: ignore [missing-import]
        from omni.isaac.core import World
        # pyrefly: ignore [missing-import]
        from omni.isaac.core.robots import Robot
        # pyrefly: ignore [missing-import]
        from omni.isaac.core.objects import VisualSphere
        # pyrefly: ignore [missing-import]
        from omni.isaac.core.prims import RigidPrim as SingleRigidPrim

    # 1. Open the user's Fairino USD stage
    usd_path = Path(args.usd)
    if not usd_path.exists():
        raise FileNotFoundError(f"Fairino USD stage not found at: {usd_path}")

    print(f"Opening Fairino USD stage: {usd_path}")
    omni.usd.get_context().open_stage(str(usd_path))
    
    # Initialize simulation world
    world = World(stage_units_in_meters=1.0)
    stage = omni.usd.get_context().get_stage()

    # Load robot config to create the wood table and paper environment
    config_path = Path("config/robot_config.json")
    paper_config = {}
    table_height = 0.4
    paper_thick = 0.002
    
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            paper_config = config_data.get("paper", {})
        except Exception as e:
            print(f"Warning: could not parse config/robot_config.json: {e}")

    # 2. Automatically build the table and paper environment
    _create_environment(stage, paper_config, table_height, paper_thick)

    # 3. Add the robot to the simulation scene
    robot_prim_path = "/World/fairino3_v6_robot"
    prim = stage.GetPrimAtPath(robot_prim_path)
    if not prim.IsValid():
        # Fallback search if path is different
        for path in ["/fairino3_v6_robot", "/World/fairino3", "/fairino3"]:
            p = stage.GetPrimAtPath(path)
            if p.IsValid():
                robot_prim_path = path
                prim = p
                break
        if not prim.IsValid():
            raise RuntimeError("Could not find Fairino robot prim in the USD stage! Checked paths: /World/fairino3_v6_robot")

    print(f"Found Fairino robot prim at: {robot_prim_path}")
    
    # Adjust robot base position to stand on the table (Z = table_height)
    robot_xform = UsdGeom.Xformable(prim)
    translate_op = None
    for op in robot_xform.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
            break
    if translate_op is None:
        translate_op = robot_xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(0.0, 0.0, table_height))

    # Wrap as Robot object and initialize
    fairino_robot = world.scene.add(Robot(prim_path=robot_prim_path, name="fairino_robot"))
    
    # Setup path preview group
    preview_root_path = "/World/DrawingPath"
    UsdGeom.Xform.Define(stage, preview_root_path)
    drawn_points_count = 0

    # Start simulation world
    world.reset()

    # Identify end effector link name and prim path (typically the last link in the chain)
    # pyrefly: ignore [missing-import]
    from pxr import Usd
    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    
    ee_link_name = None
    ee_prim_path = None
    for l_name in ["flange", "link6", "link_6", "wrist3_link", "wrist_3_link", "tool0"]:
        for p in Usd.PrimRange(robot_prim):
            if l_name in p.GetName().lower():
                ee_link_name = p.GetName()
                ee_prim_path = p.GetPath()
                break
        if ee_link_name:
            break
    
    if not ee_link_name:
        for p in Usd.PrimRange(robot_prim):
            ee_link_name = p.GetName()
            ee_prim_path = p.GetPath()
    
    print(f"End effector link identified: {ee_link_name} at path {ee_prim_path}")

    # Wrap ee as SingleRigidPrim and add to scene
    ee_rigid = world.scene.add(SingleRigidPrim(prim_path=str(ee_prim_path), name="ee_rigid"))

    # Start simulation world
    world.reset()

    # Initialize physics view for the rigid body
    ee_rigid.initialize(world.physics_sim_view)

    # Helper function to get world pose of end effector using physics view
    def get_ee_world_pose():
        pos, quat = ee_rigid.get_world_pose()
        return [
            float(pos[0]), float(pos[1]), float(pos[2]),
            float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
        ]
    
    print(f"End effector link identified: {ee_link_name}")

    # Read paper config for coordinate mapping
    paper_z_real = float(paper_config.get("paper_z", 292.206))

    # Helper math functions for mock server and kinematics
    def quat_to_euler_deg(qw, qx, qy, qz):
        import math
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

    def euler_to_quat(rx, ry, rz):
        rot_x = Gf.Rotation(Gf.Vec3d(1, 0, 0), rx)
        rot_y = Gf.Rotation(Gf.Vec3d(0, 1, 0), ry)
        rot_z = Gf.Rotation(Gf.Vec3d(0, 0, 1), rz)
        rot = rot_x * rot_y * rot_z
        return rot.GetQuaternion()

    # Numerical IK solver using Scipy optimization
    def solve_numerical_ik(target_pos: np.ndarray, target_quat) -> np.ndarray:
        from scipy.optimize import minimize
        q_real = target_quat.GetReal()
        q_img = target_quat.GetImaginary()
        target_q = np.array([q_real, q_img[0], q_img[1], q_img[2]])
        joints_init = fairino_robot.get_joint_positions()
        if joints_init is None:
            # Fallback to zero angles if physics view is not yet fully initialized
            joints_init = np.zeros(6)

        def objective(joints):
            fairino_robot.set_joint_positions(joints)
            pose = get_ee_world_pose()
            pos_err = np.sum((pose[:3] - target_pos) ** 2)
            rot_err = 1.0 - np.abs(np.dot(pose[3:], target_q))
            return pos_err + 0.1 * rot_err

        bounds = [(-np.pi, np.pi) for _ in range(len(joints_init))]
        res = minimize(objective, joints_init, method="SLSQP", bounds=bounds, options={"maxiter": 20, "ftol": 1e-5})
        return res.x

    # Communication queues for thread-safety
    request_queue = queue.Queue()
    motion_queue = []
    spline_cache = []

    # Mock XML-RPC Server implementations
    class MockFairinoXmlRpcServer:
        def _send_request(self, cmd, *args):
            event = threading.Event()
            holder = []
            request_queue.put((cmd, args, event, holder))
            if event.wait(timeout=5.0):
                return holder[0]
            return [-1, "Timeout waiting for simulator main thread"]

        def _dispatch(self, method, params):
            func = getattr(self, method, None)
            if func is not None:
                try:
                    return func(*params)
                except Exception as e:
                    print(f"[MOCK_SERVER] Error executing {method}: {e}")
                    return [-1, str(e)]
            
            # Gripper or diagnostic commands fallback
            # print(f"[MOCK_SERVER] Fallback called for method: {method}")
            if method.startswith("Get"):
                return [0, 0]
            return 0

        def GetControllerIP(self):
            return [0, "127.0.0.1"]

        def GetRobotErrorCode(self):
            return [0, 0]

        def CloseRPC(self):
            return 0

        def GetActualJointPosDegree(self, flag=0):
            return self._send_request("GET_JOINTS")

        def GetActualTCPPose(self, flag=0):
            return self._send_request("GET_TCP")

        def GetInverseKin(self, flag, pose, config=-1):
            return self._send_request("IK", pose)

        def GetInverseKinRef(self, flag, pose, joint_ref):
            return self._send_request("IK", pose)

        def MoveJ(self, joint_pos, pose, tool=0, user=0, vel=10.0, acc=0.0, ovl=100.0, exaxis_pos=None, blendT=-1.0, offset_flag=0, offset_pos=None):
            return self._send_request("MOVE_JOINT", joint_pos)

        def MoveL(self, params):
            # First 6 parameters are joint positions
            joint_pos = params[0:6]
            return self._send_request("MOVE_JOINT", joint_pos)

        def NewSplineStart(self, spline_type, average_time_ms):
            return self._send_request("SPLINE_START")

        def NewSplinePoint(self, desc_pos, tool, user, lastFlag, vel, acc, blendR):
            return self._send_request("SPLINE_POINT", desc_pos, lastFlag)

        def NewSplineEnd(self):
            return self._send_request("SPLINE_END")

    # Command Router for main thread
    def process_mock_request(cmd, cmd_args):
        if cmd == "GET_JOINTS":
            joints_rad = fairino_robot.get_joint_positions()
            joints_deg = [float(np.rad2deg(j)) for j in joints_rad]
            return [0, *joints_deg]
            
        elif cmd == "GET_TCP":
            pose = get_ee_world_pose()
            x_mm = pose[0] * 1000.0
            y_mm = pose[1] * 1000.0
            z_mm = paper_z_real + (pose[2] - (table_height + paper_thick)) * 1000.0
            rx, ry, rz = quat_to_euler_deg(pose[3], pose[4], pose[5], pose[6])
            return [0, [x_mm, y_mm, z_mm, rx, ry, rz]]
            
        elif cmd == "IK":
            pose_mm_deg = cmd_args[0]
            x_m = pose_mm_deg[0] * 0.001
            y_m = pose_mm_deg[1] * 0.001
            z_m = (table_height + paper_thick) + (pose_mm_deg[2] - paper_z_real) * 0.001
            target_pos = np.array([x_m, y_m, z_m])
            target_quat = euler_to_quat(pose_mm_deg[3], pose_mm_deg[4], pose_mm_deg[5])
            joints_rad = solve_numerical_ik(target_pos, target_quat)
            joints_deg = [float(np.rad2deg(j)) for j in joints_rad]
            return [0, *joints_deg]
            
        elif cmd == "MOVE_JOINT":
            joints_deg = cmd_args[0]
            joints_rad = [np.deg2rad(j) for j in joints_deg]
            motion_queue.append(np.array(joints_rad))
            return 0
            
        elif cmd == "SPLINE_START":
            spline_cache.clear()
            return 0
            
        elif cmd == "SPLINE_POINT":
            pose_mm_deg, last_flag = cmd_args
            x_m = pose_mm_deg[0] * 0.001
            y_m = pose_mm_deg[1] * 0.001
            z_m = (table_height + paper_thick) + (pose_mm_deg[2] - paper_z_real) * 0.001
            target_pos = np.array([x_m, y_m, z_m])
            target_quat = euler_to_quat(pose_mm_deg[3], pose_mm_deg[4], pose_mm_deg[5])
            joints_rad = solve_numerical_ik(target_pos, target_quat)
            spline_cache.append(joints_rad)
            if last_flag == 1:
                for j in spline_cache:
                    motion_queue.append(np.array(j))
                spline_cache.clear()
            return 0
            
        elif cmd == "SPLINE_END":
            for j in spline_cache:
                motion_queue.append(np.array(j))
            spline_cache.clear()
            return 0
            
        return 0

    # Start the controller connection / server thread
    controller_raw = None
    reconnect_in_progress = False

    if args.mock_server:
        print("[MOCK] Starting Mock XML-RPC Server on port 20003...")
        try:
            xmlrpc_server = SimpleXMLRPCServer(("127.0.0.1", 20003), logRequests=False, allow_none=True)
            xmlrpc_server.register_instance(MockFairinoXmlRpcServer())
            
            # Set socket option to reuse port immediately on shutdown
            import socket
            xmlrpc_server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            t_server = threading.Thread(target=xmlrpc_server.serve_forever, daemon=True)
            t_server.start()
            print("[MOCK] Mock XML-RPC Server running in background thread.")
        except Exception as exc:
            print(f"[MOCK] Failed to start Mock XML-RPC Server: {exc}")
            raise

        print("----------------------------------------------------------------")
        print("Direct Control Simulation Active (Mock Server Mode)!")
        print("1. Run your code/test script pointing to IP 127.0.0.1.")
        print("2. The simulated robot will solve IK/FK and write in Isaac Sim.")
        print("Press Ctrl+C in terminal to stop.")
        print("----------------------------------------------------------------")

    else:
        # Import Fairino SDK using the project modules path setup
        import sys
        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from modules.sdk_path import setup_fairino_sdk_path
        setup_fairino_sdk_path()
        
        # pyrefly: ignore [missing-import]
        from fairino import Robot as FairinoRobotSDK
        
        sdk_robot = None
        reconnect_in_progress = False

        def reconnect_thread_func() -> None:
            nonlocal sdk_robot, controller_raw, reconnect_in_progress
            try:
                robot = FairinoRobotSDK.RPC(args.ip)
                is_conn = getattr(robot, "is_connect", False)
                if callable(is_conn):
                    is_conn = is_conn()
                if is_conn:
                    raw = getattr(robot, "robot", None)
                    if raw is not None:
                        sdk_robot = robot
                        controller_raw = raw
                        print("[THREAD] Connection to Fairino controller successful! Real-time mirroring is now active.")
                    else:
                        print("[THREAD] Connected but raw controller object is None.")
                else:
                    pass
            except Exception as e:
                pass
            finally:
                reconnect_in_progress = False

        print(f"Connecting to Fairino Controller RPC at {args.ip} in background thread...")
        reconnect_in_progress = True
        t_init = threading.Thread(target=reconnect_thread_func, daemon=True)
        t_init.start()

        print("----------------------------------------------------------------")
        print("Real-time Mirroring Active (Mirror Mode)!")
        print("1. Run your code/test script to send commands to the Fairino robot controller.")
        print("2. The robot in Isaac Sim will mirror the joints and draw on the virtual paper.")
        print("Press Ctrl+C in terminal to stop.")
        print("----------------------------------------------------------------")

        last_reconnect_time = time.time()

    # Monitor and command execution loop
    try:
        while simulation_app.is_running():
            # Step simulation
            world.step(render=True)

            if args.mock_server:
                # 1. Process requests from background XML-RPC server thread
                while not request_queue.empty():
                    try:
                        cmd, cmd_args, event, holder = request_queue.get_nowait()
                    except queue.Empty:
                        break
                    
                    try:
                        result = process_mock_request(cmd, cmd_args)
                        holder.append(result)
                    except Exception as ex:
                        print(f"[MOCK] Error executing command {cmd}: {ex}")
                        holder.append([-1, str(ex)])
                    finally:
                        event.set()

                # 2. Smoothly interpolate joints towards the queued targets
                if motion_queue:
                    target_joints = motion_queue[0]
                    current_joints = fairino_robot.get_joint_positions()
                    if current_joints is None:
                        # Skip this step and wait for physics view to initialize
                        continue
                    
                    diff = target_joints - current_joints
                    dist = np.linalg.norm(diff)
                    
                    # Limit joint velocity per simulation step for smooth movement
                    max_step = 0.08
                    if dist > max_step:
                        step_joints = current_joints + (diff / dist) * max_step
                    else:
                        step_joints = target_joints
                        motion_queue.pop(0) # Target reached
                    
                    fairino_robot.set_joint_positions(step_joints)

            else:
                # Mirror mode: reconnect and pull joints
                if controller_raw is None:
                    current_time = time.time()
                    if not reconnect_in_progress and (current_time - last_reconnect_time > 5.0):
                        last_reconnect_time = current_time
                        reconnect_in_progress = True
                        print(f"Reconnecting to Fairino Controller RPC at {args.ip}...")
                        t = threading.Thread(target=reconnect_thread_func, daemon=True)
                        t.start()
                    
                    time.sleep(0.01)
                    continue

                res_j = controller_raw.GetActualJointPosDegree(0)
                if isinstance(res_j, list) and len(res_j) > 6 and res_j[0] == 0:
                    joints_deg = [float(v) for v in res_j[1:7]]
                    joints_rad = np.deg2rad(joints_deg)
                    fairino_robot.set_joint_positions(joints_rad)

            # 3. Determine TCP coordinates and draw ink points
            is_valid_tcp = False
            tcp_x_mm = 0.0
            tcp_y_mm = 0.0
            tcp_z_mm = 0.0

            if args.mock_server:
                pose = get_ee_world_pose()
                tcp_x_mm = pose[0] * 1000.0
                tcp_y_mm = pose[1] * 1000.0
                tcp_z_mm = paper_z_real + (pose[2] - (table_height + paper_thick)) * 1000.0
                is_valid_tcp = True
            else:
                if controller_raw is not None:
                    res_tcp = controller_raw.GetActualTCPPose(0)
                    if isinstance(res_tcp, list) and len(res_tcp) > 6 and res_tcp[0] == 0:
                        tcp_pose = [float(v) for v in res_tcp[1:7]]
                        tcp_x_mm = tcp_pose[0]
                        tcp_y_mm = tcp_pose[1]
                        tcp_z_mm = tcp_pose[2]
                        is_valid_tcp = True

            if is_valid_tcp:
                # If TCP height is close to or below the paper surface + margin (5mm)
                is_drawing = tcp_z_mm <= (paper_z_real + 5.0)
                
                if is_drawing and drawn_points_count < 2000:
                    sim_x = tcp_x_mm * 0.001
                    sim_y = tcp_y_mm * 0.001
                    sim_z = table_height + paper_thick + (tcp_z_mm - paper_z_real) * 0.001
                    
                    sphere_name = f"p_{drawn_points_count:04d}"
                    sphere_path = f"{preview_root_path}/{sphere_name}"
                    
                    sphere = UsdGeom.Sphere.Define(stage, sphere_path)
                    sphere.CreateRadiusAttr(0.003)
                    sphere.CreateDisplayColorAttr([(0.0, 0.8, 0.0)]) # Green ink
                    UsdGeom.Xformable(sphere).AddTranslateOp().Set(
                        Gf.Vec3d(sim_x, sim_y, sim_z)
                    )
                    drawn_points_count += 1

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Stopping monitor...")
    except Exception as e:
        print(f"[FATAL] Exception in monitor loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_app.close()


def _create_environment(stage, paper_config: dict, table_height: float, paper_thick: float) -> None:
    # pyrefly: ignore [missing-import]
    from pxr import Gf, UsdGeom

    # Remove old environment prims to recreate them
    for path in ["/World/Environment", "/Environment"]:
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            stage.RemovePrim(path)

    # Extract paper configuration from corners
    if "corners" in paper_config:
        corners = paper_config["corners"]
        try:
            top_left = np.array(corners["top_left"][:3]) / 1000.0
            top_right = np.array(corners["top_right"][:3]) / 1000.0
            bottom_right = np.array(corners["bottom_right"][:3]) / 1000.0
            bottom_left = np.array(corners["bottom_left"][:3]) / 1000.0
            
            center = (top_left + top_right + bottom_right + bottom_left) / 4.0
            width = np.linalg.norm(bottom_right - bottom_left)
            height = np.linalg.norm(top_left - bottom_left)
        except Exception as e:
            print(f"Error parsing paper corners, using default: {e}")
            center = np.array([0.0, 0.45, 0.292])
            width = 0.210
            height = 0.297
    else:
        center = np.array([0.0, 0.45, 0.292])
        width = 0.210
        height = 0.297

    # Create Group
    UsdGeom.Xform.Define(stage, "/World/Environment")

    # Create Table Top
    table = UsdGeom.Cube.Define(stage, "/World/Environment/Table")
    table.CreateSizeAttr(1.0)
    table.CreateDisplayColorAttr([(0.5, 0.35, 0.2)]) # Wooden color
    
    table_thick = 0.02
    table_xform = UsdGeom.Xformable(table)
    table_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.35, table_height - table_thick/2.0))
    table_xform.AddScaleOp().Set(Gf.Vec3f(1.2, 1.2, table_thick))
    
    # Add table legs
    for index, offset in enumerate([(-0.55, -0.2), (-0.55, 0.9), (0.55, -0.2), (0.55, 0.9)]):
        leg = UsdGeom.Cube.Define(stage, f"/World/Environment/TableLeg_{index}")
        leg.CreateSizeAttr(1.0)
        leg.CreateDisplayColorAttr([(0.2, 0.2, 0.2)]) # Metal dark grey
        
        leg_height = table_height - table_thick
        leg_z = leg_height / 2.0
        leg_xform = UsdGeom.Xformable(leg)
        leg_xform.AddTranslateOp().Set(Gf.Vec3d(offset[0], offset[1], leg_z))
        leg_xform.AddScaleOp().Set(Gf.Vec3f(0.04, 0.04, leg_height))

    # Create Paper Sheet
    paper = UsdGeom.Cube.Define(stage, f"/World/Environment/Paper")
    paper.CreateSizeAttr(1.0)
    paper.CreateDisplayColorAttr([(1.0, 1.0, 1.0)]) # White paper
    
    paper_xform = UsdGeom.Xformable(paper)
    # Center paper (Z = table_height + paper_thick/2)
    paper_xform.AddTranslateOp().Set(Gf.Vec3d(center[0], center[1], table_height + paper_thick/2.0))
    paper_xform.AddScaleOp().Set(Gf.Vec3f(width, height, paper_thick))
    
    print(f"Environment created in simulation: Table Z={table_height:.3f}m, Paper Size={width:.3f}x{height:.3f}m")


if __name__ == "__main__":
    main()
