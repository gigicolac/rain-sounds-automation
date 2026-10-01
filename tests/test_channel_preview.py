import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_preview import select


class ChannelPreviewTests(unittest.TestCase):
    def test_no_tags_required_and_no_publication_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'data').mkdir(); (root/'audio').mkdir()
            (root/'clip.mp4').touch(); (root/'audio/rain.mp3').touch()
            (root/'data/channel_profile.json').write_text(json.dumps({'name':'Rain','video_ids':['local:a'],'audio_ids':['1']}))
            (root/'data/video_library.json').write_text(json.dumps([{'asset_id':'local:a','local_path':'clip.mp4'}]))
            (root/'audio/metadata.json').write_text(json.dumps([{'id':1,'filename':'rain.mp3'}]))
            plan=select(root,random.Random(1))
            self.assertFalse(plan['review_approved'])
            self.assertEqual(plan['video']['asset_id'],'local:a')
            (root/'audio/rain.mp3').unlink()
            with self.assertRaises(ValueError): select(root,random.Random(1))

    def test_missing_default_does_not_select_unrelated_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'default rain'):
                select(Path(folder),random.Random(1))
