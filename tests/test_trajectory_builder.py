import unittest
from shapely.geometry import Polygon, MultiPolygon
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths
from src.outline_to_skeleton.errors import SkeletonExtractionError

class TestTrajectoryBuilder(unittest.TestCase):
    def test_simple_box_skeleton(self):
        # Create a simple thick horizontal rectangle: width 20, height 4
        # Centerline should run horizontally in the middle (y=2)
        poly = Polygon([(0, 0), (20, 0), (20, 4), (0, 4), (0, 0)])
        
        paths = polygons_to_robot_paths(
            [poly],
            resolution=2.0,
            z_light=-1.0,
            z_heavy=-5.0,
            point_spacing=1.0,
            min_branch_length=4.0,
            simplify_tolerance=0.01,
        )
        
        self.assertGreater(len(paths), 0)
        print("Generated paths:", paths)
        # Check that centerline runs roughly horizontally around y=2.0
        for stroke in paths:
            self.assertGreater(len(stroke), 1)
            for x, y, z in stroke:
                # x should be within 0.5 and 19.5
                self.assertTrue(0.5 <= x <= 19.5, f"x coordinate {x} out of bounds")
                # y should be within 0.5 and 3.5
                self.assertTrue(0.5 <= y <= 3.5, f"y coordinate {y} out of bounds")
                # z-depth should be mapped within bounds
                self.assertTrue(-5.0 <= z <= -1.0, f"z-depth {z} out of range")

    def test_skeleton_with_theta_pruning(self):
        poly = Polygon([(0, 0), (20, 0), (20, 4), (0, 4), (0, 0)])
        paths = polygons_to_robot_paths(
            [poly],
            resolution=2.0,
            z_light=-1.0,
            z_heavy=-5.0,
            point_spacing=1.0,
            min_branch_length=4.0,
            simplify_tolerance=0.01,
            theta=1.5,
        )
        self.assertGreater(len(paths), 0)

    def test_empty_polygons_raises_error(self):
        with self.assertRaises(SkeletonExtractionError):
            polygons_to_robot_paths([], resolution=2.0)

    def test_z_depth_mapping_limits(self):
        poly = Polygon([(0, 0), (30, 0), (30, 10), (0, 10), (0, 0)])
        paths = polygons_to_robot_paths(
            [poly],
            resolution=2.0,
            z_light=-0.5,
            z_heavy=-3.0,
        )
        for stroke in paths:
            for x, y, z in stroke:
                self.assertTrue(-3.01 <= z <= -0.49, f"z {z} violates configured bounds")

if __name__ == "__main__":
    unittest.main()
