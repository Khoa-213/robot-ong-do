from typing import Any
import unicodedata

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

from modules.paper_zone import build_pose_in_paper


Point = tuple[float, float]
Glyph = list[list[Point]]


GLYPH_WIDTH = 1.0
GLYPH_GAP = 0.35
SPACE_WIDTH = 0.8


SINGLE_LINE_GLYPHS: dict[str, Glyph] = {
    "A": [[(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)], [(0.25, 0.45), (0.75, 0.45)]],
    "B": [[(0.0, 0.0), (0.0, 1.0), (0.55, 1.0), (0.8, 0.8), (0.55, 0.55), (0.0, 0.55)], [(0.0, 0.55), (0.6, 0.55), (0.85, 0.3), (0.6, 0.0), (0.0, 0.0)]],
    "C": [[(0.85, 0.9), (0.55, 1.0), (0.15, 0.85), (0.0, 0.5), (0.15, 0.15), (0.55, 0.0), (0.85, 0.1)]],
    "D": [[(0.0, 0.0), (0.0, 1.0), (0.55, 1.0), (0.9, 0.65), (0.9, 0.35), (0.55, 0.0), (0.0, 0.0)]],
    "E": [[(0.85, 1.0), (0.0, 1.0), (0.0, 0.0), (0.85, 0.0)], [(0.0, 0.5), (0.65, 0.5)]],
    "F": [[(0.0, 0.0), (0.0, 1.0), (0.85, 1.0)], [(0.0, 0.5), (0.65, 0.5)]],
    "G": [[(0.85, 0.85), (0.6, 1.0), (0.15, 0.8), (0.0, 0.45), (0.2, 0.1), (0.65, 0.0), (0.95, 0.25), (0.95, 0.45), (0.55, 0.45)]],
    "H": [[(0.0, 0.0), (0.0, 1.0)], [(1.0, 0.0), (1.0, 1.0)], [(0.0, 0.5), (1.0, 0.5)]],
    "I": [[(0.5, 0.0), (0.5, 1.0)], [(0.2, 1.0), (0.8, 1.0)], [(0.2, 0.0), (0.8, 0.0)]],
    "J": [[(0.85, 1.0), (0.85, 0.2), (0.65, 0.0), (0.25, 0.05), (0.1, 0.25)]],
    "K": [[(0.0, 0.0), (0.0, 1.0)], [(1.0, 1.0), (0.0, 0.45), (1.0, 0.0)]],
    "L": [[(0.0, 1.0), (0.0, 0.0), (0.85, 0.0)]],
    "M": [[(0.0, 0.0), (0.0, 1.0), (0.5, 0.45), (1.0, 1.0), (1.0, 0.0)]],
    "N": [[(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)]],
    "O": [[(0.5, 1.0), (0.15, 0.85), (0.0, 0.5), (0.15, 0.15), (0.5, 0.0), (0.85, 0.15), (1.0, 0.5), (0.85, 0.85), (0.5, 1.0)]],
    "P": [[(0.0, 0.0), (0.0, 1.0), (0.6, 1.0), (0.9, 0.75), (0.6, 0.5), (0.0, 0.5)]],
    "Q": [[(0.5, 1.0), (0.15, 0.85), (0.0, 0.5), (0.15, 0.15), (0.5, 0.0), (0.85, 0.15), (1.0, 0.5), (0.85, 0.85), (0.5, 1.0)], [(0.6, 0.2), (1.0, -0.15)]],
    "R": [[(0.0, 0.0), (0.0, 1.0), (0.6, 1.0), (0.9, 0.75), (0.6, 0.5), (0.0, 0.5)], [(0.45, 0.5), (1.0, 0.0)]],
    "S": [[(0.9, 0.85), (0.6, 1.0), (0.15, 0.85), (0.2, 0.55), (0.75, 0.45), (0.9, 0.15), (0.55, 0.0), (0.1, 0.15)]],
    "T": [[(0.0, 1.0), (1.0, 1.0)], [(0.5, 1.0), (0.5, 0.0)]],
    "U": [[(0.0, 1.0), (0.0, 0.25), (0.25, 0.0), (0.75, 0.0), (1.0, 0.25), (1.0, 1.0)]],
    "V": [[(0.0, 1.0), (0.5, 0.0), (1.0, 1.0)]],
    "W": [[(0.0, 1.0), (0.25, 0.0), (0.5, 0.55), (0.75, 0.0), (1.0, 1.0)]],
    "X": [[(0.0, 1.0), (1.0, 0.0)], [(1.0, 1.0), (0.0, 0.0)]],
    "Y": [[(0.0, 1.0), (0.5, 0.5), (1.0, 1.0)], [(0.5, 0.5), (0.5, 0.0)]],
    "Z": [[(0.0, 1.0), (1.0, 1.0), (0.0, 0.0), (1.0, 0.0)]],
    "0": [[(0.5, 1.0), (0.15, 0.85), (0.0, 0.5), (0.15, 0.15), (0.5, 0.0), (0.85, 0.15), (1.0, 0.5), (0.85, 0.85), (0.5, 1.0)]],
    "1": [[(0.35, 0.8), (0.5, 1.0), (0.5, 0.0)], [(0.25, 0.0), (0.75, 0.0)]],
    "2": [[(0.1, 0.75), (0.35, 1.0), (0.8, 0.85), (0.85, 0.55), (0.1, 0.0), (0.9, 0.0)]],
    "3": [[(0.1, 0.9), (0.85, 0.9), (0.5, 0.5), (0.85, 0.15), (0.1, 0.1)]],
    "4": [[(0.8, 0.0), (0.8, 1.0), (0.1, 0.35), (1.0, 0.35)]],
    "5": [[(0.9, 1.0), (0.2, 1.0), (0.1, 0.55), (0.65, 0.55), (0.9, 0.25), (0.6, 0.0), (0.15, 0.1)]],
    "6": [[(0.85, 0.85), (0.45, 1.0), (0.1, 0.55), (0.2, 0.15), (0.55, 0.0), (0.9, 0.2), (0.75, 0.5), (0.25, 0.5)]],
    "7": [[(0.1, 1.0), (0.9, 1.0), (0.35, 0.0)]],
    "8": [[(0.5, 1.0), (0.2, 0.8), (0.5, 0.55), (0.8, 0.8), (0.5, 1.0)], [(0.5, 0.55), (0.15, 0.25), (0.5, 0.0), (0.85, 0.25), (0.5, 0.55)]],
    "9": [[(0.85, 0.45), (0.65, 0.0), (0.2, 0.15), (0.1, 0.55), (0.45, 1.0), (0.85, 0.85), (0.85, 0.45), (0.25, 0.45)]],
    "-": [[(0.2, 0.5), (0.8, 0.5)]],
    ".": [[(0.5, 0.0), (0.52, 0.02)]],
}


