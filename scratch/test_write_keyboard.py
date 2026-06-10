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
from math import hypot
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths


# ── Helpers tái hiện post-processing của robot trong không gian pixel ────────

def _xy_dist(a, b) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _stroke_length_2d(stroke) -> float:
    return sum(_xy_dist(a, b) for a, b in zip(stroke, stroke[1:]))


def _prune_short_px(strokes, min_len_px):
    """Loại bỏ nét quá ngắn — tương đương prune_short_pose_strokes(28 mm)."""
    return [s for s in strokes if len(s) >= 2 and _stroke_length_2d(s) >= min_len_px]


def _connect_nearby_px(strokes, max_gap_px):
    """Nối các nét gần nhau — tương đương connect_nearby_pose_strokes(8 mm)."""
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
    """Cắt phần đầu nét đi trim_px pixel."""
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
    """Cắt 2 đầu mỗi nét — tương đương trim_pose_stroke_ends(3 mm)."""
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


# ─────────────────────────────────────────────────────────────────────────────

def check_api_server(base_url):
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2.0) as conn:
            data = json.loads(conn.read().decode('utf-8'))
            return data.get("status") == "ok"
    except Exception:
        return False


def show_skeleton_preview_locally(text, font_path, out_img):
    """
    Tạo ảnh preview skeleton khớp với những gì robot thực tế sẽ vẽ.

    Các bước khớp với robot:
      1. Sinh skeleton giống hệt pipeline robot (cùng tham số)
      2. Áp dụng invert_y (robot dùng invert_y=True trong adapter)
      3. Áp dụng prune / connect / trim tương đương (scale pixel → mm)
    """
    try:
        # 1. Sinh outline polygon & skeleton (pixel space)
        polys = text_to_outline_polygons(text, font_path, 200)
        geom  = MultiPolygon(polys)
        paths = polygons_to_robot_paths(
            geom,
            resolution=2.0,
            z_light=-0.5,
            z_heavy=-3.0,
            point_spacing=1.0,
            min_branch_length=4.0,
            simplify_tolerance=0.05,
            theta=1.5,
        )

        if not paths:
            print("[Preview] Không có nét nào được tạo ra!")
            return

        # 2. Tính bounding box để ước tính scale pixel → mm
        all_pts = [pt for s in paths for pt in s]
        min_x   = min(pt[0] for pt in all_pts)
        max_x   = max(pt[0] for pt in all_pts)
        min_y   = min(pt[1] for pt in all_pts)
        max_y   = max(pt[1] for pt in all_pts)
        px_w    = max(max_x - min_x, 1.0)
        px_h    = max(max_y - min_y, 1.0)

        # Robot dùng fit_width_mm=90, fit_height_mm=80 → ước tính tỉ lệ
        scale_mm_per_px = min(90.0 / px_w, 80.0 / px_h)

        # 3. Áp dụng invert_y — giống robot adapter (invert_y=True)
        #    y_display = (min_y + max_y) - y_original  (lật quanh giữa bbox)
        def inv_y(stroke):
            return [(x, min_y + max_y - y, z) for x, y, z in stroke]

        inverted = [inv_y(s) for s in paths]

        # 4. Áp dụng post-processing tương đương robot (đơn vị pixel)
        PRUNE_MM, CONNECT_MM, TRIM_MM = 8.0, 2.0, 1.0
        prune_px   = PRUNE_MM   / scale_mm_per_px
        connect_px = CONNECT_MM / scale_mm_per_px
        trim_px    = TRIM_MM    / scale_mm_per_px

        processed = _prune_short_px(inverted, prune_px)
        processed = _connect_nearby_px(processed, connect_px)
        processed = _trim_ends_px(processed, trim_px)

        # 5. Plot
        fig, ax = plt.subplots(figsize=(10, 6))

        # Vẽ viền chữ (cũng lật Y để khớp với skeleton)
        for poly in polys:
            ox, oy = poly.exterior.xy
            oy_inv  = [min_y + max_y - yi for yi in oy]
            lbl = "Outline" if "Outline" not in ax.get_legend_handles_labels()[1] else ""
            ax.plot(ox, oy_inv, color="#ccc", linestyle="--", linewidth=1.5, label=lbl)
            for interior in poly.interiors:
                xi, yi = interior.xy
                yi_inv = [min_y + max_y - yii for yii in yi]
                ax.plot(xi, yi_inv, color="#ccc", linestyle="--", linewidth=1.5)

        # Vẽ skeleton sau post-processing
        for idx, stroke in enumerate(processed):
            xs = [pt[0] for pt in stroke]
            ys = [pt[1] for pt in stroke]
            ax.plot(xs, ys, linewidth=2.5, label=f"Stroke {idx + 1}")
            ax.scatter(xs, ys, s=15, zorder=3)

        ax.set_aspect("equal")
        ax.set_title(
            f"Robot Skeleton Preview – Times New Roman: '{text}'\n"
            f"[invert_y ✓  |  prune {PRUNE_MM} mm  |"
            f"  connect {CONNECT_MM} mm  |  trim {TRIM_MM} mm]"
        )
        plt.tight_layout()
        plt.savefig(out_img, dpi=150)
        plt.close()
        print(f"[Preview] Đã tạo file ảnh mô phỏng nét vẽ tại: {out_img}")

    except Exception as e:
        import traceback
        print(f"[Preview] Lỗi vẽ ảnh mô phỏng: {e}")
        traceback.print_exc()


def main():
    base_url = "http://localhost:8000"
    font_path = "C:/Windows/Fonts/times.ttf"
    out_img   = str(ROOT / "output" / "test_keyboard_skeleton.png")

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

    # 3. Tạo preview ảnh cục bộ (khớp với robot)
    print(f"\n[1/3] Đang phân tích chữ '{text}' và tạo bản vẽ mô phỏng...")
    show_skeleton_preview_locally(text, font_path, out_img)

    # 4. Gọi API preview
    print("\n[2/3] Gửi yêu cầu phân tích quỹ đạo nét vẽ tới API Server...")
    url_preview = f"{base_url}/trajectory/text/skeleton/preview"
    payload     = json.dumps({"text": text, "continuous": False}).encode("utf-8")
    req_preview = urllib.request.Request(
        url_preview,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
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
    confirm = input(
        f"BẠN CÓ CHẮC CHẮN MUỐN ROBOT BẮT ĐẦU VIẾT CHỮ '{text}' KHÔNG? (y/N): "
    ).strip().lower()
    if confirm != 'y':
        print("Đã hủy lệnh viết thực tế.")
        return

    print("Đang gửi lệnh viết tới robot (đang đợi robot thực hiện xong)...")
    url_draw     = f"{base_url}/robot/draw/text/skeleton"
    payload_draw = json.dumps({"text": text, "continuous": False, "vel": 12.0}).encode("utf-8")
    req_draw     = urllib.request.Request(
        url_draw,
        data=payload_draw,
        headers={"Content-Type": "application/json"},
        method="POST",
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
