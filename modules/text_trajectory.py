from typing import Any
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.textpath import TextPath

from modules.paper_zone import build_pose_in_paper
from modules.svg_trajectory import sample_svg_strokes


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
            font_path=str(demo.get("font_path", "")).strip(),
            font_size=float(demo.get("font_size", 1.0)),
        )
    elif mode in ("font_skeleton", "mistral", "mistral_single_line"):
        strokes = _font_skeleton_strokes(
            text=text,
            font_family=str(demo.get("font_family", "Mistral")),
            font_path=str(demo.get("font_path", "")).strip(),
            font_size=float(demo.get("font_size", 1.0)),
            raster_scale=int(demo.get("skeleton_raster_scale", 96)),
            min_stroke_pixels=int(demo.get("skeleton_min_stroke_pixels", 10)),
        )
    elif mode in ("skeleton_svg", "svg_skeleton"):
        strokes = _svg_skeleton_strokes(demo, text)
    elif mode == "calligraphy":
        strokes = _calligraphy_text_strokes(text)
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
    point_spacing = float(demo.get("point_spacing", 0.04))
    return [
        [build_pose_in_paper(config, u, v) for u, v in _prepare_stroke(stroke, max_points, point_spacing)]
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


def _text_polygons(text: str, font_family: str, font_path: str, font_size: float) -> list[list[Point]]:
    font = _font_properties(font_family, font_path)
    try:
        path = TextPath((0.0, 0.0), text, size=font_size, prop=font)
    except FileNotFoundError:
        path = TextPath((0.0, 0.0), text, size=font_size, prop=_family_font_properties(font_family))
    polygons = []
    for polygon in path.to_polygons():
        points = [(float(point[0]), float(point[1])) for point in polygon]
        if len(points) >= 2:
            polygons.append(points)
    if not polygons:
        raise ValueError(f"No drawable contours were generated for text: {text!r}")
    return polygons


def _font_skeleton_strokes(
    text: str,
    font_family: str,
    font_path: str,
    font_size: float,
    raster_scale: int,
    min_stroke_pixels: int,
) -> list[list[Point]]:
    polygons = _text_polygons(text, font_family, font_path, font_size)
    points = [point for polygon in polygons for point in polygon]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    scale = max(float(raster_scale), 24.0)
    pad = int(scale * 0.25)
    width = max(int((max_x - min_x) * scale) + pad * 2 + 1, 3)
    height = max(int((max_y - min_y) * scale) + pad * 2 + 1, 3)

    mask = np.zeros((height, width), dtype=np.uint8)
    for polygon in polygons:
        contour = np.array(
            [
                [
                    int(round((x - min_x) * scale)) + pad,
                    int(round((max_y - y) * scale)) + pad,
                ]
                for x, y in polygon
            ],
            dtype=np.int32,
        )
        if len(contour) >= 3:
            cv2.fillPoly(mask, [contour], 255)

    if not np.any(mask):
        raise ValueError(f"No Mistral skeleton mask was generated for text: {text!r}")

    skeleton = _zhang_suen_thinning(mask > 0)
    pixel_strokes = _trace_skeleton_pixels(skeleton, min_stroke_pixels)
    strokes = [
        [
            (
                min_x + (float(x) - pad) / scale,
                max_y - (float(y) - pad) / scale,
            )
            for x, y in stroke
        ]
        for stroke in pixel_strokes
        if len(stroke) >= 2
    ]
    if not strokes:
        raise ValueError(f"No Mistral single-line strokes were generated for text: {text!r}")
    return _order_strokes_nearest(strokes)


def _zhang_suen_thinning(binary: np.ndarray) -> np.ndarray:
    image = binary.astype(np.uint8).copy()
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            remove: list[tuple[int, int]] = []
            rows, cols = image.shape
            for y in range(1, rows - 1):
                for x in range(1, cols - 1):
                    if image[y, x] == 0:
                        continue
                    p2 = image[y - 1, x]
                    p3 = image[y - 1, x + 1]
                    p4 = image[y, x + 1]
                    p5 = image[y + 1, x + 1]
                    p6 = image[y + 1, x]
                    p7 = image[y + 1, x - 1]
                    p8 = image[y, x - 1]
                    p9 = image[y - 1, x - 1]
                    neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
                    count = int(sum(neighbors))
                    if count < 2 or count > 6:
                        continue
                    transitions = sum(1 for a, b in zip(neighbors, neighbors[1:] + neighbors[:1]) if a == 0 and b == 1)
                    if transitions != 1:
                        continue
                    if step == 0:
                        if p2 * p4 * p6 != 0 or p4 * p6 * p8 != 0:
                            continue
                    else:
                        if p2 * p4 * p8 != 0 or p2 * p6 * p8 != 0:
                            continue
                    remove.append((y, x))
            if remove:
                changed = True
                for y, x in remove:
                    image[y, x] = 0
    return image.astype(bool)


def _trace_skeleton_pixels(skeleton: np.ndarray, min_stroke_pixels: int) -> list[list[tuple[int, int]]]:
    pixels = {(int(x), int(y)) for y, x in np.argwhere(skeleton)}
    if not pixels:
        return []

    def neighbors(point: tuple[int, int]) -> list[tuple[int, int]]:
        x, y = point
        found = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                candidate = (x + dx, y + dy)
                if candidate in pixels:
                    found.append(candidate)
        return found

    degree = {point: len(neighbors(point)) for point in pixels}
    starts = [point for point, value in degree.items() if value != 2]
    visited_edges: set[frozenset[tuple[int, int]]] = set()
    strokes: list[list[tuple[int, int]]] = []

    def edge(a: tuple[int, int], b: tuple[int, int]) -> frozenset[tuple[int, int]]:
        return frozenset((a, b))

    def walk(start: tuple[int, int], nxt: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, nxt]
        visited_edges.add(edge(start, nxt))
        prev = start
        current = nxt
        while degree.get(current, 0) == 2:
            options = [item for item in neighbors(current) if item != prev and edge(current, item) not in visited_edges]
            if not options:
                break
            following = options[0]
            visited_edges.add(edge(current, following))
            path.append(following)
            prev, current = current, following
        return path

    for start in starts:
        for nxt in neighbors(start):
            if edge(start, nxt) in visited_edges:
                continue
            path = walk(start, nxt)
            if len(path) >= min_stroke_pixels:
                strokes.append(_simplify_pixel_stroke(path))

    for point in pixels:
        for nxt in neighbors(point):
            if edge(point, nxt) in visited_edges:
                continue
            path = walk(point, nxt)
            if len(path) >= min_stroke_pixels:
                strokes.append(_simplify_pixel_stroke(path))

    return strokes


def _simplify_pixel_stroke(stroke: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(stroke) <= 2:
        return stroke
    simplified = [stroke[0]]
    last_dx = stroke[1][0] - stroke[0][0]
    last_dy = stroke[1][1] - stroke[0][1]
    for prev, point in zip(stroke[1:], stroke[2:]):
        dx = point[0] - prev[0]
        dy = point[1] - prev[1]
        if (dx, dy) != (last_dx, last_dy):
            simplified.append(prev)
            last_dx, last_dy = dx, dy
    simplified.append(stroke[-1])
    return simplified


def _font_properties(font_family: str, font_path: str) -> FontProperties:
    if not font_path:
        return _family_font_properties(font_family)

    path = Path(font_path)
    if path.is_file():
        return FontProperties(fname=str(path))

    if not path.suffix:
        for suffix in (".ttf", ".otf", ".ttc"):
            candidate = path.with_suffix(suffix)
            if candidate.is_file():
                return FontProperties(fname=str(candidate))

    return _family_font_properties(font_family)


def _family_font_properties(font_family: str) -> FontProperties:
    family = font_family or "DejaVu Sans"
    try:
        findfont(FontProperties(family=family), fallback_to_default=False)
    except ValueError:
        family = "DejaVu Sans"
    return FontProperties(family=family)


def _svg_skeleton_strokes(demo: dict[str, Any], text: str) -> list[list[Point]]:
    skeletons = demo.get("skeleton_svgs", {})
    skeleton_path = ""
    if isinstance(skeletons, dict):
        skeleton_path = str(skeletons.get(text, "")).strip()
    if not skeleton_path:
        skeleton_text = str(demo.get("skeleton_svg_text", "")).strip()
        if skeleton_text and text != skeleton_text:
            raise ValueError(
                f"Configured skeleton SVG is for {skeleton_text!r}, but requested text is {text!r}. "
                "Generate a matching skeleton SVG or add it to text_demo.skeleton_svgs."
            )
        skeleton_path = str(demo.get("skeleton_svg_path", "")).strip()
    if not skeleton_path:
        raise ValueError("text_demo.skeleton_svg_path is required when mode is skeleton_svg")

    strokes = sample_svg_strokes(
        Path(skeleton_path),
        samples_per_path=int(demo.get("samples_per_path", demo.get("max_points_per_stroke", 120))),
    )
    return _order_strokes_nearest(strokes)


def _order_strokes_nearest(strokes: list[list[Point]]) -> list[list[Point]]:
    remaining = [stroke for stroke in strokes if len(stroke) >= 2]
    ordered: list[list[Point]] = []
    cursor: Point | None = None

    while remaining:
        if cursor is None:
            index = min(range(len(remaining)), key=lambda item: _stroke_start_key(remaining[item]))
            stroke = remaining.pop(index)
        else:
            options = [(item, False) for item in range(len(remaining))]
            options.extend((item, True) for item in range(len(remaining)))
            index, reverse = min(options, key=lambda option: _distance(cursor, remaining[option[0]][-1 if option[1] else 0]))
            stroke = remaining.pop(index)
            if reverse:
                stroke = list(reversed(stroke))
        ordered.append(stroke)
        cursor = stroke[-1]
    return ordered


def _stroke_start_key(stroke: list[Point]) -> tuple[float, float]:
    start, end = stroke[0], stroke[-1]
    point = start if (start[1], start[0]) <= (end[1], end[0]) else end
    return point[0], point[1]


def _distance(start: Point, end: Point) -> float:
    return ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5


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


def _calligraphy_text_strokes(text: str) -> list[list[Point]]:
    strokes: list[list[Point]] = []
    cursor_x = 0.0
    for raw_char in text:
        if raw_char.isspace():
            cursor_x += SPACE_WIDTH
            continue

        base_char, marks = _split_base_and_marks(raw_char)
        glyph = _calligraphy_glyph(base_char.lower())
        if glyph is None:
            cursor_x += GLYPH_WIDTH + GLYPH_GAP
            continue

        strokes.extend(_shift_strokes(glyph, cursor_x, 0.0))
        strokes.extend(_accent_strokes(marks, cursor_x))
        cursor_x += GLYPH_WIDTH + GLYPH_GAP

    if not strokes:
        raise ValueError(f"No calligraphy glyphs were generated for text: {text!r}")
    return strokes


def _calligraphy_glyph(char: str) -> Glyph | None:
    glyphs: dict[str, Glyph] = {
        "a": [[(0.15, 0.35), (0.28, 0.68), (0.62, 0.72), (0.82, 0.45), (0.68, 0.18), (0.35, 0.14), (0.18, 0.32), (0.38, 0.58), (0.78, 0.58), (0.86, 0.18)]],
        "b": [[(0.22, 0.05), (0.2, 0.92), (0.42, 1.05), (0.52, 0.78), (0.35, 0.48), (0.58, 0.7), (0.9, 0.58), (0.82, 0.22), (0.48, 0.1), (0.28, 0.28)]],
        "c": [[(0.82, 0.58), (0.58, 0.78), (0.22, 0.62), (0.12, 0.32), (0.34, 0.12), (0.78, 0.22)]],
        "d": [[(0.82, 1.02), (0.72, 0.5), (0.78, 0.12), (0.58, 0.18), (0.32, 0.12), (0.14, 0.34), (0.3, 0.66), (0.65, 0.7), (0.84, 0.48), (0.95, 0.18)]],
        "e": [[(0.16, 0.38), (0.45, 0.58), (0.78, 0.52), (0.58, 0.3), (0.2, 0.34), (0.32, 0.12), (0.78, 0.2)]],
        "f": [[(0.62, 1.0), (0.38, 0.85), (0.42, 0.42), (0.34, -0.18), (0.1, -0.32), (0.0, -0.08), (0.5, 0.48), (0.82, 0.48)]],
        "g": [[(0.78, 0.62), (0.52, 0.76), (0.2, 0.58), (0.16, 0.28), (0.42, 0.14), (0.72, 0.28), (0.78, 0.68), (0.62, -0.2), (0.28, -0.38), (0.08, -0.18), (0.32, 0.02)]],
        "h": [[(0.2, 0.05), (0.18, 0.96), (0.42, 1.06), (0.55, 0.82), (0.28, 0.42), (0.48, 0.66), (0.78, 0.62), (0.78, 0.18), (0.94, 0.14)]],
        "i": [[(0.42, 0.62), (0.34, 0.2), (0.5, 0.12), (0.68, 0.22)], [(0.45, 0.92), (0.47, 0.94)]],
        "j": [[(0.56, 0.62), (0.4, -0.2), (0.16, -0.36), (0.0, -0.18), (0.24, 0.02)], [(0.58, 0.92), (0.6, 0.94)]],
        "k": [[(0.2, 0.04), (0.18, 0.96), (0.44, 1.04), (0.48, 0.76), (0.2, 0.42), (0.78, 0.72), (0.36, 0.42), (0.86, 0.12)]],
        "l": [[(0.28, 0.05), (0.28, 0.88), (0.46, 1.08), (0.62, 0.9), (0.45, 0.52), (0.34, 0.18), (0.62, 0.12), (0.8, 0.24)]],
        "m": [[(0.12, 0.16), (0.22, 0.64), (0.42, 0.68), (0.42, 0.18), (0.56, 0.62), (0.78, 0.66), (0.78, 0.18), (0.96, 0.28)]],
        "n": [[(0.12, 0.16), (0.22, 0.64), (0.48, 0.66), (0.48, 0.18), (0.72, 0.62), (0.92, 0.2)]],
        "o": [[(0.46, 0.72), (0.18, 0.58), (0.12, 0.3), (0.34, 0.1), (0.72, 0.22), (0.82, 0.52), (0.58, 0.72), (0.36, 0.5), (0.66, 0.36), (0.94, 0.42)]],
        "p": [[(0.18, -0.35), (0.2, 0.62), (0.5, 0.7), (0.82, 0.52), (0.76, 0.2), (0.44, 0.12), (0.22, 0.36)]],
        "q": [[(0.78, 0.62), (0.52, 0.76), (0.2, 0.58), (0.16, 0.28), (0.42, 0.14), (0.72, 0.28), (0.78, 0.68), (0.76, -0.3), (1.0, -0.2)]],
        "r": [[(0.16, 0.14), (0.24, 0.62), (0.44, 0.64), (0.54, 0.48), (0.72, 0.72), (0.92, 0.62)]],
        "s": [[(0.78, 0.62), (0.48, 0.78), (0.18, 0.62), (0.34, 0.42), (0.72, 0.34), (0.74, 0.12), (0.34, 0.1), (0.12, 0.26)]],
        "t": [[(0.44, 0.9), (0.36, 0.24), (0.54, 0.08), (0.78, 0.28)], [(0.18, 0.58), (0.72, 0.58)]],
        "u": [[(0.16, 0.62), (0.18, 0.22), (0.42, 0.12), (0.68, 0.56), (0.68, 0.18), (0.88, 0.18)]],
        "v": [[(0.14, 0.62), (0.36, 0.12), (0.72, 0.58), (0.9, 0.46)]],
        "w": [[(0.12, 0.62), (0.28, 0.12), (0.48, 0.5), (0.66, 0.12), (0.9, 0.6)]],
        "x": [[(0.16, 0.62), (0.78, 0.12)], [(0.8, 0.62), (0.18, 0.12)]],
        "y": [[(0.14, 0.62), (0.34, 0.14), (0.72, 0.58), (0.54, -0.22), (0.18, -0.36), (0.02, -0.16), (0.28, 0.02)]],
        "z": [[(0.16, 0.62), (0.78, 0.62), (0.22, 0.12), (0.84, 0.12)]],
    }
    if char == "đ":
        base = glyphs["d"]
        return [*base, [(0.36, 0.74), (0.9, 0.74)]]
    return glyphs.get(char)


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


def _prepare_stroke(stroke: list[Point], max_points: int, point_spacing: float) -> list[Point]:
    dense = _densify_stroke(stroke, point_spacing)
    if max_points <= 0 or len(dense) <= max_points:
        return dense

    step = max(len(dense) / max_points, 1.0)
    sampled = [dense[int(index * step)] for index in range(max_points)]
    if sampled[-1] != dense[-1]:
        sampled.append(dense[-1])
    return sampled


def _densify_stroke(stroke: list[Point], point_spacing: float) -> list[Point]:
    if point_spacing <= 0.0 or len(stroke) < 2:
        return stroke

    dense = [stroke[0]]
    for start, end in zip(stroke, stroke[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = (dx * dx + dy * dy) ** 0.5
        steps = max(int(distance / point_spacing), 1)
        for index in range(1, steps + 1):
            t = index / steps
            dense.append((start[0] + dx * t, start[1] + dy * t))
    return dense
