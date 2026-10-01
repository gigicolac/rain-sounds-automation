import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import media_quality
import build_video


class AudioDurationTests(unittest.TestCase):
    def test_short_normalized_audio_cannot_pass(self):
        report = {'loudness': {'input_i': '-20', 'input_tp': '-2', 'input_lra': '7',
                              'input_thresh': '-30', 'target_offset': '0'}}
        with tempfile.TemporaryDirectory() as folder, \
                patch('media_quality.probe', side_effect=[
                    {'format': {'duration': '74.666667'}}, {'format': {'duration': '66.666667'}}]), \
                patch('media_quality.audio_report', side_effect=[copy.deepcopy(report) for _ in range(3)]), \
                patch('media_quality.subprocess.run'):
            with self.assertRaisesRegex(ValueError, 'does not match target'):
                media_quality.prepare_audio(Path('rain.mp3'), Path(folder) / 'prepared.wav', 300)

    def test_five_minute_video_with_one_minute_audio_fails_final_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); run = root / 'run'; run.mkdir(); (root / 'scenes').mkdir()
            (root / 'scenes/source.mp4').write_bytes(b'source')
            (run / 'output.mp4').write_bytes(b'rendered')
            (run / 'assets.json').write_text(json.dumps({
                'video': {'asset_id': 'local:test', 'local_path': 'scenes/source.mp4'},
                'audio': {'freesound_id': '1'}, 'duration_seconds': 300,
                'selection_explanation': {'policy': 'channel_profile'}}))
            (run / 'prepared-audio.quality.json').write_text(json.dumps({
                'normalized_output': {'peak_db': -2}}))
            with patch.multiple(build_video, ROOT=root, RUN_DIR=run,
                                ASSETS_PATH=run / 'assets.json', SCENE_PATH=run / 'scene.mp4',
                                OUTPUT_PATH=run / 'output.mp4'), \
                    patch('build_video.run_ffmpeg'), \
                    patch('build_video.probe', return_value={'streams': [
                        {'codec_type': 'audio', 'duration': '66.666'}]}), \
                    patch('preflight_assets.measure', return_value={
                        'decode_ok': True, 'width': 1920, 'height': 1080, 'duration_seconds': 300}):
                with self.assertRaisesRegex(ValueError, 'failed automatic channel checks'):
                    build_video.main()
            report = json.loads((run / 'channel-quality.json').read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(report['audio_duration_seconds'], 66.666)


if __name__ == '__main__':
    unittest.main()
