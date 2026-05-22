from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import torch

from opentoonz_line_tools.autoclose import AutoCloseSettings, autoclose_gaps
from opentoonz_line_tools.cleanup import BlueCleanupSettings, cleanup_blue_lines
from opentoonz_line_tools.nodes import OTBlueLineCleanup, OTLineAutoClose, OTRegionPaletteMap
from opentoonz_line_tools.regions import RegionSettings, label_fill_regions

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CleanupTests(unittest.TestCase):
    def test_cleanup_extracts_blue_line_and_removes_tiny_speck(self) -> None:
        image = np.full((48, 64, 3), 255, dtype=np.uint8)
        image[20:23, 8:56] = np.array([40, 100, 230], dtype=np.uint8)
        image[5, 5] = np.array([40, 100, 230], dtype=np.uint8)

        result = cleanup_blue_lines(image, BlueCleanupSettings(despeckle_px=4, close_px=0))

        self.assertTrue(result["line_mask"][21, 24])
        self.assertFalse(result["line_mask"][5, 5])
        self.assertEqual(result["line_rgb"][21, 24].tolist(), [0, 0, 0])
        self.assertEqual(result["line_rgba"][0, 0, 3], 0)


class AutoCloseTests(unittest.TestCase):
    def test_autoclose_connects_small_horizontal_gap(self) -> None:
        mask = np.zeros((40, 70), dtype=bool)
        mask[20, 6:28] = True
        mask[20, 37:62] = True

        result = autoclose_gaps(mask, AutoCloseSettings(closing_distance=12, spot_angle=90, line_width=1))

        self.assertGreaterEqual(len(result["segments"]), 1)
        self.assertTrue(result["closed_mask"][20, 32])


class RegionTests(unittest.TestCase):
    def test_region_labeling_finds_closed_interior_area(self) -> None:
        line = np.zeros((60, 80), dtype=bool)
        line[10, 10:60] = True
        line[40, 10:60] = True
        line[10:41, 10] = True
        line[10:41, 60] = True

        result = label_fill_regions(line, RegionSettings(min_area=20, ignore_border_regions=True))

        self.assertEqual(len(result["regions"]), 1)
        self.assertEqual(result["regions"][0]["bbox"], [11, 11, 49, 29])
        self.assertGreater(result["label_map"][20, 20], 0)


class ExampleWorkflowTests(unittest.TestCase):
    def test_ui_workflow_has_visible_nodes_and_links(self) -> None:
        workflow_path = PROJECT_ROOT / "examples" / "opentoonz_line_tools_basic_ui.json"
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

        self.assertIn("nodes", workflow)
        self.assertGreaterEqual(len(workflow["nodes"]), 8)
        self.assertGreaterEqual(len(workflow["links"]), 7)
        self.assertEqual(workflow["nodes"][0]["type"], "LoadImage")
        self.assertIn("OTBlueLineCleanup", {node["type"] for node in workflow["nodes"]})
        self.assertIn("OTLineAutoClose", {node["type"] for node in workflow["nodes"]})
        self.assertIn("OTRegionPaletteMap", {node["type"] for node in workflow["nodes"]})

    def test_api_workflow_uses_custom_node_class_types(self) -> None:
        workflow_path = PROJECT_ROOT / "examples" / "opentoonz_line_tools_basic_api.json"
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        class_types = {node["class_type"] for node in workflow.values()}

        self.assertIn("LoadImage", class_types)
        self.assertIn("OTBlueLineCleanup", class_types)
        self.assertIn("OTLineAutoClose", class_types)
        self.assertIn("OTRegionPaletteMap", class_types)
        self.assertIn("SaveImage", class_types)


class ComfyNodeBatchTests(unittest.TestCase):
    def test_cleanup_node_preserves_image_batch_size(self) -> None:
        images = np.ones((2, 48, 64, 3), dtype=np.float32)
        images[0, 20:23, 8:56] = np.array([40, 100, 230], dtype=np.float32) / 255.0
        images[1, 25:28, 6:58] = np.array([40, 100, 230], dtype=np.float32) / 255.0

        clean, overlay, preview, settings_json = OTBlueLineCleanup().cleanup(
            torch.from_numpy(images),
            90,
            145,
            28,
            20,
            False,
            8,
            1,
        )

        payload = json.loads(settings_json)
        self.assertEqual(clean.shape[0], 2)
        self.assertEqual(overlay.shape[0], 2)
        self.assertEqual(preview.shape[0], 2)
        self.assertEqual(payload["batch_size"], 2)
        self.assertGreater(payload["images"][0]["line_pixels"], 0)
        self.assertGreater(payload["images"][1]["line_pixels"], 0)

    def test_autoclose_and_region_nodes_preserve_image_batch_size(self) -> None:
        images = np.ones((2, 60, 80, 3), dtype=np.float32)
        for index in range(2):
            images[index, 20, 8:30] = 0.0
            images[index, 20, 38:62] = 0.0
            images[index, 34, 10:60] = 0.0
            images[index, 45, 10:60] = 0.0
            images[index, 34:46, 10] = 0.0
            images[index, 34:46, 60] = 0.0

        closed, overlay, segments_json = OTLineAutoClose().autoclose(torch.from_numpy(images), 180, 12, 90.0, 1, 600)
        regions, regions_json = OTRegionPaletteMap().regions(closed, 180, 20, 128, True)

        self.assertEqual(closed.shape[0], 2)
        self.assertEqual(overlay.shape[0], 2)
        self.assertEqual(json.loads(segments_json)["batch_size"], 2)
        self.assertEqual(regions.shape[0], 2)
        self.assertEqual(json.loads(regions_json)["batch_size"], 2)


if __name__ == "__main__":
    unittest.main()
