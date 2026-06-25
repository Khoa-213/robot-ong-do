import sys
import numpy as np
from pathlib import Path

# Clean sys.argv for Isaac Sim
sys.argv = [sys.argv[0]]

# pyrefly: ignore [missing-import]
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

# pyrefly: ignore [missing-import]
from pxr import Usd, UsdGeom
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

# Open USD
usd_path = "D:/Capstone/fairino3.usd"
print(f"Opening stage: {usd_path}")
# pyrefly: ignore [missing-import]
import omni.usd
omni.usd.get_context().open_stage(usd_path)

world = World(stage_units_in_meters=1.0)
stage = omni.usd.get_context().get_stage()

# Find robot prim
robot_prim_path = "/World/fairino3_v6_robot"
prim = stage.GetPrimAtPath(robot_prim_path)
if not prim.IsValid():
    for path in ["/fairino3_v6_robot", "/World/fairino3", "/fairino3"]:
        p = stage.GetPrimAtPath(path)
        if p.IsValid():
            robot_prim_path = path
            prim = p
            break

print(f"Found robot: {robot_prim_path}")
fairino_robot = world.scene.add(Robot(prim_path=robot_prim_path, name="fairino_robot"))

# Find EE link
ee_link_name = None
ee_prim_path = None
for l_name in ["flange", "link6", "link_6", "wrist3_link", "wrist_3_link", "tool0"]:
    for p in Usd.PrimRange(prim):
        if l_name in p.GetName().lower():
            ee_link_name = p.GetName()
            ee_prim_path = p.GetPath()
            break
    if ee_link_name:
        break

print(f"EE identified: {ee_link_name} at {ee_prim_path}")

# Add ee as SingleRigidPrim
ee_rigid = SingleRigidPrim(prim_path=str(ee_prim_path), name="ee_rigid")
world.scene.add(ee_rigid)

world.reset()
# Initialize rigid prim view
ee_rigid.initialize(world.physics_sim_view)

def get_ee_pose_usd():
    p = stage.GetPrimAtPath(ee_prim_path)
    xformable = UsdGeom.Xformable(p)
    world_transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    translation = world_transform.ExtractTranslation()
    rotation = world_transform.ExtractRotationQuat()
    return translation[0], translation[1], translation[2]

def get_ee_pose_rigid():
    pos, quat = ee_rigid.get_world_pose()
    return pos[0], pos[1], pos[2]

# Test setting joint positions and reading pose
init_joints = fairino_robot.get_joint_positions()
print(f"Initial joints: {init_joints}")
print(f"Initial USD pose:   {get_ee_pose_usd()}")
print(f"Initial Rigid pose: {get_ee_pose_rigid()}")

# Shift joints slightly
test_joints = init_joints + 0.1
print("\nSetting joints to:", test_joints)
fairino_robot.set_joint_positions(test_joints)

print(f"USD pose after set:   {get_ee_pose_usd()}")
print(f"Rigid pose after set: {get_ee_pose_rigid()}")

# Now step physics and check
print("\nStepping world...")
world.step(render=False)
print(f"USD pose after step:   {get_ee_pose_usd()}")
print(f"Rigid pose after step: {get_ee_pose_rigid()}")

simulation_app.close()
