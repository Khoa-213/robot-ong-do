# Single-Stroke SVG Guide

Use this format when the robot should write one centerline stroke per letter instead of tracing font outlines.

## Correct SVG Shape

A robot-friendly single-stroke SVG should contain visible drawing paths like this:

```xml
<path
  id="letter_a_centerline"
  fill="none"
  stroke="#000000"
  stroke-width="1.2"
  stroke-linecap="round"
  stroke-linejoin="round"
  d="M 24 42 C 17 39, 15 28, 22 23 C 29 18, 38 24, 35 33" />
```

Good elements:

- `<path d="...">` with open centerline geometry.
- `<polyline points="...">` for skeleton strokes.
- `fill="none"`.
- `stroke` set to a visible color.
- One path per natural pen stroke.
- Use separate paths only when the pen should lift.

Avoid for single-line writing:

- Font text objects (`<text>an</text>`) that have not been converted or skeletonized.
- Filled outline paths (`fill="#000000"`) from `Path > Object to Path`.
- Double-contour font outlines.
- Closed filled shapes where the robot will trace the outside boundary.

## Inkscape Workflow

1. Set the document size to match your desired design area.
2. Draw with the Bezier/Pen tool or Pencil tool as simple centerline strokes.
3. Set `Fill` to none.
4. Set `Stroke paint` to black.
5. Set a visible `Stroke style` width, for example `1 mm`. Stroke width is only visual; robot follows the centerline.
6. Keep one object per pen stroke. If the pen should not lift, keep it as one continuous path.
7. If you used text as a reference, put it on a locked guide layer, then manually draw centerlines over it.
8. Delete or hide guide text before export.
9. Save as `Plain SVG`.

## Important Note

`Path > Object to Path` converts text to outline contours. That is useful for engraving/filling, but the robot will trace the contour, not write a single centerline. For single-line writing, draw centerlines manually or use a real single-line font/skeletonization tool.

Example file:

```text
assets/svg/single_stroke_example.svg
```

Prompt for ChatGPT/Gemini:

```text
I need a robot/plotter-friendly single-stroke SVG, not a filled outline font.
Please design the word as centerline paths only.
Requirements:
- Use only <path> or <polyline> for visible strokes.
- Each natural pen stroke should be one open path.
- Use fill="none", stroke="#000000", stroke-linecap="round", stroke-linejoin="round".
- Do not use <text>.
- Do not use filled outline contours.
- Do not close paths unless the pen should draw a closed loop.
- The robot will follow each path once and lift the pen between separate paths.
Return plain SVG with a clean viewBox.
```
