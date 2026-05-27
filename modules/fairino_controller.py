from typing import Any

from modules.sdk_path import setup_fairino_sdk_path


class FairinoController:
    def __init__(
        self,
        robot_ip: str,
        tool: int = 0,
        user: int = 0,
        allow_xmlrpc_motion_when_cnde_unavailable: bool = False,
    ):
        self.robot_ip = robot_ip
        self.tool = tool
        self.user = user
        self.allow_xmlrpc_motion_when_cnde_unavailable = allow_xmlrpc_motion_when_cnde_unavailable
        self.robot: Any | None = None
        self.sdk_imported = False
        self.xmlrpc_connected = False
        self._robot_module: Any | None = None

    def connect(self) -> bool:
        print(f"[CONNECT] Preparing Fairino SDK import for robot {self.robot_ip}")
        try:
            setup_fairino_sdk_path()
            from fairino import Robot

            self._robot_module = Robot
            self.sdk_imported = True
            print("[CONNECT] Fairino SDK import OK")
        except Exception as exc:
            self.sdk_imported = False
            self.robot = None
            print("[CONNECT] Fairino SDK import FAILED:", exc)
            return False

        print(f"[CONNECT] Calling Robot.RPC({self.robot_ip})")
        try:
            self.robot = self._robot_module.RPC(self.robot_ip)
            print("[CONNECT] Robot.RPC returned:", self.robot)
        except Exception as exc:
            self.robot = None
            print("[CONNECT] Robot.RPC FAILED:", exc)
            return False

        connected = self.is_connected()
        print("[CONNECT] is_connected:", connected)
        if not connected:
            self.xmlrpc_connected = self.check_xmlrpc_status()
            print("[CONNECT] xmlrpc_connected:", self.xmlrpc_connected)
        return connected

    def is_connected(self) -> bool:
        if self.robot is None:
            print("[STATE] Robot object is None")
            return False

        if hasattr(self.robot, "is_connect"):
            value = bool(getattr(self.robot, "is_connect"))
            print("[STATE] robot.is_connect:", value)
            return value

        print("[STATE] robot.is_connect attribute not found; assuming Robot.RPC object is usable")
        return True

    def check_xmlrpc_status(self) -> bool:
        if self.robot is None:
            print("[XMLRPC] Robot object is None")
            return False

        print("[XMLRPC] Checking command/status methods over XML-RPC")
        all_ok = True
        try:
            if hasattr(self.robot, "GetControllerIP"):
                result = self.robot.GetControllerIP()
                print("[XMLRPC] GetControllerIP:", result)
                all_ok = all_ok and self._sdk_result_ok(result)
            if hasattr(self.robot, "GetActualTCPPose"):
                result = self.robot.GetActualTCPPose(0)
                print("[XMLRPC] GetActualTCPPose:", result)
                all_ok = all_ok and self._sdk_result_ok(result)
            if hasattr(self.robot, "GetRobotEmergencyStopState"):
                result = self.robot.GetRobotEmergencyStopState()
                print("[XMLRPC] GetRobotEmergencyStopState:", result)
                all_ok = all_ok and self._sdk_result_ok(result)
            if hasattr(self.robot, "GetRobotErrorCode"):
                result = self.robot.GetRobotErrorCode()
                print("[XMLRPC] GetRobotErrorCode:", result)
                all_ok = all_ok and self._sdk_result_ok(result)
        except Exception as exc:
            print("[XMLRPC] XML-RPC status check FAILED:", exc)
            return False

        if not all_ok:
            print("[XMLRPC] XML-RPC status check returned SDK error codes")
            return False

        print("[XMLRPC] XML-RPC status check OK")
        return True

    @staticmethod
    def _sdk_result_ok(result: Any) -> bool:
        if isinstance(result, tuple) and result:
            return result[0] == 0
        if isinstance(result, list) and result:
            return result[0] == 0
        if isinstance(result, int):
            return result == 0
        return result is not None

    def can_send_motion(self) -> bool:
        if self.robot is None:
            print("[STATE] Robot object is None")
            return False
        if hasattr(self.robot, "is_connect") and bool(getattr(self.robot, "is_connect")):
            print("[STATE] CNDE is_connect=True; motion commands are allowed by connection policy")
            return True
        if self.allow_xmlrpc_motion_when_cnde_unavailable and self.xmlrpc_connected:
            print("[STATE] WARNING: CNDE is unavailable, using XML-RPC compatibility motion policy")
            return True
        print("[STATE] Motion blocked: CNDE is_connect=False and XML-RPC compatibility motion is disabled")
        return False

    def move_l(self, pose: list[float], vel: float = 10, enable_move: bool = False):
        print("[MOVEL] Requested pose:", pose)
        print("[MOVEL] Velocity:", vel)
        print("[MOVEL] enable_move:", enable_move)

        if not self.sdk_imported:
            raise RuntimeError("Fairino SDK has not been imported successfully")
        if self.robot is None:
            raise RuntimeError("Robot object is None; call connect() first")
        if not self.can_send_motion():
            raise RuntimeError("Connection policy refuses to send MoveL")
        if not enable_move:
            print("[MOVEL] SAFETY LOCK: robot movement disabled")
            print("[MOVEL] Preview only, MoveL was NOT sent")
            return None

        print("[MOVEL] Sending robot.MoveL command")
        try:
            result = self.robot.MoveL(pose, self.tool, self.user, vel=vel)
            print("[MOVEL] MoveL result:", result)
            return result
        except Exception as exc:
            print("[MOVEL] MoveL FAILED:", exc)
            raise

    def draw_line_air(
        self,
        start_pose: list[float],
        end_pose: list[float],
        vel: float = 5,
        enable_move: bool = False,
    ):
        print("[DRAW_LINE_AIR] Preparing trajectory")
        print("[DRAW_LINE_AIR] Start pose:", start_pose)
        print("[DRAW_LINE_AIR] End pose:", end_pose)
        print("[DRAW_LINE_AIR] Velocity:", vel)

        if not enable_move:
            print("[DRAW_LINE_AIR] SAFETY LOCK: robot movement disabled")
            print("[DRAW_LINE_AIR] Planned trajectory:")
            print("  1. MoveL start_pose:", start_pose)
            print("  2. MoveL end_pose:", end_pose)
            return [start_pose, end_pose]

        print("[DRAW_LINE_AIR] Sending MoveL to start_pose")
        first = self.move_l(start_pose, vel=vel, enable_move=enable_move)
        print("[DRAW_LINE_AIR] Sending MoveL to end_pose")
        second = self.move_l(end_pose, vel=vel, enable_move=enable_move)
        return [first, second]

    def disconnect(self) -> None:
        if self.robot is None:
            print("[DISCONNECT] Robot object is None, nothing to close")
            return

        if hasattr(self.robot, "CloseRPC"):
            try:
                print("[DISCONNECT] Calling robot.CloseRPC()")
                self.robot.CloseRPC()
            except Exception as exc:
                print("[DISCONNECT] CloseRPC FAILED:", exc)
        else:
            print("[DISCONNECT] CloseRPC not supported by this SDK object")
