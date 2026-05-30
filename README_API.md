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
- GET /robot/raw_status
  - Cong dung: doc trang thai qua raw XML-RPC (controller IP, TCP pose, error code); khong gui lenh chuyen dong.
- POST /robot/moveL
  - Cong dung: MoveL toi mot pose; bi khoa boi enable_robot_move.
- POST /robot/ik
  - Cong dung: tinh IK cho 1 pose bang raw XML-RPC; khong gui lenh chuyen dong.
- POST /robot/move/start
  - Cong dung: dua robot ve before_draw.start_pose; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/line
  - Cong dung: ve line demo theo vung giay da do; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/circle
  - Cong dung: ve circle demo theo vung giay da do; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/shape
  - Cong dung: ve hinh co ban; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/svg
  - Cong dung: viet/ve theo file SVG, word_key trong config/word_library.json, hoac danh sach svg_paths; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/text
  - Cong dung: viet chu theo cau hinh text_demo hien tai; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.
- POST /robot/draw/paper_corners
  - Cong dung: cho robot di qua 4 goc de kiem tra; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.

### Vi du body Robot
- POST /robot/move/start
```json
{
  "vel": 20
}
```

- POST /robot/ik
```json
{
  "pose": [-105.657, 275.606, 371.442, 179.379, 8.605, -113.274]
}
```

- POST /robot/draw/svg
```json
{
  "svg_path": "assets/svg/Nhan.svg",
  "vel": 12
}
```

- POST /robot/draw/svg voi nhieu file tren cung layout
```json
{
  "svg_paths": ["assets/svg/tam3.svg", "assets/svg/an.svg"],
  "vel": 12
}
```

- POST /robot/draw/text
```json
{
  "text": "Tam",
  "continuous": false,
  "vel": 12
}
```

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
- tam
- tam1: ve theo file assets/svg/tam1.svg
