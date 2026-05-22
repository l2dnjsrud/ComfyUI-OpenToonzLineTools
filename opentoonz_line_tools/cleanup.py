from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - ComfyUI normally provides cv2.
    cv2 = None


@dataclass(frozen=True)
class BlueCleanupSettings:
    hue_low: int = 90
    hue_high: int = 145
    saturation_min: int = 28
    value_min: int = 20
    include_dark_lines: bool = False
    dark_threshold: int = 90
    despeckle_px: int = 8
    close_px: int = 1
    line_rgb: tuple[int, int, int] = (0, 0, 0)
    background_rgb: tuple[int, int, int] = (255, 255, 255)


def ensure_uint8_rgb(image: Any) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError("Expected an HxWx3 or HxWx4 image array.")
    if np.issubdtype(array.dtype, np.floating):
        array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    else:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array[:, :, :3]


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    if cv2 is None:
        # Small fallback good enough for thresholding tests.
        rgb_float = rgb.astype(np.float32) / 255.0
        maxc = rgb_float.max(axis=2)
        minc = rgb_float.min(axis=2)
        delta = maxc - minc
        hue = np.zeros_like(maxc)
        mask = delta > 1e-6
        r, g, b = rgb_float[:, :, 0], rgb_float[:, :, 1], rgb_float[:, :, 2]
        hue[(maxc == r) & mask] = ((g - b) / delta % 6)[(maxc == r) & mask]
        hue[(maxc == g) & mask] = ((b - r) / delta + 2)[(maxc == g) & mask]
        hue[(maxc == b) & mask] = ((r - g) / delta + 4)[(maxc == b) & mask]
        hue = (hue * 30).astype(np.uint8)
        sat = np.where(maxc == 0, 0, delta / maxc)
        return np.stack([hue, (sat * 255).astype(np.uint8), (maxc * 255).astype(np.uint8)], axis=2)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)


def _morphology(mask: np.ndarray, despeckle_px: int, close_px: int) -> np.ndarray:
    mask_u8 = (mask > 0).astype(np.uint8)
    if cv2 is None:
        return mask_u8.astype(bool)

    if close_px > 0:
        kernel = np.ones((close_px * 2 + 1, close_px * 2 + 1), dtype=np.uint8)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)

    if despeckle_px > 0:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, 8)
        cleaned = np.zeros_like(mask_u8)
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] >= despeckle_px:
                cleaned[labels == label] = 1
        mask_u8 = cleaned

    return mask_u8.astype(bool)


def extract_blue_mask(rgb: np.ndarray, settings: BlueCleanupSettings) -> np.ndarray:
    hsv = _rgb_to_hsv(rgb)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    if settings.hue_low <= settings.hue_high:
        hue_mask = (h >= settings.hue_low) & (h <= settings.hue_high)
    else:
        hue_mask = (h >= settings.hue_low) | (h <= settings.hue_high)

    blue = hue_mask & (s >= settings.saturation_min) & (v >= settings.value_min)
    if settings.include_dark_lines:
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])
        blue = blue | (gray <= settings.dark_threshold)
    return _morphology(blue, settings.despeckle_px, settings.close_px)


def mask_to_line_rgb(mask: np.ndarray, settings: BlueCleanupSettings) -> np.ndarray:
    out = np.empty((*mask.shape, 3), dtype=np.uint8)
    out[:, :] = np.array(settings.background_rgb, dtype=np.uint8)
    out[mask] = np.array(settings.line_rgb, dtype=np.uint8)
    return out


def mask_to_rgba(mask: np.ndarray, settings: BlueCleanupSettings) -> np.ndarray:
    out = np.zeros((*mask.shape, 4), dtype=np.uint8)
    out[mask, :3] = np.array(settings.line_rgb, dtype=np.uint8)
    out[mask, 3] = 255
    return out


def make_cleanup_overlay(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    overlay = rgb.copy()
    tint = np.array([255, 60, 40], dtype=np.uint8)
    overlay[mask] = (0.45 * overlay[mask] + 0.55 * tint).astype(np.uint8)
    return overlay


def cleanup_blue_lines(image: Any, settings: BlueCleanupSettings | None = None) -> dict[str, np.ndarray]:
    """OpenToonz-inspired blue rough cleanup.

    This is not a port of OpenToonz internals. It recreates the useful behavior
    for ComfyUI: classify blue rough strokes, remove specks, normalize line art,
    and expose transparent line output for later compositing/colorization.
    """

    settings = settings or BlueCleanupSettings()
    rgb = ensure_uint8_rgb(image)
    mask = extract_blue_mask(rgb, settings)
    return {
        "source_rgb": rgb,
        "line_mask": mask,
        "line_rgb": mask_to_line_rgb(mask, settings),
        "line_rgba": mask_to_rgba(mask, settings),
        "overlay_rgb": make_cleanup_overlay(rgb, mask),
    }
