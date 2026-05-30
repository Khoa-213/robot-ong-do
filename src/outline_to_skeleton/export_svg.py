from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


def export_debug_svg(robot_paths, output_path: str, show_radius: bool = False):
    """
    Export centerline SVG for debugging. This exports single-stroke centerlines only.
    It never exports the original outline.
    """
    points = [point for stroke in robot_paths for point in stroke]
    if not points:
        raise ValueError("robot_paths is empty")
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    pad = max(width, height) * 0.03

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="'
            f'{min_x - pad:.3f} {min_y - pad:.3f} {width + pad * 2:.3f} {height + pad * 2:.3f}">'
        ),
    ]
    for stroke in robot_paths:
        if len(stroke) < 2:
            continue
        d = f"M {stroke[0][0]:.3f} {stroke[0][1]:.3f} " + " ".join(
            f"L {point[0]:.3f} {point[1]:.3f}" for point in stroke[1:]
        )
        parts.append(
            '<path fill="none" stroke="#000000" stroke-width="1" '
            f'stroke-linecap="round" stroke-linejoin="round" d="{escape(d)}" />'
        )
        if show_radius:
            for x, y, z in stroke[:: max(1, len(stroke) // 40)]:
                radius = max(0.4, abs(float(z)))
                parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}" fill="none" stroke="#d44" stroke-width="0.2" />')
    parts.append("</svg>")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
