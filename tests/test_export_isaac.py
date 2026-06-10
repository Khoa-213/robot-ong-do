from __future__ import annotations

from src.dataset.isaac_exporter import export_isaac
from src.dataset.synthetic_generator import generate_synthetic_dataset


def test_isaac_export_has_required_target_fields(tmp_path) -> None:
    dataset = generate_synthetic_dataset(episodes_per_task=1, seed=3)
    output = tmp_path / "isaac_motion_dataset.json"
    payload = export_isaac(dataset, output, tmp_path / "isaac_motion_dataset.npz")
    assert output.exists()
    assert (tmp_path / "isaac_motion_dataset.npz").exists()
    assert payload["metadata"]["format"] == "robot_motion_isaac_v1"
    target = payload["episodes"][0]["end_effector_targets"][0]
    assert set(target["position"]) == {"x", "y", "z"}
    assert set(target["rotation_euler"]) == {"x", "y", "z"}
    assert "gripper" in target
