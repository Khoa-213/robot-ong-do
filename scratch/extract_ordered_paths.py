import os, sys
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from skimage.morphology import skeletonize
import networkx as nx

def extract_paths(img_path, name):
    print(f"\n==========================================")
    print(f"Extracting paths for {name} from {img_path}")
    print(f"==========================================")
    
    img = Image.open(img_path).convert('L')
    img_np = np.array(img)
    
    # Invert binary image so foreground (black) is 1
    binary = img_np < 127
    skel = skeletonize(binary)
    
    # Build NetworkX graph
    y_indices, x_indices = np.where(skel)
    points = list(zip(x_indices, y_indices))
    point_set = set(points)
    
    G = nx.Graph()
    for p in points:
        G.add_node(p)
        # Check 8-neighbors
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                neighbor = (p[0] + dx, p[1] + dy)
                if neighbor in point_set:
                    G.add_edge(p, neighbor)
                    
    # Find endpoints and junctions
    degrees = dict(G.degree())
    endpoints = [n for n, d in degrees.items() if d == 1]
    junctions = [n for n, d in degrees.items() if d > 2]
    
    print(f"Endpoints: {len(endpoints)}")
    print(f"Junctions: {len(junctions)}")
    
    # Remove junctions to find independent branches
    G_branches = G.copy()
    G_branches.remove_nodes_from(junctions)
    
    # Get connected components of branches
    components = list(nx.connected_components(G_branches))
    print(f"Found {len(components)} branches.")
    
    # Plot components
    plt.figure(figsize=(6, 6))
    
    # Normalize coordinates to glyph space
    # Target bounding box: x in [0.2, 0.8], y in [0.05, 1.05]
    all_x = [p[0] for p in points]
    all_y = [p[1] for p in points]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    w = max(max_x - min_x, 1)
    h = max(max_y - min_y, 1)
    
    def to_glyph_space(x, y):
        # Scale to fit standard glyph bounding box
        # Flip Y so y=0 is at bottom (max_y in image coordinates)
        # For d, height goes from baseline (0.12) to ascender (1.02)
        # Let's map Y-height range to [0.05, 1.0]
        gx = 0.2 + 0.6 * (x - min_x) / w
        gy = 0.05 + 0.95 * (max_y - y) / h
        return round(gx, 3), round(gy, 3)

    # For each component, order the points
    for idx, comp in enumerate(components):
        subg = G_branches.subgraph(comp)
        # Find path (should be a simple path because we removed junctions)
        # If it's a cycle or has other issues, handle it
        path_nodes = list(subg.nodes())
        if len(path_nodes) < 2:
            continue
            
        # Order path nodes from one end to another
        # Find nodes with degree <= 1 in subg
        sub_degrees = dict(subg.degree())
        sub_ends = [n for n, d in sub_degrees.items() if d <= 1]
        
        if sub_ends:
            start_node = sub_ends[0]
        else:
            start_node = path_nodes[0]
            
        ordered_path = list(nx.dfs_preorder_nodes(subg, source=start_node))
        
        # Convert to glyph coordinates
        glyph_path = [to_glyph_space(x, y) for x, y in ordered_path]
        
        # Print path info
        print(f"Branch {idx+1} ({len(glyph_path)} points):")
        # Sub-sample path to ~8 points for calligraphy parser
        step = max(len(glyph_path) // 8, 1)
        sampled_path = [glyph_path[i] for i in range(0, len(glyph_path), step)]
        if glyph_path[-1] not in sampled_path:
            sampled_path.append(glyph_path[-1])
        print(f"  Sampleed coordinates: {sampled_path}")
        
        # Plot
        g_xs = [p[0] for p in glyph_path]
        g_ys = [p[1] for p in glyph_path]
        plt.plot(g_xs, g_ys, label=f"Branch {idx+1}", marker='o', markersize=3)
        
    plt.xlim(-0.1, 1.1)
    plt.ylim(-0.2, 1.2)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.legend()
    plt.title(f"Traced Branches: {name}")
    plt.grid(True)
    plt.savefig(f"scratch/traced_{name}.png")
    plt.close()

if __name__ == '__main__':
    extract_paths('scratch/media__b.png', 'b')
    extract_paths('scratch/media__d.png', 'd')
