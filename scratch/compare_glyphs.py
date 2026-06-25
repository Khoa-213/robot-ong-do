import sys, os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.calligraphy_parser import _LOWER_GLYPHS

# Reference images from artifacts directory
brain_dir = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\8ab68182-9d81-43bc-971e-3758fddfa153"
ref_images = {
    'm': os.path.join(brain_dir, "media__1782355455833.png"), # M, N
    'n': os.path.join(brain_dir, "media__1782355455833.png"), # M, N
    'l': os.path.join(brain_dir, "media__1782355491720.png"), # L
    'k': os.path.join(brain_dir, "media__1782355505826.png"), # K
    'q': os.path.join(brain_dir, "media__1782355561905.png"), # Q
    'h': os.path.join(brain_dir, "media__1782355579786.png"), # H, B
    'b': os.path.join(brain_dir, "media__1782355579786.png"), # H, B
}

fig, axes = plt.subplots(7, 2, figsize=(10, 20))

for idx, char in enumerate(['m', 'n', 'l', 'k', 'q', 'h', 'b']):
    # Plot reference image on the left
    ax_ref = axes[idx, 0]
    img_path = ref_images[char]
    if os.path.exists(img_path):
        img = mpimg.imread(img_path)
        ax_ref.imshow(img)
        ax_ref.set_title(f"Ref {char.upper()}")
    ax_ref.axis('off')
    
    # Plot current glyph on the right
    ax_glyph = axes[idx, 1]
    strokes = _LOWER_GLYPHS[char]
    for s in strokes:
        xs = [p[0] for p in s.points]
        ys = [p[1] for p in s.points]
        ax_glyph.plot(xs, ys, marker='o', linewidth=2)
    ax_glyph.set_xlim(-0.1, 1.1)
    ax_glyph.set_ylim(-0.5, 1.2)
    ax_glyph.set_aspect('equal')
    ax_glyph.grid(True)
    ax_glyph.set_title(f"Current {char}")

plt.tight_layout()
out_path = os.path.join(brain_dir, "compare_glyphs.png")
plt.savefig(out_path, dpi=150)
print(f"Comparison plot saved to: {out_path}")
