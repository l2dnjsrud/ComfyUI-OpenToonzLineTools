# OpenToonz Line Tools Implementation Plan

> **Worker note:** Execute this plan task-by-task. Each step uses checkbox syntax
> for progress tracking.

**Goal:** Build a standalone ComfyUI custom-node prototype that reimplements the
OpenToonz cleanup, autoclose, and palette-region ideas useful for blue rough
manuscript sketch-to-color research.

**Architecture:** Core algorithms live in plain Python modules and do not depend
on ComfyUI tensors. ComfyUI node classes only adapt tensors, bind parameters, and
return preview images plus JSON artifacts.

**Tech Stack:** Python 3.10+, NumPy, OpenCV, PyTorch tensors for ComfyUI node IO,
unittest smoke tests.

**Work Scope:**

- **In scope:** blue line cleanup, endpoint gap closing, region label map, ComfyUI
  wrappers, bilingual docs, visual diagrams, smoke tests.
- **Out of scope:** direct OpenToonz C++ binding, TLV/PLI support, semantic AI
  inking/colorization, full indexed Toonz Raster implementation.

**Verification Strategy:**

- **Level:** test-suite
- **Command:** `/Users/iwongyeong/AI/ComfyUI/.venv/bin/python -m unittest discover -s tests -v`
- **What it validates:** blue extraction, gap closing, and region labeling work
  on synthetic images.

---

## File Structure Mapping

- Create `opentoonz_line_tools/cleanup.py` for blue-line cleanup.
- Create `opentoonz_line_tools/autoclose.py` for gap closing.
- Create `opentoonz_line_tools/regions.py` for region labels and palette preview.
- Create `opentoonz_line_tools/nodes.py` for ComfyUI node wrappers.
- Create `README.md` and `README.ko.md` for bilingual usage docs.
- Create `docs/architecture.md` and `docs/architecture.ko.md`.
- Create `docs/visual_pipeline.md` and `docs/visual_pipeline.ko.md`.
- Create `tests/test_line_tools.py` for smoke tests.

## Tasks

### Task 1: Project Skeleton

**Dependencies:** None

- [x] Create the standalone folder.
- [x] Add package and ComfyUI entrypoint files.

### Task 2: Core Algorithms

**Dependencies:** Task 1

- [x] Implement blue-line cleanup.
- [x] Implement endpoint-based autoclose.
- [x] Implement region labeling and palette preview.

### Task 3: ComfyUI Nodes

**Dependencies:** Task 2

- [x] Add `Blue Sketch Cleaner` (`OTBlueLineCleanup` internally).
- [x] Add `Line Gap Closer` (`OTLineAutoClose` internally).
- [x] Add `Color Region Finder` (`OTRegionPaletteMap` internally).

### Task 4: Documentation

**Dependencies:** Task 3

- [x] Write English README.
- [x] Write Korean README.
- [x] Write English/Korean architecture docs.
- [x] Write English/Korean visual pipeline docs.

### Task 5: Verification

**Dependencies:** Task 4

- [x] Add smoke tests.
- [x] Run unittest verification in the ComfyUI venv.
