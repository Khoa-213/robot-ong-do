from fairino import Robot
import time


class FairinoController:
    def __init__(self, ip: str, tool: int = 0, user: int = 0):
        self.ip = ip
        self.tool = tool
        self.user = user
        self.robot = None

    def connect(self):
        self.robot = Robot.RPC(self.ip)
        print(f"Connected to Fairino robot at {self.ip}")

    def move_l(self, pose, vel=20):
        if self.robot is None:
            raise RuntimeError("Robot is not connected")
        return self.robot.MoveL(pose, self.tool, self.user, vel=vel)

    def move_to_lift_position(self, x, y, z_lift, rx, ry, rz, vel=20):
        pose = [x, y, z_lift, rx, ry, rz]
        return self.move_l(pose, vel=vel)

    def write_trajectory_servo(self, trajectory, rx, ry, rz, sleep_time=0.008):
        if self.robot is None:
            raise RuntimeError("Robot is not connected")

        for point in trajectory:
            x, y, z = point
            pose = [x, y, z, rx, ry, rz]
            ret = self.robot.ServoL(pose)
            time.sleep(sleep_time)

        return True