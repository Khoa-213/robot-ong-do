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

Available actions include lines, circle, square, triangle, `tam`, `tam1`, `paper_corners`, `keyboard_text`, and `[SVG] Load and write custom SVG`.

## Load Custom SVG

Generic SVG support lives in `src/svg/svg_to_strokes.py`. It is intentionally single-stroke oriented: each accepted `<path>`, `<polyline>`, or `<line>` becomes one pen stroke, and the robot lifts the pen between strokes. It applies nested SVG transforms, samples Bezier curves, removes duplicate/nearby points, optionally smooths/resamples the stroke, fits the drawing onto the configured paper region, validates safety, and then the robot menu sends each stroke through the smooth `NewSpline` writer.

Supported inputs include:

- `<polyline>` and `<line>`
- `<path d="...">` with `M/m`, `L/l`, `H/h`, `V/v`, `C/c`, `Q/q`, `S/s`, `T/t`, and `Z/z`
- Nested `<g>` layers with `translate`, `scale`, `rotate`, `matrix`, `skewX`, and `skewY`
- `viewBox`, `width`, and `height`; if no document size exists, bounds are computed from drawable points

Public API:

```python
from src.svg.svg_to_strokes import load_svg_as_strokes, svg_strokes_to_robot_strokes

strokes = load_svg_as_strokes("assets/svg/tron.svg")
robot_strokes = svg_strokes_to_robot_strokes(
    strokes,
    paper_origin=[0, 0],
    paper_width_mm=100,
    paper_height_mm=100,
    writing_z=0,
)
```

CLI dry-run, preview, and JSON export:

```powershell
python -m src.svg.svg_to_strokes --input assets\svg\tron.svg --dry-run
python -m src.svg.svg_to_strokes --input assets\svg\tron.svg --preview
python -m src.svg.svg_to_strokes --input assets\svg\tron.svg --export-json outputs\tron_strokes.json
```

Robot menu dry-run:

```powershell
python tests\test_draw_shape_menu_raw_xmlrpc.py --shape custom_svg --svg assets\svg\tron.svg --dry-run --preview
```

Real robot motion still requires config safety flags and typed confirmation:

```powershell
python tests\test_draw_shape_menu_raw_xmlrpc.py --shape custom_svg --svg assets\svg\tron.svg
```

Filled outline SVG is rejected or ignored because it would make the robot trace contours instead of writing a centerline. Avoid `<text>`, `<rect>`, `<circle>`, `<ellipse>`, `<polygon>`, and paths with `fill` other than `none`. Closed `Z/z` paths are accepted only as intentional closed strokes and recorded in `svg_warnings`.

Key config knobs are in `config/robot_config.json` under `svg_pipeline`: `sample_step_mm`, `max_point_distance_mm`, `min_point_distance_mm`, `smoothing_enabled`, `smoothing_window`, `curve_sample_resolution`, `preserve_aspect_ratio`, `fit_width`, `fit_height`, `center_on_paper`, `offset_x`, `offset_y`, `fit_to_drawable_bounds`, `invert_y`, `allow_closed_paths`, `max_strokes`, and `max_points_per_stroke`. Keep `fit_to_drawable_bounds=true` for Inkscape files where the drawing is a small object on an A4 page; set it to `false` only when the SVG page layout itself should be preserved.

Calligraphy thickness is not read from SVG `stroke-width`. Enable `calligraphy_pressure.enabled` to vary robot Z by movement direction: downward strokes press slightly deeper, upward strokes lift slightly, and horizontal strokes stay near normal. Keep offsets small and test in dry-run first.

## Outline To Centerline

`src/outline_to_skeleton` converts filled font/SVG outlines into robot-ready single-stroke centerlines with Z-depth. The robot must not trace the outline: the outline is used only to calculate the medial axis, local radius, and brush pressure, then discarded before export.

Pipeline:

1. Outline Extraction: text plus a `.ttf/.otf` font is converted with Matplotlib/fontTools-backed paths, or closed SVG `<path>` outlines are sampled with `svgpathtools`. Shapely repairs invalid polygons and preserves holes such as `O`, `A`, `D`, `P`, `a`, `o`, and Vietnamese marks.
2. Medial Axis / Skeleton: polygons are rasterized to a binary mask and processed with `skimage.morphology.medial_axis(..., return_distance=True)`.
3. Radius To Z-depth: distance-map radius is mapped by `map_radius_to_z`; thin areas use `z_light`, thick areas use `z_heavy`. Z is smoothed and extra points are inserted when adjacent Z changes exceed `0.2mm`.
4. Export Centerline Only: skeleton pixels are traced as 8-neighborhood graph strokes, short noisy branches are filtered, strokes are ordered, smoothed, resampled, and exported as only `x/y/z` robot points.

Text demo for `Tâm`:

```powershell
python examples\test_text_to_skeleton.py
```

Outputs:

- `output/tam_centerline.svg`: debug SVG with `<path fill="none">` centerlines only.
- `output/tam_robot_path.json`: robot paths containing only `stroke_id` and `points: [{x,y,z}]`.

CLI text input:

```powershell
python -m outline_to_skeleton --text "Tâm" --font "assets/fonts/UTM ThuPhap Thien An.ttf" --out output/tam_robot_path.json --debug-svg output/tam_centerline.svg --z-light -0.5 --z-heavy -3.0 --resolution 2.0
```

CLI SVG outline input:

```powershell
python -m outline_to_skeleton --input-svg assets/input/tam_outline.svg --out output/tam_robot_path.json --debug-svg output/tam_centerline.svg --z-light -0.5 --z-heavy -3.0 --resolution 2.0
```

Debug SVG intentionally does not include the original filled outline. `show_radius=True` or `--show-radius` adds small centerline markers only for pressure inspection.

Fairino integration:

```python
from src.robot.fairino_path_adapter import execute_robot_path_json

execute_robot_path_json(
    "output/tam_robot_path.json",
    paper_origin={"x": -119.724, "y": 569.186, "z": 292.206},
    orientation=[-179.07, -0.108, -109.105],
    scale=1.0,
    safe_z=20.0,
    dry_run=True,
)
```

Set `dry_run=False`, pass `robot_ip`, and keep the existing `enable_move` plus `allow_raw_xmlrpc_motion` safety flags explicit when the robot is physically ready.

Tuning knobs:

- `font_size`: larger source outline for text conversion.
- `output_scale`: convert font/SVG units to robot millimeters.
- `z_light` / `z_heavy`: light and heavy brush pressure.
- `resolution`: raster pixels per source unit; higher preserves more detail but costs time.
- `point_spacing`, `smoothing_window`, `min_branch_length`, `simplify_tolerance`: available in `polygons_to_robot_paths` for custom callers.

Common errors:

- Font cannot be read: check the font path and file extension.
- SVG has no valid closed path outline: convert text/object to path in Inkscape/Illustrator and use filled closed contours.
- Polygon empty after repair: simplify the source outline or remove self-intersections.
- Skeleton is empty or too branchy: increase `resolution`, clean the SVG, or raise `min_branch_length`.
- Z-depth too deep: keep `z_heavy` above `-10mm` and test on dry-run first.
- Output has too many points: increase spacing or simplify tolerance.
- Y appears inverted: debug SVG uses original geometric coordinates; apply robot-coordinate flipping only in the robot adapter or paper transform layer.

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
- `src/svg/svg_to_strokes.py`: generic SVG parser, scaler, preview, JSON export, and CLI.
- `tests/test_draw_shape_menu_raw_xmlrpc.py`: main interactive menu.
- `tests/test_smooth_writing_menu.py`: focused smooth-writing tests.
