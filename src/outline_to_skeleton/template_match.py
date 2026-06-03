from __future__ import annotations

from dataclasses import dataclass
from math import hypot

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.affinity import scale as shapely_scale
from shapely.affinity import translate as shapely_translate
from shapely.geometry import LineString
from shapely.geometry import MultiPolygon, Point, Polygon
from skimage.morphology import medial_axis

from modules.text_trajectory import _single_line_text_strokes

from .errors import RobotPathError
from .font_outline import text_to_outline_polygons
from .geometry import rings_to_polygons
from .path_smoothing import moving_average_stroke, resample_stroke, rdp_stroke
from .rasterize import pixel_to_world, rasterize_polygons
from .z_depth import enforce_max_z_step, map_radius_to_z, smooth_z_values


Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class TemplateMatchConfig:
    font_size: int = 220
    resolution: float = 2.0
    z_light: float = -0.5
    z_heavy: float = -3.0
    template_spacing: float = 2.0
    output_spacing: float = 1.0
    iterations: int = 80
    search_radius_px: int = 4
    initial_snap_radius_px: int = 45
    template_inset_scale: float = 0.82
    spring_weight: float = 0.35
    simplify_tolerance: float = 0.0
    smooth_window: int = 3


@dataclass(frozen=True)
class TemplateMatchDebug:
    outlines: list[Polygon]
    fitted_template: list[list[Point2]]
    relaxed_template: list[list[Point2]]
    robot_paths: list[list[Point3]]


def text_to_template_matched_robot_paths(
    text: str,
    font_path: str,
    config: TemplateMatchConfig | None = None,
) -> list[list[Point3]]:
    cfg = config or TemplateMatchConfig()
    return text_to_template_match_debug(text, font_path, cfg).robot_paths


def text_to_template_match_debug(
    text: str,
    font_path: str,
    config: TemplateMatchConfig | None = None,
) -> TemplateMatchDebug:
    cfg = config or TemplateMatchConfig()
    outlines, fitted = _fit_template_text_per_glyph(text, font_path, cfg.font_size, cfg.template_inset_scale)
    outline_geom = MultiPolygon(outlines)
    mask, raster_info = rasterize_polygons(outlines, cfg.resolution)
    skeleton, distance = medial_axis(mask, return_distance=True)
    if not np.any(mask) or not np.any(skeleton):
        raise RobotPathError("Outline mask/skeleton is empty")

    dense = [resample_stroke([(x, y, 0.0) for x, y in stroke], cfg.template_spacing) for stroke in fitted]
    relaxed = [
        _relax_stroke_to_distance_ridge(
            [(x, y) for x, y, _ in stroke],
            mask,
            distance,
            raster_info,
            cfg.iterations,
            cfg.search_radius_px,
            cfg.spring_weight,
            cfg.initial_snap_radius_px,
        )
        for stroke in dense
    ]
    relaxed = _split_strokes_to_inside_segments(relaxed, outline_geom)
    robot_paths = _add_z_depth(relaxed, outline_geom, cfg)
    if not robot_paths:
        raise RobotPathError("Template matching produced no robot paths")
    fitted_2d = [[(x, y) for x, y, _ in stroke] for stroke in dense]
    return TemplateMatchDebug(
        outlines=outlines,
        fitted_template=fitted_2d,
        relaxed_template=relaxed,
        robot_paths=robot_paths,
    )


def _fit_template_text_per_glyph(
    text: str,
    font_path: str,
    font_size: int,
    template_inset_scale: float,
) -> tuple[list[Polygon], list[list[Point2]]]:
    outlines: list[Polygon] = []
    fitted: list[list[Point2]] = []
    cursor_x = 0.0
    props = FontProperties(fname=str(font_path))

    for raw_char in text:
        if raw_char.isspace():
            cursor_x += font_size * 0.35
            continue
        glyph_polygons, glyph_bounds, advance = _glyph_outline_at_cursor(raw_char, props, font_size, cursor_x)
        try:
            template = _single_line_text_strokes(raw_char)
        except ValueError:
            cursor_x += advance
            continue

        if glyph_polygons:
            outlines.extend(glyph_polygons)
            fitted.extend(_fit_template_to_bounds(template, glyph_bounds, template_inset_scale))
        cursor_x += advance

    if not outlines or not fitted:
        raise RobotPathError(f"No template glyph strokes were generated for {text!r}")
    return outlines, fitted


