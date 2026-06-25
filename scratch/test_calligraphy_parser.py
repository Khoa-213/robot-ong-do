"""
scratch/test_calligraphy_parser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Script kiểm thử CalligraphyParser — Dry-run không cần kết nối robot.

Chức năng:
  1. Phân rã các từ thư pháp tiếng Việt
  2. Xuất thứ tự nét (BASE → DIACRITIC → TONE_MARK)
  3. Kiểm tra Z-profile của từng loại nét
  4. Render preview đường đi 2D (matplotlib)
  5. Xuất robot paths và kiểm tra an toàn

Chạy:
  python scratch/test_calligraphy_parser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import sys
import os

# Fix encoding cho Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Thêm project root vào PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from modules.calligraphy_parser import (
    parse_vietnamese_text,
    calligraphy_strokes_to_robot_paths,
    describe_character,
    list_supported_characters,
    StrokeLayer,
    StrokeType,
)


# ── Màu sắc theo layer ──────────────────────────────────────────────────────

LAYER_COLORS = {
    StrokeLayer.BASE:      '#1a73e8',   # xanh dương — thân chữ
    StrokeLayer.DIACRITIC: '#e67700',   # cam — dấu phụ chữ
    StrokeLayer.TONE_MARK: '#c5221f',   # đỏ — dấu thanh
}

TYPE_MARKERS = {
    StrokeType.DOT:        'o',
    StrokeType.HORIZONTAL: 's',
    StrokeType.VERTICAL:   '^',
    StrokeType.LEFT_FALL:  'v',
    StrokeType.RISING:     '>',
    StrokeType.TURNING:    'D',
    StrokeType.HOOK:       'P',
    StrokeType.CURVE:      '*',
}


# ── Test cases ───────────────────────────────────────────────────────────────

TEST_WORDS = [
    "Nhẫn",       # chữ đặc trưng dự án
    "Nhã",        # có dấu ngã
    "na",         # không dấu
    "Nhãna",      # hai âm tiết có dấu
    "thư pháp",   # cụm từ tiếng Việt đầy đủ
    "ABCĐ",       # chữ hoa có đặc biệt Đ
    "ắ ồ ợ ừ ỹ",  # các tổ hợp phức tạp
    "12345678",   # 8 nét thư pháp mới dựng
]

Z_LIGHT = -0.5
Z_HEAVY = -3.0
FONT_SCALE = 220.0
OUTPUT_DIR = Path(PROJECT_ROOT) / "output" / "calligraphy_v2_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_character_decomposition() -> None:
    """Test 1: Phân rã từng ký tự và in thông tin chi tiết."""
    print("\n" + "═" * 60)
    print("TEST 1: Phân rã ký tự đơn")
    print("═" * 60)

    test_chars = ['N', 'h', 'ẫ', 'n', 'a', 'đ', 'Đ', 'ơ', 'ư', 'ắ', 'ồ']
    for char in test_chars:
        print()
        print(describe_character(char))


def test_word_parsing() -> None:
    """Test 2: Phân rã từ/cụm từ và kiểm tra thứ tự nét."""
    print("\n" + "═" * 60)
    print("TEST 2: Phân rã từ và kiểm tra thứ tự")
    print("═" * 60)

    for word in TEST_WORDS:
        strokes = parse_vietnamese_text(word)
        print(f"\nTừ: '{word}'  → {len(strokes)} nét")

        for i, s in enumerate(strokes):
            print(f"  [{i+1:2d}] {s.layer.value:10s}  {s.stroke_type.value:12s}  "
                  f"Z({s.z_profile.z_start:.2f}→{s.z_profile.z_mid:.2f}→{s.z_profile.z_end:.2f})")

        # Kiểm tra thứ tự: trong mỗi ký tự, BASE → DIACRITIC → TONE_MARK
        # Nhóm nét theo vị trí x (glyph_width + gap = 1.35 units)
        char_groups: list[list] = []
        if strokes:
            current_group = [strokes[0]]
            group_x = strokes[0].points[0][0]
            for s in strokes[1:]:
                # Nếu nét mới cách xa hơn 1 glyph-width, tạo nhóm mới
                stroke_x = s.points[0][0]
                if stroke_x - group_x > 1.2:
                    char_groups.append(current_group)
                    current_group = [s]
                    group_x = stroke_x
                else:
                    current_group.append(s)
            char_groups.append(current_group)

        all_ok = True
        for g in char_groups:
            layers_in_group = [s.layer for s in g]
            # Kiểm tra không có BASE sau TONE_MARK trong cùng nhóm
            tone_idx = next((i for i, l in enumerate(layers_in_group) if l == StrokeLayer.TONE_MARK), None)
            if tone_idx is not None:
                has_base_after_tone = any(
                    l == StrokeLayer.BASE for l in layers_in_group[tone_idx + 1:]
                )
                if has_base_after_tone:
                    all_ok = False
                    break

        status = "✓ ĐÚNG THỨ TỰ (per-char)" if all_ok else "✗ SAI THỨ TỰ trong một ký tự!"


        print(f"  Thứ tự thư pháp: {status}")


def test_robot_paths() -> None:
    """Test 3: Xuất robot paths và kiểm tra Z-depth an toàn."""
    print("\n" + "═" * 60)
    print("TEST 3: Robot paths + Z-depth safety check")
    print("═" * 60)

    for word in ["Nhẫn", "thư pháp"]:
        strokes = parse_vietnamese_text(word)
        paths = calligraphy_strokes_to_robot_paths(
            strokes, z_light=Z_LIGHT, z_heavy=Z_HEAVY, font_scale=FONT_SCALE
        )

        all_z = [z for path in paths for _x, _y, z in path]
        all_ok = all(Z_HEAVY <= z <= Z_LIGHT for z in all_z)

        print(f"\nTừ '{word}': {len(paths)} paths, {sum(len(p) for p in paths)} điểm")
        print(f"  Z range: [{min(all_z):.3f}, {max(all_z):.3f}]  "
              f"(cho phép [{Z_HEAVY}, {Z_LIGHT}])")
        print(f"  Z safety: {'✓ AN TOÀN' if all_ok else '✗ NGOÀI GIỚI HẠN!'}")

        # Xuất JSON mẫu
        output = {
            "text": word,
            "stroke_count": len(paths),
            "point_count": sum(len(p) for p in paths),
            "z_range": {"min": round(min(all_z), 3), "max": round(max(all_z), 3)},
            "paths": [
                {
                    "stroke_index": i + 1,
                    "points": [{"x": x, "y": y, "z": z} for x, y, z in path],
                }
                for i, path in enumerate(paths)
            ],
        }
        out_file = OUTPUT_DIR / f"robot_paths_{word.replace(' ', '_')}.json"
        out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  → Xuất JSON: {out_file.name}")


def test_preview_render() -> None:
    """Test 4: Render ảnh preview đường đi với màu theo layer/type."""
    print("\n" + "═" * 60)
    print("TEST 4: Render preview ảnh")
    print("═" * 60)

    for word in ["Nhẫn", "thư pháp", "Nhãna"]:
        strokes = parse_vietnamese_text(word)
        _render_preview(word, strokes)


def _render_preview(word: str, strokes: list) -> None:
    """Vẽ preview 2D tô màu theo StrokeLayer và đánh số thứ tự."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor('#0f1117')

    for ax in axes:
        ax.set_facecolor('#1a1d27')
        ax.tick_params(colors='#aaaaaa')
        ax.spines[:].set_color('#333344')

    # Subplot 1: Tô màu theo StrokeLayer
    ax1 = axes[0]
    ax1.set_title(f"'{word}' — Thứ tự nét theo Layer", color='white', fontsize=12, pad=10)

    for i, s in enumerate(strokes):
        color = LAYER_COLORS[s.layer]
        xs = [p[0] for p in s.points]
        ys = [p[1] for p in s.points]
        ax1.plot(xs, ys, color=color, linewidth=2.0, alpha=0.9, zorder=3)
        ax1.scatter([xs[0]], [ys[0]], s=60, color='lime', zorder=5, marker='o')
        ax1.scatter([xs[-1]], [ys[-1]], s=60, color='#ff4444', zorder=5, marker='x')
        # Số thứ tự
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        ax1.text(mx, my + 0.04, str(i + 1), fontsize=7, color='white',
                 ha='center', va='bottom', fontweight='bold', zorder=6)

    # Legend layer
    patches = [
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.BASE],      label='BASE (thân chữ)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.DIACRITIC], label='DIACRITIC (dấu phụ)'),
        mpatches.Patch(color=LAYER_COLORS[StrokeLayer.TONE_MARK], label='TONE MARK (dấu thanh)'),
    ]
    ax1.legend(handles=patches, loc='lower right', fontsize=9,
               facecolor='#1a1d27', labelcolor='white', edgecolor='#444')
    ax1.set_xlabel("X (glyph units)", color='#aaaaaa')
    ax1.set_ylabel("Y (glyph units)", color='#aaaaaa')
    ax1.set_aspect('equal', adjustable='box')
    ax1.grid(True, color='#333344', linewidth=0.4)
    ax1.invert_yaxis()   # Y tăng xuống để khớp với cách nhìn thông thường

    # Subplot 2: Màu theo StrokeType
    ax2 = axes[1]
    ax2.set_title(f"'{word}' — Loại nét (StrokeType)", color='white', fontsize=12, pad=10)

    cmap = plt.cm.get_cmap('tab10')
    type_to_idx = {t: i for i, t in enumerate(StrokeType)}

    seen_types: set = set()
    for s in strokes:
        color = cmap(type_to_idx[s.stroke_type] / len(StrokeType))
        xs = [p[0] for p in s.points]
        ys = [p[1] for p in s.points]
        label = s.stroke_type.value if s.stroke_type not in seen_types else None
        seen_types.add(s.stroke_type)
        ax2.plot(xs, ys, color=color, linewidth=2.2, alpha=0.88, label=label, zorder=3)
        ax2.scatter([xs[0]], [ys[0]], s=50, color='lime', zorder=5)

    ax2.legend(loc='lower right', fontsize=8,
               facecolor='#1a1d27', labelcolor='white', edgecolor='#444')
    ax2.set_xlabel("X (glyph units)", color='#aaaaaa')
    ax2.set_ylabel("Y (glyph units)", color='#aaaaaa')
    ax2.set_aspect('equal', adjustable='box')
    ax2.grid(True, color='#333344', linewidth=0.4)
    ax2.invert_yaxis()

    fig.suptitle(
        f"CalligraphyParser Preview — '{word}'  ({len(strokes)} nét)",
        color='white', fontsize=14, fontweight='bold'
    )
    fig.tight_layout()

    safe_name = word.replace(' ', '_').replace('/', '_')
    out_path = OUTPUT_DIR / f"preview_{safe_name}.png"
    fig.savefig(out_path, dpi=180, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  → Preview: {out_path}")


def test_full_character_support() -> None:
    """Test 5: Kiểm tra toàn bộ bảng ký tự được hỗ trợ."""
    print("\n" + "═" * 60)
    print("TEST 5: Kiểm tra bảng ký tự đầy đủ")
    print("═" * 60)

    info = list_supported_characters()
    print(f"Chữ thường: {len(info['lowercase_base'])}  — {' '.join(info['lowercase_base'])}")
    print(f"Chữ hoa:    {len(info['uppercase_base'])}  — {' '.join(info['uppercase_base'])}")
    print(f"Dấu phụ:    {len(info['diacritic_marks'])} — {' '.join(info['diacritic_marks'])}")
    print(f"Dấu thanh:  {len(info['tone_marks'])}  — {' '.join(info['tone_marks'])}")
    print(f"Ký tự VN mẫu: {len(info['sample_vietnamese'])}")

    # Kiểm tra từng ký tự mẫu có parse được không
    failed = []
    for char in info['sample_vietnamese']:
        try:
            strokes = parse_vietnamese_text(char)
            if not strokes:
                failed.append(char)
        except Exception as e:
            failed.append(f"{char}({e})")

    if failed:
        print(f"✗ Không xử lý được: {', '.join(failed)}")
    else:
        print(f"✓ Tất cả {len(info['sample_vietnamese'])} ký tự mẫu parse thành công!")


def main() -> None:
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║    Calligraphy Trajectory Parser — Test Suite               ║")
    print("║    Robot Ông Đồ — Hệ thống phân rã thư pháp tiếng Việt     ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    test_character_decomposition()
    test_word_parsing()
    test_robot_paths()
    test_preview_render()
    test_full_character_support()

    print("\n" + "═" * 60)
    print("✓ Hoàn thành tất cả tests!")
    print(f"Output: {OUTPUT_DIR}")
    print("═" * 60)


if __name__ == "__main__":
    main()
