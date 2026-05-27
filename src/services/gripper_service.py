from typing import Any

from modules.fairino_gripper import FairinoGripperController

from src.services.config_service import get_config


def get_gripper_status() -> dict[str, Any]:
    config = get_config()
    controller = FairinoGripperController(config["robot_ip"])

    status: dict[str, Any] = {
        "connected": False,
        "config": None,
        "snapshot": None,
    }

    try:
        status["connected"] = controller.connect()
        if not status["connected"]:
            return status
        status["config"] = controller.get_config()
        status["snapshot"] = controller.get_gripper_status_snapshot()
    finally:
        controller.disconnect()
    return status


def open_gripper(pos: int | None, vel: int | None, force: int | None) -> dict[str, Any]:
    return _move_gripper(pos, vel, force, is_open=True)


def close_gripper(pos: int | None, vel: int | None, force: int | None) -> dict[str, Any]:
    return _move_gripper(pos, vel, force, is_open=False)


def _move_gripper(pos: int | None, vel: int | None, force: int | None, is_open: bool) -> dict[str, Any]:
    config = get_config()
    gripper = config.get("gripper", {})

    enable_motion = bool(gripper.get("enable_gripper_motion", False))
    allow_raw = bool(gripper.get("allow_raw_xmlrpc_gripper", False))

    index = int(gripper.get("index", 1))
    target_pos = int(pos) if pos is not None else int(gripper.get("open_pos" if is_open else "close_pos", 50))
    velocity = int(vel) if vel is not None else int(gripper.get("test_vel", 20))
    force_val = int(force) if force is not None else int(gripper.get("test_force", 20))

    controller = FairinoGripperController(config["robot_ip"])
    try:
        if not controller.connect():
            return {"connected": False}

        controller.set_config(
            company=int(gripper.get("company", 3)),
            device=int(gripper.get("device", 0)),
            softversion=int(gripper.get("softversion", 0)),
            bus=int(gripper.get("bus", 0)),
            enable_gripper_motion=enable_motion,
            allow_raw_xmlrpc_gripper=allow_raw,
        )
        controller.activate(index=index, enable_gripper_motion=enable_motion, allow_raw_xmlrpc_gripper=allow_raw)
        result = controller.move(
            index=index,
            pos=target_pos,
            vel=velocity,
            force=force_val,
            maxtime=int(gripper.get("max_time_ms", 5000)),
            block=int(gripper.get("block", 0)),
            gripper_type=int(gripper.get("type", 0)),
            enable_gripper_motion=enable_motion,
            allow_raw_xmlrpc_gripper=allow_raw,
        )
    finally:
        controller.disconnect()

    return {
        "enable_gripper_motion": enable_motion,
        "allow_raw_xmlrpc_gripper": allow_raw,
        "result": result,
    }
