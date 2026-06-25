import os, sys
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from skimage.morphology import skeletonize
from scipy.interpolate import splprep, splev

def trace_image(img_path, name):
    print(f"\nTracing {name} from {img_path}...")
    # Load image and convert to grayscale
    img = Image.open(img_path).convert('L')
    img_np = np.array(img)
    
    # Binarize (black ink is foreground, so invert)
    # Adjust threshold if needed
    thresh = 127
    binary = img_np < thresh
    
    if not np.any(binary):
        print("No foreground found!")
        return
        
    # Skeletonize
    skel = skeletonize(binary)
    
    # Get coordinates of skeleton points
    y_coords, x_coords = np.where(skel)
    
    # Scale coordinates to [0, 1] range
    # In image coordinates, y increases downwards, so we flip y: y_norm = 1.0 - (y - min_y) / height
    min_x, max_x = np.min(x_coords), np.max(x_coords)
    min_y, max_y = np.min(y_coords), np.max(y_coords)
    
    w = max(max_x - min_x, 1)
    h = max(max_y - min_y, 1)
    
    # Standardize scale: we want the glyph to fit within [0.1, 0.9] of our coordinate space.
    # For b: height is standard ascender height (baseline to 1.05). Let's scale accordingly.
    xs_norm = 0.2 + 0.6 * (x_coords - min_x) / w
    ys_norm = 0.05 + 0.95 * (max_y - y_coords) / h
    
    # Let's find endpoints/path sequence. Since skeleton might have branches,
    # let's sort points from top to bottom or do a simple distance-based traveler.
    points = list(zip(xs_norm, ys_norm))
    
    # Just print the range and count for debugging
    print(f"Skeleton has {len(points)} points. X range: [{np.min(xs_norm):.2f}, {np.max(xs_norm):.2f}], Y range: [{np.min(ys_norm):.2f}, {np.max(ys_norm):.2f}]")
    
    # Let's write a simple path tracer that orders points
    # Start at one end (e.g. top of the stem) and find the next nearest point.
    # For b, we have a straight vertical stem and a bowl.
    # Let's save a plot of the skeleton points
    plt.figure()
    plt.scatter(xs_norm, ys_norm, c=ys_norm, cmap='viridis')
    plt.title(f"Skeleton of {name}")
    plt.colorbar(label='Y normalized')
    plt.gca().set_aspect('equal', adjustable='box')
    plt.savefig(f"scratch/skel_{name}.png")
    plt.close()

if __name__ == '__main__':
    trace_image('scratch/media__b.png', 'b')
    trace_image('scratch/media__d.png', 'd')
