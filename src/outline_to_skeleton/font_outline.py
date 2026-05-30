from __future__ import annotations

from pathlib import Path

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

from .errors import OutlineExtractionError
from .geometry import rings_to_polygons


def text_to_outline_polygons(text: str, font_path: str, font_size: int = 200):
    if not text:
        raise OutlineExtractionError("Text input is empty")

    path = Path(font_path)
    if not path.is_file():
        raise OutlineExtractionError(f"Font cannot be read: {font_path}")

    try:
        props = FontProperties(fname=str(path))
        text_path = TextPath((0.0, 0.0), text, size=float(font_size), prop=props)
        rings = [
            [(float(x), float(y)) for x, y in polygon]
            for polygon in text_path.to_polygons()
            if len(polygon) >= 3
        ]
    except Exception as exc:
        raise OutlineExtractionError(f"Font outline extraction failed for {font_path}: {exc}") from exc

    if not rings:
        raise OutlineExtractionError(f"No valid outline contours were generated for text {text!r}")
    return rings_to_polygons(rings)