def build_text_pose_strokes(config: dict[str, Any], text: str) -> list[list[list[float]]]:
    text = text.strip()
    if not text:
        raise ValueError("Text to write must not be empty")

    demo = config.get("text_demo", {})
    mode = str(demo.get("mode", "single_line")).strip().lower()
    if mode == "outline":
        strokes = _text_polygons(
            text=text,
            font_family=str(demo.get("font_family", "DejaVu Sans")),
            font_size=float(demo.get("font_size", 1.0)),
        )
    else:
        strokes = _single_line_text_strokes(text)
    normalized_strokes = fit_strokes_to_uv(
        strokes,
        u_min=float(demo.get("u_min", 0.2)),
        u_max=float(demo.get("u_max", 0.8)),
        v_min=float(demo.get("v_min", 0.2)),
        v_max=float(demo.get("v_max", 0.8)),
        invert_y=bool(demo.get("invert_y", True)),
    )
    max_points = int(demo.get("max_points_per_stroke", 48))
    return [
        [build_pose_in_paper(config, u, v) for u, v in _downsample_stroke(stroke, max_points)]
        for stroke in normalized_strokes
        if len(stroke) >= 2
    ]


def flatten_strokes(strokes: list[list[list[float]]]) -> list[list[float]]:
    return [pose for stroke in strokes for pose in stroke]


def connect_pose_strokes(strokes: list[list[list[float]]]) -> list[list[float]]:
    connected = []
    for stroke in strokes:
        if not stroke:
            continue
        connected.extend(stroke)
    if not connected:
        raise ValueError("No text poses were generated")
    return connected


