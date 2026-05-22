from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import torch

from .autoclose import AutoCloseSettings, autoclose_gaps, closure_overlay, ensure_binary_mask, mask_to_rgb
from .cleanup import BlueCleanupSettings, cleanup_blue_lines
from .regions import RegionSettings, label_fill_regions, labels_to_preview


def _tensor_to_rgb_batch(image: torch.Tensor) -> list[np.ndarray]:
    array = image.detach().cpu().numpy()
    if array.ndim == 3:
        array = array[None,]
    if array.ndim != 4:
        raise ValueError("Expected an IMAGE tensor shaped [B,H,W,C] or [H,W,C].")
    array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    return [array[index, :, :, :3] for index in range(array.shape[0])]


def _rgb_to_tensor(image: np.ndarray) -> torch.Tensor:
    rgb = image[:, :, :3].astype(np.float32) / 255.0
    return torch.from_numpy(rgb)[None,]


def _rgb_batch_to_tensor(images: list[np.ndarray]) -> torch.Tensor:
    if not images:
        raise ValueError("Expected at least one image.")
    arrays = [image[:, :, :3].astype(np.float32) / 255.0 for image in images]
    shapes = {array.shape for array in arrays}
    if len(shapes) != 1:
        raise ValueError("Batched IMAGE outputs must share the same height and width.")
    return torch.from_numpy(np.stack(arrays, axis=0))


def _image_stats(mask: np.ndarray, index: int) -> dict[str, int | float]:
    pixels = int(mask.size)
    line_pixels = int(mask.astype(bool).sum())
    return {
        "index": index,
        "width": int(mask.shape[1]),
        "height": int(mask.shape[0]),
        "line_pixels": line_pixels,
        "line_ratio": round(line_pixels / max(1, pixels), 6),
    }


