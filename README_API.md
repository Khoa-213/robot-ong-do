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
  - Cong dung: cho robot di qua 4 goc hien tai trong `config.paper.corners` de kiem tra; bi khoa boi enable_robot_move va allow_raw_xmlrpc_motion.

### Dieu kien an toan khi robot chay
- Cac API ve/viet (`/robot/draw/line`, `/robot/draw/circle`, `/robot/draw/shape`, `/robot/draw/svg`, `/robot/draw/text`, `/robot/draw/paper_corners`) deu dung toa do giay da do trong `config.paper.corners`.
- Truoc khi ve/viet, robot se di ve `before_draw.start_pose` neu pose nay duoc cau hinh.
- Moi diem ve/viet phai nam trong polygon 4 goc giay. Neu target nam ngoai vung giay, API se dung truoc khi gui lenh chuyen dong.
- Trong luc gui lenh raw XML-RPC, paper guard se doc TCP pose sau moi lenh. Neu TCP pose nam ngoai vung giay va khong phai `before_draw.start_pose`/`after_draw.return_pose`, service se goi lenh dung robot (`StopMotion`, fallback `ProgramStop`/`CNDESendStop`) va tra loi loi.
- `before_draw.start_pose` va `after_draw.return_pose` duoc xem la pose an toan, co the nam ngoai vung giay.

### Vi du body Robot
Cac API move/ve/viet co field `vel` se dung gia tri nay lam toc do robot cho ca lenh chinh, di chuyen toi start, travel/approach va return. Neu khong gui `vel`, backend moi dung toc do trong config.

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
  - Cong dung: dung 4 goc hien tai trong `config.paper.corners` de kiem tra start/end 6D co nam trong vung giay (chi dung XY).

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
