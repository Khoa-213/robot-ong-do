from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.paper_zone import build_circle_demo_poses, build_line_demo_poses, distance_xy, get_paper_corners, paper_size_from_corners
from modules.shape_api import build_shape_poses
from src.services.config_service import get_config


def test_a4_paper_corners_are_rectangular() -> None:
    config = get_config()
    corners = get_paper_corners(config)
    width, height = paper_size_from_corners(corners)

    assert round(width, 3) == 210.0
    assert round(height, 3) == 297.0
    assert corners["bottom_left"][0] == corners["top_left"][0]
    assert corners["bottom_right"][0] == corners["top_right"][0]
    assert corners["bottom_left"][1] == corners["bottom_right"][1]
    assert corners["top_left"][1] == corners["top_right"][1]


def test_measured_line_square_and_circle_keep_true_geometry() -> None:
    config = get_config()

    line_start, line_end = build_line_demo_poses(config)
    assert round(line_end[1] - line_start[1], 6) == 0.0

    square = build_shape_poses(config, "square")
    sides = [round(distance_xy(square[index], square[index + 1]), 3) for index in range(4)]
    assert len(set(sides)) == 1

    circle = build_circle_demo_poses(config)
    xs = [pose[0] for pose in circle]
    ys = [pose[1] for pose in circle]
    assert round(max(xs) - min(xs), 3) == round(max(ys) - min(ys), 3)


if __name__ == "__main__":
    test_a4_paper_corners_are_rectangular()
    test_measured_line_square_and_circle_keep_true_geometry()
    print("[A4_GEOMETRY] Paper and shape geometry OK")