class OTBlueLineCleanup:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "hue_low": ("INT", {"default": 90, "min": 0, "max": 179}),
                "hue_high": ("INT", {"default": 145, "min": 0, "max": 179}),
                "saturation_min": ("INT", {"default": 28, "min": 0, "max": 255}),
                "value_min": ("INT", {"default": 20, "min": 0, "max": 255}),
                "include_dark_lines": ("BOOLEAN", {"default": False}),
                "despeckle_px": ("INT", {"default": 8, "min": 0, "max": 4096}),
                "close_px": ("INT", {"default": 1, "min": 0, "max": 16}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("clean_line", "line_overlay", "transparent_line_preview", "settings_json")
    FUNCTION = "cleanup"
    CATEGORY = "manga/opentoonz-line-tools"

    def cleanup(
        self,
        image,
        hue_low: int,
        hue_high: int,
        saturation_min: int,
        value_min: int,
        include_dark_lines: bool,
        despeckle_px: int,
        close_px: int,
    ):
        settings = BlueCleanupSettings(
            hue_low=hue_low,
            hue_high=hue_high,
            saturation_min=saturation_min,
            value_min=value_min,
            include_dark_lines=include_dark_lines,
            despeckle_px=despeckle_px,
            close_px=close_px,
        )
        line_images: list[np.ndarray] = []
        overlays: list[np.ndarray] = []
        alpha_previews: list[np.ndarray] = []
        images_json: list[dict[str, int | float]] = []
        for index, source in enumerate(_tensor_to_rgb_batch(image)):
            result = cleanup_blue_lines(source, settings)
            alpha_preview = result["line_rgba"].copy()
            alpha_preview[:, :, :3] = np.where(alpha_preview[:, :, 3:4] > 0, alpha_preview[:, :, :3], 255)
            line_images.append(result["line_rgb"])
            overlays.append(result["overlay_rgb"])
            alpha_previews.append(alpha_preview[:, :, :3])
            images_json.append(_image_stats(result["line_mask"], index))
        return (
            _rgb_batch_to_tensor(line_images),
            _rgb_batch_to_tensor(overlays),
            _rgb_batch_to_tensor(alpha_previews),
            json.dumps({"settings": asdict(settings), "batch_size": len(images_json), "images": images_json}, ensure_ascii=False),
        )


class OTLineAutoClose:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "threshold": ("INT", {"default": 180, "min": 0, "max": 255}),
                "closing_distance": ("INT", {"default": 18, "min": 1, "max": 256}),
                "spot_angle": ("FLOAT", {"default": 75.0, "min": 0.0, "max": 180.0, "step": 1.0}),
                "line_width": ("INT", {"default": 1, "min": 1, "max": 16}),
                "max_endpoints": ("INT", {"default": 600, "min": 2, "max": 10000}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("closed_line", "closure_overlay", "segments_json")
    FUNCTION = "autoclose"
    CATEGORY = "manga/opentoonz-line-tools"

    def autoclose(
        self,
        image,
        threshold: int,
        closing_distance: int,
        spot_angle: float,
        line_width: int,
        max_endpoints: int,
    ):
        settings = AutoCloseSettings(
            closing_distance=closing_distance,
            spot_angle=spot_angle,
            line_width=line_width,
            max_endpoints=max_endpoints,
        )
        closed_images: list[np.ndarray] = []
        overlays: list[np.ndarray] = []
        images_json: list[dict[str, object]] = []
        for index, source in enumerate(_tensor_to_rgb_batch(image)):
            mask = ensure_binary_mask(source, threshold)
            result = autoclose_gaps(mask, settings)
            closed_images.append(mask_to_rgb(result["closed_mask"]))
            overlays.append(closure_overlay(mask, result["closed_mask"]))
            images_json.append(
                {
                    **_image_stats(mask, index),
                    "segment_count": len(result["segments"]),
                    "segments": result["segments"],
                    "skipped": result["skipped"],
                }
            )
        return (
            _rgb_batch_to_tensor(closed_images),
            _rgb_batch_to_tensor(overlays),
            json.dumps({"settings": asdict(settings), "batch_size": len(images_json), "images": images_json}, ensure_ascii=False),
        )


class OTRegionPaletteMap:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "threshold": ("INT", {"default": 180, "min": 0, "max": 255}),
                "min_area": ("INT", {"default": 32, "min": 1, "max": 100000}),
                "max_regions": ("INT", {"default": 128, "min": 1, "max": 4096}),
                "ignore_border_regions": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("region_preview", "regions_json")
    FUNCTION = "regions"
    CATEGORY = "manga/opentoonz-line-tools"

    def regions(self, image, threshold: int, min_area: int, max_regions: int, ignore_border_regions: bool):
        settings = RegionSettings(min_area=min_area, max_regions=max_regions, ignore_border_regions=ignore_border_regions)
        previews: list[np.ndarray] = []
        images_json: list[dict[str, object]] = []
        for index, source in enumerate(_tensor_to_rgb_batch(image)):
            line_mask = ensure_binary_mask(source, threshold)
            result = label_fill_regions(line_mask, settings)
            previews.append(labels_to_preview(result["label_map"], line_mask))
            images_json.append(
                {
                    **_image_stats(line_mask, index),
                    "region_count": len(result["regions"]),
                    "regions": result["regions"],
                }
            )
        payload = {"settings": asdict(settings), "batch_size": len(images_json), "images": images_json}
        return (_rgb_batch_to_tensor(previews), json.dumps(payload, ensure_ascii=False))


NODE_CLASS_MAPPINGS = {
    "OTBlueLineCleanup": OTBlueLineCleanup,
    "OTLineAutoClose": OTLineAutoClose,
    "OTRegionPaletteMap": OTRegionPaletteMap,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OTBlueLineCleanup": "OT Blue Line Cleanup",
    "OTLineAutoClose": "OT Line AutoClose",
    "OTRegionPaletteMap": "OT Region Palette Map",
}
