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

def run_local_skeleton(text, font_path, out_img):
    print("\n--- 1. CHẠY THỬ LUỒNG SKELETON NỘI BỘ (KHÔNG CẦN API SERVER) ---")
    print(f"Đang sử dụng font: {font_path}")
    try:
        polys = text_to_outline_polygons(text, font_path, 200)
        geom = MultiPolygon(polys)
        
        # Run polygons to robot paths
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
        
        print("Kết quả trích xuất cục bộ thành công:")
        print(f"  - Số nét vẽ (Strokes): {len(paths)}")
        print(f"  - Tổng số điểm tọa độ: {sum(len(p) for p in paths)}")
        
        # Plot local result
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
        ax.set_title(f"Local Skeleton Preview: '{text}'")
        plt.tight_layout()
        plt.savefig(out_img, dpi=150)
        plt.close()
        print(f"Đã lưu ảnh kết quả cục bộ vào: {out_img}")
        print("Bạn có thể mở file ảnh trên để kiểm tra hình dáng nét đơn sinh ra.")
        return True
    except Exception as e:
        print(f"Lỗi chạy skeleton cục bộ: {e}")
        return False

def check_api_server(base_url):
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2.0) as conn:
            data = json.loads(conn.read().decode('utf-8'))
            return data.get("status") == "ok"
    except Exception:
        return False

def call_preview_api(base_url, text):
    print("\n--- 2. GỌI API PREVIEW (TRAJECTORY PREVIEW) ---")
    url = f"{base_url}/trajectory/text/skeleton/preview"
    payload = json.dumps({"text": text, "continuous": False}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as conn:
            resp = json.loads(conn.read().decode('utf-8'))
            print("API Preview trả về thành công:")
            print(f"  - Font chữ: {resp.get('font_family')}")
            print(f"  - Chế độ vẽ: {resp.get('text_mode')}")
            print(f"  - Số nét vẽ (Strokes): {resp.get('stroke_count')}")
            poses = resp.get('poses', [])
            print(f"  - Tổng số điểm tọa độ robot (poses): {len(poses)}")
            if poses:
                print(f"  - Điểm đầu: {poses[0]}")
                print(f"  - Điểm cuối: {poses[-1]}")
            return True
    except urllib.error.HTTPError as e:
        print(f"API Preview báo lỗi HTTP {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Lỗi kết nối tới API Preview: {e}")
    return False

def call_draw_api(base_url, text):
    print("\n--- 3. GỌI API DRAW (ĐIỀU KHIỂN ROBOT VẼ) ---")
    confirm = input("Bạn có muốn thực hiện lệnh vẽ thực tế trên robot không? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Đã hủy lệnh vẽ thực tế.")
        return False
        
    url = f"{base_url}/robot/draw/text/skeleton"
    payload = json.dumps({"text": text, "continuous": False, "vel": 12.0}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120.0) as conn:
            resp = json.loads(conn.read().decode('utf-8'))
            print("API Draw trả về thành công:")
            print(f"  - Trạng thái di chuyển: {resp.get('enable_move')}")
            print(f"  - Chế độ di chuyển: {resp.get('motion_mode')}")
            print(f"  - Phản hồi từ robot: {resp.get('result')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"API Draw báo lỗi HTTP {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Lỗi kết nối tới API Draw: {e}")
    return False

def main():
    print("====================================================")
    print("       CÔNG CỤ KIỂM THỬ SKELETON CHỮ VIẾT")
    print("====================================================")
    
    text = input("Nhập chữ bạn muốn chạy thử skeleton: ").strip()
    if not text:
        text = "Tâm"
        print(f"Không nhập chữ, mặc định sử dụng từ: '{text}'")
        
    font_path = "C:/Windows/Fonts/times.ttf"
    out_img = str(ROOT / "output" / "test_skeleton_result.png")
    base_url = "http://localhost:8000"
    
    # 1. Chạy thử skeleton nội bộ trước
    run_local_skeleton(text, font_path, out_img)
    
    # 2. Kiểm tra và gọi API
    if check_api_server(base_url):
        print(f"\n[API Server đang hoạt động tại {base_url}]")
        call_preview_api(base_url, text)
        call_draw_api(base_url, text)
    else:
        print(f"\n[API Server tại {base_url} chưa khởi động. Vui lòng chạy lệnh:")
        print("  .\\.venv\\Scripts\\python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload")
        print("  sau đó chạy lại file test này để kiểm tra luồng API.]")

if __name__ == "__main__":
    main()
