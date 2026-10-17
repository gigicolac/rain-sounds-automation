from pathlib import Path
import sys
import tempfile
import unittest
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from create_custom_audio import droplets, create


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
