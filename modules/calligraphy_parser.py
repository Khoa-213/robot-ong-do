"""
modules/calligraphy_parser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hệ thống Phân rã Quỹ đạo Thư pháp  (Calligraphy Trajectory Parser)
Robot Ông Đồ — Fairino FR3/FR5

Chuyển đổi văn bản tiếng Việt thành danh sách lệnh nét bút thư pháp có thứ
tự và tham số lực nhấn Z, tương thích hoàn toàn với pipeline robot hiện có.

Quy tắc thư pháp tiếng Việt được áp dụng:
  1. BASE strokes  — thân chữ (trái sang phải)
  2. DIACRITIC     — dấu phụ chữ cái (mũ ^, móc ̛, trăng ˘)
  3. TONE_MARK     — dấu thanh (viết sau cùng): sắc, huyền, hỏi, ngã, nặng

8 nét cơ bản được hỗ trợ:
  DOT, HORIZONTAL, VERTICAL, LEFT_FALL, RISING, TURNING, HOOK, CURVE

Bộ ký tự hỗ trợ (106+ ký tự tiếng Việt):
  - 27 chữ thường:  a-z + đ
  - 27 chữ hoa:     A-Z + Đ
  - 3 dấu phụ chữ:  ^ (mũ), ˘ (trăng), ʻ (móc)
  - 5 dấu thanh:    sắc, huyền, hỏi, ngã, nặng
  → NFD decomposition tự động xử lý mọi tổ hợp
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from dataclasses import dataclass, field
from enum import Enum
from math import hypot
import unicodedata


# ════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

GLYPH_WIDTH: float = 1.0    # Chiều rộng chuẩn hóa của mỗi ký tự
GLYPH_GAP:   float = -0.23   # Khoảng cách giữa các ký tự (giảm từ 0.15 → -0.23 để các chữ liên kết cursive)
SPACE_WIDTH: float = 0.65   # Chiều rộng khoảng trắng


# ════════════════════════════════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════════════════════════════════

class StrokeType(Enum):
    """8 loại nét cơ bản trong thư pháp Việt."""
    DOT        = "dot"        # Nét chấm  — nhấn lực tại chỗ, hình giọt nước
    HORIZONTAL = "horizontal" # Nét ngang  — trái sang phải
    VERTICAL   = "vertical"   # Nét sổ    — trên xuống dưới (kim hoặc gọn)
    LEFT_FALL  = "left_fall"  # Nét phẩy  — chéo phải-trên → trái-dưới
    RISING     = "rising"     # Nét hất   — chéo trái-dưới → phải-trên
    TURNING    = "turning"    # Nét gập   — đổi hướng, tăng lực ở góc quay
    HOOK       = "hook"       # Nét móc   — kéo thành móc cong ở cuối
    CURVE      = "curve"      # Nét cong  — đường cong mượt mà


class StrokeLayer(Enum):
    """Thứ tự lớp viết theo quy tắc thư pháp tiếng Việt."""
    BASE       = "base"       # Thân chữ chính
    DIACRITIC  = "diacritic"  # Dấu phụ chữ cái (mũ, trăng, móc)
    TONE_MARK  = "tone_mark"  # Dấu thanh (viết sau cùng)


# ════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ZProfile:
    """
    Biểu đồ lực nhấn Z theo chiều dài nét bút.

    Các giá trị fraction [0.0, 1.0]:
      0.0 = chạm nhẹ nhất (z_light)
      1.0 = nhấn mạnh nhất (z_heavy)

    Nội suy tuyến tính từng đoạn:
      [start → mid] tại t ∈ [0, 0.5]
      [mid → end]   tại t ∈ [0.5, 1.0]
    """
    z_start: float = 0.70   # Lực khởi bút  (phần đầu nét)
    z_mid:   float = 0.50   # Lực hành bút  (giữa nét)
    z_end:   float = 0.10   # Lực thu bút   (cuối nét)


@dataclass
class CalligraphyStroke:
    """Một nét bút thư pháp hoàn chỉnh."""
    stroke_type: StrokeType
    layer:       StrokeLayer
    points:      list[tuple[float, float]]   # Tọa độ chuẩn hóa (x, y)
    z_profile:   ZProfile = field(default_factory=ZProfile)


# ════════════════════════════════════════════════════════════════════════════
# Z-PROFILE PRESETS — Bộ lực nhấn chuẩn cho từng loại nét
# ════════════════════════════════════════════════════════════════════════════

# Nét chấm: nhấn ngay, giữ, nhả nhẹ
Z_DOT        = ZProfile(z_start=1.00, z_mid=1.00, z_end=0.80)
# Nét ngang: nhấn khởi → nhả giữa → nhấn thu
Z_HORIZONTAL = ZProfile(z_start=0.75, z_mid=0.35, z_end=0.60)
# Nét sổ kim: khởi nặng → giảm dần → vuốt nhọn
Z_VERT_KIM   = ZProfile(z_start=0.85, z_mid=0.50, z_end=0.05)
# Nét sổ gọn: lực đều, thu tròn
Z_VERT_GON   = ZProfile(z_start=0.75, z_mid=0.70, z_end=0.55)
# Nét phẩy: khởi vừa → vuốt nhọn về 0
Z_LEFT_FALL  = ZProfile(z_start=0.65, z_mid=0.40, z_end=0.05)
# Nét hất: rất nhẹ, nhanh
Z_RISING     = ZProfile(z_start=0.25, z_mid=0.20, z_end=0.10)
# Nét gập: nhẹ qua vòm → nặng hơn ở góc quay
Z_TURNING    = ZProfile(z_start=0.40, z_mid=0.65, z_end=0.45)
# Nét móc: vừa phải → giảm dần qua móc
Z_HOOK       = ZProfile(z_start=0.55, z_mid=0.45, z_end=0.25)
# Nét cong: lực đều vừa phải suốt
Z_CURVE      = ZProfile(z_start=0.30, z_mid=0.50, z_end=0.30)
# Dấu phụ chữ cái: rất nhẹ
Z_DIACRITIC  = ZProfile(z_start=0.20, z_mid=0.18, z_end=0.08)
# Dấu thanh: nhẹ nhàng
Z_TONE       = ZProfile(z_start=0.22, z_mid=0.18, z_end=0.08)
# Dấu nặng: nhấn mạnh một chấm
Z_DOT_BELOW  = ZProfile(z_start=0.90, z_mid=0.90, z_end=0.70)


# ════════════════════════════════════════════════════════════════════════════
# LOWERCASE GLYPH DEFINITIONS (a-z + đ)
# Tọa độ chuẩn hóa: x ∈ [0, 1], y ∈ [−0.4, 1.1] (Y hướng lên)
# Thân chữ thường (x-height): y ∈ [0, 0.65]
# Nét lên (ascender):          y ∈ [0.65, 1.1]
# Nét xuống (descender):       y ∈ [−0.4, 0]
# ════════════════════════════════════════════════════════════════════════════

_LOWER_GLYPHS: dict[str, list[CalligraphyStroke]] = {

    # ── 1 ── Nét ngang (horizontal)
    '1': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.1, 0.48), (0.2, 0.495), (0.3, 0.508), (0.4, 0.517), (0.5, 0.52), (0.6, 0.517), (0.7, 0.508), (0.8, 0.495), (0.9, 0.48)],
            Z_HORIZONTAL),
    ],

    # ── 2 ── Nét sổ (vertical)
    '2': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.5, 0.9), (0.5, 0.8), (0.5, 0.7), (0.5, 0.6), (0.5, 0.5), (0.5, 0.4), (0.5, 0.3), (0.5, 0.2), (0.5, 0.1)],
            Z_VERT_GON),
    ],

    # ── 3 ── Nét chấm (dot)
    '3': [
        CalligraphyStroke(StrokeType.DOT, StrokeLayer.BASE,
            [(0.35, 0.7), (0.41, 0.66), (0.47, 0.62), (0.53, 0.56), (0.59, 0.48), (0.65, 0.4)],
            Z_DOT),
    ],

    # ── 4 ── Nét phác (left fall)
    '4': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.75, 0.95), (0.685, 0.86), (0.621, 0.77), (0.56, 0.68), (0.502, 0.59), (0.45, 0.5), (0.402, 0.41), (0.36, 0.32), (0.321, 0.23), (0.285, 0.14), (0.25, 0.05)],
            Z_LEFT_FALL),
    ],

    # ── 5 ── Nét cong (curve)
    '5': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.85, 0.78), (0.73, 0.87), (0.6, 0.9), (0.47, 0.87), (0.35, 0.78), (0.28, 0.65), (0.25, 0.5), (0.28, 0.35), (0.35, 0.22), (0.47, 0.13), (0.6, 0.1), (0.73, 0.13), (0.85, 0.22)],
            Z_CURVE),
    ],

    # ── 6 ── Nét vòng (closed oval / curve)
    '6': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.745, 0.448), (0.758, 0.602), (0.732, 0.739), (0.671, 0.841), (0.583, 0.891), (0.483, 0.881), (0.386, 0.813), (0.306, 0.698), (0.255, 0.552), (0.242, 0.398), (0.268, 0.261), (0.329, 0.159), (0.417, 0.109), (0.517, 0.119), (0.614, 0.187), (0.694, 0.302), (0.745, 0.448)],
            Z_CURVE),
    ],

    # ── 7 ── Nét lượn (wavy S-curve)
    '7': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.35, 0.72), (0.45, 0.85), (0.62, 0.88), (0.75, 0.8), (0.76, 0.65), (0.64, 0.52), (0.52, 0.4), (0.48, 0.28), (0.55, 0.16), (0.68, 0.12), (0.78, 0.15)],
            Z_CURVE),
    ],

    # ── 8 ── Nét móc (hook)
    '8': [
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.35, 0.52), (0.4, 0.32), (0.48, 0.18), (0.6, 0.1), (0.56, 0.18), (0.48, 0.32), (0.38, 0.48)],
            Z_HOOK),
    ],

    # ── a ── oval body (CCW) + right tail (sổ kim)
    'a': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.15, 0.35), (0.28, 0.68), (0.62, 0.72), (0.82, 0.45),
             (0.68, 0.18), (0.35, 0.14), (0.18, 0.32), (0.38, 0.58), (0.78, 0.58)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.78, 0.58), (0.86, 0.18)], Z_VERT_KIM),
    ],

    # ── b ── straight vertical stem + rounded bowl
    'b': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.25, 1.05), (0.25, 0.55), (0.25, 0.08)],
            Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.25, 0.08), (0.52, 0.08), (0.74, 0.22), (0.72, 0.46), (0.54, 0.54),
             (0.25, 0.40)],
            Z_CURVE),
    ],

    # ── c ── open arc
    'c': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.82, 0.58), (0.58, 0.78), (0.22, 0.62), (0.12, 0.32),
             (0.34, 0.12), (0.78, 0.22)],
            Z_CURVE),
    ],

    # ── d ── straight vertical stem + oval bowl
    'd': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.75, 1.05), (0.75, 0.55), (0.75, 0.08)],
            Z_VERT_KIM),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.75, 0.12), (0.55, 0.12), (0.34, 0.24), (0.32, 0.48), (0.48, 0.60),
             (0.75, 0.52)],
            Z_CURVE),
    ],

    # ── đ ── d + crossbar
    'đ': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.75, 1.05), (0.75, 0.55), (0.75, 0.08)],
            Z_VERT_KIM),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.75, 0.12), (0.55, 0.12), (0.34, 0.24), (0.32, 0.48), (0.48, 0.60),
             (0.75, 0.52)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.48, 0.74), (0.90, 0.74)], Z_HORIZONTAL),
    ],

    # ── e ── crossbar entry + curved body
    'e': [
        CalligraphyStroke(StrokeType.TURNING, StrokeLayer.BASE,
            [(0.16, 0.38), (0.45, 0.58), (0.78, 0.52), (0.58, 0.30),
             (0.20, 0.34), (0.32, 0.12), (0.78, 0.20)],
            Z_TURNING),
    ],

    # ── f ── curved stem with descender + crossbar
    'f': [
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.62, 1.00), (0.38, 0.85), (0.42, 0.42), (0.34, -0.18),
             (0.10, -0.32), (0.00, -0.08)],
            Z_HOOK),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.08, 0.48), (0.72, 0.48)], Z_HORIZONTAL),
    ],

    # ── g ── bowl + descender tail with loop
    'g': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.78, 0.62), (0.52, 0.76), (0.20, 0.58), (0.16, 0.28),
             (0.42, 0.14), (0.72, 0.28), (0.78, 0.68)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.78, 0.68), (0.62, -0.20), (0.28, -0.38), (0.08, -0.18), (0.32, 0.02)],
            Z_HOOK),
    ],

    # ── h ── looped stem + arch + leg
    'h': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.05, 0.15), (0.22, 0.52), (0.36, 0.85), (0.34, 1.05), (0.28, 0.96),
             (0.30, 0.62), (0.32, 0.22), (0.32, 0.05)],
            Z_VERT_GON),
        CalligraphyStroke(StrokeType.TURNING, StrokeLayer.BASE,
            [(0.32, 0.35), (0.46, 0.58), (0.64, 0.62), (0.74, 0.45), (0.76, 0.18),
             (0.86, 0.15)],
            Z_TURNING),
    ],

    # ── i ── short stem + dot above
    'i': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.42, 0.62), (0.34, 0.20), (0.50, 0.12), (0.68, 0.22)], Z_VERT_KIM),
        CalligraphyStroke(StrokeType.DOT, StrokeLayer.BASE,
            [(0.44, 0.88), (0.48, 0.92)], Z_DOT),
    ],

    # ── j ── curved descender + dot above
    'j': [
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.56, 0.62), (0.40, -0.20), (0.16, -0.36), (0.00, -0.18), (0.24, 0.02)],
            Z_HOOK),
        CalligraphyStroke(StrokeType.DOT, StrokeLayer.BASE,
            [(0.56, 0.88), (0.60, 0.92)], Z_DOT),
    ],

    # ── k ── vertical stem + cursive loop and leg
    'k': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.24, 0.05), (0.24, 0.15), (0.36, 0.85), (0.34, 1.05), (0.28, 0.96),
             (0.30, 0.62), (0.32, 0.22), (0.32, 0.05)],
            Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.32, 0.40), (0.46, 0.60), (0.58, 0.58), (0.54, 0.42), (0.42, 0.38),
             (0.56, 0.22), (0.74, 0.10), (0.84, 0.18)],
            Z_CURVE),
    ],

    # ── l ── tall stem with loop top serif
    'l': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.24, 0.15), (0.36, 0.85), (0.34, 1.05), (0.28, 0.96), (0.30, 0.62),
             (0.32, 0.22), (0.46, 0.10), (0.68, 0.18)],
            Z_CURVE),
    ],

    # ── m ── continuous loops and arches
    'm': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.22, 0.48), (0.16, 0.58), (0.10, 0.52), (0.12, 0.16), (0.14, 0.38),
             (0.24, 0.58), (0.38, 0.62), (0.46, 0.42), (0.48, 0.16), (0.50, 0.38),
             (0.60, 0.58), (0.74, 0.62), (0.82, 0.42), (0.84, 0.16), (0.94, 0.22)],
            Z_CURVE),
    ],

    # ── n ── continuous loop and arch
    'n': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.22, 0.48), (0.16, 0.58), (0.10, 0.52), (0.12, 0.16), (0.14, 0.38),
             (0.26, 0.58), (0.46, 0.62), (0.58, 0.45), (0.60, 0.16), (0.72, 0.22)],
            Z_CURVE),
    ],

    # ── o ── oval closed curve
    'o': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.46, 0.72), (0.18, 0.58), (0.12, 0.30), (0.34, 0.10),
             (0.72, 0.22), (0.82, 0.52), (0.58, 0.72), (0.36, 0.50),
             (0.66, 0.36), (0.94, 0.42)],
            Z_CURVE),
    ],

    # ── p ── descender stem + bowl
    'p': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.20, -0.35), (0.20, 0.62)], Z_VERT_KIM),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.20, 0.62), (0.50, 0.70), (0.82, 0.52), (0.76, 0.20),
             (0.44, 0.12), (0.22, 0.36), (0.42, 0.14), (0.64, 0.12),
             (0.82, 0.20)],
            Z_CURVE),
    ],

    # ── q ── bowl + straight vertical descender
    'q': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.66, 0.52), (0.48, 0.62), (0.30, 0.44), (0.30, 0.26), (0.46, 0.14),
             (0.66, 0.24)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.66, 0.62), (0.66, 0.135), (0.66, -0.35)],
            Z_VERT_KIM),
    ],

    # ── r ── cursive looped r
    'r': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.24, 0.14), (0.36, 0.48), (0.42, 0.60), (0.32, 0.62), (0.26, 0.54),
             (0.34, 0.46), (0.48, 0.52), (0.68, 0.56), (0.72, 0.24), (0.86, 0.16)],
            Z_CURVE),
    ],

    # ── s ── double S-curve
    's': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.78, 0.62), (0.48, 0.78), (0.18, 0.62), (0.34, 0.42),
             (0.72, 0.34), (0.74, 0.12), (0.34, 0.10), (0.12, 0.26)],
            Z_CURVE),
    ],

    # ── t ── looped stem + crossbar
    't': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.44, 0.90), (0.36, 0.24), (0.54, 0.08), (0.78, 0.28)], Z_VERT_KIM),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.18, 0.58), (0.72, 0.58)], Z_HORIZONTAL),
    ],

    # ── u ── arch from top + right leg
    'u': [
        CalligraphyStroke(StrokeType.TURNING, StrokeLayer.BASE,
            [(0.16, 0.62), (0.18, 0.22), (0.42, 0.12), (0.68, 0.56)], Z_TURNING),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.68, 0.56), (0.68, 0.18), (0.88, 0.18)], Z_VERT_KIM),
    ],

    # ── v ── two diagonals
    'v': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.14, 0.62), (0.36, 0.12)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.36, 0.12), (0.72, 0.58), (0.90, 0.46)], Z_RISING),
    ],

    # ── w ── four diagonals
    'w': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.12, 0.62), (0.28, 0.12)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.28, 0.12), (0.48, 0.50)], Z_RISING),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.48, 0.50), (0.66, 0.12)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.66, 0.12), (0.90, 0.60)], Z_RISING),
    ],

    # ── x ── two crossing diagonals
    'x': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.16, 0.62), (0.78, 0.12)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.80, 0.62), (0.18, 0.12)], Z_LEFT_FALL),
    ],

    # ── y ── left fall + descender hook
    'y': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.14, 0.62), (0.34, 0.14)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.34, 0.14), (0.72, 0.58), (0.54, -0.22), (0.18, -0.36),
             (0.02, -0.16), (0.28, 0.02)],
            Z_HOOK),
    ],

    # ── z ── top bar + diagonal + bottom bar
    'z': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.16, 0.62), (0.78, 0.62)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.78, 0.62), (0.22, 0.12)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.22, 0.12), (0.84, 0.12)], Z_HORIZONTAL),
    ],
}


# ════════════════════════════════════════════════════════════════════════════
# UPPERCASE GLYPH DEFINITIONS (A-Z + Đ)
# Full height: y ∈ [0, 1.0]; Y hướng lên
# ════════════════════════════════════════════════════════════════════════════

_UPPER_GLYPHS: dict[str, list[CalligraphyStroke]] = {

    # ── A ── two diagonals + crossbar
    'A': [
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.00, 0.00), (0.50, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.50, 1.00), (1.00, 0.00)], Z_VERT_KIM),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.22, 0.44), (0.78, 0.44)], Z_HORIZONTAL),
    ],

    # ── B ── vertical stem + upper bowl + lower bowl
    'B': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 1.00), (0.55, 1.00), (0.80, 0.80), (0.55, 0.55), (0.00, 0.55)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 0.55), (0.60, 0.55), (0.85, 0.30), (0.60, 0.00), (0.00, 0.00)],
            Z_CURVE),
    ],

    # ── C ── open arc
    'C': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.85, 0.90), (0.55, 1.00), (0.15, 0.85), (0.00, 0.50),
             (0.15, 0.15), (0.55, 0.00), (0.85, 0.10)],
            Z_CURVE),
    ],

    # ── D ── vertical stem + curve
    'D': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 1.00), (0.55, 1.00), (0.90, 0.65), (0.90, 0.35), (0.55, 0.00), (0.00, 0.00)],
            Z_CURVE),
    ],

    # ── Đ ── D + crossbar through stem
    'Đ': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 1.00), (0.55, 1.00), (0.90, 0.65), (0.90, 0.35), (0.55, 0.00), (0.00, 0.00)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(-0.15, 0.55), (0.42, 0.55)], Z_HORIZONTAL),
    ],

    # ── E ── vertical + three horizontals
    'E': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.85, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.50), (0.65, 0.50)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.85, 0.00)], Z_HORIZONTAL),
    ],

    # ── F ── vertical + two horizontals (no bottom bar)
    'F': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.85, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.50), (0.65, 0.50)], Z_HORIZONTAL),
    ],

    # ── G ── C-arc + inward horizontal stop
    'G': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.85, 0.85), (0.60, 1.00), (0.15, 0.80), (0.00, 0.45),
             (0.20, 0.10), (0.65, 0.00), (0.95, 0.25), (0.95, 0.45), (0.55, 0.45)],
            Z_CURVE),
    ],

    # ── H ── two verticals + crossbar
    'H': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(1.00, 0.00), (1.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.50), (1.00, 0.50)], Z_HORIZONTAL),
    ],

    # ── I ── top serif + vertical + bottom serif
    'I': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.20, 1.00), (0.80, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.50, 1.00), (0.50, 0.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.20, 0.00), (0.80, 0.00)], Z_HORIZONTAL),
    ],

    # ── J ── top serif + hook tail
    'J': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.45, 1.00), (0.90, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.BASE,
            [(0.75, 1.00), (0.75, 0.20), (0.55, 0.00), (0.20, 0.05), (0.08, 0.28)],
            Z_HOOK),
    ],

    # ── K ── vertical + two arm diagonals
    'K': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(1.00, 1.00), (0.00, 0.45)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.00, 0.45), (1.00, 0.00)], Z_RISING),
    ],

    # ── L ── vertical + horizontal base
    'L': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.00, 0.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.85, 0.00)], Z_HORIZONTAL),
    ],

    # ── M ── two verticals + V peak
    'M': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.50, 0.45)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.50, 0.45), (1.00, 1.00)], Z_RISING),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(1.00, 1.00), (1.00, 0.00)], Z_VERT_GON),
    ],

    # ── N ── two verticals + diagonal
    'N': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (1.00, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(1.00, 0.00), (1.00, 1.00)], Z_VERT_GON),
    ],

    # ── O ── closed oval
    'O': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.50, 1.00), (0.15, 0.85), (0.00, 0.50), (0.15, 0.15), (0.50, 0.00),
             (0.85, 0.15), (1.00, 0.50), (0.85, 0.85), (0.50, 1.00)],
            Z_CURVE),
    ],

    # ── P ── vertical + upper bowl
    'P': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 1.00), (0.60, 1.00), (0.90, 0.75), (0.60, 0.50), (0.00, 0.50)],
            Z_CURVE),
    ],

    # ── Q ── oval + diagonal tail
    'Q': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.50, 1.00), (0.15, 0.85), (0.00, 0.50), (0.15, 0.15), (0.50, 0.00),
             (0.85, 0.15), (1.00, 0.50), (0.85, 0.85), (0.50, 1.00)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.60, 0.22), (1.00, -0.14)], Z_LEFT_FALL),
    ],

    # ── R ── vertical + upper bowl + diagonal leg
    'R': [
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.00, 0.00), (0.00, 1.00)], Z_VERT_GON),
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.00, 1.00), (0.60, 1.00), (0.90, 0.75), (0.60, 0.50), (0.00, 0.50)],
            Z_CURVE),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.45, 0.50), (1.00, 0.00)], Z_LEFT_FALL),
    ],

    # ── S ── double S-curve
    'S': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.BASE,
            [(0.90, 0.85), (0.60, 1.00), (0.15, 0.85), (0.20, 0.55),
             (0.75, 0.45), (0.90, 0.15), (0.55, 0.00), (0.10, 0.15)],
            Z_CURVE),
    ],

    # ── T ── horizontal bar + vertical stem
    'T': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 1.00), (1.00, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.50, 1.00), (0.50, 0.00)], Z_VERT_KIM),
    ],

    # ── U ── U-arch (turning stroke)
    'U': [
        CalligraphyStroke(StrokeType.TURNING, StrokeLayer.BASE,
            [(0.00, 1.00), (0.00, 0.25), (0.25, 0.00), (0.75, 0.00),
             (1.00, 0.25), (1.00, 1.00)],
            Z_TURNING),
    ],

    # ── V ── two diagonals
    'V': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.50, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.50, 0.00), (1.00, 1.00)], Z_RISING),
    ],

    # ── W ── four diagonals
    'W': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.25, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.25, 0.00), (0.50, 0.55)], Z_RISING),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.50, 0.55), (0.75, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(0.75, 0.00), (1.00, 1.00)], Z_RISING),
    ],

    # ── X ── two crossing diagonals
    'X': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (1.00, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(1.00, 1.00), (0.00, 0.00)], Z_LEFT_FALL),
    ],

    # ── Y ── two upper diagonals + vertical stem
    'Y': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(0.00, 1.00), (0.50, 0.50)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.BASE,
            [(1.00, 1.00), (0.50, 0.50)], Z_RISING),
        CalligraphyStroke(StrokeType.VERTICAL, StrokeLayer.BASE,
            [(0.50, 0.50), (0.50, 0.00)], Z_VERT_KIM),
    ],

    # ── Z ── top bar + diagonal + bottom bar
    'Z': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 1.00), (1.00, 1.00)], Z_HORIZONTAL),
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.BASE,
            [(1.00, 1.00), (0.00, 0.00)], Z_LEFT_FALL),
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.BASE,
            [(0.00, 0.00), (1.00, 0.00)], Z_HORIZONTAL),
    ],
}


# ════════════════════════════════════════════════════════════════════════════
# DIACRITIC COMBINING MARKS  (viết sau BASE, trước TONE)
# Vị trí tương đối: y > 0.65 (phía trên thân chữ thường)
# ════════════════════════════════════════════════════════════════════════════

_DIACRITICS: dict[str, list[CalligraphyStroke]] = {

    # Dấu mũ ^ (circumflex)  — dùng cho â, ê, ô
    # Hai nét gặp nhau ở đỉnh
    '\u0302': [
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.DIACRITIC,
            [(0.24, 1.10), (0.50, 1.30), (0.76, 1.10)], Z_DIACRITIC),
    ],

    # Dấu trăng ˘ (breve) — dùng cho ă
    # Cung lõm hướng lên (smile)
    '\u0306': [
        CalligraphyStroke(StrokeType.CURVE, StrokeLayer.DIACRITIC,
            [(0.22, 1.24), (0.50, 1.10), (0.78, 1.24)], Z_DIACRITIC),
    ],

    # Dấu móc ʻ (horn) — dùng cho ơ, ư
    # Móc nhỏ cong ra phía trên-phải
    '\u031b': [
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.DIACRITIC,
            [(0.78, 0.72), (1.02, 0.98), (0.88, 1.12)], Z_DIACRITIC),
    ],
}


# ════════════════════════════════════════════════════════════════════════════
# TONE MARKS  (dấu thanh — viết SAU CÙNG theo quy tắc thư pháp)
# Vị trí tương đối: y > 1.08 (phía trên mọi dấu phụ chữ)
# Ngoại lệ: dấu nặng ở dưới baseline (y < 0)
# ════════════════════════════════════════════════════════════════════════════

_TONES: dict[str, list[CalligraphyStroke]] = {

    # Dấu sắc ´  (acute / U+0301)  — nét hất, trái-dưới → phải-trên
    '\u0301': [
        CalligraphyStroke(StrokeType.RISING, StrokeLayer.TONE_MARK,
            [(0.34, 1.16), (0.66, 1.42)], Z_TONE),
    ],

    # Dấu huyền ` (grave / U+0300)  — nét phẩy, trái-trên → phải-dưới
    '\u0300': [
        CalligraphyStroke(StrokeType.LEFT_FALL, StrokeLayer.TONE_MARK,
            [(0.34, 1.42), (0.66, 1.16)], Z_TONE),
    ],

    # Dấu hỏi ̉  (hook above / U+0309)  — cung nhỏ + đầu xoắn
    '\u0309': [
        CalligraphyStroke(StrokeType.HOOK, StrokeLayer.TONE_MARK,
            [(0.36, 1.38), (0.56, 1.48), (0.60, 1.30)], Z_TONE),
    ],

    # Dấu ngã ~  (tilde / U+0303)  — sóng đôi nằm ngang
    '\u0303': [
        CalligraphyStroke(StrokeType.HORIZONTAL, StrokeLayer.TONE_MARK,
            [(0.22, 1.30), (0.40, 1.44), (0.60, 1.24), (0.78, 1.38)], Z_TONE),
    ],

    # Dấu nặng . (dot below / U+0323)  — chấm tròn bên dưới baseline
    '\u0323': [
        CalligraphyStroke(StrokeType.DOT, StrokeLayer.TONE_MARK,
            [(0.46, -0.22), (0.54, -0.14)], Z_DOT_BELOW),
    ],
}


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API — PARSER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def parse_vietnamese_text(
    text: str,
    glyph_width: float = GLYPH_WIDTH,
    glyph_gap: float = GLYPH_GAP,
    space_width: float = SPACE_WIDTH,
) -> list[CalligraphyStroke]:
    """
    Phân rã văn bản tiếng Việt thành danh sách CalligraphyStroke có thứ tự.

    Quy tắc thứ tự (cho mỗi ký tự):
      BASE (trái→phải) → DIACRITIC → TONE_MARK

    Args:
        text:        Văn bản đầu vào (UTF-8, Unicode đầy đủ)
        glyph_width: Chiều rộng chuẩn hóa của một ký tự (mặc định 1.0)
        glyph_gap:   Khoảng cách giữa các ký tự (mặc định 0.35)
        space_width: Chiều rộng khoảng trắng (mặc định 0.80)

    Returns:
        list[CalligraphyStroke] — Có thể truyền thẳng vào
        calligraphy_strokes_to_robot_paths()
    """
    result: list[CalligraphyStroke] = []
    cursor_x = 0.0

    for char in text:
        if char.isspace():
            cursor_x += space_width
            continue

        # NFD decompose: tách base char khỏi combining marks
        nfd = unicodedata.normalize('NFD', char)
        base_char = ''
        combining: list[str] = []
        for cp in nfd:
            if unicodedata.combining(cp):
                combining.append(cp)
            elif not base_char:
                base_char = cp

        if not base_char:
            cursor_x += glyph_width + glyph_gap
            continue

        # Tìm kiếm nét glyph
        base_strokes = _get_base_strokes(base_char)
        if not base_strokes:
            cursor_x += glyph_width + glyph_gap
            continue

        # Phân loại combining marks
        diacritic_marks = [m for m in combining if m in _DIACRITICS]
        tone_marks      = [m for m in combining if m in _TONES]

        # Thêm BASE strokes (đã offset theo cursor_x)
        for stroke in base_strokes:
            result.append(_offset_stroke(stroke, cursor_x, 0.0))

        # Thêm DIACRITIC (dấu phụ chữ — trước dấu thanh)
        for mark in diacritic_marks:
            for stroke in _DIACRITICS[mark]:
                result.append(_offset_stroke(stroke, cursor_x, 0.0))

        # Thêm TONE MARK (dấu thanh — sau cùng)
        for mark in tone_marks:
            for stroke in _TONES[mark]:
                result.append(_offset_stroke(stroke, cursor_x, 0.0))

        cursor_x += glyph_width + glyph_gap

    return result


def calligraphy_strokes_to_robot_paths(
    strokes: list[CalligraphyStroke],
    z_light: float = -0.5,
    z_heavy: float = -3.0,
    font_scale: float = 220.0,
) -> list[list[tuple[float, float, float]]]:
    """
    Chuyển đổi CalligraphyStroke thành robot paths với Z-depth tích hợp.

    Output tương thích trực tiếp với robot_paths_to_measured_paper_poses()
    và FontSkeletonPipeline.

    Args:
        strokes:    Danh sách nét từ parse_vietnamese_text()
        z_light:    Tọa độ Z nhẹ nhất (chạm mặt giấy) [mm] — thường -0.5
        z_heavy:    Tọa độ Z nặng nhất (nhấn mạnh) [mm] — thường -3.0
        font_scale: Hệ số tỷ lệ x,y (khớp với font_size, mặc định 220)

    Returns:
        list[list[tuple[x, y, z]]] — Robot paths trong không gian tọa độ font
    """
    robot_paths: list[list[tuple[float, float, float]]] = []
    for stroke in strokes:
        if len(stroke.points) < 2:
            # Nét chấm (DOT) chỉ có 1-2 điểm — vẫn xử lý
            if len(stroke.points) == 0:
                continue
            # Duplicate point để tạo path hợp lệ
            pts = stroke.points * 2 if len(stroke.points) == 1 else stroke.points

        else:
            pts = stroke.points

        # B-spline interpolation for smoother curves
        if len(pts) >= 3:
            try:
                from scipy.interpolate import splprep, splev
                import numpy as np
                x_pts = np.array([p[0] for p in pts])
                y_pts = np.array([p[1] for p in pts])
                
                # Filter out consecutive duplicate points to avoid divide by zero
                keep = [0]
                for idx in range(1, len(pts)):
                    d = ((x_pts[idx] - x_pts[idx-1])**2 + (y_pts[idx] - y_pts[idx-1])**2)**0.5
                    if d > 1e-5:
                        keep.append(idx)
                
                if len(keep) >= 3:
                    x_pts = x_pts[keep]
                    y_pts = y_pts[keep]
                    k = min(3, len(x_pts) - 1)
                    num_smooth = max(len(pts) * 3, 40)
                    tck, u = splprep([x_pts, y_pts], s=0, k=k)
                    u_new = np.linspace(0, 1, num_smooth)
                    x_new, y_new = splev(u_new, tck)
                    pts = [(float(xi), float(yi)) for xi, yi in zip(x_new, y_new)]
            except ImportError:
                pass

        # Scale tọa độ sang không gian font
        scaled: list[tuple[float, float]] = [
            (x * font_scale, y * font_scale) for x, y in pts
        ]
        # Nội suy Z theo ZProfile
        path_3d = _interpolate_z_along_stroke(scaled, stroke.z_profile, z_light, z_heavy)
        robot_paths.append(path_3d)

    return robot_paths


def describe_character(char: str) -> str:
    """
    Trả về mô tả dạng text cho việc phân rã một ký tự đơn.
    Hữu ích cho debugging và xuất báo cáo.
    """
    strokes = parse_vietnamese_text(char)
    lines = [f"Phân rã ký tự: '{char}'  (NFD: {unicodedata.normalize('NFD', char)!r})"]
    lines.append(f"Tổng số nét: {len(strokes)}")
    for i, s in enumerate(strokes, 1):
        lines.append(
            f"  Nét {i:2d}: [{s.layer.value:10s}] {s.stroke_type.value:12s} "
            f"— {len(s.points)} điểm  "
            f"Z({s.z_profile.z_start:.2f}→{s.z_profile.z_mid:.2f}→{s.z_profile.z_end:.2f})"
        )
    return "\n".join(lines)


def list_supported_characters() -> dict[str, list[str]]:
    """Liệt kê tất cả ký tự được hỗ trợ theo loại."""
    # Tự động sinh danh sách từ bảng glyph + combining marks
    base_lower = sorted(_LOWER_GLYPHS.keys())
    base_upper = sorted(_UPPER_GLYPHS.keys())
    diacritics = sorted(_DIACRITICS.keys())
    tones = sorted(_TONES.keys())

    # Sinh một số ký tự tiếng Việt mẫu
    sample_viet = []
    for base in ['a', 'e', 'o', 'u']:
        for tone in ['\u0301', '\u0300', '\u0309', '\u0303', '\u0323']:
            sample_viet.append(unicodedata.normalize('NFC', base + tone))
        for diacritic in ['\u0302', '\u0306', '\u031b']:
            combined = base + diacritic
            sample_viet.append(unicodedata.normalize('NFC', combined))
            for tone in ['\u0301', '\u0300']:
                sample_viet.append(unicodedata.normalize('NFC', combined + tone))

    return {
        'lowercase_base': base_lower,
        'uppercase_base': base_upper,
        'diacritic_marks': diacritics,
        'tone_marks': tones,
        'sample_vietnamese': sample_viet,
    }


# ════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _get_base_strokes(char: str) -> list[CalligraphyStroke]:
    """Tra cứu nét thư pháp cho một ký tự gốc (phân biệt hoa/thường)."""
    # Kiểm tra chính xác trước (đ, Đ)
    if char in _LOWER_GLYPHS:
        return _LOWER_GLYPHS[char]
    if char in _UPPER_GLYPHS:
        return _UPPER_GLYPHS[char]
    # Fallback lowercase
    lower = char.lower()
    if lower in _LOWER_GLYPHS:
        return _LOWER_GLYPHS[lower]
    return []


def _offset_stroke(
    stroke: CalligraphyStroke, dx: float, dy: float
) -> CalligraphyStroke:
    """Tạo bản sao của stroke với tất cả điểm dịch chuyển (dx, dy)."""
    return CalligraphyStroke(
        stroke_type=stroke.stroke_type,
        layer=stroke.layer,
        points=[(x + dx, y + dy) for x, y in stroke.points],
        z_profile=stroke.z_profile,
    )


def _interpolate_z_along_stroke(
    points: list[tuple[float, float]],
    z_profile: ZProfile,
    z_light: float,
    z_heavy: float,
) -> list[tuple[float, float, float]]:
    """
    Nội suy Z-depth theo từng điểm trong nét bút.

    Dùng nội suy tuyến tính từng đoạn:
      t ∈ [0.0, 0.5]: z_start → z_mid
      t ∈ [0.5, 1.0]: z_mid   → z_end

    fraction = 0.0 → z = z_light (nhẹ nhất)
    fraction = 1.0 → z = z_heavy (nặng nhất)
    """
    n = len(points)
    z_min = min(z_light, z_heavy)   # giá trị Z nhỏ hơn (âm hơn = sâu hơn)
    z_max = max(z_light, z_heavy)   # giá trị Z lớn hơn (ít âm = nhẹ hơn)

    result: list[tuple[float, float, float]] = []
    for i, (x, y) in enumerate(points):
        t = i / max(n - 1, 1)   # [0.0 .. 1.0]

        # Nội suy fraction theo profile
        if t <= 0.5:
            alpha = t / 0.5
            frac = z_profile.z_start + (z_profile.z_mid - z_profile.z_start) * alpha
        else:
            alpha = (t - 0.5) / 0.5
            frac = z_profile.z_mid + (z_profile.z_end - z_profile.z_mid) * alpha

        # Map fraction → z thực (0 → z_light, 1 → z_heavy)
        z = z_light + frac * (z_heavy - z_light)

        # Clamp an toàn
        z = max(z_min, min(z_max, z))

        result.append((round(x, 4), round(y, 4), round(z, 4)))

    return result
