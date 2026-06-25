import sys, os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.calligraphy_parser import _LOWER_GLYPHS

fig, axes = plt.subplots(2, 2, figsize=(8, 8))

# B
ax_ref_b = axes[0, 0]
img_b = mpimg.imread('scratch/media__b.png')
ax_ref_b.imshow(img_b)
ax_ref_b.set_title("Ref B")
ax_ref_b.axis('off')

ax_glyph_b = axes[0, 1]
for s in _LOWER_GLYPHS['b']:
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    ax_glyph_b.plot(xs, ys, marker='o', linewidth=2)
ax_glyph_b.set_xlim(-0.1, 1.1)
ax_glyph_b.set_ylim(-0.2, 1.2)
ax_glyph_b.set_aspect('equal')
ax_glyph_b.grid(True)
ax_glyph_b.set_title("Current b")

# D
ax_ref_d = axes[1, 0]
img_d = mpimg.imread('scratch/media__d.png')
ax_ref_d.imshow(img_d)
ax_ref_d.set_title("Ref D")
ax_ref_d.axis('off')

ax_glyph_d = axes[1, 1]
for s in _LOWER_GLYPHS['d']:
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    ax_glyph_d.plot(xs, ys, marker='o', linewidth=2)
ax_glyph_d.set_xlim(-0.1, 1.1)
ax_glyph_d.set_ylim(-0.2, 1.2)
ax_glyph_d.set_aspect('equal')
ax_glyph_d.grid(True)
ax_glyph_d.set_title("Current d")

plt.tight_layout()
out_path = 'scratch/compare_bd.png'
plt.savefig(out_path, dpi=150)
print(f"B and D comparison plot saved to: {out_path}")
