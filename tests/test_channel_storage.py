import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_profile import digest
from channel_storage import restore


class StorageTests(unittest.TestCase):
    def test_verified_restore_and_existing_file_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'data').mkdir()
            sample = root / 'sample'; sample.write_bytes(b'video')
            bundle = root / 'bundle.zip'
            with zipfile.ZipFile(bundle, 'w') as archive:
                archive.write(sample, 'scenes/a.mp4')
            (root / 'data/channel_storage.json').write_text(json.dumps({'bundle_sha256': digest(bundle)}))
            (root / 'data/channel_asset_manifest.json').write_text(json.dumps([
                {'path': 'scenes/a.mp4', 'sha256': digest(sample), 'bytes': 5}]))
            restore(bundle, root)
            target = root / 'scenes/a.mp4'
            self.assertEqual(target.read_bytes(), b'video')
            target.write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError, 'Existing media differs'):
                restore(bundle, root)
            self.assertEqual(target.read_bytes(), b'preserve')

    def test_bundle_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'data').mkdir()
            bundle = root / 'bundle.zip'; bundle.write_bytes(b'bad')
            (root / 'data/channel_storage.json').write_text(json.dumps({'bundle_sha256': 'wrong'}))
            with self.assertRaisesRegex(ValueError, 'checksum'):
                restore(bundle, root)
