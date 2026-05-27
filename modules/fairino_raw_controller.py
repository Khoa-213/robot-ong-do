from typing import Any

from modules.sdk_path import setup_fairino_sdk_path


class FairinoRawXmlRpcController:
    def __init__(self, robot_ip: str, tool: int = 0, user: int = 0):
        self.robot_ip = robot_ip
        self.tool = int(tool)
        self.user = int(user)
        self.robot: Any | None = None
        self.raw: Any | None = None

    def connect(self) -> bool:
        print(f"[RAW_CONNECT] Preparing Fairino SDK import for robot {self.robot_ip}")
        setup_fairino_sdk_path()
        from fairino import Robot

        print(f"[RAW_CONNECT] Creating Robot.RPC({self.robot_ip})")
        self.robot = Robot.RPC(self.robot_ip)
        self.raw = getattr(self.robot, "robot", None)
        print("[RAW_CONNECT] SDK robot.is_connect:", getattr(self.robot, "is_connect", None))
        print("[RAW_CONNECT] Raw XML-RPC server:", self.raw)
        return self.raw is not None

    def disconnect(self) -> None:
        if self.robot is not None and hasattr(self.robot, "CloseRPC"):
            print("[RAW_DISCONNECT] Calling robot.CloseRPC()")
            self.robot.CloseRPC()

    def get_controller_ip(self):
        self._require_raw()
        result = self.raw.GetControllerIP()
        print("[RAW_STATUS] GetControllerIP:", result)
        return result

    def get_actual_tcp_pose(self):
        self._require_raw()
        result = self.raw.GetActualTCPPose(0)
        print("[RAW_STATUS] GetActualTCPPose:", result)
        return result

    def get_actual_joint_pos_degree(self) -> list[float]:
        self._require_raw()
        result = self.raw.GetActualJointPosDegree(0)
        print("[RAW_STATUS] GetActualJointPosDegree:", result)
        if not isinstance(result, list) or not result or result[0] != 0:
            raise RuntimeError(f"GetActualJointPosDegree failed: {result}")
        return [float(value) for value in result[1:7]]

    def get_robot_error_code(self):
        self._require_raw()
        result = self.raw.GetRobotErrorCode()
        print("[RAW_STATUS] GetRobotErrorCode:", result)
        return result

    def get_inverse_kin(self, pose: list[float], config: int = -1) -> list[float]:
        self._require_raw()
        print("[RAW_IK] Pose:", pose)
        result = self.raw.GetInverseKin(0, pose, int(config))
        print("[RAW_IK] GetInverseKin result:", result)
        if not isinstance(result, list) or not result or result[0] != 0:
            raise RuntimeError(f"GetInverseKin failed for pose {pose}: {result}")
        return [float(value) for value in result[1:7]]

    def get_inverse_kin_ref(self, pose: list[float], joint_ref: list[float]) -> list[float]:
        self._require_raw()
        print("[RAW_IK_REF] Pose:", pose)
        print("[RAW_IK_REF] Joint reference:", joint_ref)
        result = self.raw.GetInverseKinRef(0, pose, joint_ref)
        print("[RAW_IK_REF] GetInverseKinRef result:", result)
        if not isinstance(result, list) or not result or result[0] != 0:
            raise RuntimeError(f"GetInverseKinRef failed for pose {pose}: {result}")
        return [float(value) for value in result[1:7]]

    def resolve_joint_for_pose(self, pose: list[float]) -> list[float]:
        """Resolve IK for a pose, falling back when reference-based IK has no solution."""
        joint_ref = self.get_actual_joint_pos_degree()
        try:
            return self.get_inverse_kin_ref(pose, joint_ref)
        except RuntimeError as exc:
            print("[RAW_IK_RESOLVE] GetInverseKinRef failed, trying GetInverseKin fallback:", exc)
            return self.get_inverse_kin(pose)

    def move_j_to_pose(
        self,
        pose: list[float],
        vel: float = 5.0,
        enable_move: bool = False,
        allow_raw_xmlrpc_motion: bool = False,
    ):
        print("[RAW_MOVEJ] Requested pose:", pose)
        print("[RAW_MOVEJ] Velocity:", vel)
        print("[RAW_MOVEJ] enable_move:", enable_move)
        print("[RAW_MOVEJ] allow_raw_xmlrpc_motion:", allow_raw_xmlrpc_motion)

        joint_pos = self.resolve_joint_for_pose(pose)
        print("[RAW_MOVEJ] IK joint_pos:", joint_pos)

        if not enable_move or not allow_raw_xmlrpc_motion:
            print("[RAW_MOVEJ] SAFETY LOCK: raw XML-RPC robot movement disabled")
            print("[RAW_MOVEJ] Preview only, raw MoveJ was NOT sent")
            return None

        print("[RAW_MOVEJ] Sending raw MoveJ to approach pose")
        result = self.raw.MoveJ(
            joint_pos,
            pose,
            self.tool,
            self.user,
            float(vel),
            0.0,
            100.0,
            [0.0, 0.0, 0.0, 0.0],
            -1.0,
            0,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        print("[RAW_MOVEJ] raw MoveJ result:", result)
        return result

    def move_l(
        self,
        pose: list[float],
        vel: float = 5.0,
        enable_move: bool = False,
        allow_raw_xmlrpc_motion: bool = False,
    ):
        print("[RAW_MOVEL] Requested pose:", pose)
        print("[RAW_MOVEL] Velocity:", vel)
        print("[RAW_MOVEL] enable_move:", enable_move)
        print("[RAW_MOVEL] allow_raw_xmlrpc_motion:", allow_raw_xmlrpc_motion)

        joint_pos = self.get_inverse_kin(pose)
        print("[RAW_MOVEL] IK joint_pos:", joint_pos)

        if not enable_move or not allow_raw_xmlrpc_motion:
            print("[RAW_MOVEL] SAFETY LOCK: raw XML-RPC robot movement disabled")
            print("[RAW_MOVEL] Preview only, raw MoveL was NOT sent")
            return None

        params = self._build_raw_movel_params(pose, joint_pos, vel)
        print("[RAW_MOVEL] Sending raw MoveL params:", params)
        result = self.raw.MoveL(params)
        print("[RAW_MOVEL] raw MoveL result:", result)
        return result

    def draw_line_air(
        self,
        start_pose: list[float],
        end_pose: list[float],
        return_pose: list[float] | None = None,
        vel: float = 5.0,
        return_vel: float | None = None,
        approach_with_move_j: bool = False,
        approach_vel: float | None = None,
        enable_move: bool = False,
        allow_raw_xmlrpc_motion: bool = False,
    ):
        print("[RAW_DRAW_LINE_AIR] Start pose:", start_pose)
        print("[RAW_DRAW_LINE_AIR] End pose:", end_pose)
        if return_pose is not None:
            print("[RAW_DRAW_LINE_AIR] Return pose:", return_pose)
        print("[RAW_DRAW_LINE_AIR] Checking robot status before motion")
        self.get_controller_ip()
        self.get_actual_tcp_pose()
        self.get_robot_error_code()

        if approach_with_move_j:
            print("[RAW_DRAW_LINE_AIR] Using MoveJ/PTP for the first approach point")
            first = self.move_j_to_pose(
                start_pose,
                approach_vel if approach_vel is not None else vel,
                enable_move,
                allow_raw_xmlrpc_motion,
            )
        else:
            first = self.move_l(start_pose, vel, enable_move, allow_raw_xmlrpc_motion)
        second = self.move_l(end_pose, vel, enable_move, allow_raw_xmlrpc_motion)
        if return_pose is None:
            return [first, second]

        print("[RAW_DRAW_LINE_AIR] Returning to configured corner pose after drawing")
        third = self.move_l(
            return_pose,
            return_vel if return_vel is not None else vel,
            enable_move,
            allow_raw_xmlrpc_motion,
        )
        return [first, second, third]

    def draw_polyline_air(
        self,
        poses: list[list[float]],
        start_pose: list[float] | None = None,
        return_pose: list[float] | None = None,
        vel: float = 5.0,
        start_vel: float | None = None,
        return_vel: float | None = None,
        approach_with_move_j: bool = False,
        approach_vel: float | None = None,
        enable_move: bool = False,
        allow_raw_xmlrpc_motion: bool = False,
    ):
        print("[RAW_DRAW_POLYLINE_AIR] Pose count:", len(poses))
        if not poses:
            raise ValueError("poses must not be empty")
        if start_pose is not None:
            print("[RAW_DRAW_POLYLINE_AIR] Start pose:", start_pose)
        if return_pose is not None:
            print("[RAW_DRAW_POLYLINE_AIR] Return pose:", return_pose)

        print("[RAW_DRAW_POLYLINE_AIR] Checking robot status before motion")
        self.get_controller_ip()
        self.get_actual_tcp_pose()
        self.get_robot_error_code()

        results = []
        if start_pose is not None:
            print("[RAW_DRAW_POLYLINE_AIR] Moving to configured start pose")
            if approach_with_move_j:
                results.append(
                    self.move_j_to_pose(
                        start_pose,
                        start_vel if start_vel is not None else approach_vel if approach_vel is not None else vel,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )
            else:
                results.append(
                    self.move_l(
                        start_pose,
                        start_vel if start_vel is not None else vel,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )

        for index, pose in enumerate(poses):
            if index == 0 and start_pose is None and approach_with_move_j:
                print("[RAW_DRAW_POLYLINE_AIR] Using MoveJ/PTP for the first approach point")
                results.append(
                    self.move_j_to_pose(
                        pose,
                        approach_vel if approach_vel is not None else vel,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )
                continue

            print(f"[RAW_DRAW_POLYLINE_AIR] MoveL point {index + 1}/{len(poses)}")
            results.append(self.move_l(pose, vel, enable_move, allow_raw_xmlrpc_motion))

        if return_pose is not None:
            print("[RAW_DRAW_POLYLINE_AIR] Returning to configured corner pose after drawing")
            results.append(
                self.move_l(
                    return_pose,
                    return_vel if return_vel is not None else vel,
                    enable_move,
                    allow_raw_xmlrpc_motion,
                )
            )

        return results

    def draw_pose_strokes(
        self,
        strokes: list[list[list[float]]],
        start_pose: list[float] | None = None,
        return_pose: list[float] | None = None,
        vel: float = 5.0,
        travel_vel: float | None = None,
        travel_z_offset: float = 20.0,
        start_vel: float | None = None,
        return_vel: float | None = None,
        approach_with_move_j: bool = False,
        approach_vel: float | None = None,
        enable_move: bool = False,
        allow_raw_xmlrpc_motion: bool = False,
    ):
        print("[RAW_DRAW_STROKES] Stroke count:", len(strokes))
        if not strokes:
            raise ValueError("strokes must not be empty")
        if start_pose is not None:
            print("[RAW_DRAW_STROKES] Start pose:", start_pose)
        if return_pose is not None:
            print("[RAW_DRAW_STROKES] Return pose:", return_pose)

        print("[RAW_DRAW_STROKES] Checking robot status before motion")
        self.get_controller_ip()
        self.get_actual_tcp_pose()
        self.get_robot_error_code()

        travel_speed = travel_vel if travel_vel is not None else vel
        results = []
        if start_pose is not None:
            print("[RAW_DRAW_STROKES] Moving to configured start pose")
            if approach_with_move_j:
                results.append(
                    self.move_j_to_pose(
                        start_pose,
                        start_vel if start_vel is not None else approach_vel if approach_vel is not None else travel_speed,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )
            else:
                results.append(
                    self.move_l(
                        start_pose,
                        start_vel if start_vel is not None else travel_speed,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )

        for stroke_index, stroke in enumerate(strokes, start=1):
            if not stroke:
                continue
            first_pose = stroke[0]
            travel_pose = self._offset_pose_z(first_pose, travel_z_offset)
            print(f"[RAW_DRAW_STROKES] Stroke {stroke_index}/{len(strokes)} point count:", len(stroke))
            if stroke_index == 1 and start_pose is None and approach_with_move_j:
                results.append(
                    self.move_j_to_pose(
                        travel_pose,
                        approach_vel if approach_vel is not None else travel_speed,
                        enable_move,
                        allow_raw_xmlrpc_motion,
                    )
                )
            else:
                results.append(self.move_l(travel_pose, travel_speed, enable_move, allow_raw_xmlrpc_motion))

            print("[RAW_DRAW_STROKES] Lowering pen")
            results.append(self.move_l(first_pose, travel_speed, enable_move, allow_raw_xmlrpc_motion))
            for point_index, pose in enumerate(stroke[1:], start=2):
                print(f"[RAW_DRAW_STROKES] Stroke {stroke_index} MoveL point {point_index}/{len(stroke)}")
                results.append(self.move_l(pose, vel, enable_move, allow_raw_xmlrpc_motion))

            print("[RAW_DRAW_STROKES] Lifting pen")
            results.append(self.move_l(travel_pose, travel_speed, enable_move, allow_raw_xmlrpc_motion))

        if return_pose is not None:
            print("[RAW_DRAW_STROKES] Returning to configured pose after drawing")
            results.append(
                self.move_l(
                    return_pose,
                    return_vel if return_vel is not None else travel_speed,
                    enable_move,
                    allow_raw_xmlrpc_motion,
                )
            )

        return results

    def _require_raw(self) -> None:
        if self.raw is None:
            raise RuntimeError("Raw XML-RPC server is not connected")

    def _offset_pose_z(self, pose: list[float], z_offset: float) -> list[float]:
        lifted_pose = list(pose)
        lifted_pose[2] = round(float(lifted_pose[2]) + float(z_offset), 3)
        return lifted_pose

    def _build_raw_movel_params(
        self,
        pose: list[float],
        joint_pos: list[float],
        vel: float,
    ) -> list[float]:
        acc = 0.0
        ovl = 100.0
        blend_r = -1.0
        blend_mode = 0
        exaxis_pos = [0.0, 0.0, 0.0, 0.0]
        search = 0
        offset_flag = 0
        offset_pos = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        oacc = 100.0
        vel_acc_param_mode = 0

        return [
            joint_pos[0],
            joint_pos[1],
            joint_pos[2],
            joint_pos[3],
            joint_pos[4],
            joint_pos[5],
            pose[0],
            pose[1],
            pose[2],
            pose[3],
            pose[4],
            pose[5],
            self.tool,
            self.user,
            float(vel),
            acc,
            ovl,
            blend_r,
            blend_mode,
            exaxis_pos[0],
            exaxis_pos[1],
            exaxis_pos[2],
            exaxis_pos[3],
            search,
            offset_flag,
            offset_pos[0],
            offset_pos[1],
            offset_pos[2],
            offset_pos[3],
            offset_pos[4],
            offset_pos[5],
            oacc,
            vel_acc_param_mode,
        ]
