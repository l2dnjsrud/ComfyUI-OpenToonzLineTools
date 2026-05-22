from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


@dataclass(frozen=True)
class RegionSettings:
    min_area: int = 32
    max_regions: int = 128
    ignore_border_regions: bool = True


DEFAULT_PALETTE = np.array(
    [
        [244, 176, 132],
        [141, 211, 199],
        [190, 186, 218],
        [251, 128, 114],
        [128, 177, 211],
        [253, 180, 98],
        [179, 222, 105],
        [252, 205, 229],
        [217, 217, 217],
        [188, 128, 189],
    ],
    dtype=np.uint8,
)


def _connected_components(mask: np.ndarray) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    mask_u8 = mask.astype(np.uint8)
    if cv2 is not None:
        return cv2.connectedComponentsWithStats(mask_u8, 4)

    labels = np.zeros(mask.shape, dtype=np.int32)
    stats = [[0, 0, 0, 0, 0]]
    centroids = [[0.0, 0.0]]
    label = 0
    height, width = mask.shape
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            label += 1
            stack = [(x, y)]
            labels[y, x] = label
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                px, py = stack.pop()
                xs.append(px)
                ys.append(py)
                for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = label
                        stack.append((nx, ny))
            area = len(xs)
            stats.append([min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, area])
            centroids.append([float(sum(xs)) / area, float(sum(ys)) / area])
    return label + 1, labels, np.asarray(stats, dtype=np.int32), np.asarray(centroids, dtype=np.float32)


def _touches_border(x: int, y: int, w: int, h: int, image_w: int, image_h: int) -> bool:
    return x <= 0 or y <= 0 or x + w >= image_w or y + h >= image_h


def label_fill_regions(line_mask: Any, settings: RegionSettings | None = None) -> dict[str, Any]:
    settings = settings or RegionSettings()
    line = np.asarray(line_mask).astype(bool)
    fillable = ~line
    count, labels, stats, centroids = _connected_components(fillable)
    height, width = line.shape

    output_labels = np.zeros_like(labels, dtype=np.int32)
    regions: list[dict[str, Any]] = []
    next_id = 1
    candidates: list[tuple[int, int]] = []
    for label in range(1, count):
        area = int(stats[label, 4])
        if area < settings.min_area:
            continue
        x, y, w, h = [int(v) for v in stats[label, :4]]
        if settings.ignore_border_regions and _touches_border(x, y, w, h, width, height):
            continue
        candidates.append((area, label))

    candidates.sort(reverse=True)
    for _, label in candidates[: settings.max_regions]:
        x, y, w, h = [int(v) for v in stats[label, :4]]
        cx, cy = [float(v) for v in centroids[label]]
        output_labels[labels == label] = next_id
        regions.append(
            {
                "id": f"region_{next_id:03d}",
                "label": next_id,
                "bbox": [x, y, w, h],
                "area": int(stats[label, 4]),
                "centroid": [round(cx, 2), round(cy, 2)],
                "style_id": next_id,
            }
        )
        next_id += 1

    return {"label_map": output_labels, "regions": regions}


def labels_to_preview(label_map: np.ndarray, line_mask: np.ndarray | None = None) -> np.ndarray:
    preview = np.full((*label_map.shape, 3), 255, dtype=np.uint8)
    for label in np.unique(label_map):
        if label <= 0:
            continue
        preview[label_map == label] = DEFAULT_PALETTE[(label - 1) % len(DEFAULT_PALETTE)]
    if line_mask is not None:
        preview[np.asarray(line_mask).astype(bool)] = np.array([0, 0, 0], dtype=np.uint8)
    return preview
