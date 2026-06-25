"""
scratch/run_alphabet_calligraphy.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sinh đường đi thực tế cho trọn bộ bảng chữ cái Latinh tiếng Việt viết bằng
thư pháp nâng cao (Calligraphy V2).

Hỗ trợ đầy đủ:
  - 29 chữ cái tiếng Việt cơ bản (a-z) + các chữ tiếng Anh (f, j, w, z)
  - Các chữ cái hoa (A-Z)
  - Các chữ cái ghép dấu đặc trưng (ă, â, đ, ê, ô, ơ, ư)
  - Layout 6 dòng cân đối trên trang giấy A4.

Chạy:
  python scratch/run_alphabet_calligraphy.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import sys, os, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import numpy as np

from modules.calligraphy_parser import (
    parse_vietnamese_text,
    calligraphy_strokes_to_robot_paths,
    CalligraphyStroke,
    StrokeLayer,
)

# ── Cấu hình ─────────────────────────────────────────────────────────────────

Z_LIGHT      = -0.5            # Z chạm nhẹ nhất (mm offset từ paper_z)
Z_HEAVY      = -3.0            # Z nhấn mạnh nhất
FONT_SCALE   = 220.0           # pixel-scale

# Tọa độ giấy thực từ robot_config.json
PAPER_ORIGIN_X  = -129.426    # mm
PAPER_ORIGIN_Y  =  311.78     # mm
PAPER_Z         =  292.206    # mm (baseline)
PAPER_WIDTH_MM  =  210.0
PAPER_HEIGHT_MM =  297.0
MARGIN_MM       =   15.0

# Vùng vẽ UV rộng rãi cho toàn bộ bảng chữ cái (layout 6 dòng)
U_MIN, U_MAX = 0.10, 0.90
V_MIN, V_MAX = 0.12, 0.88

# Layout chữ cái thành 6 dòng
ALPHABET_LINES = [
    "a ă â b c d đ e ê f g",
    "h i j k l m n o ô ơ p",
    "q r s t u ư v w x y z",
    "A Ă Â B C D Đ E Ê F G",
    "H I J K L M N O Ô Ơ P",
    "Q R S T U Ư V W X Y Z"
]

# Output
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = Path(PROJECT_ROOT) / "output" / f"vietnamese_alphabet_{TIMESTAMP}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Layer colors ──────────────────────────────────────────────────────────────

LAYER_COLORS = {
    StrokeLayer.BASE:      '#4fc3f7',
    StrokeLayer.DIACRITIC: '#ffb74d',
    StrokeLayer.TONE_MARK: '#ef5350',
}


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1: Phân rã & Dịch chuyển các dòng chữ
# ════════════════════════════════════════════════════════════════════════════

def step1_assemble():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Calligraphy V2 — Sinh bảng chữ cái Latinh tiếng Việt        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    all_strokes: list[CalligraphyStroke] = []
    row_height = 1.9  # Khoảng cách dòng đủ rộng cho dấu phụ phía trên/dưới
    
    for row_idx, line in enumerate(ALPHABET_LINES):
        print(f"▶  Đang xử lý Dòng {row_idx + 1}: \"{line}\"")
        line_strokes = parse_vietnamese_text(line)
        
        # Dịch chuyển trục Y của dòng hiện tại xuống dưới
        dy = -row_idx * row_height
        for s in line_strokes:
            shifted_points = [(x, y + dy) for x, y in s.points]
            shifted_stroke = CalligraphyStroke(
                stroke_type=s.stroke_type,
                layer=s.layer,
                points=shifted_points,
                z_profile=s.z_profile
            )
            all_strokes.append(shifted_stroke)

    print()
    print("─" * 60)
    print(f"📋 Tổng số nét bút của bảng chữ cái: {len(all_strokes)} nét")
    print("─" * 60)
    return all_strokes


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2: Sinh robot paths (tọa độ mm thực)
# ════════════════════════════════════════════════════════════════════════════

def step2_robot_paths(strokes):
    raw_paths = calligraphy_strokes_to_robot_paths(
        strokes, z_light=Z_LIGHT, z_heavy=Z_HEAVY, font_scale=FONT_SCALE
    )

    all_xy = [(x, y) for path in raw_paths for x, y, _ in path]
    xs = [p[0] for p in all_xy]
    ys = [p[1] for p in all_xy]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    glyph_w = max(max_x - min_x, 1e-6)
    glyph_h = max(max_y - min_y, 1e-6)

    print(f"▶  Glyph space: x=[{min_x:.1f}, {max_x:.1f}]  y=[{min_y:.1f}, {max_y:.1f}]  ({glyph_w:.1f}×{glyph_h:.1f} px)")

    u_span = U_MAX - U_MIN
    v_span = V_MAX - V_MIN
    drawable_w = u_span * PAPER_WIDTH_MM
    drawable_h = v_span * PAPER_HEIGHT_MM
    scale_mm = min(drawable_w / glyph_w, drawable_h / glyph_h)

    scale_x = scale_mm / PAPER_WIDTH_MM
    scale_y = scale_mm / PAPER_HEIGHT_MM
    fitted_w_u = glyph_w * scale_x
    fitted_h_v = glyph_h * scale_y

    u_offset = U_MIN + (u_span - fitted_w_u) / 2.0
    v_offset = V_MIN + (v_span - fitted_h_v) / 2.0

    print(f"▶  Scale: {scale_mm:.4f} mm/px  → Bảng chữ cái chiếm {fitted_w_u*PAPER_WIDTH_MM:.1f}mm × {fitted_h_v*PAPER_HEIGHT_MM:.1f}mm trên giấy")
    print(f"▶  UV offset: ({u_offset:.3f}, {v_offset:.3f})")
    print()

    robot_paths_mm = []
    for path in raw_paths:
        path_mm = []
        for gx, gy, gz_offset in path:
            u = u_offset + (gx - min_x) * scale_x
            v = v_offset + (max_y - gy) * scale_y    # invert_y=True

            rx = PAPER_ORIGIN_X + u * PAPER_WIDTH_MM
            ry = PAPER_ORIGIN_Y + (1.0 - v) * PAPER_HEIGHT_MM
            rz = PAPER_Z + gz_offset

            path_mm.append({
                "x_mm": round(rx, 3),
                "y_mm": round(ry, 3),
                "z_mm": round(rz, 3),
                "gz_offset": round(gz_offset, 4),
                "u":    round(u, 4),
                "v":    round(v, 4),
            })
        robot_paths_mm.append(path_mm)

    all_z = [pt["z_mm"] for path in robot_paths_mm for pt in path]
    all_rx = [pt["x_mm"] for path in robot_paths_mm for pt in path]
    all_ry = [pt["y_mm"] for path in robot_paths_mm for pt in path]

    print(f"✅ Sinh {len(robot_paths_mm)} robot paths, {sum(len(p) for p in robot_paths_mm)} điểm tổng cộng")
    print(f"   X robot: [{min(all_rx):.1f}, {max(all_rx):.1f}] mm")
    print(f"   Y robot: [{min(all_ry):.1f}, {max(all_ry):.1f}] mm")
    print(f"   Z robot: [{min(all_z):.3f}, {max(all_z):.3f}] mm")
    print(f"   Paper Z (baseline): {PAPER_Z:.3f} mm")
    print()

    return raw_paths, robot_paths_mm, (min_x, max_x, min_y, max_y), scale_x, scale_y, u_offset, v_offset


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 3: Xuất JSON
# ════════════════════════════════════════════════════════════════════════════

def step3_export_json(strokes, robot_paths_mm):
    report = {
        "text": " ".join(ALPHABET_LINES),
        "mode": "vietnamese_alphabet_multiline",
        "generated_at": TIMESTAMP,
        "config": {
            "z_light": Z_LIGHT,
            "z_heavy": Z_HEAVY,
            "font_scale": FONT_SCALE,
            "paper_z_baseline_mm": PAPER_Z,
            "paper_width_mm": PAPER_WIDTH_MM,
            "paper_height_mm": PAPER_HEIGHT_MM,
        },
        "summary": {
            "stroke_count": len(robot_paths_mm),
            "total_points": sum(len(p) for p in robot_paths_mm),
            "z_range_mm": {
                "min": round(min(pt["z_mm"] for path in robot_paths_mm for pt in path), 3),
                "max": round(max(pt["z_mm"] for path in robot_paths_mm for pt in path), 3),
            },
        },
        "robot_paths": [
            {
                "stroke_index": i + 1,
                "layer": strokes[i].layer.value if i < len(strokes) else "unknown",
                "stroke_type": strokes[i].stroke_type.value if i < len(strokes) else "unknown",
                "points": path,
            }
            for i, path in enumerate(robot_paths_mm)
        ],
    }

    json_path = OUTPUT_DIR / "alphabet_robot_paths.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"▶  JSON robot paths: {json_path}")
    return report


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 4: Render Preview
# ════════════════════════════════════════════════════════════════════════════

def step4_render(strokes, raw_paths, bbox, scale_x, scale_y, u_offset, v_offset):
    min_x, max_x, min_y, max_y = bbox
    glyph_w = max_x - min_x
    glyph_h = max_y - min_y
    fitted_w_u = glyph_w * scale_x
    fitted_h_v = glyph_h * scale_y

    fig = plt.figure(figsize=(22, 14), facecolor='#0d1117')

    gs = fig.add_gridspec(2, 3, hspace=0.32, wspace=0.30,
                          left=0.04, right=0.97, top=0.92, bottom=0.05)
    ax_order   = fig.add_subplot(gs[0, :2])  # Thứ tự nét
    ax_z       = fig.add_subplot(gs[0, 2])   # Z-depth heatmap
    ax_paper   = fig.add_subplot(gs[1, :2])  # Trên giấy thực (mm)
    ax_detail  = fig.add_subplot(gs[1, 2])   # Tóm tắt thông tin

    for ax in [ax_order, ax_z, ax_paper, ax_detail]:
        ax.set_facecolor('#161b22')
        ax.tick_params(colors='#8b949e', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

    fig.suptitle(
        f'Robot Trajectory — Bảng Chữ Cái Latinh Tiếng Việt Thư Pháp',
        color='white', fontsize=16, fontweight='bold', y=0.97
    )

    # ─── Subplot 1: Thứ tự nét ──────────────────────────────────────────────
    ax_order.set_title("Nét chữ cái chuẩn hóa (Layout 6 dòng)", color='#c9d1d9', fontsize=11)

    for i, (stroke, path) in enumerate(zip(strokes, raw_paths)):
        color = LAYER_COLORS[stroke.layer]
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        ax_order.plot(xs, ys, color=color, linewidth=1.8, alpha=0.85, zorder=3,
                      solid_capstyle='round')
        ax_order.scatter(xs[0], ys[0], s=12, color='#56d364', zorder=5, marker='o')
        ax_order.scatter(xs[-1], ys[-1], s=12, color='#f78166', zorder=5, marker='x', linewidths=1.0)

    # Legend
    patches = [
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.BASE],      label='BASE (Thân chữ)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.DIACRITIC], label='DIACRITIC (Dấu phụ chữ)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.TONE_MARK], label='TONE MARK (Dấu thanh)'),
        mpatches.Patch(color='#56d364', label='Bắt đầu nét'),
        mpatches.Patch(color='#f78166', label='Kết thúc nét'),
    ]
    ax_order.legend(handles=patches, loc='upper right', fontsize=8,
                    facecolor='#161b22', labelcolor='#c9d1d9', edgecolor='#30363d',
                    framealpha=0.9)
    ax_order.set_xlabel("X (glyph units)", color='#8b949e', fontsize=8)
    ax_order.set_ylabel("Y", color='#8b949e', fontsize=8)
    # ax_order.invert_yaxis()
    ax_order.set_aspect('equal', adjustable='box')
    ax_order.grid(True, color='#21262d', linewidth=0.3, linestyle=':')

    # ─── Subplot 2: Z-depth heatmap ─────────────────────────────────────────
    ax_z.set_title("Z-depth theo nét (Lực nhấn)", color='#c9d1d9', fontsize=11)

    cmap_z = matplotlib.colormaps.get_cmap('RdYlGn_r')
    z_norm = mcolors.Normalize(vmin=Z_HEAVY, vmax=Z_LIGHT)

    for stroke, path in zip(strokes, raw_paths):
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        zs = [p[2] for p in path]
        for j in range(len(xs) - 1):
            z_avg = (zs[j] + zs[j+1]) / 2
            color_z = cmap_z(z_norm(z_avg))
            ax_z.plot([xs[j], xs[j+1]], [ys[j], ys[j+1]],
                      color=color_z, linewidth=2.0, alpha=0.85,
                      solid_capstyle='round')

    cb = fig.colorbar(sm := plt.cm.ScalarMappable(cmap=cmap_z, norm=z_norm), ax=ax_z, fraction=0.04, pad=0.02)
    cb.set_label('Z offset (mm)\nĐỏ=nhấn mạnh / Xanh=nhẹ', color='#c9d1d9', fontsize=7)
    cb.ax.yaxis.set_tick_params(color='#8b949e', labelsize=7)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color='#c9d1d9')

    # ax_z.invert_yaxis()
    ax_z.set_aspect('equal', adjustable='box')
    ax_z.grid(True, color='#21262d', linewidth=0.3, linestyle=':')

    # ─── Subplot 3: Tọa độ trên giấy thực (mm) ──────────────────────────────
    ax_paper.set_title(
        f"Đường đi trên giấy thực — Paper A4 ({PAPER_WIDTH_MM}×{PAPER_HEIGHT_MM}mm)\n"
        f"Robot XY từ paper_origin ({PAPER_ORIGIN_X:.1f}, {PAPER_ORIGIN_Y:.1f})",
        color='#c9d1d9', fontsize=10
    )

    paper_rect = plt.Rectangle(
        (PAPER_ORIGIN_X, PAPER_ORIGIN_Y),
        PAPER_WIDTH_MM, PAPER_HEIGHT_MM,
        fill=False, edgecolor='#30363d', linewidth=1.0, linestyle='--'
    )
    ax_paper.add_patch(paper_rect)

    draw_rect = plt.Rectangle(
        (PAPER_ORIGIN_X + MARGIN_MM, PAPER_ORIGIN_Y + MARGIN_MM),
        PAPER_WIDTH_MM - 2*MARGIN_MM, PAPER_HEIGHT_MM - 2*MARGIN_MM,
        fill=True, facecolor='#1c2128', edgecolor='#3d4450', linewidth=0.5
    )
    ax_paper.add_patch(draw_rect)

    for i, (stroke, path) in enumerate(zip(strokes, raw_paths)):
        color = LAYER_COLORS[stroke.layer]
        rxs, rys = [], []
        for gx, gy, _ in path:
            u = u_offset + (gx - min_x) * scale_x
            v = v_offset + (max_y - gy) * scale_y
            rx = PAPER_ORIGIN_X + u * PAPER_WIDTH_MM
            ry = PAPER_ORIGIN_Y + (1.0 - v) * PAPER_HEIGHT_MM
            rxs.append(rx)
            rys.append(ry)

        ax_paper.plot(rxs, rys, color=color, linewidth=2.0, alpha=0.85,
                      solid_capstyle='round', zorder=4)

    ax_paper.set_xlabel("Robot X (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_ylabel("Robot Y (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_aspect('equal', adjustable='box')
    ax_paper.grid(True, color='#21262d', linewidth=0.3, linestyle=':')

    ax_paper.scatter(PAPER_ORIGIN_X, PAPER_ORIGIN_Y, s=80, color='#ff7b72', zorder=8, marker='*')

    # ─── Subplot 4: Bảng tóm tắt thông tin ──────────────────────────────────
    ax_detail.set_title("Tóm tắt thông tin quỹ đạo", color='#c9d1d9', fontsize=11)
    ax_detail.axis('off')

    info_text = (
        "📊 THÔNG TIN CHI TIẾT BẢN VẼ:\n\n"
        f"• Số lượng kí tự dòng: {len(ALPHABET_LINES)} dòng\n"
        f"• Tổng số nét vẽ:      {len(strokes)} nét\n"
        f"• Tổng số điểm tọa độ:  {sum(len(p) for p in raw_paths)} điểm\n"
        f"• Lực nhấn chạm giấy:   {Z_LIGHT} mm (z_light)\n"
        f"• Lực nhấn đậm nhất:    {Z_HEAVY} mm (z_heavy)\n\n"
        "📍 PHẠM VI KHÔNG GIAN (MM):\n"
        f"• Bề rộng chữ vẽ:      {fitted_w_u*PAPER_WIDTH_MM:.1f} mm\n"
        f"• Chiều cao chữ vẽ:     {fitted_h_v*PAPER_HEIGHT_MM:.1f} mm\n"
        f"• Tọa độ X robot:      [{PAPER_ORIGIN_X + u_offset*PAPER_WIDTH_MM:.1f}, {PAPER_ORIGIN_X + (u_offset+fitted_w_u)*PAPER_WIDTH_MM:.1f}] mm\n"
        f"• Tọa độ Y robot:      [{PAPER_ORIGIN_Y + v_offset*PAPER_HEIGHT_MM:.1f}, {PAPER_ORIGIN_Y + (v_offset+fitted_h_v)*PAPER_HEIGHT_MM:.1f}] mm\n\n"
        "📜 QUY TẮC THỨ TỰ THƯ PHÁP TIẾNG VIỆT:\n"
        "  1. Viết toàn bộ thân chữ chính (BASE)\n"
        "  2. Viết toàn bộ dấu phụ chữ cái (DIACRITIC)\n"
        "  3. Viết toàn bộ dấu thanh (TONE MARK)\n\n"
        "✅ Các đường cong tròn mịn màng, co giãn\n"
        "   đều đồng dạng và kiểm tra giới hạn an toàn Z."
    )
    ax_detail.text(0.05, 0.95, info_text, transform=ax_detail.transAxes,
                   color='#c9d1d9', fontsize=9.5, va='top', ha='left',
                   fontfamily='monospace')

    # Lưu ảnh
    out_path = OUTPUT_DIR / "alphabet_trajectory_preview.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"▶  Preview PNG: {out_path}")
    return out_path


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 5: Báo cáo thống kê
# ════════════════════════════════════════════════════════════════════════════

def step5_report(strokes, robot_paths_mm):
    all_z_offset = [pt["gz_offset"] for path in robot_paths_mm for pt in path]
    all_z_abs    = [pt["z_mm"]     for path in robot_paths_mm for pt in path]
    all_rx       = [pt["x_mm"]     for path in robot_paths_mm for pt in path]
    all_ry       = [pt["y_mm"]     for path in robot_paths_mm for pt in path]

    print("─" * 60)
    print(f"📊 BÁO CÁO ĐƯỜNG ĐI ROBOT — BẢNG CHỮ CÁI THƯ PHÁP")
    print("─" * 60)
    print(f"   Tổng số dòng: {len(ALPHABET_LINES)} dòng")
    print(f"   Tổng số nét:  {len(strokes)} nét")
    print(f"   Tổng số điểm: {sum(len(p) for p in robot_paths_mm)} điểm")
    print()
    print("   📍 Tọa độ Robot thực (mm):")
    print(f"   ├─ X: [{min(all_rx):.2f}, {max(all_rx):.2f}]")
    print(f"   ├─ Y: [{min(all_ry):.2f}, {max(all_ry):.2f}]")
    print(f"   ├─ Z absolute:  [{min(all_z_abs):.3f}, {max(all_z_abs):.3f}]  (paper_z = {PAPER_Z})")
    print(f"   └─ Z offset:    [{min(all_z_offset):.3f}, {max(all_z_offset):.3f}]  (từ bề mặt giấy)")
    print()

    z_safe = all(Z_HEAVY <= zoff <= Z_LIGHT for zoff in all_z_offset)
    print(f"   🛡️  An toàn Z: {'✅ TẤT CẢ ĐỂM TRONG GIỚI HẠN AN TOÀN' if z_safe else '⚠️  CÓ ĐIỂM NGOÀI GIỚI HẠN!'}")
    print()
    print(f"   📁 Output: {OUTPUT_DIR}")
    print("─" * 60)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    strokes = step1_assemble()
    raw_paths, robot_paths_mm, bbox, scale_x, scale_y, u_offset, v_offset = step2_robot_paths(strokes)
    step3_export_json(strokes, robot_paths_mm)
    step4_render(strokes, raw_paths, bbox, scale_x, scale_y, u_offset, v_offset)
    step5_report(strokes, robot_paths_mm)

    print()
    print("✅  HOÀN THÀNH! Đường đi thực tế cho bảng chữ cái đã được tạo thành công.")
    print(f"    Xem ảnh preview tại: {OUTPUT_DIR / 'alphabet_trajectory_preview.png'}")


if __name__ == "__main__":
    main()
