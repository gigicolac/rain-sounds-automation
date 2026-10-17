import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_profile import digest
from package_custom_scenes import package


class CustomSceneTests(unittest.TestCase):
    def library(self, root):
        folder = root / 'run/image-scenes/approved'; folder.mkdir(parents=True)
        (folder / 'master.png').write_bytes(b'master')
        (folder / 'approved.mp4').write_bytes(b'approved preview')
        (folder / 'draft.mp4').write_bytes(b'unapproved draft')
        spec = {'approved_preview': 'approved.mp4', 'preview': 'draft.mp4',
                'approved_preview_sha256': digest(folder / 'approved.mp4'),
                'master_sha256': digest(folder / 'master.png')}
        (folder / 'package.json').write_text(json.dumps(spec))
        registry = {'approved': {'status': 'approve', 'package_checked': True,
                    'package': 'run/image-scenes/approved', 'notes': 'Explicitly approved preview'},
                    'reject': {'status': 'reject', 'package_checked': True, 'package': 'missing'},
                    'spare': {'status': 'pass', 'package_checked': True, 'package': 'missing'}}
        (root / 'run/image-scene-library.json').write_text(json.dumps(registry))
        return folder

    def test_only_exact_approved_preview_exports_and_old_catalogue_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); library = root / 'library'; destination = root / 'destination'
            library.mkdir(); destination.mkdir(); (destination / 'data').mkdir()
            (destination / 'data/video_library.json').write_text(json.dumps([{'asset_id': 'old'}]))
            (destination / 'data/channel_profile.json').write_text(json.dumps({'audio_ids': ['1']}))
            self.library(library)
            with patch('package_custom_scenes.probe', return_value={'streams': [{'codec_type':'video', 'width':1920, 'height':1080}], 'format': {'duration':10}}):
                bundle = package(library, destination)
            import zipfile
            with zipfile.ZipFile(bundle) as archive:
                self.assertEqual(archive.namelist(), ['scenes/custom-approved.mp4'])
                self.assertEqual(archive.read(archive.namelist()[0]), b'approved preview')
            profile = json.loads((destination / 'data/channel_profile.json').read_text())
            self.assertEqual(profile['video_ids'], ['custom:approved'])
            self.assertEqual(profile['audio_ids'], ['1'])
            catalogue = json.loads((destination / 'data/video_library.json').read_text())
            self.assertEqual(catalogue[0]['asset_id'], 'old')
            self.assertEqual(catalogue[1]['review']['labels'], {})

    def test_changed_approved_media_cannot_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); library = root / 'library'; destination = root / 'destination'
            library.mkdir(); destination.mkdir()
            folder = self.library(library)
            (folder / 'approved.mp4').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'reviewed media changed'):
                package(library, destination)
            self.assertFalse((destination / 'data/channel_profile.json').exists())
