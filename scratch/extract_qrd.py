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
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                neighbor = (p[0] + dx, p[1] + dy)
                if neighbor in point_set:
                    G.add_edge(p, neighbor)
                    
    degrees = dict(G.degree())
    endpoints = [n for n, d in degrees.items() if d == 1]
    junctions = [n for n, d in degrees.items() if d > 2]
    
    print(f"Endpoints: {len(endpoints)}")
    print(f"Junctions: {len(junctions)}")
    
    # Segment branches
    G_branches = G.copy()
    G_branches.remove_nodes_from(junctions)
    components = list(nx.connected_components(G_branches))
    print(f"Found {len(components)} branches.")
    
    all_x = [p[0] for p in points]
    all_y = [p[1] for p in points]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    w = max(max_x - min_x, 1)
    h = max(max_y - min_y, 1)
    
    def to_glyph_space(x, y):
        # We normalize: x to [0.15, 0.85] or similar, y to fit standard ascender/descender ranges.
        # For r: y goes from baseline (0.12) to x-height (0.62)
        # For d: y goes from baseline (0.08) to ascender (1.02)
        # For q: y goes from descender (-0.35) to x-height (0.62)
        # Let's map normalized coordinates depending on character:
        gx = 0.2 + 0.6 * (x - min_x) / w
        
        # We flip Y so that top of image is max Y (which is 1.05 for ascenders, 0.62 for regular).
        # We need a proper scaling factor for each letter:
        if name == 'q':
            # y range in glyph: [-0.35, 0.62] -> total height = 0.97
            gy = -0.35 + 0.97 * (max_y - y) / h
        elif name == 'd':
            # y range in glyph: [0.08, 1.05] -> total height = 0.97
            gy = 0.08 + 0.97 * (max_y - y) / h
        else: # r
            # y range in glyph: [0.12, 0.62] -> total height = 0.50
            gy = 0.12 + 0.50 * (max_y - y) / h
            
        return round(gx, 3), round(gy, 3)

    for idx, comp in enumerate(components):
        subg = G_branches.subgraph(comp)
        path_nodes = list(subg.nodes())
        if len(path_nodes) < 2:
            continue
            
        sub_degrees = dict(subg.degree())
        sub_ends = [n for n, d in sub_degrees.items() if d <= 1]
        start_node = sub_ends[0] if sub_ends else path_nodes[0]
        
        ordered_path = list(nx.dfs_preorder_nodes(subg, source=start_node))
        glyph_path = [to_glyph_space(x, y) for x, y in ordered_path]
        
        # Sort or trace direction
        # If it's a stem, order it from top to bottom
        # Let's check coordinates
        ys = [p[1] for p in glyph_path]
        if len(ys) > 5 and ys[0] < ys[-1] and (name == 'd' or name == 'q'):
            # Reverse vertical stems to go from top to bottom
            glyph_path.reverse()
            
        print(f"Branch {idx+1} ({len(glyph_path)} points):")
        step = max(len(glyph_path) // 8, 1)
        sampled_path = [glyph_path[i] for i in range(0, len(glyph_path), step)]
        if glyph_path[-1] not in sampled_path:
            sampled_path.append(glyph_path[-1])
        print(f"  Sampled coordinates: {sampled_path}")

if __name__ == '__main__':
    extract_paths('scratch/media__q2.png', 'q')
    extract_paths('scratch/media__r2.png', 'r')
    extract_paths('scratch/media__d2.png', 'd')
