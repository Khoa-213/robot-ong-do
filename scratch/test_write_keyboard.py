import sys
import io

# Force UTF-8 encoding for standard I/O to avoid Windows console errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')

import json
import urllib.request
import urllib.error
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths

def check_api_server(base_url):
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2.0) as conn:
            data = json.loads(conn.read().decode('utf-8'))
            return data.get("status") == "ok"
    except Exception:
        return False

def show_skeleton_preview_locally(text, font_path, out_img):
    try:
        polys = text_to_outline_polygons(text, font_path, 200)
        geom = MultiPolygon(polys)
        paths = polygons_to_robot_paths(
            geom,
            resolution=2.0,
            z_light=-0.5,
            z_heavy=-3.0,
            point_spacing=1.0,
            min_branch_length=4.0,
            simplify_tolerance=0.05,
            theta=1.5
        )
        
        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        for poly in polys:
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#ccc", linestyle="--", linewidth=1.5)
            for interior in poly.interiors:
                xi, yi = interior.xy
                ax.plot(xi, yi, color="#ccc", linestyle="--", linewidth=1.5)

        for idx, stroke in enumerate(paths):
            xs = [pt[0] for pt in stroke]
            ys = [pt[1] for pt in stroke]
            ax.plot(xs, ys, linewidth=2.5, label=f"Stroke {idx+1}")
            ax.scatter(xs, ys, s=15, zorder=3)

        ax.set_aspect("equal")
        ax.set_title(f"Times New Roman Skeleton: '{text}'")
        plt.tight_layout()
        plt.savefig(out_img, dpi=150)
        plt.close()
        print(f"[Preview] Đã tạo file ảnh mô phỏng nét vẽ tại: {out_img}")
    except Exception as e:
        print(f"[Preview] Lỗi vẽ ảnh mô phỏng: {e}")

def main():
    base_url = "http://localhost:8000"
    font_path = "C:/Windows/Fonts/times.ttf"
    out_img = str(ROOT / "output" / "test_keyboard_skeleton.png")
    
    print("====================================================")
    print(" CỬA SỔ ĐIỀU KHIỂN ROBOT VIẾT CHỮ SKELETON (TIMES)")
    print("====================================================")
    
    # 1. Kiểm tra kết nối tới API server trước
    if not check_api_server(base_url):
        print(f"Lỗi: Không thể kết nối tới API Server tại {base_url}!")
        print("Vui lòng khởi động server API bằng lệnh sau trước khi chạy test:")
        print("  .\\.venv\\Scripts\\python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload")
        return

    # 2. Nhận text từ bàn phím
    text = input("Nhập chữ bạn muốn cánh tay robot viết: ").strip()
    if not text:
        print("Lỗi: Chữ nhập vào không được để trống!")
        return

    # 3. Tạo preview và vẽ ảnh cục bộ
    print(f"\n[1/3] Đang phân tích chữ '{text}' và tạo bản vẽ mô phỏng...")
    show_skeleton_preview_locally(text, font_path, out_img)
    
    # 4. Gọi API preview
    print("\n[2/3] Gửi yêu cầu phân tích quỹ đạo nét vẽ tới API Server...")
    url_preview = f"{base_url}/trajectory/text/skeleton/preview"
    payload = json.dumps({"text": text, "continuous": False}).encode("utf-8")
    req_preview = urllib.request.Request(
        url_preview,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req_preview, timeout=15.0) as conn:
            resp = json.loads(conn.read().decode('utf-8'))
            print("API Preview phản hồi:")
            print(f"  - Số nét robot sẽ vẽ: {resp.get('stroke_count')}")
            print(f"  - Tổng số điểm tọa độ: {len(resp.get('poses', []))}")
    except urllib.error.HTTPError as e:
        print(f"API Preview báo lỗi HTTP {e.code}: {e.read().decode('utf-8')}")
        return
    except Exception as e:
        print(f"Lỗi kết nối API Preview: {e}")
        return

    # 5. Gọi API draw để bắt đầu cho robot viết thực tế
    print("\n[3/3] RA LỆNH CHO ROBOT VIẾT THỰC TẾ")
    confirm = input(f"BẠN CÓ CHẮC CHẮN MUỐN ROBOT BẮT ĐẦU VIẾT CHỮ '{text}' KHÔNG? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Đã hủy lệnh viết thực tế.")
        return

    print(f"Đang gửi lệnh viết tới robot (đang đợi robot thực hiện xong)...")
    url_draw = f"{base_url}/robot/draw/text/skeleton"
    payload_draw = json.dumps({"text": text, "continuous": False, "vel": 12.0}).encode("utf-8")
    req_draw = urllib.request.Request(
        url_draw,
        data=payload_draw,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req_draw, timeout=300.0) as conn:
            resp = json.loads(conn.read().decode('utf-8'))
            print("\n================ ROBOT HOÀN THÀNH ================")
            print(f"Robot di chuyển: {resp.get('enable_move')}")
            print(f"Kết quả di chuyển: {resp.get('result')}")
            print("==================================================")
    except urllib.error.HTTPError as e:
        print(f"API Draw báo lỗi HTTP {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Lỗi kết nối API Draw: {e}")

if __name__ == "__main__":
    main()
