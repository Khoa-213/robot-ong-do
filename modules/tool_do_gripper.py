from typing import Any

from modules.sdk_path import setup_fairino_sdk_path


class ToolDOGripperController:
    """Control a simple gripper through Fairino tool digital output.

    This is for grippers wired as a valve/relay on the tool-end DO, not the
    native Fairino smart gripper API.
    """

    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        self.robot: Any | None = None
        self.raw: Any | None = None

    def connect(self) -> bool:
        print(f"[TOOL_DO_CONNECT] Preparing Fairino SDK import for robot {self.robot_ip}")
        setup_fairino_sdk_path()
        from fairino import Robot

        print(f"[TOOL_DO_CONNECT] Creating Robot.RPC({self.robot_ip})")
        self.robot = Robot.RPC(self.robot_ip)
        self.raw = getattr(self.robot, "robot", None)
        print("[TOOL_DO_CONNECT] SDK robot.is_connect:", getattr(self.robot, "is_connect", None))
        print("[TOOL_DO_CONNECT] Raw XML-RPC server:", self.raw)
        return self.raw is not None

    def disconnect(self) -> None:
        if self.robot is not None and hasattr(self.robot, "CloseRPC"):
            print("[TOOL_DO_DISCONNECT] Calling robot.CloseRPC()")
            self.robot.CloseRPC()

    def get_controller_ip(self):
        self._require_raw()
        result = self.raw.GetControllerIP()
        print("[TOOL_DO_STATUS] GetControllerIP:", result)
        return result

    def get_robot_error_code(self):
        self._require_raw()
        result = self.raw.GetRobotErrorCode()
        print("[TOOL_DO_STATUS] GetRobotErrorCode:", result)
        return result

    def set_tool_do(
        self,
        do_id: int,
        status: int,
        smooth: int = 0,
        block: int = 1,
        enable_tool_do_gripper: bool = False,
    ):
        self._require_raw()
        self._validate_do(do_id, status, smooth, block)
        print(
            "[TOOL_DO_SET] Request:",
            {"id": do_id, "status": status, "smooth": smooth, "block": block},
        )
        print("[TOOL_DO_SET] enable_tool_do_gripper:", enable_tool_do_gripper)

        if not enable_tool_do_gripper:
            print("[TOOL_DO_SET] SAFETY LOCK: tool DO gripper command disabled")
            print("[TOOL_DO_SET] Preview only, SetToolDO was NOT sent")
            return None

        result = self.raw.SetToolDO(int(do_id), int(status), int(smooth), int(block))
        print("[TOOL_DO_SET] raw SetToolDO result:", result)
        return result

    def open(
        self,
        do_id: int,
        open_status: int,
        smooth: int = 0,
        block: int = 1,
        enable_tool_do_gripper: bool = False,
    ):
        print("[TOOL_DO_GRIPPER] OPEN")
        return self.set_tool_do(do_id, open_status, smooth, block, enable_tool_do_gripper)

    def close(
        self,
        do_id: int,
        close_status: int,
        smooth: int = 0,
        block: int = 1,
        enable_tool_do_gripper: bool = False,
    ):
        print("[TOOL_DO_GRIPPER] CLOSE")
        return self.set_tool_do(do_id, close_status, smooth, block, enable_tool_do_gripper)

    def _require_raw(self) -> None:
        if self.raw is None:
            raise RuntimeError("Raw XML-RPC server is not connected")

    def _require_robot(self) -> None:
        if self.robot is None:
            raise RuntimeError("Fairino SDK robot is not connected")

    def _validate_do(self, do_id: int, status: int, smooth: int, block: int) -> None:
        if int(do_id) not in (0, 1):
            raise ValueError(f"tool DO id must be 0 or 1, got {do_id}")
        if int(status) not in (0, 1):
            raise ValueError(f"tool DO status must be 0 or 1, got {status}")
        if int(smooth) not in (0, 1):
            raise ValueError(f"smooth must be 0 or 1, got {smooth}")
        if int(block) not in (0, 1):
            raise ValueError(f"block must be 0 or 1, got {block}")
