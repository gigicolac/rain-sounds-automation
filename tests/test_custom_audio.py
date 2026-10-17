from pathlib import Path
import sys
import tempfile
import unittest
import wave
import json
import random
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from create_custom_audio import droplets, create, density_at, PROFILES
from stage_custom_audio import stage
from channel_profile import choose, digest
from upload_history import fingerprint


class CustomAudioTests(unittest.TestCase):
    def test_droplets_reproduce_seed_and_have_exact_stereo_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = [Path(tmp) / name for name in ('a.wav', 'b.wav', 'c.wav')]
            droplets(a, .5, 123); droplets(b, .5, 123); droplets(c, .5, 124)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertNotEqual(a.read_bytes(), c.read_bytes())
            with wave.open(str(a)) as audio:
                self.assertEqual(audio.getnchannels(), 2)
                self.assertEqual(audio.getnframes(), 24000)

    def test_existing_candidates_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'approved.flac'; marker.write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                create(Path(tmp), Path(tmp))
            self.assertEqual(marker.read_bytes(), b'keep')

    def test_light_and_moderate_have_distinct_density_and_loudness(self):
        self.assertLess(PROFILES[0]['rate'], PROFILES[-1]['rate'])
        self.assertLessEqual(PROFILES[0]['target'], PROFILES[-1]['target']-6)
        curve=[.2,.8,.3,.9,.2]
        self.assertEqual(density_at(0,90,curve),.2)
        self.assertEqual(density_at(22.5,90,curve),.8)
        self.assertAlmostEqual(density_at(90,90,curve),.2)
        with tempfile.TemporaryDirectory() as tmp:
            light=droplets(Path(tmp)/'light.wav',1,123,rate=5,curve=curve)
            moderate=droplets(Path(tmp)/'moderate.wav',1,123,rate=80,curve=curve)
            self.assertLess(len(light),len(moderate))

    def test_pending_custom_audio_cannot_publish_even_if_enabled_in_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'data').mkdir(); (root/'audio').mkdir(); (root/'scenes').mkdir()
            (root/'scenes/a.mp4').write_bytes(b'video'); (root/'audio/custom.flac').write_bytes(b'audio')
            (root/'data/channel_profile.json').write_text(json.dumps({'video_ids':['custom:a'], 'audio_ids':['custom-audio:a']}))
            (root/'data/video_library.json').write_text(json.dumps([{'asset_id':'custom:a','local_path':'scenes/a.mp4','source_url':'source','license_url':'terms'}]))
            (root/'audio/metadata.json').write_text(json.dumps([{'id':'custom-audio:a','asset_id':'custom-audio:a','filename':'custom.flac','components':[{'kind':'procedural'}],'source_url':'code','license':'original','review':{'approved':False}}]))
            with self.assertRaisesRegex(RuntimeError, 'No unused channel pair'):
                choose(root, {}, random.Random(1), 'publish')
            self.assertEqual(choose(root, {}, random.Random(1), 'preview')[1]['id'], 'custom-audio:a')

    def test_reviewed_staging_preserves_legacy_metadata_and_keeps_pending_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'data').mkdir(); (root/'audio').mkdir()
            candidates=root/'candidates'; candidates.mkdir(); source=candidates/'sound.flac';source.write_bytes(b'audio')
            record={'id':'custom-audio:a','path':'sound.flac','sha256':digest(source),'technical_pass':True,
                    'title':'Custom rain','duration':90,'components':[{'kind':'procedural'}],
                    'review':{'approved':False,'status':'pending'}}
            (candidates/'candidates.json').write_text(json.dumps([record]))
            with self.assertRaisesRegex(ValueError,'Full listening'):
                stage(candidates,['custom-audio:a'],root)
            self.assertFalse((root/'audio/metadata.json').exists())
            record['review']={'approved':True,'status':'approved','notes':'User approved full playback and repeat boundaries',
                              'reviewed_at':'2026-10-17','quality':{'full_playback':True,'loop_checked':True}}
            record['target_lufs']=-29
            (candidates/'candidates.json').write_text(json.dumps([record]))
            legacy={'id':1,'review':{'notes':'keep'}}
            (root/'audio/metadata.json').write_text(json.dumps([legacy]))
            (root/'data/channel_profile.json').write_text(json.dumps({'audio_ids':['1']}))
            stage(candidates,['custom-audio:a'],root)
            metadata=json.loads((root/'audio/metadata.json').read_text())
            self.assertEqual(metadata[0],legacy)
            self.assertEqual(metadata[1]['asset_id'],'custom-audio:a')
            self.assertEqual(metadata[1]['target_lufs'],-29)
            a={'video':{'asset_id':'custom:v'},'audio':{'asset_id':'custom-audio:a','freesound_id':None}}
            b={'video':{'asset_id':'custom:v'},'audio':{'asset_id':'custom-audio:b','freesound_id':None}}
            self.assertNotEqual(fingerprint(a),fingerprint(b))
