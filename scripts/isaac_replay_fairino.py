from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

# This script must run with Isaac Sim's python.bat/python.sh, not the project venv.
# pyrefly: ignore [missing-import]
from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a Cartesian trajectory on a Fairino FR3 robot in Isaac Sim offline."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/exports/isaac/tam_trajectory.json"),
        help="Path to the Isaac-compatible trajectory JSON file.",
    )
    parser.add_argument(
        "--usd",
        type=str,
        default="D:/Capstone/fairino3.usd",
        help="Path to the fairino3.usd stage file.",
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--loop", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Clean sys.argv to prevent Isaac Sim's internal parser from exiting early on custom arguments
    import sys
    sys.argv = [sys.argv[0]]

    # Start simulation app
    simulation_app = SimulationApp({"headless": args.headless})

    # pyrefly: ignore [missing-import]
    import omni.usd
    # pyrefly: ignore [missing-import]
    from pxr import Gf, UsdGeom

    # Try importing using Isaac Sim namespaces
    try:
        # pyrefly: ignore [missing-import]
        from isaacsim.core.api.world import World
        # pyrefly: ignore [missing-import]
        from isaacsim.core.api.robots import Robot
        # pyrefly: ignore [missing-import]
        from isaacsim.core.prims import SingleRigidPrim
    except ImportError:
        # pyrefly: ignore [missing-import]
        from omni.isaac.core import World
        # pyrefly: ignore [missing-import]
        from omni.isaac.core.robots import Robot
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

    # Load trajectory dataset
    if not args.input.exists():
        raise FileNotFoundError(f"Trajectory input file not found: {args.input}")
    
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    episode = payload["episodes"][0]
    frames = episode.get("end_effector_targets", [])
    if not frames:
        raise ValueError("No end_effector_targets found in the trajectory file.")

    # Load robot config to create the environment
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

    # Calculate offset_z to align writing path with paper surface (dynamic offset based on min Z)
    first_z = min(f["position"]["z"] for f in frames)
    offset_z = table_height + paper_thick - first_z
    print(f"Minimum Z in dataset: {first_z:.4f}m. Table height: {table_height:.3f}m, Paper thick: {paper_thick:.3f}m.")
    print(f"Calculated dynamic Z-offset: {offset_z:.4f}m to align writing path with paper surface.")

    # 2. Draw preview path points
    _create_path_points(stage, frames, offset_z)
            
    # 3. Create Table and Paper environment
    _create_environment(stage, paper_config, table_height, paper_thick)

    # 4. Detect and position the Fairino robot base
    robot_prim_path = "/World/fairino3_v6_robot"
    prim = stage.GetPrimAtPath(robot_prim_path)
    if not prim.IsValid():
        for path in ["/fairino3_v6_robot", "/World/fairino3", "/fairino3"]:
            p = stage.GetPrimAtPath(path)
            if p.IsValid():
                robot_prim_path = path
                prim = p
                break
        if not prim.IsValid():
            raise RuntimeError("Could not find Fairino robot prim in the USD stage!")

    # Place the base on the table (Z = table_height, Y = 0.0m)
    robot_xform = UsdGeom.Xformable(prim)
    translate_op = None
    for op in robot_xform.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
            break
    if translate_op is None:
        translate_op = robot_xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(0.0, 0.0, table_height))

    # Wrap in Robot class
    fairino_robot = world.scene.add(Robot(prim_path=robot_prim_path, name="fairino_robot"))

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

    # Wrap ee as SingleRigidPrim
    ee_rigid = world.scene.add(SingleRigidPrim(prim_path=str(ee_prim_path), name="ee_rigid"))

    # Start simulation world (initializes articulation joints)
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


    # Get drawing orientation from config
    draw_orientation = paper_config.get("draw_orientation", [180.0, 0.0, 0.0])
    if not isinstance(draw_orientation, list) or len(draw_orientation) != 3:
        draw_orientation = [180.0, 0.0, 0.0]

    # Replay Trajectory Loop
    print(f"Replaying {episode['episode_id']} ({episode.get('task', '')}) with {len(frames)} frames offline...")
    
    # Cache initial joints to speed up IK solver search
    current_joints = fairino_robot.get_joint_positions()
    if current_joints is None:
        current_joints = np.zeros(6)

    # Numerical IK solver using Scipy optimization
    def solve_numerical_ik(target_pos: np.ndarray, target_quat_gf) -> np.ndarray:
        nonlocal current_joints
        
        # Convert target quaternion to w, x, y, z array
        q_real = target_quat_gf.GetReal()
        q_img = target_quat_gf.GetImaginary()
        target_q = np.array([q_real, q_img[0], q_img[1], q_img[2]])

        # Objective function to minimize position and rotation errors
        def objective(joints):
            # Temporarily set joints in physics stage (no physics step)
            fairino_robot.set_joint_positions(joints)
            # Query the forward kinematics pose from USD
            pose = get_ee_world_pose()
            
            # Position error square
            pos_err = np.sum((pose[:3] - target_pos) ** 2)
            
            # Orientation error (quaternion distance)
            rot_err = 1.0 - np.abs(np.dot(pose[3:], target_q))
            
            return pos_err + 0.1 * rot_err

        # Bounds for the 6 revolute joints (typically -pi to pi or similar)
        bounds = [(-np.pi, np.pi) for _ in range(len(current_joints))]
        
        # Run optimization starting from current joint values
        res = minimize(objective, current_joints, method="SLSQP", bounds=bounds, options={"maxiter": 20, "ftol": 1e-5})
        return res.x

    while simulation_app.is_running():
        # Setup and replay once
        previous_t = frames[0].get("t", 0.0)
        
        for frame in frames:
            if not simulation_app.is_running():
                break
                
            position = frame["position"]
            rot_euler = frame["rotation_euler"]
            
            # Target Cartesian position (meters) shifted by offset_z to lie on the paper
            target_pos = np.array([position["x"], position["y"], position["z"] + offset_z])
            
            # Compute orientation quaternion
            is_zero_rotation = all(abs(rot_euler[k]) < 1e-4 for k in ["x", "y", "z"])
            if is_zero_rotation:
                orient = draw_orientation
                rot_x = Gf.Rotation(Gf.Vec3d(1, 0, 0), orient[0])
                rot_y = Gf.Rotation(Gf.Vec3d(0, 1, 0), orient[1])
                rot_z = Gf.Rotation(Gf.Vec3d(0, 0, 1), orient[2])
            else:
                rot_x = Gf.Rotation(Gf.Vec3d(1, 0, 0), rot_euler["x"])
                rot_y = Gf.Rotation(Gf.Vec3d(0, 1, 0), rot_euler["y"])
                rot_z = Gf.Rotation(Gf.Vec3d(0, 0, 1), rot_euler["z"])
                
            rot = rot_x * rot_y * rot_z
            target_quat = rot.GetQuaternion()

            # Solve Inverse Kinematics offline using numerical optimization
            joint_positions = solve_numerical_ik(target_pos, target_quat)
            
            fairino_robot.set_joint_positions(joint_positions)
            
            # Update cache
            current_joints = joint_positions
            
            # Step the simulation loop
            world.step(render=True)
            
            # Control speed
            dt = max(0.0, frame.get("t", previous_t) - previous_t) / args.speed
            previous_t = frame.get("t", previous_t)
            if dt > 0:
                time.sleep(min(dt, 0.05))
                
        if not args.loop:
            break

    # Keep stage visible for a moment
    if not args.headless:
        print("Replay finished. Keeping stage visible for 3 seconds...")
        for _ in range(180):
            if not simulation_app.is_running():
                break
            world.step(render=True)
            time.sleep(1.0 / 60.0)

    simulation_app.close()


