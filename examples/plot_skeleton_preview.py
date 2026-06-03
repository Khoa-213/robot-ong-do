import argparse
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import _voronoi_skeleton

def main():
    parser = argparse.ArgumentParser(description="Plot original font outline and generated skeleton side-by-side.")
    parser.add_argument("--text", default="Tâm", help="Text to convert")
    parser.add_argument("--font", default="assets/fonts/UTM ThuPhap Thien An.ttf", help="Font path")
    parser.add_argument("--no-show", action="store_true", help="Do not show the plot window")
    args = parser.parse_args()

    # 1. Get outline polygons
    polys = text_to_outline_polygons(args.text, args.font, 200)
    geom = MultiPolygon(polys)

    # 2. Get skeleton
    strokes = _voronoi_skeleton(geom, spacing=1.0, min_branch_length=4.0)

    # 3. Plotting
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot original outline
    for poly in polys:
        # Plot exterior
        x, y = poly.exterior.xy
        ax.plot(x, y, color="#ccc", linestyle="--", linewidth=1.5, label="Outline" if "Outline" not in ax.get_legend_handles_labels()[1] else "")
        # Plot interiors (holes)
        for interior in poly.interiors:
            xi, yi = interior.xy
            ax.plot(xi, yi, color="#ccc", linestyle="--", linewidth=1.5)

    # Plot skeleton strokes
    for idx, stroke in enumerate(strokes):
        xs = [pt[0] for pt in stroke]
        ys = [pt[1] for pt in stroke]
        # Draw lines and scatter points representing individual robot target coordinates
        label = "Skeleton" if idx == 0 else ""
        ax.plot(xs, ys, color="#1f77b4", linewidth=2.0, label=label)
        ax.scatter(xs, ys, color="#d62728", s=10, zorder=3)

    ax.set_aspect("equal")
    ax.set_title(f"Font Outline & Voronoi Skeleton: '{args.text}'")
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