def _glyph_outline_at_cursor(
    char: str,
    props: FontProperties,
    font_size: int,
    cursor_x: float,
) -> tuple[list[Polygon], tuple[float, float, float, float], float]:
    path = TextPath((cursor_x, 0.0), char, size=float(font_size), prop=props)
    rings = [
        [(float(x), float(y)) for x, y in polygon]
        for polygon in path.to_polygons()
        if len(polygon) >= 3
    ]
    polygons = rings_to_polygons(rings) if rings else []
    if polygons:
        bounds = MultiPolygon(polygons).bounds
    else:
        bounds = (cursor_x, 0.0, cursor_x + font_size * 0.5, font_size)

    bbox = path.get_extents()
    advance = max(float(bbox.width) * 1.08, font_size * 0.28)
    return polygons, bounds, advance


def _fit_template_to_bounds(
    strokes: list[list[Point2]],
    bounds: tuple[float, float, float, float],
    inset_scale: float = 1.0,
) -> list[list[Point2]]:
    points = [point for stroke in strokes for point in stroke]
    min_tx = min(x for x, _ in points)
    max_tx = max(x for x, _ in points)
    min_ty = min(y for _, y in points)
    max_ty = max(y for _, y in points)
    min_x, min_y, max_x, max_y = bounds
    template_width = max(max_tx - min_tx, 1e-9)
    template_height = max(max_ty - min_ty, 1e-9)
    target_width = max(max_x - min_x, 1e-9)
    target_height = max(max_y - min_y, 1e-9)
    scale_x = target_width / template_width
    scale_y = target_height / template_height
    source_center = ((min_tx + max_tx) / 2.0, (min_ty + max_ty) / 2.0)
    target_center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
    dx = target_center[0] - source_center[0]
    dy = target_center[1] - source_center[1]

    fitted = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        line = LineString(stroke)
        line = shapely_scale(line, xfact=scale_x, yfact=scale_y, origin=source_center)
        line = shapely_translate(line, xoff=dx, yoff=dy)
        if inset_scale > 0 and inset_scale != 1.0:
            line = shapely_scale(line, xfact=inset_scale, yfact=inset_scale, origin=target_center)
        fitted.append([(float(x), float(y)) for x, y in line.coords])
    return fitted


def _relax_stroke_to_distance_ridge(
    stroke: list[Point2],
    mask: np.ndarray,
    distance: np.ndarray,
    raster_info,
    iterations: int,
    search_radius_px: int,
    spring_weight: float,
    initial_snap_radius_px: int = 45,
) -> list[Point2]:
    pixels = np.array([_world_to_pixel(point, raster_info) for point in stroke], dtype=float)
    rows, cols = mask.shape
    search_radius_px = max(1, int(search_radius_px))
    ridge_pixels = np.argwhere(distance > 0)
    pixels = _snap_pixels_to_ridge(pixels, ridge_pixels, mask, distance, int(initial_snap_radius_px))

    for _ in range(max(0, int(iterations))):
        updated = pixels.copy()
        for index in range(len(pixels)):
            row, col = pixels[index]
            anchor = pixels[index]
            if 0 < index < len(pixels) - 1:
                anchor = (pixels[index - 1] + pixels[index + 1]) / 2.0
            best = pixels[index]
            best_score = -1e18
            row0 = int(round(row))
            col0 = int(round(col))
            for dr in range(-search_radius_px, search_radius_px + 1):
                for dc in range(-search_radius_px, search_radius_px + 1):
                    rr = row0 + dr
                    cc = col0 + dc
                    if rr < 0 or rr >= rows or cc < 0 or cc >= cols or not mask[rr, cc]:
                        continue
                    ridge_score = float(distance[rr, cc])
                    spring_cost = spring_weight * hypot(rr - anchor[0], cc - anchor[1])
                    movement_cost = 0.05 * hypot(rr - row, cc - col)
                    score = ridge_score - spring_cost - movement_cost
                    if score > best_score:
                        best_score = score
                        best = np.array([float(rr), float(cc)])
            updated[index] = best
        pixels = 0.65 * pixels + 0.35 * updated

    return [pixel_to_world(float(row), float(col), raster_info) for row, col in pixels]


def _snap_pixels_to_ridge(
    pixels: np.ndarray,
    ridge_pixels: np.ndarray,
    mask: np.ndarray,
    distance: np.ndarray,
    max_radius_px: int,
) -> np.ndarray:
    if len(ridge_pixels) == 0 or max_radius_px <= 0:
        return pixels
    snapped = pixels.copy()
    max_radius_px = float(max_radius_px)
    rows, cols = mask.shape
    for index, pixel in enumerate(pixels):
        row = int(round(pixel[0]))
        col = int(round(pixel[1]))
        if 0 <= row < rows and 0 <= col < cols and mask[row, col] and distance[row, col] >= 1.5:
            continue
        deltas = ridge_pixels - pixel
        d2 = deltas[:, 0] * deltas[:, 0] + deltas[:, 1] * deltas[:, 1]
        candidates = np.where(d2 <= max_radius_px * max_radius_px)[0]
        if len(candidates) == 0:
            candidates = np.argsort(d2)[:1]
        best_index = max(
            candidates,
            key=lambda item: float(distance[tuple(ridge_pixels[item])]) - 0.03 * float(d2[item]) ** 0.5,
        )
        snapped[index] = ridge_pixels[best_index].astype(float)
    return snapped


