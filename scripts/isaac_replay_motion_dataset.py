from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay an exported Isaac motion dataset inside NVIDIA Isaac Sim."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/exports/isaac/isaac_motion_dataset.json"),
    )
    parser.add_argument("--episode_id", default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--save_stage", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # This script must run with Isaac Sim's python.bat/python.sh, not the project venv.
    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": args.headless})

    import omni.usd
    from pxr import Gf, Sdf, UsdGeom

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    episode = _select_episode(payload["episodes"], args.episode_id)
    frames = episode.get("end_effector_targets", [])
    if not frames:
        raise ValueError(f"Episode {episode['episode_id']} has no end_effector_targets")

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    _create_ground(stage)
    sphere_xform = _create_target_sphere(stage)
    path_xform = _create_path_points(stage, frames)

    print(f"Replaying {episode['episode_id']} ({episode.get('task', '')}) with {len(frames)} frames")
    while simulation_app.is_running():
        _replay_once(simulation_app, sphere_xform, frames, args.speed)
        if not args.loop:
            break

    if args.save_stage:
        args.save_stage.parent.mkdir(parents=True, exist_ok=True)
        stage.GetRootLayer().Export(str(args.save_stage))
        print(f"Saved stage to {args.save_stage}")

    # Keep the final frame visible for a moment in GUI mode.
    if not args.headless:
        for _ in range(120):
            simulation_app.update()
            time.sleep(1.0 / 60.0)

    simulation_app.close()


def _select_episode(episodes: list[dict], episode_id: str | None) -> dict:
    if episode_id is None:
        return episodes[0]
    for episode in episodes:
        if episode.get("episode_id") == episode_id:
            return episode
    raise ValueError(f"Episode not found: {episode_id}")


def _create_ground(stage):
    from pxr import Gf, UsdGeom

    cube = UsdGeom.Cube.Define(stage, "/World/Ground")
    cube.CreateSizeAttr(1.0)
    cube.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 0.01))
    cube.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, -0.01))
    return cube


def _create_target_sphere(stage):
    from pxr import Gf, UsdGeom

    sphere = UsdGeom.Sphere.Define(stage, "/World/ReplayTarget")
    sphere.CreateRadiusAttr(0.025)
    xform = UsdGeom.Xformable(sphere)
    xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.0))
    return xform


def _create_path_points(stage, frames: list[dict]):
    from pxr import Gf, UsdGeom

    root = UsdGeom.Xform.Define(stage, "/World/PathPreview")
    stride = max(1, len(frames) // 80)
    for index, frame in enumerate(frames[::stride]):
        position = frame["position"]
        sphere = UsdGeom.Sphere.Define(stage, f"/World/PathPreview/p_{index:04d}")
        sphere.CreateRadiusAttr(0.006)
        UsdGeom.Xformable(sphere).AddTranslateOp().Set(
            Gf.Vec3d(position["x"], position["y"], position["z"])
        )
    return root


def _replay_once(simulation_app, sphere_xform, frames: list[dict], speed: float) -> None:
    from pxr import Gf

    speed = max(speed, 0.01)
    previous_t = frames[0].get("t", 0.0)
    translate_op = sphere_xform.GetOrderedXformOps()[0]
    for frame in frames:
        position = frame["position"]
        translate_op.Set(Gf.Vec3d(position["x"], position["y"], position["z"]))
        simulation_app.update()
        dt = max(0.0, frame.get("t", previous_t) - previous_t) / speed
        previous_t = frame.get("t", previous_t)
        if dt > 0:
            time.sleep(min(dt, 0.05))


if __name__ == "__main__":
    main()
