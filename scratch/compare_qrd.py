import sys, os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.calligraphy_parser import _LOWER_GLYPHS

fig, axes = plt.subplots(3, 2, figsize=(8, 12))

# Q
ax_ref_q = axes[0, 0]
img_q = mpimg.imread('scratch/media__q2.png')
ax_ref_q.imshow(img_q)
ax_ref_q.set_title("Ref Q")
ax_ref_q.axis('off')

ax_glyph_q = axes[0, 1]
for s in _LOWER_GLYPHS['q']:
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    ax_glyph_q.plot(xs, ys, marker='o', linewidth=2)
ax_glyph_q.set_xlim(-0.1, 1.1)
ax_glyph_q.set_ylim(-0.5, 1.2)
ax_glyph_q.set_aspect('equal')
ax_glyph_q.grid(True)
ax_glyph_q.set_title("Current q")

# R
ax_ref_r = axes[1, 0]
img_r = mpimg.imread('scratch/media__r2.png')
ax_ref_r.imshow(img_r)
ax_ref_r.set_title("Ref R")
ax_ref_r.axis('off')

ax_glyph_r = axes[1, 1]
for s in _LOWER_GLYPHS['r']:
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    ax_glyph_r.plot(xs, ys, marker='o', linewidth=2)
ax_glyph_r.set_xlim(-0.1, 1.1)
ax_glyph_r.set_ylim(-0.2, 1.2)
ax_glyph_r.set_aspect('equal')
ax_glyph_r.grid(True)
ax_glyph_r.set_title("Current r")

# D
ax_ref_d = axes[2, 0]
img_d = mpimg.imread('scratch/media__d2.png')
ax_ref_d.imshow(img_d)
ax_ref_d.set_title("Ref D")
ax_ref_d.axis('off')

ax_glyph_d = axes[2, 1]
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
out_path = 'scratch/compare_qrd.png'
plt.savefig(out_path, dpi=150)
print(f"Q, R, D comparison plot saved to: {out_path}")
