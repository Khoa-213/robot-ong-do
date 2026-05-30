from __future__ import annotations

from math import hypot

import numpy as np

from .errors import SkeletonExtractionError


Pixel = tuple[int, int]


def trace_skeleton_pixels(
    skeleton: np.ndarray,
    min_branch_length_px: float = 6.0,
    max_branch_count: int = 2000,
) -> list[list[Pixel]]:
    pixels: set[Pixel] = {(int(row), int(col)) for row, col in np.argwhere(skeleton)}
    if not pixels:
        raise SkeletonExtractionError("Skeleton is empty; medial axis may be disconnected from the outline mask")

    def neighbors(pixel: Pixel) -> list[Pixel]:
        row, col = pixel
        found = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                candidate = (row + dr, col + dc)
                if candidate in pixels:
                    found.append(candidate)
        return found

    degree = {pixel: len(neighbors(pixel)) for pixel in pixels}
    starts = [pixel for pixel, value in degree.items() if value != 2]
    visited_edges: set[frozenset[Pixel]] = set()
    paths: list[list[Pixel]] = []

    def edge(a: Pixel, b: Pixel) -> frozenset[Pixel]:
        return frozenset((a, b))

    def walk(start: Pixel, nxt: Pixel) -> list[Pixel]:
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

    seed_points = starts if starts else list(pixels)
    for start in seed_points:
        for nxt in neighbors(start):
            if edge(start, nxt) in visited_edges:
                continue
            path = walk(start, nxt)
            if _pixel_length(path) >= min_branch_length_px:
                paths.append(_simplify_collinear_pixels(path))
            if len(paths) > max_branch_count:
                raise SkeletonExtractionError("Skeleton has too many branches; outline may be noisy")

    for point in pixels:
        for nxt in neighbors(point):
            if edge(point, nxt) in visited_edges:
                continue
            path = walk(point, nxt)
            if _pixel_length(path) >= min_branch_length_px:
                paths.append(_simplify_collinear_pixels(path))

    if not paths:
        raise SkeletonExtractionError("Skeleton produced no traceable strokes after short-branch filtering")
    return paths


def _pixel_length(path: list[Pixel]) -> float:
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def _simplify_collinear_pixels(path: list[Pixel]) -> list[Pixel]:
    if len(path) <= 2:
        return path
    simplified = [path[0]]
    last = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    for prev, point in zip(path[1:], path[2:]):
        direction = (point[0] - prev[0], point[1] - prev[1])
        if direction != last:
            simplified.append(prev)
            last = direction
    simplified.append(path[-1])
    return simplified
