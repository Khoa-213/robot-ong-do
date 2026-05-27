from typing import Any

from modules.sdk_path import setup_fairino_sdk_path


class FairinoGripperController:
    """Small raw XML-RPC wrapper for Fairino gripper commands.

    The current FR3 controller exposes XML-RPC on 20003, while this SDK build
    reports SDK-level connection false because CNDE/status port 20005 is closed.
    For that reason gripper commands are sent through the raw ServerProxy, and
    all motion commands require explicit safety flags.
    """

    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        self.robot: Any | None = None
        self.raw: Any | None = None

    def connect(self) -> bool:
        print(f"[GRIPPER_CONNECT] Preparing Fairino SDK import for robot {self.robot_ip}")
        setup_fairino_sdk_path()
        from fairino import Robot

        print(f"[GRIPPER_CONNECT] Creating Robot.RPC({self.robot_ip})")
        self.robot = Robot.RPC(self.robot_ip)
        self.raw = getattr(self.robot, "robot", None)
        print("[GRIPPER_CONNECT] SDK robot.is_connect:", getattr(self.robot, "is_connect", None))
        print("[GRIPPER_CONNECT] Raw XML-RPC server:", self.raw)
        return self.raw is not None

    def disconnect(self) -> None:
        if self.robot is not None and hasattr(self.robot, "CloseRPC"):
            print("[GRIPPER_DISCONNECT] Calling robot.CloseRPC()")
            self.robot.CloseRPC()

    def get_controller_ip(self):
        self._require_raw()
        result = self.raw.GetControllerIP()
        print("[GRIPPER_STATUS] GetControllerIP:", result)
        return result

    def get_config(self):
        self._require_raw()
        print("[GRIPPER_CONFIG] Calling raw GetGripperConfig()")
        result = self.raw.GetGripperConfig()
        print("[GRIPPER_CONFIG] GetGripperConfig:", result)
        return result

    def get_robot_error_code(self):
        self._require_raw()
        result = self.raw.GetRobotErrorCode()
        print("[GRIPPER_DIAG] GetRobotErrorCode:", result)
        return result

    def get_tool_end_communication_param(self):
        self._require_raw()
        result = self.raw.GetAxleCommunicationParam()
        print("[GRIPPER_DIAG] GetAxleCommunicationParam:", result)
        return result

    def get_tool_end_lua_enable_status(self):
        self._require_raw()
        result = self.raw.GetAxleLuaEnableStatus()
        print("[GRIPPER_DIAG] GetAxleLuaEnableStatus:", result)
        return result

    def get_tool_end_lua_device_type(self):
        self._require_raw()
        result = self.raw.GetAxleLuaEnableDeviceType()
        print("[GRIPPER_DIAG] GetAxleLuaEnableDeviceType:", result)
        return result

    def get_tool_end_lua_enabled_device(self):
        self._require_raw()
        result = self.raw.GetAxleLuaEnableDevice()
        print("[GRIPPER_DIAG] GetAxleLuaEnableDevice:", result)
        return result

    def get_tool_end_lua_gripper_func(self, gripper_id: int = 1):
        self._require_raw()
        result = self.raw.GetAxleLuaGripperFunc(int(gripper_id))
        print(f"[GRIPPER_DIAG] GetAxleLuaGripperFunc({gripper_id}):", result)
        return result

    def get_gripper_status_snapshot(self) -> dict[str, Any]:
        self._require_raw()
        calls = {
            "motion_done": lambda: self.raw.GetGripperMotionDone(),
            "activate_status": lambda: self.raw.GetGripperActivateStatus(),
            "position": lambda: self.raw.GetGripperCurPosition(),
            "current": lambda: self.raw.GetGripperCurCurrent(),
            "voltage": lambda: self.raw.GetGripperVoltage(),
            "temperature": lambda: self.raw.GetGripperTemp(),
            "speed": lambda: self.raw.GetGripperCurSpeed(),
        }
        snapshot: dict[str, Any] = {}
        for name, call in calls.items():
            try:
                snapshot[name] = call()
            except Exception as exc:
                snapshot[name] = repr(exc)
            print(f"[GRIPPER_DIAG] {name}:", snapshot[name])
        return snapshot

    def set_config(
        self,
        company: int,
        device: int,
        softversion: int = 0,
        bus: int = 0,
        enable_gripper_motion: bool = False,
        allow_raw_xmlrpc_gripper: bool = False,
    ):
        self._require_gripper_motion(enable_gripper_motion, allow_raw_xmlrpc_gripper)
        print("[GRIPPER_CONFIG] Calling raw SetGripperConfig")
        print(
            "[GRIPPER_CONFIG] Params:",
            {
                "company": company,
                "device": device,
                "softversion": softversion,
                "bus": bus,
            },
        )
        result = self.raw.SetGripperConfig(
            int(company),
            int(device),
            int(softversion),
            int(bus),
        )
        print("[GRIPPER_CONFIG] SetGripperConfig:", result)
        return result

    def configure_tool_end_lua(
        self,
        tool_end_lua: dict[str, Any],
        enable_gripper_motion: bool = False,
        allow_raw_xmlrpc_gripper: bool = False,
    ) -> list[Any]:
        self._require_gripper_motion(enable_gripper_motion, allow_raw_xmlrpc_gripper)
        self._require_raw()

        print("[GRIPPER_TOOL_END] Configuring tool-end communication and Lua gripper device")
        results = []
        results.append(
            self.raw.SetAxleCommunicationParam(
                int(tool_end_lua.get("baud_rate_code", 7)),
                int(tool_end_lua.get("data_bit", 8)),
                int(tool_end_lua.get("stop_bit", 1)),
                int(tool_end_lua.get("verify", 0)),
                int(tool_end_lua.get("timeout_ms", 5)),
                int(tool_end_lua.get("timeout_times", 3)),
                int(tool_end_lua.get("period_ms", 1000)),
            )
        )
        print("[GRIPPER_TOOL_END] SetAxleCommunicationParam:", results[-1])

        if bool(tool_end_lua.get("enable_lua", True)):
            results.append(self.raw.SetAxleLuaEnable(1))
            print("[GRIPPER_TOOL_END] SetAxleLuaEnable:", results[-1])

        results.append(
            self.raw.SetAxleLuaEnableDeviceType(
                int(tool_end_lua.get("force_sensor_enable", 0)),
                int(tool_end_lua.get("gripper_enable", 1)),
                int(tool_end_lua.get("io_enable", 0)),
            )
        )
        print("[GRIPPER_TOOL_END] SetAxleLuaEnableDeviceType:", results[-1])

        if bool(tool_end_lua.get("enable_gripper_func", True)):
            func = tool_end_lua.get("gripper_func", [1] * 16)
            results.append(self.raw.SetAxleLuaGripperFunc(1, [int(value) for value in func]))
            print("[GRIPPER_TOOL_END] SetAxleLuaGripperFunc(1):", results[-1])
        return results

    def setup_tool_end_gripper(
        self,
        tool_end_lua: dict[str, Any],
        apply_setup: bool = False,
    ) -> list[Any] | None:
        """Configure tool-end RS485/Lua gripper path without moving gripper."""
        self._require_raw()

        params = {
            "baud_rate_code": int(tool_end_lua.get("baud_rate_code", 7)),
            "data_bit": int(tool_end_lua.get("data_bit", 8)),
            "stop_bit": int(tool_end_lua.get("stop_bit", 1)),
            "verify": int(tool_end_lua.get("verify", 0)),
            "timeout_ms": int(tool_end_lua.get("timeout_ms", 5)),
            "timeout_times": int(tool_end_lua.get("timeout_times", 3)),
            "period_ms": int(tool_end_lua.get("period_ms", 1000)),
            "enable_lua": bool(tool_end_lua.get("enable_lua", True)),
            "force_sensor_enable": int(tool_end_lua.get("force_sensor_enable", 0)),
            "gripper_enable": int(tool_end_lua.get("gripper_enable", 1)),
            "io_enable": int(tool_end_lua.get("io_enable", 0)),
            "enable_gripper_func": bool(tool_end_lua.get("enable_gripper_func", True)),
            "gripper_func": [int(value) for value in tool_end_lua.get("gripper_func", [1] * 16)],
        }
        print("[GRIPPER_TOOL_END_SETUP] Planned setup:", params)
        print("[GRIPPER_TOOL_END_SETUP] apply_setup:", apply_setup)

        if not apply_setup:
            print("[GRIPPER_TOOL_END_SETUP] Preview only, no Set* command was sent")
            return None

        results = []
        results.append(
            self.raw.SetAxleCommunicationParam(
                params["baud_rate_code"],
                params["data_bit"],
                params["stop_bit"],
                params["verify"],
                params["timeout_ms"],
                params["timeout_times"],
                params["period_ms"],
            )
        )
        print("[GRIPPER_TOOL_END_SETUP] SetAxleCommunicationParam:", results[-1])

        if params["enable_lua"]:
            results.append(self.raw.SetAxleLuaEnable(1))
            print("[GRIPPER_TOOL_END_SETUP] SetAxleLuaEnable:", results[-1])

        results.append(
            self.raw.SetAxleLuaEnableDeviceType(
                params["force_sensor_enable"],
                params["gripper_enable"],
                params["io_enable"],
            )
        )
        print("[GRIPPER_TOOL_END_SETUP] SetAxleLuaEnableDeviceType:", results[-1])

        if params["enable_gripper_func"]:
            results.append(self.raw.SetAxleLuaGripperFunc(1, params["gripper_func"]))
            print("[GRIPPER_TOOL_END_SETUP] SetAxleLuaGripperFunc(1):", results[-1])
        return results

    def activate(
        self,
        index: int = 1,
        enable_gripper_motion: bool = False,
        allow_raw_xmlrpc_gripper: bool = False,
    ) -> list[Any]:
        self._require_gripper_motion(enable_gripper_motion, allow_raw_xmlrpc_gripper)
        self._require_raw()
        print(f"[GRIPPER_ACT] Reset then activate gripper index={index}")
        reset_result = self.raw.ActGripper(int(index), 0)
        print("[GRIPPER_ACT] ActGripper reset:", reset_result)
        activate_result = self.raw.ActGripper(int(index), 1)
        print("[GRIPPER_ACT] ActGripper activate:", activate_result)
        return [reset_result, activate_result]

    def move(
        self,
        index: int,
        pos: int,
        vel: int,
        force: int,
        maxtime: int,
        block: int = 0,
        gripper_type: int = 0,
        rot_num: float = 0,
        rot_vel: int = 0,
        rot_torque: int = 0,
        enable_gripper_motion: bool = False,
        allow_raw_xmlrpc_gripper: bool = False,
    ):
        self._require_gripper_motion(enable_gripper_motion, allow_raw_xmlrpc_gripper)
        self._require_raw()
        self._validate_percent("pos", pos)
        self._validate_percent("vel", vel)
        self._validate_percent("force", force)

        params = {
            "index": int(index),
            "pos": int(pos),
            "vel": int(vel),
            "force": int(force),
            "maxtime": int(maxtime),
            "block": int(block),
            "type": int(gripper_type),
            "rot_num": float(rot_num),
            "rot_vel": int(rot_vel),
            "rot_torque": int(rot_torque),
        }
        print("[GRIPPER_MOVE] Sending raw MoveGripper params:", params)
        result = self.raw.MoveGripper(
            params["index"],
            params["pos"],
            params["vel"],
            params["force"],
            params["maxtime"],
            params["block"],
            params["type"],
            params["rot_num"],
            params["rot_vel"],
            params["rot_torque"],
        )
        print("[GRIPPER_MOVE] MoveGripper:", result)
        return result

    def get_motion_done(self):
        self._require_raw()
        result = self.raw.GetGripperMotionDone()
        print("[GRIPPER_STATUS] GetGripperMotionDone:", result)
        return result

    def preview_move(self, label: str, pos: int, vel: int, force: int) -> None:
        print(f"[GRIPPER_PREVIEW] {label}: pos={pos}, vel={vel}, force={force}")
        print("[GRIPPER_PREVIEW] SAFETY LOCK: gripper motion disabled")
        print("[GRIPPER_PREVIEW] No ActGripper or MoveGripper command was sent")

    def _require_raw(self) -> None:
        if self.raw is None:
            raise RuntimeError("Raw XML-RPC server is not connected")

    def _require_gripper_motion(
        self,
        enable_gripper_motion: bool,
        allow_raw_xmlrpc_gripper: bool,
    ) -> None:
        self._require_raw()
        print("[GRIPPER_SAFETY] enable_gripper_motion:", enable_gripper_motion)
        print("[GRIPPER_SAFETY] allow_raw_xmlrpc_gripper:", allow_raw_xmlrpc_gripper)
        if not enable_gripper_motion or not allow_raw_xmlrpc_gripper:
            raise RuntimeError(
                "SAFETY LOCK: gripper motion/config write disabled. "
                "Set gripper.enable_gripper_motion=true and "
                "gripper.allow_raw_xmlrpc_gripper=true only when the gripper is clear."
            )

    def _validate_percent(self, name: str, value: int) -> None:
        if not 0 <= int(value) <= 100:
            raise ValueError(f"{name} must be in range 0..100, got {value}")
