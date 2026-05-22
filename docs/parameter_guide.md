# Node and Parameter Guide

This guide uses the friendly ComfyUI display names. The internal node IDs stay
unchanged for workflow compatibility:

- `OTBlueLineCleanup` -> `Blue Sketch Cleaner`
- `OTLineAutoClose` -> `Line Gap Closer`
- `OTRegionPaletteMap` -> `Color Region Finder`

Recommended pipeline:

```text
panel crop
  -> Blue Sketch Cleaner
  -> Line Gap Closer
  -> Color Region Finder
  -> colorization / correction
```

For full pages, run panel detection and cropping first. Full MC/MS pages are too
complex for gap closing and region mapping as a default.

## Blue Sketch Cleaner

Use this first. It detects blue rough pencil strokes and turns them into black
line art on a white background.

Outputs:

- `clean_line`: black line art on white background.
- `line_overlay`: original image with detected blue strokes marked red.
- `transparent_line_preview`: line-only preview on white.
- `settings_json`: parameters plus per-image line statistics.

Parameters:

| Parameter | Default | How to use it |
|---|---:|---|
| `hue_low` | 90 | Lower bound of blue hue in OpenCV HSV, range `0-179`. Lower it if cyan strokes are missed. |
| `hue_high` | 145 | Upper bound of blue hue. Raise it if purple-blue strokes are missed. |
| `saturation_min` | 28 | Minimum color saturation. Raise it to ignore pale paper/background noise. Lower it for very faint blue pencil. |
| `value_min` | 20 | Minimum brightness. Lower it if dark blue strokes disappear. Raise it if shadows/noise are selected. |
| `include_dark_lines` | false | Also include black/dark line art. Useful for mixed blue+black panels, but can catch text, borders, and shadows. |
| `despeckle_px` | 8 | Removes tiny connected specks below this pixel area. Raise it to remove dust; lower it if small intentional marks vanish. |
| `close_px` | 1 | Small morphological closing radius. Raise it to connect tiny cracks; too high will thicken or merge lines. |

Starting recipes:

- Blue rough only: defaults.
- Very faint blue: `saturation_min 15-25`, `value_min 10-20`.
- Too much background detected: `saturation_min 45-70`, `despeckle_px 16-64`.
- Mixed blue and black line art: `include_dark_lines true`, then check the overlay carefully.

## Line Gap Closer

Use this after `Blue Sketch Cleaner`. It skeletonizes line art, finds endpoints,
and draws short closure strokes between compatible endpoints.

Outputs:

- `closed_line`: line art after attempted gap closing.
- `closure_overlay`: original lines in black and newly closed gaps in red.
- `segments_json`: per-image closed segment coordinates and skip reason.

Parameters:

| Parameter | Default | How to use it |
|---|---:|---|
| `threshold` | 180 | Pixels darker than this are treated as line. Lower it for strict black-only lines; raise it if gray lines are missed. |
| `closing_distance` | 18 | Maximum pixel distance between endpoints. Raise for bigger gaps; lower if unrelated lines get connected. |
| `spot_angle` | 75 | Direction tolerance in degrees. Lower values are stricter; higher values close more ambiguous gaps. |
| `line_width` | 1 | Width of newly drawn closure strokes. Use `1-2` for line art; higher values can muddy sketches. |
| `max_endpoints` | 600 | Safety cap. If exceeded, the node skips instead of making chaotic closures. Full pages often exceed this. |

Starting recipes:

- Panel crop: defaults.
- Tiny broken strokes only: `closing_distance 8-12`, `spot_angle 45-60`.
- Larger sketch gaps: `closing_distance 20-32`, `spot_angle 75-100`.
- Full pages: avoid, or raise `max_endpoints` only for experiments after checking overlays.

## Color Region Finder

Use this after gap closing. It finds connected white regions separated by black
line art and makes a colored preview of fillable areas.

Outputs:

- `region_preview`: colored labels for detected regions, with line art in black.
- `regions_json`: bbox, area, centroid, and style id per detected region.

Parameters:

| Parameter | Default | How to use it |
|---|---:|---|
| `threshold` | 180 | Pixels darker than this are treated as line boundaries. Match this with Line Gap Closer. |
| `min_area` | 32 | Ignore fill regions smaller than this pixel area. Raise it to reduce noise; lower it to keep small details. |
| `max_regions` | 128 | Maximum regions returned per image. Raise for dense panels; if every image hits the cap, the input is too broad. |
| `ignore_border_regions` | true | Ignore open regions touching image borders. Keep true for panel crops; false can be useful for page/layout debugging. |

Starting recipes:

- Panel crop: defaults.
- Too many tiny colored fragments: `min_area 128-512`.
- Missing small eyes/details/accessories: `min_area 8-24`.
- Full page debug only: `max_regions 512+`, but expect noisy maps.

## Quick Interpretation

- If `Blue Sketch Cleaner` overlay looks right, the hue/saturation settings are good.
- If `Line Gap Closer` returns `endpoint_count_exceeded`, crop smaller before using it.
- If `Color Region Finder` always returns exactly `max_regions`, the image is too complex or too open.
