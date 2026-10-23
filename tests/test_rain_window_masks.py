"""Rain must reach every pane and never draw over excluded foreground."""
import json
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from rain_window_masks import pane_masks, rain_drops, rain_layer, rain_mask


class RainWindowMasksTest(unittest.TestCase):
    def test_every_batch_pane_receives_rain_without_spill(self):
        masks = json.loads((ROOT / 'data/three_week_window_masks.json').read_text())
        plan = json.loads((ROOT / 'data/three_week_asset_plan.json').read_text())
        self.assertEqual(set(masks), {scene[0] for scene in plan['scenes']})
        size = (1920, 1080)
        drops = rain_drops(size)
        for slug, settings in masks.items():
            with self.subTest(scene=slug):
                settings = dict(settings, _rain_mask=rain_mask(size, settings))
                panes = pane_masks(size, settings)
                accumulated = Image.new('L', size)
                outside = ImageChops.invert(settings['_rain_mask'])
                for frame in range(24):
                    alpha = rain_layer(size, settings, frame/24, drops).getchannel('A')
                    self.assertIsNone(ImageChops.multiply(alpha, outside).getbbox())
                    accumulated = ImageChops.lighter(accumulated, alpha)
                for index, pane in enumerate(panes):
                    # Some lower panes are completely hidden by furniture/plants.
                    if not pane.getbbox():
                        continue
                    self.assertIsNotNone(ImageChops.multiply(accumulated, pane).getbbox(),
                                         f'{slug} pane {index+1} has no rain')
                self.assertTrue(any(pane.getbbox() for pane in panes))

    def test_foreground_hole_and_window_gap_are_dry(self):
        settings = {'windows': [[[0, 0], [500, 0], [500, 941], [0, 941]],
                                [[900, 0], [1672, 0], [1672, 941], [900, 941]]],
                    'rain_exclusions': [[[50, 200], [300, 200], [300, 500], [50, 500]]]}
        mask = rain_mask((1672, 941), settings)
        self.assertEqual(mask.getpixel((100, 300)), 0)
        self.assertEqual(mask.getpixel((700, 300)), 0)
        self.assertEqual(mask.getpixel((400, 300)), 255)

    def test_full_canvas_coverage_and_periodic_boundary(self):
        size = (1672, 941)
        settings = {'windows': [[[0, 0], [1672, 0], [1672, 941], [0, 941]]]}
        settings['_rain_mask'] = rain_mask(size, settings)
        drops = rain_drops(size)
        first = rain_layer(size, settings, 0, drops)
        last = rain_layer(size, settings, 1, drops)
        self.assertIsNone(ImageChops.difference(first, last).getbbox())
        alpha = first.getchannel('A')
        self.assertIsNotNone(alpha.crop((0, 0, 500, 941)).getbbox())
        self.assertIsNotNone(alpha.crop((0, 870, 1672, 941)).getbbox())


if __name__ == '__main__':
    unittest.main()
