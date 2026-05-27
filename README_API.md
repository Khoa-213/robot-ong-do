# Tai lieu API

File nay mo ta cac endpoint FastAPI hien tai va cong dung cua tung endpoint.

Swagger UI: http://localhost:8000/docs
OpenAPI JSON: http://localhost:8000/openapi.json
ReDoc: http://localhost:8000/redoc

## Health
- GET /health
  - Cong dung: kiem tra service con song.

## Config
- GET /config
  - Cong dung: doc cau hinh hien tai.
- POST /config/reload
  - Cong dung: reload cau hinh tu file.
- PATCH /config
  - Cong dung: cap nhat mot phan cau hinh theo schema chinh xac.

## Robot
- GET /robot/ports
  - Cong dung: kiem tra cac cong 20003/20004/20005.
- GET /robot/status
  - Cong dung: doc trang thai robot (TCP pose, error code, ...).
- POST /robot/moveL
  - Cong dung: MoveL toi mot pose; bi khoa boi enable_robot_move.
- POST /robot/draw/shape
  - Cong dung: ve hinh co ban; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/paper_corners
  - Cong dung: cho robot di qua 4 goc de kiem tra; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.

## Trajectory (Preview)
- POST /trajectory/line/preview
  - Cong dung: tao danh sach pose cho line demo.
- POST /trajectory/shape/preview
  - Cong dung: tao danh sach pose cho cac hinh co ban.
- POST /trajectory/svg/preview
  - Cong dung: tao danh sach pose tu SVG.
- POST /trajectory/text/preview
  - Cong dung: tao danh sach pose tu text.

## Safety
- POST /safety/validate_pose
  - Cong dung: kiem tra 1 pose trong gioi han workspace.
- POST /safety/validate_poses
  - Cong dung: kiem tra danh sach pose trong vung giay.
- POST /safety/validate_paper_point
  - Cong dung: nhap 4 goc (6 gia tri moi goc) + start/end 6D; kiem tra start/end co nam trong vung giay (chi dung XY).

## Gripper
- GET /gripper/status
  - Cong dung: doc trang thai gripper.
- POST /gripper/open
  - Cong dung: mo gripper; bi khoa boi enable_gripper_motion va allow_raw_xmlrpc_gripper.
- POST /gripper/close
  - Cong dung: dong gripper; bi khoa boi enable_gripper_motion va allow_raw_xmlrpc_gripper.

## Cac hinh ho tro
- line_horizontal
- line_vertical
- line_diagonal_down
- line_diagonal_up
- circle
- square
- rectangle
- triangle
