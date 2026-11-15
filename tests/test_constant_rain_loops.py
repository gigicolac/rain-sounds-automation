"""Real decoded-audio regression checks for steady rain at repeat boundaries."""
import array
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from media_quality import seamless_cycle, prepare_audio, probe, ffmpeg


@unittest.skipUnless(shutil.which(ffmpeg()) and shutil.which('ffprobe'), 'FFmpeg required')
class ConstantRainTests(unittest.TestCase):
    def noise(self, path, seconds):
        rng = random.Random(1234)
        samples = array.array('h', (rng.randrange(-8000, 8001) for _ in range(48000 * seconds * 2)))
        with wave.open(str(path), 'wb') as f:
            f.setnchannels(2); f.setsampwidth(2); f.setframerate(48000)
            f.writeframes(samples.tobytes())

    def samples(self, path):
        data = subprocess.run([ffmpeg(), '-v', 'error', '-i', str(path),
            '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'],
            check=True, capture_output=True).stdout
        samples = array.array('f'); samples.frombytes(data)
        return samples

    def level(self, samples):
        return 10 * math.log10(sum(x*x for x in samples) / len(samples))

    def test_cyclic_join_keeps_noise_power_and_sample_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); self.noise(r/'source.wav',7)
            seamless_cycle(r/'source.wav',r/'cycle.flac',6,overlap=1)
            x=self.samples(r/'cycle.flac')
            self.assertEqual(len(x),6*48000)
            baseline=self.level(x[48000:4*48000])
            # Crossfade midpoint and both sides of the actual repeat stay full.
            for a,b in [(5.4,5.6),(0,.2),(5.8,6)]:
                self.assertLess(abs(self.level(x[int(a*48000):int(b*48000)])-baseline),.5)
            # Seam step is no larger than an ordinary transient in this fixture.
            normal=max(abs(x[i]-x[i-1]) for i in range(1,len(x)))
            self.assertLessEqual(abs(x[0]-x[-1]),normal)

    def test_prepared_repeats_have_no_power_dip_or_asset_edge_fades(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); self.noise(r/'source.wav',7)
            prepare_audio(r/'source.wav',r/'prepared.wav',18,fade=1,edge_fade=0)
            x=self.samples(r/'prepared.wav')
            self.assertEqual(len(x),18*48000)
            baseline=self.level(x[48000:5*48000])
            for a,b in [(0,.2),(6.4,6.6),(12.4,12.6),(17.8,18)]:
                self.assertLess(abs(self.level(x[int(a*48000):int(b*48000)])-baseline),.7)

    def test_short_cycle_handle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);self.noise(r/'source.wav',3)
            with self.assertRaisesRegex(ValueError,'extra overlap'):
                seamless_cycle(r/'source.wav',r/'cycle.flac',3,overlap=1)
