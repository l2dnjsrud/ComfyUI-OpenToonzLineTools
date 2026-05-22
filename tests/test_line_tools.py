from __future__ import annotations

import unittest

import numpy as np

from opentoonz_line_tools.autoclose import AutoCloseSettings, autoclose_gaps
from opentoonz_line_tools.cleanup import BlueCleanupSettings, cleanup_blue_lines
from opentoonz_line_tools.regions import RegionSettings, label_fill_regions


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


if __name__ == "__main__":
    unittest.main()
