import sys, os
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.calligraphy_parser import parse_vietnamese_text

TEXT = "phúc"
gaps_to_test = [0.15, 0.0, -0.05, -0.08, -0.12, -0.16, -0.20, -0.23]

print("=== Analyzing Spacing and Connection for word 'phúc' ===")
for gap in gaps_to_test:
    strokes = parse_vietnamese_text(TEXT, glyph_gap=gap)
    # The strokes are returned in sequence:
    # p (2 strokes: stem, bowl)
    # h (2 strokes: stem, arch)
    # u (3 strokes: bowl, stem, accent)
    # c (1 stroke: curve)
    
    # Let's extract key connection points:
    # 1. p's exit tail (last point of stroke 2)
    p_exit = strokes[1].points[-1]
    # 2. h's entry (first point of stroke 3)
    h_entry = strokes[2].points[0]
    
    # 3. h's exit tail (last point of stroke 4)
    h_exit = strokes[3].points[-1]
    # 4. u's entry (first point of stroke 5)
    u_entry = strokes[4].points[0]
    
    # 5. u's exit tail (last point of stroke 6)
    u_exit = strokes[5].points[-1]
    # 6. c's leftmost point (x-minimum of stroke 8)
    c_pts = strokes[7].points
    c_leftmost_x = min(p[0] for p in c_pts)
    c_leftmost_y = min(p[1] for p in c_pts if abs(p[0] - c_leftmost_x) < 0.05) # corresponding Y
    
    print(f"\nGap = {gap:+.3f}:")
    print(f"  p-h gap: p_exit={p_exit[0]:.2f} -> h_entry={h_entry[0]:.2f} (diff: {h_entry[0] - p_exit[0]:+.2f}, Y-diff: {h_entry[1] - p_exit[1]:+.2f})")
    print(f"  h-u gap: h_exit={h_exit[0]:.2f} -> u_entry={u_entry[0]:.2f} (diff: {u_entry[0] - h_exit[0]:+.2f}, Y-diff: {u_entry[1] - h_exit[1]:+.2f})")
    print(f"  u-c gap: u_exit={u_exit[0]:.2f} -> c_left={c_leftmost_x:.2f} (diff: {c_leftmost_x - u_exit[0]:+.2f})")
