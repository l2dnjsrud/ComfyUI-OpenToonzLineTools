from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

from opentoonz_line_tools.autoclose import AutoCloseSettings, autoclose_gaps
from opentoonz_line_tools.cleanup import BlueCleanupSettings, cleanup_blue_lines
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


if __name__ == "__main__":
    unittest.main()
