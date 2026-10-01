import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
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
