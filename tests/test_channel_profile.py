import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
import os
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_profile import choose, publication_ready, digest, title_allowed


class ChannelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ['data', 'audio', 'scenes', 'run']:
            (self.root / folder).mkdir()
        self.video = {'asset_id': 'local:a', 'local_path': 'scenes/a.mp4',
                      'source_url': 'https://example.com/a', 'license_url': 'https://example.com/license'}
        self.audio = {'id': 1, 'filename': 'rain.mp3', 'freesound_url': 'https://freesound.org/s/1/', 'license': 'CC0'}
        (self.root / 'scenes/a.mp4').write_bytes(b'video')
        (self.root / 'audio/rain.mp3').write_bytes(b'audio')
        self.write('data/video_library.json', [self.video])
        self.write('audio/metadata.json', [self.audio])
        self.write('data/channel_profile.json', {'video_ids': ['local:a'], 'audio_ids': ['1']})

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def test_channel_needs_no_tags_but_preserves_duplicate_protection(self):
        video, audio = choose(self.root, {}, random.Random(1), 'publish')
        self.assertEqual(video, self.video)
        entries = {'used': {'assets': {'date': '2026-10-01', 'video': video,
                                     'audio': {'freesound_id': audio['id']}}}}
        with self.assertRaises(RuntimeError):
            choose(self.root, entries, random.Random(1), 'publish')

    def test_missing_source_preview_only_and_override_cannot_escape_pool(self):
        self.video['source_url'] = ''
        self.write('data/video_library.json', [self.video])
        choose(self.root, {}, random.Random(1), 'preview')
        with self.assertRaises(RuntimeError):
            choose(self.root, {}, random.Random(1), 'publish')
        with self.assertRaises(RuntimeError):
            choose(self.root, {}, random.Random(1), 'preview', audio_id='999')

    def test_channel_cannot_fall_back_to_legacy_approval_or_stale_output(self):
        assets = {'selection_explanation': {'policy': 'channel_profile'}, 'review_approved': True,
                  'video': self.video, 'audio': dict(self.audio, freesound_id=1)}
        self.assertFalse(publication_ready(assets, self.root))
        output = self.root / 'run/output.mp4'; output.write_bytes(b'finished')
        self.write('run/channel-quality.json', {'passed': True, 'video_id': 'local:a', 'audio_id': '1',
                                               'output_sha256': digest(output)})
        self.assertTrue(publication_ready(assets, self.root))
        output.write_bytes(b'changed')
        self.assertFalse(publication_ready(assets, self.root))

    def test_titles_do_not_invent_audio_claims(self):
        self.assertTrue(title_allowed('Rainy Anime Study Room'))
        self.assertFalse(title_allowed('Traffic-free Pure Rain'))

    def test_scheduled_channel_selection_defaults_to_three_hours(self):
        import select_assets
        self.write('data/scene_terms.json', ['rain window'])
        self.write('data/title_templates.json', ['{duration} Minutes of Rain Ambience'])
        (self.root / 'data/description_template.txt').write_text('{duration} minutes of {scene_term}')
        with patch.dict(os.environ, {'PIPELINE_MODE': 'publish', 'ASSET_SELECTION': 'channel'}, clear=True), \
             patch.object(select_assets, 'ROOT', self.root), \
             patch.object(select_assets, 'DATA_DIR', self.root / 'data'), \
             patch.object(select_assets, 'AUDIO_DIR', self.root / 'audio'), \
             patch.object(select_assets, 'RUN_DIR', self.root / 'run'), \
             patch.object(select_assets, 'Ledger') as ledger:
            ledger.return_value.entries = {}
            select_assets.main()
            result = json.loads((self.root / 'run/assets.json').read_text())
            self.assertEqual(result['duration_seconds'], 10800)
            self.assertEqual(len(result['title_options']), 3)
            self.assertTrue(all('3 Hours' in title for title in result['title_options']))
            ledger.return_value.check_new.assert_called_once_with(result)
