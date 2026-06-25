"""
scratch/run_custom_text_calligraphy.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sinh đường đi thực tế cho robot viết chữ bất kỳ nhập từ bàn phím — calligraphy_v2 mode.

Cách chạy:
  python scratch/run_custom_text_calligraphy.py --text "nhẫn"
  Hoặc chỉ chạy:
  python scratch/run_custom_text_calligraphy.py (sẽ hiển thị dấu nhắc nhập chữ)
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
import argparse

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
    describe_character,
    StrokeLayer,
    StrokeType,
    GLYPH_WIDTH,
    GLYPH_GAP,
)

# ── Cấu hình mặc định ─────────────────────────────────────────────────────────

Z_LIGHT      = -0.5            # Z chạm nhẹ nhất (mm offset từ paper_z)
Z_HEAVY      = -3.0            # Z nhấn mạnh nhất
FONT_SCALE   = 220.0           # pixel-scale (khớp với font_size=1.0 × 220)

# Tọa độ giấy thực từ robot_config.json
PAPER_ORIGIN_X  = -129.426    # mm
PAPER_ORIGIN_Y  =  311.78     # mm
PAPER_Z         =  292.206    # mm (baseline)
PAPER_WIDTH_MM  =  210.0
PAPER_HEIGHT_MM =  297.0
MARGIN_MM       =   20.0

# Vùng vẽ UV (u/v ∈ [0,1] → paper space)
U_MIN, U_MAX = 0.12, 0.88
V_MIN, V_MAX = 0.35, 0.65

# ── Layer colors ──────────────────────────────────────────────────────────────

LAYER_COLORS = {
    StrokeLayer.BASE:      '#4fc3f7',
    StrokeLayer.DIACRITIC: '#ffb74d',
    StrokeLayer.TONE_MARK: '#ef5350',
}


def main():
    parser = argparse.ArgumentParser(description="Sinh quỹ đạo thư pháp cho chữ nhập bất kỳ.")
    parser.add_argument("--text", type=str, help="Văn bản tiếng Việt cần viết.")
    parser.add_argument("--gap", type=float, default=-0.23, help="Khoảng cách giữa các chữ cái (glyph_gap).")
    args = parser.parse_args()

    text = args.text
    if not text:
        text = input("Nhập chữ hoặc từ cần viết (Tiếng Việt): ").strip()
    
    if not text:
        print("❌ Lỗi: Văn bản nhập vào không được trống!")
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  Calligraphy V2 — Ghép chữ tự động cho: \"{text}\"")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Phân rã từng ký tự để báo cáo
    for ch in text:
        if not ch.isspace():
            print(describe_character(ch))
            print()

    # Bước 1: Phân rã văn bản với gap điều chỉnh
    strokes = parse_vietnamese_text(text, glyph_gap=args.gap)
    if not strokes:
        print("❌ Lỗi: Không thể phân rã văn bản thành nét bút thư pháp nào!")
        sys.exit(1)

    print("─" * 60)
    print(f"📋 Tổng cộng: {len(strokes)} nét bút")
    print()
    for i, s in enumerate(strokes, 1):
        pts_str = f"({s.points[0][0]:.2f},{s.points[0][1]:.2f})→({s.points[-1][0]:.2f},{s.points[-1][1]:.2f})"
        print(f"  Nét {i:2d}: [{s.layer.value:10s}] {s.stroke_type.value:12s}  "
              f"{len(s.points)} điểm  Z({s.z_profile.z_start:.2f}→{s.z_profile.z_mid:.2f}→{s.z_profile.z_end:.2f})  {pts_str}")
    print()

    # Tạo thư mục output
    clean_text = "".join(c for c in text if c.isalnum() or c.isspace()).replace(" ", "_")
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR = Path(PROJECT_ROOT) / "output" / f"custom_{clean_text}_{TIMESTAMP}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Bước 2: Sinh robot paths trong hệ mm thực tế
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

    print(f"▶  Scale: {scale_mm:.4f} mm/px  → Chiếm {fitted_w_u*PAPER_WIDTH_MM:.1f}mm × {fitted_h_v*PAPER_HEIGHT_MM:.1f}mm trên giấy")
    print(f"▶  UV offset: ({u_offset:.3f}, {v_offset:.3f})")
    print()

    robot_paths_mm = []
    for path in raw_paths:
        path_mm = []
        for gx, gy, gz_offset in path:
            u = u_offset + (gx - min_x) * scale_x
            v = v_offset + (max_y - gy) * scale_y

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

    # Bước 3: Xuất JSON
    report = {
        "text": text,
        "mode": "custom_keyboard_text",
        "generated_at": TIMESTAMP,
        "config": {
            "glyph_gap": args.gap,
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

    json_path = OUTPUT_DIR / f"{clean_text}_robot_paths.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"▶  JSON robot paths: {json_path}")

    # Bước 4: Render PNG preview
    fig = plt.figure(figsize=(20, 13), facecolor='#0d1117')
    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.32, left=0.04, right=0.97, top=0.91, bottom=0.05)
    ax_order   = fig.add_subplot(gs[0, :2])
    ax_z       = fig.add_subplot(gs[0, 2])
    ax_paper   = fig.add_subplot(gs[1, :2])
    ax_detail  = fig.add_subplot(gs[1, 2])

    for ax in [ax_order, ax_z, ax_paper, ax_detail]:
        ax.set_facecolor('#161b22')
        ax.tick_params(colors='#8b949e', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

    fig.suptitle(f'Robot Trajectory — Chữ bàn phím "{text}"', color='white', fontsize=15, fontweight='bold', y=0.96)

    # Subplot 1: Nét chữ thứ tự
    ax_order.set_title("Thứ tự nét viết (BASE→DIACRITIC→TONE)", color='#c9d1d9', fontsize=10)
    for i, (stroke, path) in enumerate(zip(strokes, raw_paths)):
        color = LAYER_COLORS[stroke.layer]
        xs_val = [p[0] for p in path]
        ys_val = [p[1] for p in path]
        ax_order.plot(xs_val, ys_val, color=color, linewidth=2.2, alpha=0.92, zorder=3, solid_capstyle='round')
        ax_order.scatter(xs_val[0], ys_val[0], s=50, color='#56d364', zorder=5, marker='o')
        ax_order.scatter(xs_val[-1], ys_val[-1], s=50, color='#f78166', zorder=5, marker='x', linewidths=1.5)
        mx, my = xs_val[len(xs_val)//2], ys_val[len(ys_val)//2]
        ax_order.text(mx, my, f'{i+1}', fontsize=8, color='white', ha='center', va='center', fontweight='bold', zorder=6,
                      bbox=dict(boxstyle='circle,pad=0.18', facecolor='#1f2937', edgecolor=color, linewidth=0.8))

    ax_order.invert_yaxis()
    ax_order.set_aspect('equal', adjustable='box')
    ax_order.grid(True, color='#21262d', linewidth=0.4, linestyle=':')

    # Subplot 2: Z-depth
    ax_z.set_title("Z-depth theo nét (Lực nhấn Z)", color='#c9d1d9', fontsize=10)
    cmap_z = matplotlib.colormaps.get_cmap('RdYlGn_r')
    z_norm = mcolors.Normalize(vmin=Z_HEAVY, vmax=Z_LIGHT)
    for stroke, path in zip(strokes, raw_paths):
        xs_val = [p[0] for p in path]
        ys_val = [p[1] for p in path]
        zs_val = [p[2] for p in path]
        for j in range(len(xs_val) - 1):
            z_avg = (zs_val[j] + zs_val[j+1]) / 2
            color_z = cmap_z(z_norm(z_avg))
            ax_z.plot([xs_val[j], xs_val[j+1]], [ys_val[j], ys_val[j+1]], color=color_z, linewidth=3.0, alpha=0.90, solid_capstyle='round')

    sm = plt.cm.ScalarMappable(cmap=cmap_z, norm=z_norm)
    cb = fig.colorbar(sm, ax=ax_z, fraction=0.04, pad=0.02)
    cb.set_label('Z offset (mm)\nĐỏ=nhấn mạnh / Xanh=nhẹ', color='#c9d1d9', fontsize=7)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color='#c9d1d9')
    ax_z.invert_yaxis()
    ax_z.set_aspect('equal', adjustable='box')
    ax_z.grid(True, color='#21262d', linewidth=0.4, linestyle=':')

    # Subplot 3: Trên giấy thực
    ax_paper.set_title(f"Đường đi trên giấy thực A4 ({PAPER_WIDTH_MM}×{PAPER_HEIGHT_MM}mm)", color='#c9d1d9', fontsize=9)
    paper_rect = plt.Rectangle((PAPER_ORIGIN_X, PAPER_ORIGIN_Y), PAPER_WIDTH_MM, PAPER_HEIGHT_MM, fill=False, edgecolor='#30363d', linewidth=1.0, linestyle='--')
    ax_paper.add_patch(paper_rect)
    draw_rect = plt.Rectangle((PAPER_ORIGIN_X + MARGIN_MM, PAPER_ORIGIN_Y + MARGIN_MM), PAPER_WIDTH_MM - 2*MARGIN_MM, PAPER_HEIGHT_MM - 2*MARGIN_MM, fill=True, facecolor='#1c2128', edgecolor='#3d4450', linewidth=0.5)
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
        ax_paper.plot(rxs, rys, color=color, linewidth=2.5, alpha=0.92, solid_capstyle='round', zorder=4)
        ax_paper.scatter(rxs[0], rys[0], s=45, color='#56d364', zorder=6, marker='o')
        ax_paper.scatter(rxs[-1], rys[-1], s=45, color='#f78166', zorder=6, marker='x', linewidths=1.5)

    ax_paper.set_xlabel("Robot X (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_ylabel("Robot Y (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_aspect('equal', adjustable='box')
    ax_paper.grid(True, color='#21262d', linewidth=0.35, linestyle=':')

    # Subplot 4: Bảng nét
    ax_detail.set_title("Chi tiết từng nét bút", color='#c9d1d9', fontsize=10)
    ax_detail.axis('off')
    headers = ['#', 'Lớp nét', 'Loại nét', 'Điểm', 'Z_start', 'Z_mid', 'Z_end']
    col_w = [0.06, 0.22, 0.24, 0.10, 0.12, 0.12, 0.12]
    x_positions = [0.01]
    for w in col_w[:-1]:
        x_positions.append(x_positions[-1] + w)

    for j, (h, xp) in enumerate(zip(headers, x_positions)):
        ax_detail.text(xp, 0.97, h, transform=ax_detail.transAxes, color='#58a6ff', fontsize=7.5, fontweight='bold', va='top')

    ax_detail.plot([0.01, 0.99], [0.94, 0.94], transform=ax_detail.transAxes, color='#30363d', linewidth=0.7)
    row_h = min(0.85 / max(len(strokes) + 1, 1), 0.065)
    y_pos = 0.94
    for i, s in enumerate(strokes):
        y_pos -= row_h
        row = [str(i+1), s.layer.value, s.stroke_type.value, str(len(raw_paths[i])), f'{s.z_profile.z_start:.2f}', f'{s.z_profile.z_mid:.2f}', f'{s.z_profile.z_end:.2f}']
        for j, (cell, xp) in enumerate(zip(row, x_positions)):
            ax_detail.text(xp, y_pos, cell, transform=ax_detail.transAxes, color=LAYER_COLORS[s.layer] if j <= 2 else '#c9d1d9', fontsize=7, va='top')
        if i % 2 == 0:
            rect = mpatches.FancyBboxPatch((0.01, y_pos - row_h * 0.85), 0.98, row_h, boxstyle='square,pad=0', linewidth=0, facecolor='#21262d', alpha=0.4, transform=ax_detail.transAxes)
            ax_detail.add_patch(rect)

    png_path = OUTPUT_DIR / f"{clean_text}_trajectory_preview.png"
    fig.savefig(png_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"▶  Preview PNG: {png_path}")

    # Bước 5: Xuất SVG
    svg_path = OUTPUT_DIR / f"{clean_text}_trajectory_preview.svg"
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAPER_WIDTH_MM} {PAPER_HEIGHT_MM}" width="{PAPER_WIDTH_MM}mm" height="{PAPER_HEIGHT_MM}mm" style="background:#0d1117">',
        f'  <!-- Khung giấy A4 -->',
        f'  <rect x="20" y="20" width="170" height="257" fill="#161b22" stroke="#30363d" stroke-width="0.8" rx="2" ry="2"/>'
    ]
    for i, path in enumerate(robot_paths_mm):
        stroke = strokes[i]
        color = LAYER_COLORS[stroke.layer]
        points = []
        for pt in path:
            rx = pt["x_mm"]
            ry = pt["y_mm"]
            z_offset = pt["gz_offset"]
            x_svg = rx - PAPER_ORIGIN_X
            y_svg = (PAPER_ORIGIN_Y + PAPER_HEIGHT_MM) - ry
            
            if z_offset > -0.5:
                w = 0.5
            elif z_offset < -3.0:
                w = 4.5
            else:
                frac = (z_offset - (-0.5)) / (-3.0 - (-0.5))
                w = 0.8 + frac * 3.7
            points.append((x_svg, y_svg, w))

        svg_lines.append(f'  <!-- Stroke {i+1} -->')
        svg_lines.append(f'  <g stroke="{color}" stroke-linecap="round" fill="none">')
        for j in range(len(points) - 1):
            x1, y1, w1 = points[j]
            x2, y2, w2 = points[j+1]
            w_avg = (w1 + w2) / 2.0
            svg_lines.append(f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke-width="{w_avg:.2f}"/>')
        svg_lines.append(f'  </g>')
    svg_lines.append('</svg>')
    svg_path.write_text('\n'.join(svg_lines), encoding='utf-8')
    print(f"▶  Preview SVG: {svg_path}")

    # Báo cáo thống kê
    all_z_offset = [pt["gz_offset"] for path in robot_paths_mm for pt in path]
    all_z_abs    = [pt["z_mm"]     for path in robot_paths_mm for pt in path]
    all_rx       = [pt["x_mm"]     for path in robot_paths_mm for pt in path]
    all_ry       = [pt["y_mm"]     for path in robot_paths_mm for pt in path]
    print("─" * 60)
    print(f"📊 BÁO CÁO ĐƯỜNG ĐI ROBOT — Chữ: \"{text}\"")
    print("─" * 60)
    print(f"   Tổng nét:     {len(strokes)} nét")
    print(f"   Tổng điểm:    {sum(len(p) for p in robot_paths_mm)} điểm")
    print(f"   📍 Tọa độ Robot (mm):")
    print(f"   ├─ X: [{min(all_rx):.2f}, {max(all_rx):.2f}]")
    print(f"   ├─ Y: [{min(all_ry):.2f}, {max(all_ry):.2f}]")
    print(f"   ├─ Z absolute:  [{min(all_z_abs):.3f}, {max(all_z_abs):.3f}]  (paper_z = {PAPER_Z})")
    print(f"   └─ Z offset:    [{min(all_z_offset):.3f}, {max(all_z_offset):.3f}]")
    print()
    print("✅  HOÀN THÀNH! Đường đi thực tế cho chữ đã được tạo thành công.")
    print(f"    Thư mục đầu ra: {OUTPUT_DIR}")
    print("─" * 60)


if __name__ == "__main__":
    main()
