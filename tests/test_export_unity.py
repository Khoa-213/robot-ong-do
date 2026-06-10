from __future__ import annotations

from src.dataset.synthetic_generator import generate_synthetic_dataset
from src.dataset.unity_exporter import export_unity


def test_unity_export_has_required_frame_fields(tmp_path) -> None:
    dataset = generate_synthetic_dataset(episodes_per_task=1, seed=2)
    output = tmp_path / "unity_motion_dataset.json"
    payload = export_unity(dataset, output)
    assert output.exists()
    assert payload["metadata"]["format"] == "robot_motion_unity_v1"
    frame = payload["episodes"][0]["frames"][0]
    assert set(frame["position"]) == {"x", "y", "z"}
    assert set(frame["rotation_euler"]) == {"x", "y", "z"}
    assert "gripper" in frame
