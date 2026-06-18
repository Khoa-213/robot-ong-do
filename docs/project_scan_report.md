# Project Scan Report

Generated: 2026-06-17

## Current Architecture

This project is an existing Python robot-writing stack for a Fairino FR3/FR5 robot. It already supports keyboard text, SVG paths, built-in geometric shapes, measured-paper coordinate transforms, workspace validation, dry-run flows, and smooth robot execution through the Fairino SDK.

Main entry points and surfaces:

- `main.py`: lightweight Streamlit launcher.
- `src/ui/app_streamlit.py`: Streamlit UI module.
- `src/api/app.py` and `src/api/routers/*`: FastAPI service layer for robot, trajectory, config, health, and safety endpoints.
- `tests/test_draw_shape_menu_raw_xmlrpc.py`: main interactive/manual robot writing menu.
- `tests/test_smooth_writing_menu.py`: focused smooth-writing manual tests.
- `examples/test_keyboard_text_to_robot.py`, `examples/test_text_to_skeleton.py`, `examples/run_centerline_robot_path.py`: example flows for text and skeleton pipelines.

Important packages/modules:

- `src/outline_to_skeleton/*`: existing outline-to-centerline pipeline.
- `src/svg/svg_to_strokes.py` and `src/svg_processing/*`: SVG parsing, sampling, and trajectory building.
- `modules/text_trajectory.py`: keyboard text and font-derived single-line paths used by existing demos.
- `modules/svg_trajectory.py`: SVG path sampling and paper fitting.
- `modules/paper_zone.py`: measured paper corners, normalized UV mapping, and paper guard helpers.
- `modules/safety_check.py` and `src/safety/safety_check.py`: workspace and measured-paper validation.
- `modules/trajectory_planner.py`: duplicate removal, RDP simplification, moving-average smoothing, arc-length resampling, corner speed factors, and max-point limiting.
- `modules/fairino_raw_controller.py`: raw XML-RPC Fairino motion, `NewSpline` smooth writing, MoveL fallback, paper guard, and emergency stop fallback.
- `src/robot/fairino_path_adapter.py`: converts centerline robot path JSON into measured-paper Fairino poses and executes dry-run/apply flows.
- `src/services/robot_service.py`: service orchestration for shape, SVG, text, and skeleton text robot drawing.

## Existing Robot SDK

The bundled SDK is Fairino:

- `fairino-python-sdk/windows/fairino/Robot.py`
- `fairino-python-sdk/linux/fairino/Robot.py`
- Native binaries under `fairino-python-sdk/windows/libfairino` and `fairino-python-sdk/linux/libfairino`.

The SDK exposes:

- Blocking/point commands: `MoveJ`, `MoveL`, `MoveCart`.
- Continuous/smooth APIs: `SplineStart`, `SplinePTP`, `SplineEnd`, `NewSplineStart`, `NewSplinePoint`, `NewSplineEnd`.
- Servo APIs: `ServoMoveStart`, `ServoJ`, `ServoCart`, `ServoMoveEnd`.
- Uploaded trajectory demos: `TestUploadTrajectoryJ.py`.

The project currently prefers `NewSplineStart` / `NewSplinePoint` / `NewSplineEnd` for writing strokes, with fallback to blended `MoveL` where configured.

## Motion Call Sites

Project code calls or plans robot motion in:

- `modules/fairino_raw_controller.py`: primary Fairino raw XML-RPC movement implementation.
- `src/services/robot_service.py`: calls controller draw methods and validates before motion.
- `src/api/routers/robot.py`: API route for guarded `MoveL` and drawing endpoints.
- `src/robot/fairino_path_adapter.py`: dry-run/apply execution for centerline path JSON.
- `examples/*` and `tests/test_draw_*`: manual robot tests and demos.

SDK examples under `fairino-python-sdk/*/example` contain many direct `MoveL`, `MoveJ`, servo, spline, and upload-trajectory examples. These are vendor samples and should not be refactored as project behavior.

## Existing Font/SVG/Skeleton Processing

Reusable modules already exist:

- `src/outline_to_skeleton/font_outline.py`: uses Matplotlib `TextPath` with a font file to extract text outline polygons. Handles TTF/OTF through Matplotlib/font machinery.
- `src/outline_to_skeleton/svg_outline.py`: converts filled SVG outline paths into polygons.
- `src/outline_to_skeleton/skeletonize.py`: currently uses boundary sampling plus SciPy Voronoi to produce centerlines, prunes short spurs, maps local radius to Z-depth, smooths, resamples, and validates output.
- `src/outline_to_skeleton/graph_trace.py`: 8-neighbor raster skeleton pixel tracing utility.
- `src/outline_to_skeleton/path_smoothing.py`: nearest-stroke ordering, moving-average smoothing, RDP, and arc-length resampling.
- `src/outline_to_skeleton/export_robot_path.py`: exports centerline strokes as robot path JSON.
- `src/outline_to_skeleton/export_svg.py`: debug SVG export.
- `src/outline_to_skeleton/pipeline.py`: public `text_to_robot_paths` and `svg_outline_to_robot_paths`.

The README already documents this as "Outline To Centerline" and explicitly states that the robot must not trace outlines.

## Existing Coordinate and Paper Calibration

The current production path uses measured paper corners:

- `config/robot_config.json:paper.corners` stores `top_left`, `top_right`, `bottom_right`, `bottom_left`, each with a 6D pose.
- `modules/paper_zone.py` maps normalized `u/v` into robot XYZ by bilinear interpolation across measured corners.
- `src/robot/fairino_path_adapter.py` maps local centerline coordinates into measured-paper robot poses.
- `modules/safety_check.py` validates workspace and paper bounds.

