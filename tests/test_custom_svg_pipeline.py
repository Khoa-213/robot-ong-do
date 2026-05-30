import json
import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.svg.svg_to_strokes import (
    export_strokes_json,
    load_svg_as_strokes,
    svg_strokes_to_robot_strokes,
    validate_robot_strokes_safe_zone,
)
from modules.calligraphy_pressure_controller import (
    CalligraphyPressureConfig,
    apply_calligraphy_pressure_to_stroke,
)


def write_svg(tmp_path: Path, body: str, attrs: str = 'viewBox="0 0 100 100"') -> Path:
    path = tmp_path / "input.svg"
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}>{body}</svg>', encoding="utf-8")
    return path


class CustomSvgPipelineTests(unittest.TestCase):
    def test_reads_polyline_skeleton_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<polyline points="0,0 10,0 10,10"/>')
            strokes = load_svg_as_strokes(path, {"point_spacing_mm": 0, "simplify_tolerance": 0})
            self.assertEqual(len(strokes), 1)
            self.assertEqual(strokes[0]["source"], "polyline")
            self.assertEqual(strokes[0]["points"], [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])

    def test_reads_path_with_line_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<path d="M 0 0 L 20 0 h 10 v 10 z"/>')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            strokes = load_svg_as_strokes(path, config)
            self.assertEqual(len(strokes), 1)
            self.assertTrue(strokes[0]["closed"])
            self.assertEqual(strokes[0]["points"][0], strokes[0]["points"][-1])
            self.assertIn("close command", config["svg_warnings"][0])

    def test_reads_path_with_cubic_bezier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<path d="M 0 0 C 20 0 20 20 40 20"/>')
            strokes = load_svg_as_strokes(path, {"curve_sample_resolution": 12, "point_spacing_mm": 0, "simplify_tolerance": 0})
            self.assertEqual(len(strokes), 1)
            self.assertEqual(len(strokes[0]["points"]), 12)
            self.assertEqual(strokes[0]["points"][-1], [40.0, 20.0])

    def test_uses_viewbox_for_paper_scaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<line x1="25" y1="25" x2="75" y2="75"/>', attrs='viewBox="0 0 100 100"')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            strokes = load_svg_as_strokes(path, config)
            robot = svg_strokes_to_robot_strokes(
                strokes,
                (0, 0),
                200,
                100,
                5,
                preserve_aspect_ratio=False,
                flip_y=False,
                center_on_paper=False,
                svg_bounds=config["svg_bounds"],
            )
            self.assertEqual(robot[0][0], [50.0, 25.0, 5.0])
            self.assertEqual(robot[0][-1], [150.0, 75.0, 5.0])

    def test_records_drawable_bounds_separately_from_page_viewbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<line x1="55" y1="60" x2="65" y2="75"/>', attrs='viewBox="0 0 210 297"')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            strokes = load_svg_as_strokes(path, config)
            self.assertEqual(config["svg_bounds"], [0.0, 0.0, 210.0, 297.0])
            self.assertEqual(config["svg_drawable_bounds"], [55.0, 60.0, 65.0, 75.0])
            robot = svg_strokes_to_robot_strokes(
                strokes,
                (0, 0),
                100,
                100,
                0,
                flip_y=False,
                svg_bounds=config["svg_drawable_bounds"],
            )
            self.assertGreater(robot[0][-1][0] - robot[0][0][0], 60.0)

    def test_applies_nested_translate_and_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(
                Path(tmp),
                '<g transform="translate(10,20)"><g transform="scale(2)"><line x1="1" y1="2" x2="3" y2="4"/></g></g>',
            )
            strokes = load_svg_as_strokes(path, {"point_spacing_mm": 0, "simplify_tolerance": 0})
            self.assertEqual(strokes[0]["points"], [[12.0, 24.0], [16.0, 28.0]])

    def test_scale_to_paper_size_with_flip_y(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<polyline points="0,0 100,100"/>')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            strokes = load_svg_as_strokes(path, config)
            robot = svg_strokes_to_robot_strokes(
                strokes,
                (10, 20),
                100,
                50,
                7,
                flip_y=True,
                center_on_paper=False,
                svg_bounds=config["svg_bounds"],
            )
            self.assertEqual(robot[0][0], [10.0, 70.0, 7.0])
            self.assertEqual(robot[0][-1], [60.0, 20.0, 7.0])

    def test_validate_waypoint_out_of_safe_zone_reports_stroke_and_point(self):
        with self.assertRaisesRegex(ValueError, "Waypoint out of safe zone at stroke 1 point 2"):
            validate_robot_strokes_safe_zone([[[0, 0, 0], [101, 0, 0]]], (0, 0), 100, 100)

    def test_export_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = write_svg(tmp_path, '<line x1="0" y1="0" x2="10" y2="0"/>')
            strokes = load_svg_as_strokes(path, {"point_spacing_mm": 0, "simplify_tolerance": 0})
            output = tmp_path / "strokes.json"
            export_strokes_json(output, strokes)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["strokes"][0]["source"], "line")

    def test_rejects_filled_outline_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<path fill="#000000" d="M 0 0 L 10 0 L 10 10 Z"/>')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            with self.assertRaisesRegex(ValueError, "No robot-friendly single-stroke"):
                load_svg_as_strokes(path, config)
            self.assertIn("ignored path with fill", config["svg_warnings"][0])

    def test_ignores_non_stroke_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_svg(Path(tmp), '<rect x="0" y="0" width="10" height="10"/><polyline points="0,0 5,5"/>')
            config = {"point_spacing_mm": 0, "simplify_tolerance": 0}
            strokes = load_svg_as_strokes(path, config)
            self.assertEqual(len(strokes), 1)
            self.assertEqual(strokes[0]["source"], "polyline")
            self.assertIn("ignored <rect>", config["svg_warnings"][0])

    def test_calligraphy_pressure_uses_direction_for_z(self):
        stroke = [
            [0.0, 0.0, 20.0, 0.0, 0.0, 0.0],
            [0.0, 2.0, 20.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 20.0, 0.0, 0.0, 0.0],
        ]
        config = CalligraphyPressureConfig(enabled=True, pressure_smoothing=False, max_z_change_per_mm=10.0)
        adjusted = apply_calligraphy_pressure_to_stroke(stroke, config)
        self.assertLess(adjusted[0][2], 20.0)
        self.assertGreater(adjusted[1][2], 20.0)


if __name__ == "__main__":
    unittest.main()
