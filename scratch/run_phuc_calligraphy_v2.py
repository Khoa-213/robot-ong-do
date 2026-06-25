"""
scratch/run_phuc_calligraphy_v2.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sinh đường đi thực tế cho robot viết chữ "phúc" — calligraphy_v2 mode.

Output:
  - Preview ảnh SVG + PNG (đường nét + số thứ tự + Z-depth heatmap)
  - JSON robot_paths (tọa độ thực mm của robot Fairino)
  - Báo cáo nét (stroke report)

Chạy:
  python scratch/run_phuc_calligraphy_v2.py
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
from matplotlib.collections import LineCollection
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

# ── Cấu hình ─────────────────────────────────────────────────────────────────

TEXT         = "phúc"          # chữ cần viết
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
U_MIN, U_MAX = 0.15, 0.85
V_MIN, V_MAX = 0.30, 0.70

# Output
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = Path(PROJECT_ROOT) / "output" / f"phuc_calligraphy_v2_{TIMESTAMP}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Layer colors ──────────────────────────────────────────────────────────────

LAYER_COLORS = {
    StrokeLayer.BASE:      '#4fc3f7',
    StrokeLayer.DIACRITIC: '#ffb74d',
    StrokeLayer.TONE_MARK: '#ef5350',
}


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1: Phân rã "phúc" thành CalligraphyStroke
# ════════════════════════════════════════════════════════════════════════════

def step1_parse():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Calligraphy V2 — Sinh đường đi robot viết chữ \"phúc\"       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    print(f"▶  Văn bản đầu vào: \"{TEXT}\"")
    print()

    # Phân rã từng ký tự
    for ch in TEXT:
        print(describe_character(ch))
        print()

    strokes = parse_vietnamese_text(TEXT, glyph_gap=-0.23)

    print("─" * 60)
    print(f"📋 Tổng cộng: {len(strokes)} nét")
    print()
    for i, s in enumerate(strokes, 1):
        pts_str = f"({s.points[0][0]:.2f},{s.points[0][1]:.2f})→({s.points[-1][0]:.2f},{s.points[-1][1]:.2f})"
        print(f"  Nét {i:2d}: [{s.layer.value:10s}] {s.stroke_type.value:12s}  "
              f"{len(s.points)} điểm  Z({s.z_profile.z_start:.2f}→{s.z_profile.z_mid:.2f}→{s.z_profile.z_end:.2f})  {pts_str}")
    print()
    return strokes


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2: Sinh robot paths (tọa độ mm thực)
# ════════════════════════════════════════════════════════════════════════════

def step2_robot_paths(strokes):
    """
    Chuyển CalligraphyStroke → tọa độ robot thực (mm).
    
    Ánh xạ:
      glyph (x,y) → UV [0,1]² → paper pixel (mm) → robot XYZ
    """
    # Lấy 3D paths trong glyph space
    raw_paths = calligraphy_strokes_to_robot_paths(
        strokes, z_light=Z_LIGHT, z_heavy=Z_HEAVY, font_scale=FONT_SCALE
    )

    # Bounding box trong glyph space
    all_xy = [(x, y) for path in raw_paths for x, y, _ in path]
    xs = [p[0] for p in all_xy]
    ys = [p[1] for p in all_xy]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    glyph_w = max(max_x - min_x, 1e-6)
    glyph_h = max(max_y - min_y, 1e-6)

    print(f"▶  Glyph space: x=[{min_x:.1f}, {max_x:.1f}]  y=[{min_y:.1f}, {max_y:.1f}]  ({glyph_w:.1f}×{glyph_h:.1f} px)")

    # Normalize xy → UV (với invert_y=True vì robot coordinate system)
    u_span = U_MAX - U_MIN
    v_span = V_MAX - V_MIN
    drawable_w = u_span * PAPER_WIDTH_MM
    drawable_h = v_span * PAPER_HEIGHT_MM
    scale_mm = min(drawable_w / glyph_w, drawable_h / glyph_h)

    scale_x = scale_mm / PAPER_WIDTH_MM    # glyph px → U
    scale_y = scale_mm / PAPER_HEIGHT_MM   # glyph px → V
    fitted_w_u = glyph_w * scale_x
    fitted_h_v = glyph_h * scale_y

    # Căn giữa trong vùng vẽ
    u_offset = U_MIN + (u_span - fitted_w_u) / 2.0
    v_offset = V_MIN + (v_span - fitted_h_v) / 2.0

    print(f"▶  Scale: {scale_mm:.4f} mm/px  → Text chiếm {fitted_w_u*PAPER_WIDTH_MM:.1f}mm × {fitted_h_v*PAPER_HEIGHT_MM:.1f}mm trên giấy")
    print(f"▶  UV offset: ({u_offset:.3f}, {v_offset:.3f})")
    print()

    # Chuyển sang tọa độ robot mm
    drawable_x0 = PAPER_ORIGIN_X + MARGIN_MM
    drawable_y0 = PAPER_ORIGIN_Y + MARGIN_MM
    drawable_width  = PAPER_WIDTH_MM  - 2 * MARGIN_MM
    drawable_height = PAPER_HEIGHT_MM - 2 * MARGIN_MM

    robot_paths_mm = []
    for path in raw_paths:
        path_mm = []
        for gx, gy, gz_offset in path:
            # Glyph → UV
            u = u_offset + (gx - min_x) * scale_x
            v = v_offset + (max_y - gy) * scale_y    # invert_y=True

            # UV → robot mm
            rx = PAPER_ORIGIN_X + u * PAPER_WIDTH_MM
            ry = PAPER_ORIGIN_Y + (1.0 - v) * PAPER_HEIGHT_MM
            rz = PAPER_Z + gz_offset   # Z offset từ paper surface

            path_mm.append({
                "x_mm": round(rx, 3),
                "y_mm": round(ry, 3),
                "z_mm": round(rz, 3),
                "gz_offset": round(gz_offset, 4),
                "u":    round(u, 4),
                "v":    round(v, 4),
            })
        robot_paths_mm.append(path_mm)

    # Thống kê
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
        "text": TEXT,
        "mode": "calligraphy_v2",
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
        "stroke_metadata": [
            {
                "stroke_index": i + 1,
                "layer": s.layer.value,
                "stroke_type": s.stroke_type.value,
                "z_profile": {
                    "z_start": s.z_profile.z_start,
                    "z_mid":   s.z_profile.z_mid,
                    "z_end":   s.z_profile.z_end,
                },
                "point_count": len(robot_paths_mm[i]),
            }
            for i, s in enumerate(strokes)
            if i < len(robot_paths_mm)
        ],
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

    json_path = OUTPUT_DIR / "phuc_robot_paths.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"▶  JSON robot paths: {json_path}")
    return report


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 4: Render Preview
# ════════════════════════════════════════════════════════════════════════════

def step4_render(strokes, raw_paths, bbox, scale_x, scale_y, u_offset, v_offset):
    min_x, max_x, min_y, max_y = bbox

    fig = plt.figure(figsize=(20, 13), facecolor='#0d1117')

    # Layout: 3 subplots
    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.32,
                          left=0.04, right=0.97, top=0.91, bottom=0.05)
    ax_order   = fig.add_subplot(gs[0, :2])  # Thứ tự nét (rộng)
    ax_z       = fig.add_subplot(gs[0, 2])   # Z-depth heatmap
    ax_paper   = fig.add_subplot(gs[1, :2])  # Trên giấy thực (mm)
    ax_detail  = fig.add_subplot(gs[1, 2])   # Chi tiết từng nét

    for ax in [ax_order, ax_z, ax_paper, ax_detail]:
        ax.set_facecolor('#161b22')
        ax.tick_params(colors='#8b949e', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

    fig.suptitle(
        f'Robot Trajectory — Calligraphy V2 — Chữ "{TEXT}"',
        color='white', fontsize=15, fontweight='bold', y=0.96
    )

    # ─── Subplot 1: Thứ tự nét theo Layer ───────────────────────────────────
    ax_order.set_title("Thứ tự nét (BASE→DIACRITIC→TONE)  |  số = thứ tự viết",
                       color='#c9d1d9', fontsize=10)

    for i, (stroke, path) in enumerate(zip(strokes, raw_paths)):
        color = LAYER_COLORS[stroke.layer]
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        # Nét chính
        ax_order.plot(xs, ys, color=color, linewidth=2.2, alpha=0.92, zorder=3,
                      solid_capstyle='round')
        # Điểm đầu (xanh lá)
        ax_order.scatter(xs[0], ys[0], s=50, color='#56d364', zorder=5, marker='o')
        # Điểm cuối (đỏ cam)
        ax_order.scatter(xs[-1], ys[-1], s=50, color='#f78166', zorder=5, marker='x', linewidths=1.5)
        # Số thứ tự
        mx = xs[len(xs)//2]
        my = ys[len(ys)//2]
        ax_order.text(mx, my, f'{i+1}',
                      fontsize=8, color='white', ha='center', va='center',
                      fontweight='bold', zorder=6,
                      bbox=dict(boxstyle='circle,pad=0.18', facecolor='#1f2937', edgecolor=color, linewidth=0.8))

    # Thêm nhãn chữ cái
    char_cursor = 0.0
    for ch in TEXT:
        if not ch.isspace():
            ax_order.axvline(x=char_cursor * FONT_SCALE, color='#30363d',
                             linewidth=0.6, linestyle='--', zorder=1)
            ax_order.text(char_cursor * FONT_SCALE + 0.05 * FONT_SCALE,
                          max_y * FONT_SCALE * 0.05,
                          ch, color='#8b949e', fontsize=9, alpha=0.6)
            char_cursor += GLYPH_WIDTH + GLYPH_GAP

    # Legend
    patches = [
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.BASE],      label=f'BASE ({sum(1 for s in strokes if s.layer==StrokeLayer.BASE)} nét)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.DIACRITIC], label=f'DIACRITIC ({sum(1 for s in strokes if s.layer==StrokeLayer.DIACRITIC)} nét)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.TONE_MARK], label=f'TONE MARK ({sum(1 for s in strokes if s.layer==StrokeLayer.TONE_MARK)} nét)'),
        mpatches.Patch(color='#56d364', label='Điểm bắt đầu nét'),
        mpatches.Patch(color='#f78166', label='Điểm kết thúc nét'),
    ]
    ax_order.legend(handles=patches, loc='upper right', fontsize=8,
                    facecolor='#161b22', labelcolor='#c9d1d9', edgecolor='#30363d',
                    framealpha=0.9)
    ax_order.set_xlabel("X (glyph units × 220)", color='#8b949e', fontsize=8)
    ax_order.set_ylabel("Y", color='#8b949e', fontsize=8)
    ax_order.invert_yaxis()
    ax_order.set_aspect('equal', adjustable='box')
    ax_order.grid(True, color='#21262d', linewidth=0.4, linestyle=':')

    # ─── Subplot 2: Z-depth heatmap ─────────────────────────────────────────
    ax_z.set_title("Z-depth theo nét (lực nhấn)", color='#c9d1d9', fontsize=10)

    cmap_z = matplotlib.colormaps.get_cmap('RdYlGn_r')   # đỏ=nặng, xanh=nhẹ
    z_norm = mcolors.Normalize(vmin=Z_HEAVY, vmax=Z_LIGHT)

    for stroke, path in zip(strokes, raw_paths):
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        zs = [p[2] for p in path]
        # Vẽ từng segment với màu Z
        for j in range(len(xs) - 1):
            z_avg = (zs[j] + zs[j+1]) / 2
            color_z = cmap_z(z_norm(z_avg))
            ax_z.plot([xs[j], xs[j+1]], [ys[j], ys[j+1]],
                      color=color_z, linewidth=3.0, alpha=0.90,
                      solid_capstyle='round')

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap_z, norm=z_norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax_z, fraction=0.04, pad=0.02)
    cb.set_label('Z offset (mm)\nĐỏ=nhấn mạnh / Xanh=nhẹ', color='#c9d1d9', fontsize=7)
    cb.ax.yaxis.set_tick_params(color='#8b949e', labelsize=7)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color='#c9d1d9')

    ax_z.invert_yaxis()
    ax_z.set_aspect('equal', adjustable='box')
    ax_z.grid(True, color='#21262d', linewidth=0.4, linestyle=':')
    ax_z.tick_params(labelsize=7)

    # ─── Subplot 3: Tọa độ trên giấy thực (mm) ──────────────────────────────
    ax_paper.set_title(
        f"Đường đi trên giấy thực — Paper A4 ({PAPER_WIDTH_MM}×{PAPER_HEIGHT_MM}mm)\n"
        f"Robot XY từ paper_origin ({PAPER_ORIGIN_X:.1f}, {PAPER_ORIGIN_Y:.1f})",
        color='#c9d1d9', fontsize=9
    )

    # Vẽ khung giấy A4
    paper_rect = plt.Rectangle(
        (PAPER_ORIGIN_X, PAPER_ORIGIN_Y),
        PAPER_WIDTH_MM, PAPER_HEIGHT_MM,
        fill=False, edgecolor='#30363d', linewidth=1.0, linestyle='--'
    )
    ax_paper.add_patch(paper_rect)

    # Vùng có thể vẽ (drawable area)
    draw_rect = plt.Rectangle(
        (PAPER_ORIGIN_X + MARGIN_MM, PAPER_ORIGIN_Y + MARGIN_MM),
        PAPER_WIDTH_MM - 2*MARGIN_MM, PAPER_HEIGHT_MM - 2*MARGIN_MM,
        fill=True, facecolor='#1c2128', edgecolor='#3d4450', linewidth=0.5
    )
    ax_paper.add_patch(draw_rect)

    # Vẽ đường đi của từng nét
    for i, (stroke, path) in enumerate(zip(strokes, raw_paths)):
        color = LAYER_COLORS[stroke.layer]
        # Chuyển từ glyph space → robot mm
        rxs, rys = [], []
        for gx, gy, _ in path:
            u = u_offset + (gx - min_x) * scale_x
            v = v_offset + (max_y - gy) * scale_y
            rx = PAPER_ORIGIN_X + u * PAPER_WIDTH_MM
            ry = PAPER_ORIGIN_Y + (1.0 - v) * PAPER_HEIGHT_MM
            rxs.append(rx)
            rys.append(ry)

        ax_paper.plot(rxs, rys, color=color, linewidth=2.5, alpha=0.92,
                      solid_capstyle='round', zorder=4)
        ax_paper.scatter(rxs[0], rys[0], s=45, color='#56d364', zorder=6, marker='o')
        ax_paper.scatter(rxs[-1], rys[-1], s=45, color='#f78166', zorder=6, marker='x', linewidths=1.5)

        # Số thứ tự giữa nét
        mx_r = rxs[len(rxs)//2]
        my_r = rys[len(rys)//2]
        ax_paper.text(mx_r, my_r, str(i+1), fontsize=7, color='white',
                      ha='center', va='center', fontweight='bold', zorder=7,
                      bbox=dict(boxstyle='round,pad=0.1', facecolor='#0d1117',
                                edgecolor=color, linewidth=0.6, alpha=0.85))

    ax_paper.set_xlabel("Robot X (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_ylabel("Robot Y (mm)", color='#8b949e', fontsize=8)
    ax_paper.set_aspect('equal', adjustable='box')
    ax_paper.grid(True, color='#21262d', linewidth=0.35, linestyle=':')

    # Anotation origin
    ax_paper.scatter(PAPER_ORIGIN_X, PAPER_ORIGIN_Y, s=80, color='#ff7b72',
                     zorder=8, marker='*')
    ax_paper.annotate('Paper\nOrigin', (PAPER_ORIGIN_X, PAPER_ORIGIN_Y),
                      xytext=(PAPER_ORIGIN_X + 5, PAPER_ORIGIN_Y - 15),
                      color='#ff7b72', fontsize=7,
                      arrowprops=dict(arrowstyle='->', color='#ff7b72', lw=0.7))

    # ─── Subplot 4: Bảng nét chi tiết ────────────────────────────────────────
    ax_detail.set_title("Chi tiết từng nét", color='#c9d1d9', fontsize=10)
    ax_detail.axis('off')

    headers = ['#', 'Layer', 'Loại nét', 'Điểm', 'Z_start', 'Z_mid', 'Z_end']
    col_w = [0.06, 0.22, 0.24, 0.10, 0.12, 0.12, 0.12]
    rows = []
    for i, s in enumerate(strokes):
        rows.append([
            str(i+1),
            s.layer.value.replace('_', ' '),
            s.stroke_type.value.replace('_', ' '),
            str(len(raw_paths[i]) if i < len(raw_paths) else '–'),
            f'{s.z_profile.z_start:.2f}',
            f'{s.z_profile.z_mid:.2f}',
            f'{s.z_profile.z_end:.2f}',
        ])

    # Vẽ header
    y_pos = 0.97
    row_h = min(0.85 / max(len(rows) + 1, 1), 0.065)
    header_colors = ['#1f6feb', '#1f6feb', '#1f6feb', '#1f6feb', '#1f6feb', '#1f6feb', '#1f6feb']

    x_positions = [0.01]
    for w in col_w[:-1]:
        x_positions.append(x_positions[-1] + w)

    for j, (h, xp) in enumerate(zip(headers, x_positions)):
        ax_detail.text(xp, y_pos, h, transform=ax_detail.transAxes,
                       color='#58a6ff', fontsize=7.5, fontweight='bold',
                       va='top', ha='left')

    ax_detail.plot([0.01, 0.99], [y_pos - row_h * 0.1, y_pos - row_h * 0.1],
                   transform=ax_detail.transAxes, color='#30363d', linewidth=0.7)

    for row_i, row in enumerate(rows):
        y_pos -= row_h
        # Màu nền theo layer
        layer_name = strokes[row_i].layer
        row_bg = LAYER_COLORS[layer_name] + '18'  # alpha hex

        # Màu chữ theo layer
        text_color = LAYER_COLORS[layer_name]

        for j, (cell, xp) in enumerate(zip(row, x_positions)):
            ax_detail.text(xp, y_pos, cell, transform=ax_detail.transAxes,
                           color=text_color if j <= 2 else '#c9d1d9',
                           fontsize=7, va='top', ha='left')

        if row_i % 2 == 0:
            rect = mpatches.FancyBboxPatch(
                (0.01, y_pos - row_h * 0.85), 0.98, row_h,
                boxstyle='square,pad=0', linewidth=0,
                facecolor='#21262d', alpha=0.4,
                transform=ax_detail.transAxes, clip_on=True
            )
            ax_detail.add_patch(rect)

    # Footer note
    ax_detail.text(0.5, 0.01,
                   'Z_start/mid/end là fraction [0,1] của [z_light,z_heavy]',
                   transform=ax_detail.transAxes,
                   color='#6e7681', fontsize=6.5, ha='center', va='bottom')

    # ── Lưu ảnh ──────────────────────────────────────────────────────────────
    out_path = OUTPUT_DIR / "phuc_trajectory_preview.png"
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

    base_n      = sum(1 for s in strokes if s.layer == StrokeLayer.BASE)
    diacritic_n = sum(1 for s in strokes if s.layer == StrokeLayer.DIACRITIC)
    tone_n      = sum(1 for s in strokes if s.layer == StrokeLayer.TONE_MARK)

    print("─" * 60)
    print(f"📊 BÁO CÁO ĐƯỜNG ĐI ROBOT — Chữ \"{TEXT}\"")
    print("─" * 60)
    print(f"   Tổng nét:     {len(strokes)} nét")
    print(f"   ├─ BASE:      {base_n} nét (thân chữ)")
    print(f"   ├─ DIACRITIC: {diacritic_n} nét (dấu phụ)")
    print(f"   └─ TONE:      {tone_n} nét (dấu thanh)")
    print()
    print(f"   Tổng điểm:    {sum(len(p) for p in robot_paths_mm)} điểm")
    print()
    print("   📍 Tọa độ Robot (mm):")
    print(f"   ├─ X: [{min(all_rx):.2f}, {max(all_rx):.2f}]")
    print(f"   ├─ Y: [{min(all_ry):.2f}, {max(all_ry):.2f}]")
    print(f"   ├─ Z absolute:  [{min(all_z_abs):.3f}, {max(all_z_abs):.3f}]  (paper_z = {PAPER_Z})")
    print(f"   └─ Z offset:    [{min(all_z_offset):.3f}, {max(all_z_offset):.3f}]  (từ bề mặt giấy)")
    print()

    z_safe = all(Z_HEAVY <= zoff <= Z_LIGHT for zoff in all_z_offset)
    print(f"   🛡️  An toàn Z: {'✅ TẤT CẢ ĐỂM TRONG GIỚI HẠN' if z_safe else '⚠️  CÓ ĐIỂM NGOÀI GIỚI HẠN!'}")
    print()
    print(f"   📁 Output: {OUTPUT_DIR}")
    print("─" * 60)


def step6_export_svg(strokes, robot_paths_mm):
    out_path = OUTPUT_DIR / "phuc_trajectory_preview.svg"
    width, height = 210.0, 297.0
    
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}mm" height="{height}mm" style="background:#0d1117">',
        f'  <!-- Khung giấy A4 và lề -->',
        f'  <rect x="20" y="20" width="170" height="257" fill="#161b22" stroke="#30363d" stroke-width="0.8" rx="2" ry="2"/>'
    ]
    
    for i, path in enumerate(robot_paths_mm):
        stroke = strokes[i] if i < len(strokes) else None
        color = LAYER_COLORS[stroke.layer] if stroke else '#4fc3f7'
        
        points = []
        for pt in path:
            rx = pt["x_mm"]
            ry = pt["y_mm"]
            z_offset = pt["gz_offset"]
            
            x_svg = rx - PAPER_ORIGIN_X
            y_svg = (PAPER_ORIGIN_Y + PAPER_HEIGHT_MM) - ry
            
            # Mapping Z offset to line thickness
            if z_offset > -0.5:
                w = 0.5
            elif z_offset < -3.0:
                w = 4.5
            else:
                frac = (z_offset - (-0.5)) / (-3.0 - (-0.5))
                w = 0.8 + frac * 3.7
                
            points.append((x_svg, y_svg, w))
            
        svg_lines.append(f'  <!-- Stroke {i+1}: {stroke.stroke_type.value if stroke else "unknown"} -->')
        svg_lines.append(f'  <g stroke="{color}" stroke-linecap="round" fill="none">')
        for j in range(len(points) - 1):
            x1, y1, w1 = points[j]
            x2, y2, w2 = points[j+1]
            w_avg = (w1 + w2) / 2.0
            svg_lines.append(f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke-width="{w_avg:.2f}"/>')
        svg_lines.append(f'  </g>')
        
    svg_lines.append('</svg>')
    
    out_path.write_text('\n'.join(svg_lines), encoding='utf-8')
    print(f"▶  Preview SVG: {out_path}")
    return out_path


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    strokes = step1_parse()
    raw_paths, robot_paths_mm, bbox, scale_x, scale_y, u_offset, v_offset = step2_robot_paths(strokes)
    step3_export_json(strokes, robot_paths_mm)
    step4_render(strokes, raw_paths, bbox, scale_x, scale_y, u_offset, v_offset)
    step5_report(strokes, robot_paths_mm)
    step6_export_svg(strokes, robot_paths_mm)

    print()
    print("✅  HOÀN THÀNH! Đường đi thực tế cho robot viết chữ \"phúc\" đã được tạo.")
    print(f"    Xem ảnh preview tại: {OUTPUT_DIR / 'phuc_trajectory_preview.png'}")
    print(f"    Xem file vector SVG tại: {OUTPUT_DIR / 'phuc_trajectory_preview.svg'}")


if __name__ == "__main__":
    main()