This already satisfies most of the "do not assume paper is parallel" requirement because coordinates come from measured corners, not a fixed XY plane assumption.

## Configuration

Main config files:

- `config/robot_config.json`: primary robot, paper, safety, SVG, text, pressure, and smooth-writing config.
- `config/robot_config.yaml`: small legacy/simple robot config.
- `config/paper_config.yaml`: small legacy/simple paper config.
- `config/word_library.json`: word-to-SVG mapping.

`config/robot_config.json` currently has `enable_robot_move: true` and `connection_policy.allow_raw_xmlrpc_motion: true`. This is useful for a real lab setup but is risky for new generated trajectories. The new font-skeleton pipeline must default to preview-only and require explicit trajectory approval independent of these global flags.

## Current Safety Model

Existing safety controls:

- Workspace validation in `modules/safety_check.py`.
- Measured-paper polygon validation in `modules/paper_zone.py`.
- Paper guard in `FairinoRawXmlRpcController`, including stop fallbacks: `StopMotion`, `ProgramStop`, `CNDESendStop`.
- Motion flags: `enable_robot_move` and `connection_policy.allow_raw_xmlrpc_motion`.
- Manual examples usually require a typed confirmation such as `RUN` before real motion.

Safety gaps for the requested new feature:

- Existing outline-to-skeleton JSON does not carry a formal `approved` field.
- Current skeleton exports do not include a full validation report with `is_safe_to_execute`.
- Preview files do not yet include all requested layers: original font render, raw skeleton, cleaned skeleton, pen-up travel, coordinate labels, safe zone, CSV, and validation JSON.
- Existing robot execution can run from older demos when config flags are already enabled; the new pipeline must add a stricter per-trajectory approval gate.

## Modules to Reuse

- Reuse `src/outline_to_skeleton` for outline extraction, centerline generation, smoothing, and stroke ordering.
- Reuse `modules/trajectory_planner.py` for stroke cleanup, smoothing, resampling, and corner speed profiling where robot poses are involved.
- Reuse `modules/paper_zone.py` and `src/robot/fairino_path_adapter.py` for measured-paper conversion.
- Reuse `modules/fairino_raw_controller.py` for `NewSpline` execution and paper guard.
- Reuse config from `config/robot_config.json` for paper corners, Z heights, velocities, blend radius, and workspace limits.
- Reuse `assets/fonts/UTM ThuPhap Thien An.ttf` for a local Vietnamese-capable font test.

## Modules Needing Changes or Additions

Recommended additions:

- A new high-level pipeline module to produce a full run directory under `outputs/run_YYYYMMDD_HHMMSS`.
- Dataclasses for `TrajectoryPoint`, `Stroke`, `FontSimilarityMetrics`, validation result, and run artifacts.
- A preview renderer/exporter that creates PNG, SVG, CSV, JSON, validation report, and summary text from the final robot trajectory.
- A new guarded executor that refuses motion unless the trajectory JSON is safe and explicitly approved.
- Manual test script `tests/manual_test_font_to_robot_trajectory.py`.

Recommended changes:

- Extend configuration with a `font_skeleton_pipeline` section instead of scattering thresholds through scripts.
- Update README with the new preview-first font skeleton workflow.
- Add automated tests for missing fonts, safety validation, preview-only behavior, and trajectory export schema.

## Duplicate or Legacy Areas

These are not necessarily wrong, but need care:

- `modules/safety_check.py` and `src/safety/safety_check.py` overlap.
- `src/svg/svg_to_strokes.py`, `modules/svg_trajectory.py`, and `src/svg_processing/*` overlap in SVG trajectory responsibilities.
- `config/robot_config.yaml` / `config/paper_config.yaml` are simplified compared with `config/robot_config.json`.
- Top-level `outline_to_skeleton/` is a wrapper package for `src/outline_to_skeleton`.
- Many manual robot scripts under `tests/` are operational demos, not unit tests. They must not be run automatically against a real robot.

No old code should be deleted as part of the initial integration.

## Integration Plan

1. Add a focused font-to-robot trajectory package that wraps the existing outline skeletonizer and measured-paper transform.
2. Add typed dataclasses for strokes, trajectory points, similarity metrics, and validation results.
3. Convert centerline strokes into explicit robot trajectory points with `PEN_UP`, `PEN_DOWN`, and `PEN_TRANSITION` states.
4. Generate mandatory output artifacts:
   - `input_text.txt`
   - `original_font_render.png`
   - `raw_skeleton.png`
   - `cleaned_skeleton.png`
   - `stroke_order_preview.png`
   - `robot_trajectory_preview.png`
   - `robot_trajectory_preview.svg`
   - `robot_trajectory.csv`
   - `robot_trajectory.json`
   - `validation_report.json`
   - `summary.txt`
5. Add validation that checks finite coordinates, workspace bounds, paper bounds, Z limits, max step distance, velocity, acceleration, pen-up travel, and font-similarity warnings.
6. Keep robot execution locked by default. A trajectory JSON must have `approved: true`, pass validation, and receive typed `EXECUTE` confirmation before the executor calls Fairino motion.
7. Add mock robot execution that records planned commands without connecting to hardware.
8. Add tests for pipeline generation and safety failure cases, always using mock behavior.

## Immediate Safety Recommendation

Because `config/robot_config.json` currently enables real robot movement, all new code should default to `preview_only=True`, and no new preview command should call any robot connection path. Execution must be a separate command that reloads a generated trajectory JSON, validates it again, checks `approved`, and prompts for `EXECUTE`.
