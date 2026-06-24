# BẢN GHI PHÁT TRIỂN & HƯỚNG DẪN DỰ ÁN ROBOT ÔNG ĐỒ (PROJECT DEVELOPMENT NOTES)

> [!IMPORTANT]
> **HƯỚNG DẪN BẮT BUỘC CHO LẬP TRÌNH VIÊN VÀ AI AGENT:**
> 1. **TRƯỚC KHI BẮT ĐẦU:** Đọc kỹ toàn bộ file này để nắm cấu trúc, các ràng buộc kỹ thuật và cơ chế an toàn của dự án.
> 2. **SAU KHI CẬP NHẬT/THÊM MỚI:** Phải ghi nhận chi tiết thay đổi vào mục **[Nhật ký phát triển (Change Log)](#nhật-ký-phát-triển-change-log)** ở cuối file này. Không được bỏ qua bước này.

---

## 1. Tổng quan dự án (Project Overview)

Dự án này là hệ thống điều khiển cánh tay robot **Fairino FR3/FR5** viết thư pháp tiếng Việt từ nhiều nguồn đầu vào:
- **SVG file** (hỗ trợ nét đơn - single centerline stroke).
- **Văn bản nhập từ bàn phím** (thông qua pipeline chuyển đổi viền chữ - font outline thành nét xương centerline - skeleton).
- **Các hình hình học cơ bản** (đường thẳng, tròn, vuông, tam giác...).

Hệ thống được thiết kế chạy đa nền tảng (Windows/Linux), tích hợp mô phỏng kiểm tra an toàn (preview/dry-run), điều khiển chuyển động mịn qua API spline của Fairino SDK, và hỗ trợ xuất dữ liệu quỹ đạo phục vụ huấn luyện máy học (Isaac Sim, Unity, RLDS).

---

## 2. Bản đồ cấu trúc thư mục (Directory Map)

Dưới đây là sơ đồ tổ chức mã nguồn và vai trò của từng thành phần chính:

- `config/`: Chứa file cấu hình dự án.
  - [robot_config.json](file:///d:/Capstone/robot-ong-do/config/robot_config.json): File cấu hình trung tâm (IP robot, tọa độ 4 góc giấy, thông số vẽ spline, tốc độ, giới hạn an toàn...).
  - [word_library.json](file:///d:/Capstone/robot-ong-do/config/word_library.json): Bản đồ ánh xạ từ từ khóa sang file SVG.
- `src/`: Thư mục mã nguồn chính của dự án.
  - `api/`: API Server sử dụng FastAPI.
    - [app.py](file:///d:/Capstone/robot-ong-do/src/api/app.py): Khởi chạy ứng dụng.
    - `routers/`: Chứa các route xử lý cấu hình ([config.py](file:///d:/Capstone/robot-ong-do/src/api/routers/config.py)), điều khiển robot ([robot.py](file:///d:/Capstone/robot-ong-do/src/api/routers/robot.py)), an toàn ([safety.py](file:///d:/Capstone/robot-ong-do/src/api/routers/safety.py)), và tạo quỹ đạo vẽ ([trajectory.py](file:///d:/Capstone/robot-ong-do/src/api/routers/trajectory.py)).
  - `ui/`: Giao diện người dùng.
    - [app_streamlit.py](file:///d:/Capstone/robot-ong-do/src/ui/app_streamlit.py): Giao diện web tương tác bằng Streamlit.
  - `services/`: Lớp nghiệp vụ xử lý chính.
    - [robot_service.py](file:///d:/Capstone/robot-ong-do/src/services/robot_service.py): Điều phối hoạt động vẽ hình, vẽ SVG, vẽ chữ skeleton và gọi API robot.
  - `outline_to_skeleton/`: Pipeline chuyển chữ vẽ outline/font TTF thành nét đơn (skeleton) có lực nhấn Z-depth.
    - [font_outline.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/font_outline.py): Trích xuất polygon từ font chữ bằng Matplotlib.
    - [svg_outline.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/svg_outline.py): Lấy đa giác từ file SVG đóng (filled outlines).
    - [skeletonize.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/skeletonize.py): Chuyển đổi đa giác thành pixel xương bằng thuật toán Medial Axis.
    - [graph_trace.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/graph_trace.py): Dò các nét vẽ từ ma trận điểm xương thành danh sách nét.
    - [z_depth.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/z_depth.py): Tính toán độ sâu Z (lực nhấn) dựa trên độ dày nét chữ tại vị trí tương ứng.
    - [path_smoothing.py](file:///d:/Capstone/robot-ong-do/src/outline_to_skeleton/path_smoothing.py): Làm mịn nét vẽ (Moving Average), tối ưu thứ tự nét vẽ và rút gọn điểm (RDP).
  - `svg/` & `svg_processing/`: Đọc, phân tích và tiền xử lý SVG nét đơn.
  - `robot/`: Bộ chuyển đổi quỹ đạo vẽ sang lệnh điều khiển robot.
    - [fairino_path_adapter.py](file:///d:/Capstone/robot-ong-do/src/robot/fairino_path_adapter.py): Ánh xạ tọa độ vẽ sang tọa độ giấy thực tế và gọi API di chuyển.
  - `calibration/`: Các helper hỗ trợ kết nối, cấu hình IP và giả lập robot.
  - `dataset/`: Xuất dữ liệu quỹ đạo vẽ sang Isaac Sim, Unity, định dạng OpenX / RLDS.
- `modules/`: Các module tính toán thuật toán và kết nối SDK cấp thấp.
  - [fairino_raw_controller.py](file:///d:/Capstone/robot-ong-do/modules/fairino_raw_controller.py): Điều khiển robot qua XML-RPC, thực thi chuyển động spline mịn (`NewSpline`).
  - [paper_zone.py](file:///d:/Capstone/robot-ong-do/modules/paper_zone.py): Nội suy song tuyến (Bilinear Interpolation) từ tọa độ cục bộ 2D sang không gian robot 3D dựa trên 4 góc giấy đã đo đạc thực tế.
  - [trajectory_planner.py](file:///d:/Capstone/robot-ong-do/modules/trajectory_planner.py): Xử lý điểm trùng, rút gọn khoảng cách điểm và giới hạn gia tốc chuyển động.
  - [safety_check.py](file:///d:/Capstone/robot-ong-do/modules/safety_check.py): Kiểm tra vùng làm việc an toàn của robot.
- `tests/` & `scratch/`: Chứa các script kiểm thử chẩn đoán và thử nghiệm cục bộ.
- `docs/`: Chứa tài liệu hướng dẫn kỹ thuật chi tiết.
  - [project_scan_report.md](file:///d:/Capstone/robot-ong-do/docs/project_scan_report.md): Chi tiết kiến trúc hệ thống và an toàn.
  - [gripper_project_audit.md](file:///d:/Capstone/robot-ong-do/docs/gripper_project_audit.md): Nghiên cứu và thiết kế tích hợp tay gắp JODELL EPG40.

---

## 3. Các tính năng cốt lõi đã hoàn thành

1. **Điều khiển chuyển động mịn (NewSpline):**
   - Hệ thống không điều khiển ngắt quãng từng điểm mà gom điểm của mỗi nét vẽ thành chuỗi liên tục.
   - Sử dụng các API của Fairino: `NewSplineStart`, `NewSplinePoint`, và `NewSplineEnd` để tạo đường đi mượt mà nhất.
   - Có cơ chế dự phòng chuyển sang `MoveL` kèm blend bán kính (`blendR`) nếu Spline bị lỗi trên robot thực.

2. **Căn chỉnh góc giấy (Paper Calibration):**
   - Không giả định giấy song song với hệ tọa độ XY của robot.
   - Tọa độ 4 góc giấy thực tế được đo đạc và lưu trong `paper.corners` của file cấu hình.
   - Lớp `paper_zone.py` thực hiện ánh xạ tọa độ chuẩn hóa $[0, 1] \times [0, 1]$ sang vị trí 3D thực tế thông qua nội suy song tuyến (bilinear interpolation).

3. **Thuật toán Skeletonize & Lực nhấn Z-depth:**
   - Hỗ trợ chuyển đổi font vector (TTF/OTF) hoặc SVG outline dạng khép kín thành nét viết centerline đơn lẻ.
   - Sử dụng thuật toán Medial Axis từ `scikit-image`.
   - Tính toán độ dày vùng chữ ban đầu (local radius) rồi ánh xạ thành độ sâu Z tương ứng (`z_light` cho nét mỏng, `z_heavy` cho nét dày), giúp tạo ra nét bút lông chân thực.

4. **Kiểm tra an toàn tĩnh (Static Safety Guard):**
   - Tự động kiểm tra phạm vi làm việc của robot (Workspace check).
   - Kiểm tra giới hạn trục Z để tránh việc nhấn bút quá sâu gây hỏng bút/robot.
   - Xác thực tọa độ điểm vẽ nằm hoàn toàn trong vùng giấy an toàn (Paper Guard).

5. **Xuất dữ liệu huấn luyện AI:**
   - Cho phép xuất trực tiếp dữ liệu chuyển động sang tệp tin `.json`, `.csv` hoặc các schema tương thích với Isaac Sim, Unity, và tập dữ liệu RLDS.

---

## 4. Ràng buộc kỹ thuật & Quy tắc phát triển (Development Rules)

### Quy tắc an toàn bắt buộc (Safety Constraints)
- **Không tự ý chuyển chuyển động thực sang True:** Trong cấu hình mặc định hoặc cấu hình mặc định của pipeline (`font_skeleton_pipeline`), luôn thiết lập `preview_only_default=true`.
- **Thử nghiệm Dry-Run:** Mọi thay đổi về thuật toán sinh tọa độ hoặc bộ chuyển đổi tọa độ adapter phải được kiểm thử ở chế độ `--dry-run` hoặc chạy qua API mô phỏng trước khi gửi lệnh chuyển động thực tế.
- **Giới hạn Z:** Độ sâu Z tuyệt đối không được cấu hình sâu hơn giới hạn vật lý của giấy (thông thường giữ `z_heavy` ở khoảng `-3.0 mm` đến `-5.0 mm` và kiểm tra kỹ giá trị `paper.paper_z`).

### Quy tắc lập trình trên Windows
- Hệ thống chạy trên Windows cần xử lý mã hóa UTF-8 khi đọc/ghi file hoặc ghi log ra console. Cần khai báo cấu hình ép kiểu mã hóa UTF-8 đầu file script:
  ```python
  import sys
  if hasattr(sys.stdout, 'reconfigure'):
      sys.stdout.reconfigure(encoding='utf-8')
  ```

### Quy tắc khớp tọa độ trục Y (Y-Axis Inversion)
- Trục Y của ảnh/màn hình thường hướng xuống dưới, trong khi trục Y của robot hoặc hệ tọa độ vẽ mong muốn hướng lên trên.
- Trong bộ chuyển đổi adapter (`fairino_path_adapter.py` hoặc preview cục bộ), tham số `invert_y=True` được sử dụng để lật trục Y quanh trục giữa của bounding box giúp hình vẽ không bị ngược.

---

## 5. Nhật ký phát triển (Change Log)

*Phần này ghi lại lịch sử thay đổi của dự án. Khi bạn thực hiện bất kỳ cập nhật, sửa lỗi hay thêm mới tính năng nào, hãy thêm một dòng mới vào đây.*

| Ngày (Date) | Người thực hiện / Tác vụ | File ảnh hưởng (Affected Files) | Mô tả chi tiết thay đổi (Details) |
| :--- | :--- | :--- | :--- |
| 2026-05-23 | Gripper Audit | `docs/gripper_project_audit.md` | Thực hiện kiểm định tài liệu tay gắp JODELL EPG40-050, thiết kế cấu trúc Modbus RTU và mã đăng ký điều khiển. |
| 2026-06-17 | Project Scan | `docs/project_scan_report.md` | Quét toàn bộ kiến trúc mã nguồn dự án, phân tích API FastAPI, Streamlit UI và các điểm gọi chuyển động của robot. |
| 2026-06-24 | Thiết lập tài liệu | `PROJECT_NOTES.md` | Tạo tài liệu chỉ dẫn phát triển và yêu cầu cập nhật nhật ký cho lập trình viên/AI Agent. |
| 2026-06-24 | Thử nghiệm & Kiểm chứng | `PROJECT_NOTES.md`, `walkthrough.md` | Áp dụng phương án invert_y=True và trích xuất thành công đường đi thực tế (robot trajectory) cho chữ "Nhẫn". |
| 2026-06-24 | Tối ưu hóa nét & Thứ tự viết | `src/outline_to_skeleton/skeletonize.py`, `walkthrough.md` | Triển khai phân tách góc nhọn và nối nét collinear/serif để sửa lỗi đứt nét chữ "h", đồng thời sắp xếp thứ tự viết theo quy tắc thư pháp tiếng Việt. |