def fit_strokes_to_uv(
    strokes: list[list[Point]],
    u_min: float,
    u_max: float,
    v_min: float,
    v_max: float,
    invert_y: bool = True,
) -> list[list[Point]]:
    if not (0.0 <= u_min < u_max <= 1.0):
        raise ValueError("u_min/u_max must be inside [0, 1]")
    if not (0.0 <= v_min < v_max <= 1.0):
        raise ValueError("v_min/v_max must be inside [0, 1]")

    points = [point for stroke in strokes for point in stroke]
    if not points:
        raise ValueError("No text points were generated")

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Text bounds must have positive width and height")

    u_span = u_max - u_min
    v_span = v_max - v_min
    scale = min(u_span / width, v_span / height)
    fitted_width = width * scale
    fitted_height = height * scale
    u_offset = u_min + (u_span - fitted_width) / 2.0
    v_offset = v_min + (v_span - fitted_height) / 2.0

    normalized = []
    for stroke in strokes:
        normalized_stroke = []
        for x, y in stroke:
            u = u_offset + (x - min_x) * scale
            source_y = max_y - y if invert_y else y - min_y
            v = v_offset + source_y * scale
            normalized_stroke.append((u, v))
        normalized.append(normalized_stroke)
    return normalized


def _text_polygons(text: str, font_family: str, font_size: float) -> list[list[Point]]:
    path = TextPath((0.0, 0.0), text, size=font_size, prop=FontProperties(family=font_family))
    polygons = []
    for polygon in path.to_polygons():
        points = [(float(point[0]), float(point[1])) for point in polygon]
        if len(points) >= 2:
            polygons.append(points)
    if not polygons:
        raise ValueError(f"No drawable contours were generated for text: {text!r}")
    return polygons


def _single_line_text_strokes(text: str) -> list[list[Point]]:
    strokes: list[list[Point]] = []
    cursor_x = 0.0
    for raw_char in text:
        if raw_char.isspace():
            cursor_x += SPACE_WIDTH
            continue

        base_char, marks = _split_base_and_marks(raw_char)
        glyph = SINGLE_LINE_GLYPHS.get(base_char.upper())
        if glyph is None:
            cursor_x += GLYPH_WIDTH + GLYPH_GAP
            continue

        strokes.extend(_shift_strokes(glyph, cursor_x, 0.0))
        strokes.extend(_accent_strokes(marks, cursor_x))
        cursor_x += GLYPH_WIDTH + GLYPH_GAP

    if not strokes:
        raise ValueError(f"No single-line glyphs were generated for text: {text!r}")
    return strokes


def _split_base_and_marks(char: str) -> tuple[str, list[str]]:
    normalized = unicodedata.normalize("NFD", char)
    base = ""
    marks = []
    for item in normalized:
        if unicodedata.combining(item):
            marks.append(item)
        elif not base:
            base = item
    return base or char, marks


def _shift_strokes(strokes: Glyph, offset_x: float, offset_y: float) -> Glyph:
    return [[(x + offset_x, y + offset_y) for x, y in stroke] for stroke in strokes]


def _accent_strokes(marks: list[str], offset_x: float) -> Glyph:
    strokes: Glyph = []
    top_y = 1.18
    if "\u0302" in marks:
        strokes.append([(offset_x + 0.25, top_y), (offset_x + 0.5, top_y + 0.22), (offset_x + 0.75, top_y)])
        top_y += 0.18
    if "\u0306" in marks:
        strokes.append([(offset_x + 0.25, top_y + 0.12), (offset_x + 0.5, top_y), (offset_x + 0.75, top_y + 0.12)])
        top_y += 0.18
    if "\u031b" in marks:
        strokes.append([(offset_x + 0.78, 0.85), (offset_x + 1.05, 1.08), (offset_x + 0.92, 1.2)])
    if "\u0301" in marks:
        strokes.append([(offset_x + 0.42, top_y), (offset_x + 0.72, top_y + 0.24)])
    if "\u0300" in marks:
        strokes.append([(offset_x + 0.58, top_y), (offset_x + 0.28, top_y + 0.24)])
    if "\u0309" in marks:
        strokes.append([(offset_x + 0.38, top_y + 0.18), (offset_x + 0.6, top_y + 0.26), (offset_x + 0.5, top_y + 0.08)])
    if "\u0303" in marks:
        strokes.append([(offset_x + 0.28, top_y + 0.1), (offset_x + 0.42, top_y + 0.22), (offset_x + 0.58, top_y), (offset_x + 0.72, top_y + 0.12)])
    if "\u0323" in marks:
        strokes.append([(offset_x + 0.5, -0.22), (offset_x + 0.52, -0.2)])
    return strokes


def _downsample_stroke(stroke: list[Point], max_points: int) -> list[Point]:
    if max_points <= 0 or len(stroke) <= max_points:
        return stroke

    step = max(len(stroke) / max_points, 1.0)
    sampled = [stroke[int(index * step)] for index in range(max_points)]
    if sampled[-1] != stroke[-1]:
        sampled.append(stroke[-1])
    return sampled
