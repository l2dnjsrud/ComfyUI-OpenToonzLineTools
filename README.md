# ComfyUI OpenToonz Line Tools

[한국어 README](README.ko.md)

OpenToonz-inspired ComfyUI custom nodes for rough blue manga/manhwa manuscripts.

This project does **not** embed or port the full OpenToonz application. It extracts
the useful production ideas for the current sketch-to-color research pipeline:

- scan-style blue line cleanup,
- gap closing before region fill,
- region/palette maps for later color correction.

The intended upstream/downstream flow is:

```text
blue rough panel crop
  -> OT Blue Line Cleanup
  -> OT Line AutoClose
  -> OT Region Palette Map
  -> Qwen Image Edit / MangaNinja / reference colorization
  -> panel reassemble
```

## Why These Features

OpenToonz is strongest in traditional 2D animation cleanup, ink/paint, palette
management, and compositing. For this research, the reusable ideas are not the UI
or timeline; they are the low-level line-preparation steps that make rough art
more fillable and controllable.

Relevant OpenToonz references:

- [Cleaning-up Scanned Drawings](https://opentoonz.readthedocs.io/en/latest/cleaning-up_scanned_drawings.html)
- [Painting Animation Levels](https://opentoonz.readthedocs.io/en/latest/painting_animation_levels.html)
- [Managing Palettes and Styles](https://opentoonz.readthedocs.io/en/latest/managing_palettes_and_styles.html)
- [OpenToonz source tree](https://github.com/opentoonz/opentoonz/tree/master/toonz/sources)

## Nodes

### OT Blue Line Cleanup

Classifies blue rough pencil strokes and emits a normalized black-on-white line
image plus an overlay preview.

Outputs:

- `clean_line`: white background with black extracted lines
- `line_overlay`: source image with detected strokes tinted red
- `transparent_line_preview`: line-only preview on white
- `settings_json`: exact parameters used

### OT Line AutoClose

Finds skeleton endpoints and draws short closure segments when endpoint distance
and direction are compatible.

Outputs:

- `closed_line`: line image after gap closure
- `closure_overlay`: original black lines plus red closure strokes
- `segments_json`: closure segment coordinates

### OT Region Palette Map

Labels fillable regions separated by line art and returns a JSON list of region
metadata. This is the first step toward OpenToonz-style indexed color editing.

Outputs:

- `region_preview`: colored region-label preview with black line art
- `regions_json`: bbox, area, centroid, and style id for each region

## Install

Clone or copy this folder into ComfyUI custom nodes.

On another ComfyUI installation:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/l2dnjsrud/ComfyUI-OpenToonzLineTools.git
```

Because this repository is currently private, authenticate first on machines
that do not already have GitHub credentials:

```bash
gh auth login
gh repo clone l2dnjsrud/ComfyUI-OpenToonzLineTools /path/to/ComfyUI/custom_nodes/ComfyUI-OpenToonzLineTools
```

On this Mac, using the development copy by symlink is fine:

```bash
cd /Users/iwongyeong/AI/ComfyUI/custom_nodes
ln -s /Users/iwongyeong/AI/ComfyUI-OpenToonzLineTools ComfyUI-OpenToonzLineTools
```

Install dependencies in the ComfyUI environment if needed:

```bash
cd /path/to/ComfyUI
source .venv/bin/activate
pip install -r custom_nodes/ComfyUI-OpenToonzLineTools/requirements.txt
deactivate
```

Do not reinstall or upgrade `torch` from this node. Use the `torch` build that
already belongs to that ComfyUI installation, especially on CUDA or MPS setups.

Restart ComfyUI. Nodes appear under:

```text
manga/opentoonz-line-tools
```

## Example Workflows

Use the UI workflow when opening a graph in the ComfyUI canvas:

```text
examples/opentoonz_line_tools_basic_ui.json
```

This graph is:

```text
LoadImage
  -> OT Blue Line Cleanup
  -> OT Line AutoClose
  -> OT Region Palette Map
  -> SaveImage debug outputs
```

Before queuing it, put a rough panel image into the ComfyUI `input` folder and
select it in the `LoadImage` node. The placeholder filename is `panel_001.png`.

Use the API prompt version only for `/prompt`-style scripted runs:

```text
examples/opentoonz_line_tools_basic_api.json
```

## Full-Page Inputs

For high-resolution full manga/manhwa pages, use these nodes after panel
detection and cropping whenever possible.

`OT Blue Line Cleanup` can be useful on full pages as a quick line-extraction
preview, but `OT Line AutoClose` and `OT Region Palette Map` are designed for
panel crops or other bounded line-art regions. On full pages with many panels,
speech balloons, perspective grids, and layout borders, endpoint counts can
become too high and region maps can hit the `max_regions` cap.

Use the local evaluator to check a YOLO-style research set:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-OpenToonzLineTools
/path/to/ComfyUI/.venv/bin/python scripts/evaluate_research_images.py \
  --dataset-root /path/to/dataset \
  --output-dir outputs/research_eval
```

## Verification

Run the smoke tests with the ComfyUI Python environment:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-OpenToonzLineTools
/path/to/ComfyUI/.venv/bin/python -m unittest discover -s tests -v
```

## Current Scope

Implemented:

- OpenToonz-inspired blue cleanup baseline
- endpoint-based line autoclose
- fillable region labeling and palette-preview JSON
- ComfyUI node wrappers
- English/Korean docs and visual pipeline notes

Not implemented yet:

- direct OpenToonz C++ binding
- TLV/PLI file support
- full palette-index raster format
- semantic inking or AI colorization models

## Recommended Next Experiment

Use the current Mr.Blue v5 polygon crops as input and compare:

1. raw crop -> Qwen Image Edit,
2. cleanup crop -> Qwen Image Edit,
3. cleanup + autoclose + region map -> reference colorization/correction.

Success should be measured by blue-line removal, composition retention, fill
leak reduction, and whether palette/region JSON makes post-correction easier.
