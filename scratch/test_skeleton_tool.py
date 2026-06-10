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

def _xy_dist(a, b) -> float:
    from math import hypot
    return hypot(a[0] - b[0], a[1] - b[1])


def _stroke_length_2d(stroke) -> float:
    return sum(_xy_dist(a, b) for a, b in zip(stroke, stroke[1:]))


def _prune_short_px(strokes, min_len_px):
    return [s for s in strokes if len(s) >= 2 and _stroke_length_2d(s) >= min_len_px]


def _connect_nearby_px(strokes, max_gap_px):
    if max_gap_px <= 0 or len(strokes) <= 1:
        return [list(s) for s in strokes]
    remaining = [list(s) for s in strokes if len(s) >= 2]
    connected = []
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed and remaining:
            changed = False
            best_i, best_rev, best_d = -1, False, max_gap_px
            for i, s in enumerate(remaining):
                d0 = _xy_dist(current[-1], s[0])
                d1 = _xy_dist(current[-1], s[-1])
                if d0 <= best_d:
                    best_i, best_rev, best_d = i, False, d0
                if d1 <= best_d:
                    best_i, best_rev, best_d = i, True, d1
            if best_i >= 0:
                nxt = remaining.pop(best_i)
                if best_rev:
                    nxt.reverse()
                current.extend(nxt)
                changed = True
        connected.append(current)
    return connected


def _trim_start_px(stroke, trim_px):
    remaining = float(trim_px)
    for i, (a, b) in enumerate(zip(stroke, stroke[1:])):
        seg = _xy_dist(a, b)
        if seg <= 1e-9:
            continue
        if remaining < seg:
            t = remaining / seg
            interp = tuple(a[ax] + (b[ax] - a[ax]) * t for ax in range(len(a)))
            return [interp] + list(stroke[i + 1:])
        remaining -= seg
    return []


def _trim_ends_px(strokes, trim_px):
    if trim_px <= 0:
        return [list(s) for s in strokes]
    result = []
    for s in strokes:
        s2 = _trim_start_px(s, trim_px)
        if not s2:
            continue
        s2 = list(reversed(_trim_start_px(list(reversed(s2)), trim_px)))
        if len(s2) >= 2:
            result.append(s2)
    return result


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

        if not paths:
            print("[Preview] No strokes generated!")
            return False
        
        # Calculate bounding box for pixel -> mm scaling
        all_pts = [pt for s in paths for pt in s]
        min_x = min(pt[0] for pt in all_pts)
        max_x = max(pt[0] for pt in all_pts)
        min_y = min(pt[1] for pt in all_pts)
        max_y = max(pt[1] for pt in all_pts)
        px_w = max(max_x - min_x, 1.0)
        px_h = max(max_y - min_y, 1.0)

        # Robot uses fit_width_mm=90, fit_height_mm=80
        scale_mm_per_px = min(90.0 / px_w, 80.0 / px_h)

        # Apply Y inversion to match robot drawing
        def inv_y(stroke):
            return [(x, min_y + max_y - y, z) for x, y, z in stroke]

        inverted = [inv_y(s) for s in paths]

        # Apply post-processing equivalent to robot (in pixel space)
        PRUNE_MM, CONNECT_MM, TRIM_MM = 8.0, 2.0, 1.0
        prune_px = PRUNE_MM / scale_mm_per_px
        connect_px = CONNECT_MM / scale_mm_per_px
        trim_px = TRIM_MM / scale_mm_per_px

        processed = _prune_short_px(inverted, prune_px)
        processed = _connect_nearby_px(processed, connect_px)
        processed = _trim_ends_px(processed, trim_px)
        
        print("Kết quả trích xuất cục bộ thành công:")
        print(f"  - Số nét vẽ (Strokes) sau hậu xử lý: {len(processed)}")
        print(f"  - Tổng số điểm tọa độ: {sum(len(p) for p in processed)}")
        
        # Plot local result
        fig, ax = plt.subplots(figsize=(10, 6))
        for poly in polys:
            ox, oy = poly.exterior.xy
            oy_inv = [min_y + max_y - yi for yi in oy]
            ax.plot(ox, oy_inv, color="#ccc", linestyle="--", linewidth=1.5)
            for interior in poly.interiors:
                xi, yi = interior.xy
                yi_inv = [min_y + max_y - yii for yii in yi]
                ax.plot(xi, yi_inv, color="#ccc", linestyle="--", linewidth=1.5)

        for idx, stroke in enumerate(processed):
            xs = [pt[0] for pt in stroke]
            ys = [pt[1] for pt in stroke]
            ax.plot(xs, ys, linewidth=2.5, label=f"Stroke {idx+1}")
            ax.scatter(xs, ys, s=15, zorder=3)

        ax.set_aspect("equal")
        ax.set_title(
            f"Local Robot Skeleton Preview: '{text}'\n"
            f"[invert_y ✓  |  prune {PRUNE_MM} mm  |  connect {CONNECT_MM} mm  |  trim {TRIM_MM} mm]"
        )
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
