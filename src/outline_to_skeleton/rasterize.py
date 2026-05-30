from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from skimage.draw import polygon as draw_polygon


@dataclass(frozen=True)
class RasterInfo:
    min_x: float
    max_y: float
    scale: float
    pad: int
    width: int
    height: int


def rasterize_polygons(polygons: list[Polygon] | MultiPolygon, resolution: float = 2.0):
    if resolution <= 0:
        raise ValueError("resolution must be positive")

    geoms = list(polygons.geoms) if isinstance(polygons, MultiPolygon) else list(polygons)
    min_x, min_y, max_x, max_y = MultiPolygon(geoms).bounds
    scale = float(resolution)
    pad = max(4, int(ceil(scale * 4)))
    width = max(3, int(ceil((max_x - min_x) * scale)) + pad * 2 + 1)
    height = max(3, int(ceil((max_y - min_y) * scale)) + pad * 2 + 1)
    mask = np.zeros((height, width), dtype=bool)

    for poly in geoms:
        _burn_ring(mask, poly.exterior.coords, min_x, max_y, scale, pad, True)
        for interior in poly.interiors:
            _burn_ring(mask, interior.coords, min_x, max_y, scale, pad, False)

    return mask, RasterInfo(min_x=min_x, max_y=max_y, scale=scale, pad=pad, width=width, height=height)


def pixel_to_world(row: int | float, col: int | float, info: RasterInfo) -> tuple[float, float]:
    x = info.min_x + (float(col) - info.pad) / info.scale
    y = info.max_y - (float(row) - info.pad) / info.scale
    return x, y


def _burn_ring(mask, coords, min_x: float, max_y: float, scale: float, pad: int, value: bool) -> None:
    cols = []
    rows = []
    for x, y in coords:
        cols.append((float(x) - min_x) * scale + pad)
        rows.append((max_y - float(y)) * scale + pad)
    rr, cc = draw_polygon(np.array(rows), np.array(cols), shape=mask.shape)
    mask[rr, cc] = value
