from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees
from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


@dataclass(frozen=True)
class AutoCloseSettings:
    closing_distance: int = 18
    spot_angle: float = 75.0
    line_width: int = 1
    max_endpoints: int = 600
    min_component_area: int = 2


def ensure_binary_mask(image: Any, threshold: int = 180) -> np.ndarray:
    array = np.asarray(image)
    if np.issubdtype(array.dtype, np.floating):
        array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    else:
        array = np.clip(array, 0, 255).astype(np.uint8)
    if array.ndim == 3:
        gray = (0.299 * array[:, :, 0] + 0.587 * array[:, :, 1] + 0.114 * array[:, :, 2]).astype(np.uint8)
    elif array.ndim == 2:
        gray = array
    else:
        raise ValueError("Expected a grayscale, RGB, or RGBA image.")
    return gray < threshold


def _zhang_suen_thinning(mask: np.ndarray, max_iter: int = 128) -> np.ndarray:
    img = (mask > 0).astype(np.uint8)
    if img.shape[0] < 3 or img.shape[1] < 3:
        return img.astype(bool)

    def neighbours(a: np.ndarray) -> tuple[np.ndarray, ...]:
        p2 = a[:-2, 1:-1]
        p3 = a[:-2, 2:]
        p4 = a[1:-1, 2:]
        p5 = a[2:, 2:]
        p6 = a[2:, 1:-1]
        p7 = a[2:, :-2]
        p8 = a[1:-1, :-2]
        p9 = a[:-2, :-2]
        return p2, p3, p4, p5, p6, p7, p8, p9

    for _ in range(max_iter):
        changed = False
        for step in (0, 1):
            p2, p3, p4, p5, p6, p7, p8, p9 = neighbours(img)
            center = img[1:-1, 1:-1]
            n_count = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = (
                ((p2 == 0) & (p3 == 1)).astype(np.uint8)
                + ((p3 == 0) & (p4 == 1)).astype(np.uint8)
                + ((p4 == 0) & (p5 == 1)).astype(np.uint8)
                + ((p5 == 0) & (p6 == 1)).astype(np.uint8)
                + ((p6 == 0) & (p7 == 1)).astype(np.uint8)
                + ((p7 == 0) & (p8 == 1)).astype(np.uint8)
                + ((p8 == 0) & (p9 == 1)).astype(np.uint8)
                + ((p9 == 0) & (p2 == 1)).astype(np.uint8)
            )
            if step == 0:
                condition = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                condition = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            delete = (center == 1) & (n_count >= 2) & (n_count <= 6) & (transitions == 1) & condition
            if np.any(delete):
                center[delete] = 0
                changed = True
        if not changed:
            break
    return img.astype(bool)


def _endpoint_points(skeleton: np.ndarray) -> list[tuple[int, int]]:
    padded = np.pad(skeleton.astype(np.uint8), 1)
    core = padded[1:-1, 1:-1]
    count = np.zeros_like(core, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            count += padded[1 + dy : 1 + dy + skeleton.shape[0], 1 + dx : 1 + dx + skeleton.shape[1]]
    ys, xs = np.where((core == 1) & (count == 1))
    return [(int(x), int(y)) for y, x in zip(ys, xs)]


def _trace_inner_point(skeleton: np.ndarray, point: tuple[int, int], radius: int = 9) -> tuple[int, int] | None:
    x0, y0 = point
    queue = [(x0, y0, 0)]
    seen = {(x0, y0)}
    farthest = (x0, y0, 0)
    height, width = skeleton.shape
    while queue:
        x, y, dist = queue.pop(0)
        if dist > farthest[2]:
            farthest = (x, y, dist)
        if dist >= radius:
            continue
        for yy in range(max(0, y - 1), min(height, y + 2)):
            for xx in range(max(0, x - 1), min(width, x + 2)):
                if (xx, yy) in seen or not skeleton[yy, xx]:
                    continue
                seen.add((xx, yy))
                queue.append((xx, yy, dist + 1))
    if farthest[2] == 0:
        return None
    return farthest[0], farthest[1]


def _angle_between(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    value = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
    return degrees(acos(value))


def _bresenham_line(mask: np.ndarray, p: tuple[int, int], q: tuple[int, int], width: int) -> None:
    if cv2 is not None:
        drawable = mask.astype(np.uint8)
        cv2.line(drawable, p, q, 1, max(1, int(width)), lineType=cv2.LINE_AA)
        mask[:] = drawable > 0
        return
    x0, y0 = p
    x1, y1 = q
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        mask[y0, x0] = True
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def autoclose_gaps(mask: Any, settings: AutoCloseSettings | None = None) -> dict[str, Any]:
    settings = settings or AutoCloseSettings()
    binary = np.asarray(mask).astype(bool)
    skeleton = _zhang_suen_thinning(binary)
    endpoints = _endpoint_points(skeleton)
    if len(endpoints) > settings.max_endpoints:
        return {
            "closed_mask": binary,
            "skeleton": skeleton,
            "segments": [],
            "skipped": f"endpoint_count_exceeded:{len(endpoints)}",
        }

    inner_points = {p: _trace_inner_point(skeleton, p) for p in endpoints}
    used: set[tuple[int, int]] = set()
    segments: list[dict[str, Any]] = []
    closed = binary.copy()
    max_dist2 = settings.closing_distance * settings.closing_distance

    for i, p in enumerate(endpoints):
        if p in used:
            continue
        best: tuple[float, tuple[int, int]] | None = None
        for q in endpoints[i + 1 :]:
            if q in used:
                continue
            dx = q[0] - p[0]
            dy = q[1] - p[1]
            dist2 = dx * dx + dy * dy
            if dist2 == 0 or dist2 > max_dist2:
                continue
            p_inner = inner_points.get(p)
            q_inner = inner_points.get(q)
            if p_inner is not None:
                p_out = np.array([p[0] - p_inner[0], p[1] - p_inner[1]], dtype=np.float32)
                if _angle_between(p_out, np.array([dx, dy], dtype=np.float32)) > settings.spot_angle:
                    continue
            if q_inner is not None:
                q_out = np.array([q[0] - q_inner[0], q[1] - q_inner[1]], dtype=np.float32)
                if _angle_between(q_out, np.array([-dx, -dy], dtype=np.float32)) > settings.spot_angle:
                    continue
            if best is None or dist2 < best[0]:
                best = (float(dist2), q)
        if best is None:
            continue
        q = best[1]
        _bresenham_line(closed, p, q, settings.line_width)
        used.add(p)
        used.add(q)
        segments.append({"from": [p[0], p[1]], "to": [q[0], q[1]], "distance": float(best[0] ** 0.5)})

    return {"closed_mask": closed.astype(bool), "skeleton": skeleton, "segments": segments, "skipped": ""}


def mask_to_rgb(mask: np.ndarray) -> np.ndarray:
    out = np.full((*mask.shape, 3), 255, dtype=np.uint8)
    out[mask.astype(bool)] = 0
    return out


def closure_overlay(original_mask: np.ndarray, closed_mask: np.ndarray) -> np.ndarray:
    out = np.full((*closed_mask.shape, 3), 255, dtype=np.uint8)
    out[original_mask.astype(bool)] = np.array([0, 0, 0], dtype=np.uint8)
    out[closed_mask.astype(bool) & ~original_mask.astype(bool)] = np.array([255, 40, 40], dtype=np.uint8)
    return out
