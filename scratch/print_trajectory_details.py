import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
json_path = ROOT / "output" / "nhan_run" / "run_20260624_115328" / "robot_trajectory.json"

if not json_path.exists():
    # search for latest folder
    dirs = sorted(Path(ROOT / "output" / "nhan_run").glob("run_*"))
    if dirs:
        json_path = dirs[-1] / "robot_trajectory.json"

print(f"Reading from: {json_path}")
d = json.loads(json_path.read_text(encoding="utf-8"))

stroke_pts = {}
for p in d["points"]:
    if p["motion_type"] == "DRAW":
        stroke_pts.setdefault(p["stroke_id"], []).append(p)

for sid, pts in sorted(stroke_pts.items()):
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    print(f"Stroke {sid}: pts={len(pts)} X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]")
