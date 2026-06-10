import argparse
import sys
from pathlib import Path
from math import hypot
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths


# ── Helpers to replicate robot post-processing in pixel space ─────────

def _xy_dist(a, b) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _stroke_length_2d(stroke) -> float:
    return sum(_xy_dist(a, b) for a, b in zip(stroke, stroke[1:]))


def _prune_short_px(strokes, min_len_px):
    return [s for s in strokes if len(s) >= 2 and _stroke_length_2d(s) >= min_len_px]


def _connect_nearby_px(strokes, max_gap_px):
    if max_gap_px <= 0 or len(strokes) <= 1:
        return [list(s) for s in strokes]
    remaining = [list(s) for s in strokes if len(s) >= 2]
    connected = []
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed and remaining:
            changed = False
            best_i, best_rev, best_d = -1, False, max_gap_px
            for i, s in enumerate(remaining):
                d0 = _xy_dist(current[-1], s[0])
                d1 = _xy_dist(current[-1], s[-1])
                if d0 <= best_d:
                    best_i, best_rev, best_d = i, False, d0
                if d1 <= best_d:
                    best_i, best_rev, best_d = i, True, d1
            if best_i >= 0:
                nxt = remaining.pop(best_i)
                if best_rev:
                    nxt.reverse()
                current.extend(nxt)
                changed = True
        connected.append(current)
    return connected


def _trim_start_px(stroke, trim_px):
    remaining = float(trim_px)
    for i, (a, b) in enumerate(zip(stroke, stroke[1:])):
        seg = _xy_dist(a, b)
        if seg <= 1e-9:
            continue
        if remaining < seg:
            t = remaining / seg
            interp = tuple(a[ax] + (b[ax] - a[ax]) * t for ax in range(len(a)))
            return [interp] + list(stroke[i + 1:])
        remaining -= seg
    return []


def _trim_ends_px(strokes, trim_px):
    if trim_px <= 0:
        return [list(s) for s in strokes]
    result = []
    for s in strokes:
        s2 = _trim_start_px(s, trim_px)
        if not s2:
            continue
        s2 = list(reversed(_trim_start_px(list(reversed(s2)), trim_px)))
        if len(s2) >= 2:
            result.append(s2)
    return result


def main():
    parser = argparse.ArgumentParser(description="Plot original font outline and generated skeleton side-by-side.")
    parser.add_argument("--text", default="Tâm", help="Text to convert")
    parser.add_argument("--font", default="assets/fonts/UTM ThuPhap Thien An.ttf", help="Font path")
    parser.add_argument("--no-show", action="store_true", help="Do not show the plot window")
    args = parser.parse_args()

    # 1. Get outline polygons & robot paths
    polys = text_to_outline_polygons(args.text, args.font, 200)
    geom = MultiPolygon(polys)
    paths = polygons_to_robot_paths(
        geom,
        resolution=2.0,
        z_light=-0.5,
        z_heavy=-3.0,
        point_spacing=1.0,
        min_branch_length=4.0,
        simplify_tolerance=0.05,
        theta=1.5,
    )

    if not paths:
        print("[Preview] No strokes generated!")
        return

    # 2. Estimate bounding box for pixel -> mm scaling
    all_pts = [pt for s in paths for pt in s]
    min_x = min(pt[0] for pt in all_pts)
    max_x = max(pt[0] for pt in all_pts)
    min_y = min(pt[1] for pt in all_pts)
    max_y = max(pt[1] for pt in all_pts)
    px_w = max(max_x - min_x, 1.0)
    px_h = max(max_y - min_y, 1.0)

    # Robot uses fit_width_mm=90, fit_height_mm=80
    scale_mm_per_px = min(90.0 / px_w, 80.0 / px_h)

    # 3. Apply Y inversion to match robot drawing
    def inv_y(stroke):
        return [(x, min_y + max_y - y, z) for x, y, z in stroke]

    inverted = [inv_y(s) for s in paths]

    # 4. Apply post-processing equivalent to robot (in pixel space)
    PRUNE_MM, CONNECT_MM, TRIM_MM = 8.0, 2.0, 1.0
    prune_px = PRUNE_MM / scale_mm_per_px
    connect_px = CONNECT_MM / scale_mm_per_px
    trim_px = TRIM_MM / scale_mm_per_px

    processed = _prune_short_px(inverted, prune_px)
    processed = _connect_nearby_px(processed, connect_px)
    processed = _trim_ends_px(processed, trim_px)

    # 5. Plotting
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot original outline (also inverted)
    for poly in polys:
        ox, oy = poly.exterior.xy
        oy_inv = [min_y + max_y - yi for yi in oy]
        ax.plot(ox, oy_inv, color="#ccc", linestyle="--", linewidth=1.5, label="Outline" if "Outline" not in ax.get_legend_handles_labels()[1] else "")
        for interior in poly.interiors:
            xi, yi = interior.xy
            yi_inv = [min_y + max_y - yii for yii in yi]
            ax.plot(xi, yi_inv, color="#ccc", linestyle="--", linewidth=1.5)

    # Plot skeleton strokes
    for idx, stroke in enumerate(processed):
        xs = [pt[0] for pt in stroke]
        ys = [pt[1] for pt in stroke]
        label = "Skeleton" if idx == 0 else ""
        ax.plot(xs, ys, color="#1f77b4", linewidth=2.0, label=label)
        ax.scatter(xs, ys, color="#d62728", s=15, zorder=3)

    ax.set_aspect("equal")
    ax.set_title(
        f"Robot Skeleton Preview: '{args.text}'\n"
        f"[invert_y ✓  |  prune {PRUNE_MM} mm  |  connect {CONNECT_MM} mm  |  trim {TRIM_MM} mm]"
    )
    ax.legend()
    plt.tight_layout()
    
    # Save preview image
    output_img = ROOT / "output" / "skeleton_visual_preview.png"
    output_img.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_img, dpi=150)
    print(f"Saved visual preview to: {output_img}")
    
    # Show the plot
    if not args.no_show:
        plt.show()

if __name__ == "__main__":
    main()

