import sys
from pathlib import Path
import numpy as np
from math import atan2, pi, hypot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outline_to_skeleton.font_outline import text_to_outline_polygons
from src.outline_to_skeleton.skeletonize import polygons_to_robot_paths
from shapely.geometry import MultiPolygon

def angle_between_vectors(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    return abs(atan2(det, dot))

def split_stroke_at_sharp_turns(stroke, angle_threshold_deg=50, k=2):
    if len(stroke) <= 2 * k:
        return [stroke]
    
    threshold_rad = angle_threshold_deg * pi / 180.0
    splits = [0]
    
    for i in range(k, len(stroke) - k):
        # Vector before i
        v1 = (stroke[i][0] - stroke[i-k][0], stroke[i][1] - stroke[i-k][1])
        # Vector after i
        v2 = (stroke[i+k][0] - stroke[i][0], stroke[i+k][1] - stroke[i][1])
        
        len1 = hypot(*v1)
        len2 = hypot(*v2)
        if len1 < 1e-6 or len2 < 1e-6:
            continue
            
        angle = angle_between_vectors(v1, v2)
        if angle > threshold_rad:
            splits.append(i)
            
    splits.append(len(stroke))
    
    parts = []
    for start, end in zip(splits, splits[1:]):
        part = stroke[start:end]
        # Adjust overlap at split points
        if start > 0 and len(parts) > 0:
            # include the split point in both to ensure they connect visually if needed
            parts[-1] = parts[-1] + [stroke[start]]
        if len(part) >= 2:
            parts.append(part)
            
    return parts if parts else [stroke]

def merge_collinear_strokes(strokes, dist_threshold=5.0, angle_threshold_deg=35, k=2):
    remaining = [list(s) for s in strokes if len(s) >= 2]
    merged_any = True
    
    threshold_rad = angle_threshold_deg * pi / 180.0
    
    while merged_any:
        merged_any = False
        n = len(remaining)
        best_pair = None
        best_score = float('inf')
        best_merge_type = None # 'start-start', 'end-start', etc.
        
        for i in range(n):
            for j in range(i + 1, n):
                s1 = remaining[i]
                s2 = remaining[j]
                
                # Check 4 endpoint combinations
                endpoints = [
                    (s1[-1], s2[0], 'end-start', s1, s2, False, False),
                    (s1[0], s2[-1], 'start-end', s1, s2, True, True),
                    (s1[-1], s2[-1], 'end-end', s1, s2, False, True),
                    (s1[0], s2[0], 'start-start', s1, s2, True, False)
                ]
                
                for p1, p2, mtype, stroke1, stroke2, rev1, rev2 in endpoints:
                    d = hypot(p1[0] - p2[0], p1[1] - p2[1])
                    if d < dist_threshold:
                        # Compute tangent vectors at connection
                        # For stroke 1 endpoint
                        if not rev1:
                            t1 = (stroke1[-1][0] - stroke1[-min(len(stroke1), k)][0], stroke1[-1][1] - stroke1[-min(len(stroke1), k)][1])
                        else:
                            t1 = (stroke1[0][0] - stroke1[min(len(stroke1), k)-1][0], stroke1[0][1] - stroke1[min(len(stroke1), k)-1][1])
                            
                        # For stroke 2 endpoint
                        if not rev2:
                            t2 = (stroke2[min(len(stroke2), k)-1][0] - stroke2[0][0], stroke2[min(len(stroke2), k)-1][1] - stroke2[0][1])
                        else:
                            t2 = (stroke2[-1][0] - stroke2[-min(len(stroke2), k)][0], stroke2[-1][1] - stroke2[-min(len(stroke2), k)][1])
                            # If rev2 is True, the stroke is reversed, so the flow is away from the connection point
                            t2 = (-t2[0], -t2[1])
                            
                        l1 = hypot(*t1)
                        l2 = hypot(*t2)
                        if l1 < 1e-6 or l2 < 1e-6:
                            continue
                            
                        # If distance is extremely small (e.g. < 2.0 pixels), or if one stroke is very short
                        # (serif), relax the angle threshold significantly.
                        len1 = sum(hypot(stroke1[a+1][0]-stroke1[a][0], stroke1[a+1][1]-stroke1[a][1]) for a in range(len(stroke1)-1))
                        len2 = sum(hypot(stroke2[a+1][0]-stroke2[a][0], stroke2[a+1][1]-stroke2[a][1]) for a in range(len(stroke2)-1))
                        is_serif = len1 < 25.0 or len2 < 25.0
                        
                        angle = angle_between_vectors(t1, t2)
                        effective_angle_threshold = threshold_rad
                        if d < 2.0:
                            effective_angle_threshold = 95 * pi / 180.0
                        elif is_serif:
                            effective_angle_threshold = 75 * pi / 180.0
                            
                        if angle < effective_angle_threshold:
                            # Collinear or serif!
                            score = d + angle * 5.0 # combine distance and angle
                            if score < best_score:
                                best_score = score
                                best_pair = (i, j, rev1, rev2)
                                best_merge_type = mtype

                                
        if best_pair is not None:
            i, j, rev1, rev2 = best_pair
            s1 = remaining[i]
            s2 = remaining[j]
            
            # Perform merge
            part1 = list(reversed(s1)) if rev1 else list(s1)
            part2 = list(reversed(s2)) if rev2 else list(s2)
            
            # Combine
            merged = part1 + part2[1:]
            
            # Update remaining list
            remaining.pop(max(i, j))
            remaining.pop(min(i, j))
            remaining.append(merged)
            merged_any = True
            
    return remaining

# Test
polys = text_to_outline_polygons("Nhẫn", "C:/Windows/Fonts/times.ttf", 200)
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

print(f"Original paths count: {len(paths)}")

# Step 1: Split
split_paths = []
for p in paths:
    split_paths.extend(split_stroke_at_sharp_turns(p, angle_threshold_deg=50, k=2))
print(f"Paths count after split: {len(split_paths)}")

# Step 2: Merge
merged_paths = merge_collinear_strokes(split_paths, dist_threshold=5.0, angle_threshold_deg=35, k=2)
print(f"Paths count after merge: {len(merged_paths)}")

for idx, stroke in enumerate(merged_paths):
    xs = [pt[0] for pt in stroke]
    ys = [pt[1] for pt in stroke]
    print(f"Stroke {idx}: points={len(stroke)} X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]")