def _world_to_pixel(point: Point2, raster_info) -> tuple[float, float]:
    x, y = point
    col = (x - raster_info.min_x) * raster_info.scale + raster_info.pad
    row = (raster_info.max_y - y) * raster_info.scale + raster_info.pad
    return row, col


def _add_z_depth(strokes: list[list[Point2]], outline: Polygon | MultiPolygon, cfg: TemplateMatchConfig) -> list[list[Point3]]:
    strokes = _split_strokes_to_inside_segments(strokes, outline)
    radii = []
    for stroke in strokes:
        for x, y in stroke:
            point = Point(x, y)
            radii.append(float(outline.boundary.distance(point)) if outline.contains(point) else 0.0)
    min_radius = min(radii) if radii else 0.0
    max_radius = max(radii) if radii else 1.0

    output = []
    for stroke in strokes:
        z_values = []
        for x, y in stroke:
            point = Point(x, y)
            radius = float(outline.boundary.distance(point)) if outline.contains(point) else 0.0
            z_values.append(map_radius_to_z(radius, min_radius, max_radius, cfg.z_light, cfg.z_heavy))
        z_values = smooth_z_values(z_values)
        with_z = [(x, y, z) for (x, y), z in zip(stroke, z_values)]
        with_z = moving_average_stroke(with_z, cfg.smooth_window)
        with_z = resample_stroke(with_z, cfg.output_spacing)
        if cfg.simplify_tolerance > 0:
            with_z = rdp_stroke(with_z, cfg.simplify_tolerance)
        with_z = enforce_max_z_step(with_z)
        if len(with_z) >= 2:
            output.append([(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in with_z])
    return output


def _split_strokes_to_inside_segments(
    strokes: list[list[Point2]],
    outline: Polygon | MultiPolygon,
) -> list[list[Point2]]:
    output = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        current = [_project_point_inside_outline(stroke[0], outline)]
        for raw_end in stroke[1:]:
            end = _project_point_inside_outline(raw_end, outline)
            if _segment_inside_outline(current[-1], end, outline):
                current.append(end)
                continue
            if len(current) >= 2:
                output.append(current)
            current = [end]
        if len(current) >= 2:
            output.append(current)
    return output


def _constrain_stroke_inside_outline(
    stroke: list[Point2],
    outline: Polygon | MultiPolygon,
    max_depth: int = 4,
) -> list[Point2]:
    if len(stroke) < 2:
        return stroke
    constrained = [_project_point_inside_outline(stroke[0], outline)]
    for end in stroke[1:]:
        start = constrained[-1]
        projected_end = _project_point_inside_outline(end, outline)
        constrained.extend(_inside_segment_points(start, projected_end, outline, max_depth)[1:])
    return constrained


def _inside_segment_points(
    start: Point2,
    end: Point2,
    outline: Polygon | MultiPolygon,
    depth: int,
) -> list[Point2]:
    if depth <= 0 or _segment_inside_outline(start, end, outline):
        return [start, end]
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    mid = _project_point_inside_outline(mid, outline)
    left = _inside_segment_points(start, mid, outline, depth - 1)
    right = _inside_segment_points(mid, end, outline, depth - 1)
    return left[:-1] + right


def _segment_inside_outline(start: Point2, end: Point2, outline: Polygon | MultiPolygon) -> bool:
    for index in range(0, 21):
        t = index / 20.0
        point = Point(start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
        if not outline.buffer(1e-6).contains(point):
            return False
    return True


def _project_point_inside_outline(point: Point2, outline: Polygon | MultiPolygon) -> Point2:
    shapely_point = Point(point)
    if outline.contains(shapely_point):
        return point
    nearest = None
    nearest_distance = float("inf")
    min_x, min_y, max_x, max_y = outline.bounds
    # Local grid projection is coarse but stable enough to keep the preview/path inside filled glyphs.
    span = max(max_x - min_x, max_y - min_y, 1.0)
    step = span / 160.0
    x0, y0 = point
    for radius in range(1, 12):
        offsets = range(-radius, radius + 1)
        for ox in offsets:
            for oy in offsets:
                if abs(ox) != radius and abs(oy) != radius:
                    continue
                candidate = Point(x0 + ox * step, y0 + oy * step)
                if not outline.contains(candidate):
                    continue
                dist = shapely_point.distance(candidate)
                if dist < nearest_distance:
                    nearest_distance = dist
                    nearest = candidate
        if nearest is not None:
            return (float(nearest.x), float(nearest.y))
    rp = outline.representative_point()
    return (float(rp.x), float(rp.y))
