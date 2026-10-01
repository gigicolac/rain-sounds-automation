import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from preflight_assets import suggestions, run


class PreflightTests(unittest.TestCase):
    def test_ambiguous_hints_and_event_absence_stay_unknown(self):
        hints = suggestions({'title': 'anime forest city gentle rain no voices'})
        self.assertNotIn('setting', hints)
        self.assertNotIn('voices', hints)
        self.assertEqual(hints['style']['value'], 'illustrated')

    def test_cache_invalidates_and_reviews_are_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            media = root / 'clip.mp4'
            media.write_bytes(b'first')
            catalog = root / 'data/video_library.json'
            catalog.write_text(json.dumps([{'asset_id': 'local:test', 'local_path': 'clip.mp4',
                                          'review': {'approved': False, 'labels': {'setting': 'lake'}}}]))
            original = catalog.read_bytes()
            with patch('preflight_assets.measure', return_value={'decode_ok': True}) as measure:
                run(root); run(root)
                self.assertEqual(measure.call_count, 1)
                media.write_bytes(b'changed')
                run(root)
                self.assertEqual(measure.call_count, 2)
            self.assertEqual(catalog.read_bytes(), original)

    def test_failure_is_reported_without_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data/video_library.json').write_text(json.dumps([
                {'asset_id': 'local:missing', 'local_path': 'missing.mp4'}]))
            report = json.loads(run(root).read_text())['assets']['local:missing']
            self.assertTrue(report['warnings'])
            self.assertNotIn('measurements', report)


if __name__ == '__main__':
    unittest.main()
