from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisMapping:
    position_order: tuple[int, int, int]
    position_sign: tuple[float, float, float]
    rotation_order: tuple[int, int, int] = (0, 1, 2)
    rotation_sign: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def apply_position(self, xyz: tuple[float, float, float]) -> dict[str, float]:
        values = [xyz[index] * self.position_sign[out_index] for out_index, index in enumerate(self.position_order)]
        return {"x": values[0], "y": values[1], "z": values[2]}

    def apply_rotation(self, rpy: tuple[float, float, float]) -> dict[str, float]:
        values = [rpy[index] * self.rotation_sign[out_index] for out_index, index in enumerate(self.rotation_order)]
        return {"x": values[0], "y": values[1], "z": values[2]}


# Assumed robot frame: X forward, Y left/right, Z up. Some robots differ; pass a
# custom AxisMapping when your calibration uses a different convention.
DEFAULT_UNITY_MAPPING = AxisMapping(position_order=(1, 2, 0), position_sign=(1.0, 1.0, 1.0))

# Isaac/USD is normally Z-up, so the default keeps the common robot frame.
DEFAULT_ISAAC_MAPPING = AxisMapping(position_order=(0, 1, 2), position_sign=(1.0, 1.0, 1.0))


def robot_to_unity_position(x: float, y: float, z: float, mapping: AxisMapping = DEFAULT_UNITY_MAPPING) -> dict[str, float]:
    return mapping.apply_position((x, y, z))


def robot_to_unity_rotation(roll: float, pitch: float, yaw: float, mapping: AxisMapping = DEFAULT_UNITY_MAPPING) -> dict[str, float]:
    return mapping.apply_rotation((roll, pitch, yaw))


def robot_to_isaac_position(x: float, y: float, z: float, mapping: AxisMapping = DEFAULT_ISAAC_MAPPING) -> dict[str, float]:
    return mapping.apply_position((x, y, z))


def robot_to_isaac_rotation(roll: float, pitch: float, yaw: float, mapping: AxisMapping = DEFAULT_ISAAC_MAPPING) -> dict[str, float]:
    return mapping.apply_rotation((roll, pitch, yaw))