def _create_path_points(stage, frames: list[dict], offset_z: float = 0.0) -> None:
    # pyrefly: ignore [missing-import]
    from pxr import Gf, UsdGeom
    
    root_path = "/World/PathPreview"
    prim = stage.GetPrimAtPath(root_path)
    if prim.IsValid():
        stage.RemovePrim(root_path)
        
    UsdGeom.Xform.Define(stage, root_path)
    stride = max(1, len(frames) // 80)
    for index, frame in enumerate(frames[::stride]):
        position = frame["position"]
        sphere = UsdGeom.Sphere.Define(stage, f"{root_path}/p_{index:04d}")
        sphere.CreateRadiusAttr(0.006)
        sphere.CreateDisplayColorAttr([(0.0, 0.8, 0.0)])
        UsdGeom.Xformable(sphere).AddTranslateOp().Set(
            Gf.Vec3d(position["x"], position["y"], position["z"] + offset_z)
        )


def _create_environment(stage, paper_config: dict, table_height: float, paper_thick: float) -> None:
    # pyrefly: ignore [missing-import]
    from pxr import Gf, UsdGeom

    for path in ["/World/Environment", "/Environment"]:
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            stage.RemovePrim(path)

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
    table.CreateDisplayColorAttr([(0.5, 0.35, 0.2)]) # Wooden
    
    table_thick = 0.02
    table_xform = UsdGeom.Xformable(table)
    table_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.35, table_height - table_thick/2.0))
    table_xform.AddScaleOp().Set(Gf.Vec3f(1.2, 1.2, table_thick))
    
    # Add table legs
    for index, offset in enumerate([(-0.55, -0.2), (-0.55, 0.9), (0.55, -0.2), (0.55, 0.9)]):
        leg = UsdGeom.Cube.Define(stage, f"/World/Environment/TableLeg_{index}")
        leg.CreateSizeAttr(1.0)
        leg.CreateDisplayColorAttr([(0.2, 0.2, 0.2)]) # Metal
        
        leg_height = table_height - table_thick
        leg_z = leg_height / 2.0
        leg_xform = UsdGeom.Xformable(leg)
        leg_xform.AddTranslateOp().Set(Gf.Vec3d(offset[0], offset[1], leg_z))
        leg_xform.AddScaleOp().Set(Gf.Vec3f(0.04, 0.04, leg_height))

    # Create Paper Sheet
    paper = UsdGeom.Cube.Define(stage, f"/World/Environment/Paper")
    paper.CreateSizeAttr(1.0)
    paper.CreateDisplayColorAttr([(1.0, 1.0, 1.0)]) # White A4
    
    paper_xform = UsdGeom.Xformable(paper)
    paper_xform.AddTranslateOp().Set(Gf.Vec3d(center[0], center[1], table_height + paper_thick/2.0))
    paper_xform.AddScaleOp().Set(Gf.Vec3f(width, height, paper_thick))


if __name__ == "__main__":
    main()
