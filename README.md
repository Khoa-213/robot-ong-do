# robot-ong-do

Python demo for a Fairino FR3/FR5 robot that writes Vietnamese calligraphy from SVG files, built-in shapes, or keyboard text.

## Pipeline

```text
SVG/text/shape
-> sample into strokes
-> fit into measured paper corners
-> validate workspace and paper safe zone
-> plan smooth stroke trajectory
-> send Fairino motion command
```

## Smooth Writing Mode

The smooth path is the default for the main shape menu. It avoids writing by blocking at every waypoint.

Current strategy:

- Each character/stroke is kept as a continuous list of poses.
- The pen only lifts between strokes, not between points in the same stroke.
- The planner removes duplicated points, lightly smooths the path, resamples by fixed mm spacing, and slows down at sharp corners.
- The Fairino controller uses `NewSplineStart`, `NewSplinePoint`, and `NewSplineEnd` for each stroke.
- If `NewSpline` fails on the real controller, the code can fall back to `MoveL` with `blendR`.

Main config lives in `config/robot_config.json`:

- `motion_strategy.mode`: use `new_spline` for smooth writing.
- `smooth_writing.writing_speed_mm_s`: writing speed.
- `smooth_writing.travel_speed_mm_s`: speed while moving above paper.
- `smooth_writing.point_spacing_mm`: planned distance between points.
- `smooth_writing.smoothing_tolerance`: RDP simplification tolerance.
- `smooth_writing.blend_radius_mm`: blend radius for fallback and spline points.
- `text_demo.travel_z_offset`: pen lift height between strokes.
- `paper.paper_z`: writing height.
- `before_draw.start_pose` and `after_draw.return_pose`: safe start/end pose.

Tuning guide:

- Robot shakes or corners are too harsh: lower `writing_speed_mm_s`, lower `blend_radius_mm`, or increase `corner_slowdown_angle_deg`.
- Robot is too slow: raise `writing_speed_mm_s` gradually, for example 12 -> 15 -> 18.
- Letter shape looks distorted: lower `smoothing_tolerance` and lower `point_spacing_mm`.
- Motion still looks dotted: use `motion_strategy.mode = "new_spline"` and keep `point_spacing_mm` around `0.8` to `1.2`.
- Pen presses too hard: raise `paper.paper_z` slightly or increase `z_safety.z_lift_offset`.
- Pen does not touch paper: lower `paper.paper_z` slightly.

## Run

Dry-run validation, no robot motion:

```powershell
python tests\test_smooth_writing_menu.py --test line_50mm
python tests\test_smooth_writing_menu.py --test oval
python tests\test_smooth_writing_menu.py --test bezier
python tests\test_draw_shape_menu_raw_xmlrpc.py --shape keyboard_text --text "Tâm" --dry-run
```

Real robot motion requires the safety flags in `config/robot_config.json` and a typed confirmation:

```powershell
python tests\test_smooth_writing_menu.py --test line_50mm --apply
python tests\test_draw_shape_menu_raw_xmlrpc.py --shape keyboard_text --text "Tâm"
```

To skip the prompt only when the robot is physically ready:

```powershell
python tests\test_smooth_writing_menu.py --test line_50mm --apply --yes
```

## Shape Menu

```powershell
python tests\test_draw_shape_menu_raw_xmlrpc.py
```

Available actions include lines, circle, square, triangle, `tam`, `tam1`, `paper_corners`, and `keyboard_text`.

## Safety

- Always test with `--dry-run` first.
- Validate the four paper corners and `paper.paper_z` before touching paper.
- Keep `enable_robot_move` and `connection_policy.allow_raw_xmlrpc_motion` disabled unless the robot is clear and ready.
- The script validates workspace and paper polygon before motion.
- Real motion asks for `RUN` before sending commands unless `--yes` is used.
- Do not increase speed aggressively; tune in small steps.

## Important Files

- `config/robot_config.json`: robot, paper, Z height, and smooth writing parameters.
- `modules/trajectory_planner.py`: stroke cleanup, smoothing, resampling, and corner speed profiling.
- `modules/fairino_raw_controller.py`: Fairino raw XML-RPC and smooth `NewSpline` execution.
- `modules/text_trajectory.py`: keyboard text and calligraphy-style single-line glyphs.
- `modules/svg_trajectory.py`: SVG path sampling.
- `tests/test_draw_shape_menu_raw_xmlrpc.py`: main interactive menu.
- `tests/test_smooth_writing_menu.py`: focused smooth-writing tests.
