# Visual Pipeline

[한국어 버전](visual_pipeline.ko.md)

This document shows where the OpenToonz-inspired line tools fit in the current
rough-sketch-to-color research pipeline.

## Research Position

```mermaid
flowchart TD
    A[Blue manuscript page] --> B[Mr.Blue YOLO-seg panel detector]
    B --> C[Polygon-masked panel crops]
    C --> D{Preprocess?}
    D -->|baseline| E[Raw crop to Qwen Image Edit]
    D -->|OT-inspired| F[Blue Line Cleanup]
    F --> G[Line AutoClose]
    G --> H[Region Palette Map]
    H --> I[Qwen Image Edit or MangaNinja]
    E --> J[Colored panel]
    I --> J
    J --> K[Panel Reassemble]
```

## Node Chain

```mermaid
flowchart LR
    A[Load Image / Panel Crop] --> B[OT Blue Line Cleanup]
    B --> C[OT Line AutoClose]
    C --> D[OT Region Palette Map]
    D --> E[Colorization Node]
    E --> F[Reassemble]
```

## Output Artifacts

```mermaid
flowchart TD
    A[OT Blue Line Cleanup] --> A1[clean_line IMAGE]
    A --> A2[line_overlay IMAGE]
    A --> A3[settings_json]
    B[OT Line AutoClose] --> B1[closed_line IMAGE]
    B --> B2[closure_overlay IMAGE]
    B --> B3[segments_json]
    C[OT Region Palette Map] --> C1[region_preview IMAGE]
    C --> C2[regions_json]
```

## Experiment Matrix

| Variant | Input to color model | Expected benefit | Risk |
| --- | --- | --- | --- |
| A | raw panel crop | fastest baseline | blue rough may leak into output |
| B | clean line crop | less blue noise | may remove useful semantic detail |
| C | clean line + autoclose | better fill stability | gap closure may create false lines |
| D | clean line + autoclose + region JSON | easier post-correction | needs downstream region-aware tooling |

## Adoption Gate

Use these tools as a default only if they improve at least one measurable outcome:

- fewer blue artifacts in final output,
- fewer color leaks across line boundaries,
- better character/costume color consistency after correction,
- easier manual review because overlays/JSON explain preprocessing choices.
