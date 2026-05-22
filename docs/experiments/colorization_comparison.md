# Panel Colorization Comparison

[Korean version](colorization_comparison.ko.md)

Date: 2026-05-22

This experiment checks whether OpenToonz-inspired preprocessing helps actual
panel colorization on the local ComfyUI setup.

## Input

Panel crops:

```text
/Users/iwongyeong/AI/outputs/MC-13/split_v4/panels
```

Panels used:

```text
panel_002.png
panel_003.png
panel_004.png
panel_005.png
panel_006.png
```

`panel_001.png` was excluded because it is mostly a page-label/text fragment.

## Compared Inputs

For each panel, the comparison script generated:

- `source`: resized raw blue rough crop.
- `clean_line`: output from Blue Sketch Cleaner.
- `closed_line`: Blue Sketch Cleaner plus Line Gap Closer.
- `region_preview`: Color Region Finder preview for inspection only.
- `raw_color`, `clean_color`, `closed_color`: colorization results from the
  selected ComfyUI workflow.

## Workflows Tested

### Qwen Image Edit

Qwen Image Edit was queued successfully, but local Apple Silicon MPS execution
failed during sampling because the installed `fp8mixed` Qwen model requires a
float8 path unsupported by MPS:

```text
Trying to convert Float8_e4m3fn to the MPS backend but it does not have support for that dtype.
```

This path should be retried on a CUDA/NVIDIA machine.

### SD1.5 Anything + Lineart ControlNet

Output:

```text
outputs/color_compare_mc13_split_v4_controlnet_v3_same_seed
```

This workflow produced strong color, but it often reinterpreted the panel
composition. Several raw or closed-line variants collapsed to black. It is not
stable enough as the main research path.

### SD1.5 Anything Img2Img

Output:

```text
outputs/color_compare_mc13_split_v4_img2img
```

This workflow preserved composition better. Raw blue crops often kept blue
artifacts, while `clean_line` and `closed_line` removed most blue signal. It
still changed character identity and sometimes failed completely (`panel_004`).

## Result

Best local path among tested options:

```text
panel crop -> Blue Sketch Cleaner -> Line Gap Closer -> img2img colorization
```

However, this is not production-ready. The preprocessing is useful, but the
available local SD1.5 colorization workflows are weaker than the line-prep
nodes. The strongest next experiment is to rerun the same clean/closed panel
inputs through Qwen Image Edit on CUDA, or another image-edit model that can
preserve input composition better.

## Key Takeaways

- Panel crops are the correct input level for these nodes.
- Blue Sketch Cleaner is helpful before colorization because raw blue lines tend
  to survive or steer the model badly.
- Line Gap Closer sometimes helps, but it can also over-constrain or trigger
  unstable generations depending on the sampler seed.
- Color Region Finder is useful as a fill-leak/debug preview, not as an
  automatic semantic palette.
- Local MPS cannot run the current fp8 Qwen Image Edit model.

