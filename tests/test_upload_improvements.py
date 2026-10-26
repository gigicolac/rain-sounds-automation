import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import make_thumbnail
import upload_youtube as upload
from channel_profile import clean_rain, confirmed_clean, publication_ready
from upload_history import Ledger

CLEAN = {'traffic': False, 'voices': False, 'music': False, 'thunder': False, 'animals': False}
REPO = Path(__file__).resolve().parents[1]
SIREN = 'WTHR-MIX_RAIN-Underneath Roof With City Traffic And A Siren'


def mix(notes='full, dense', sources=('Heavy Rain Forest',), labels=None):
    return {'title': 'Week 3 / 21 - Quiet music room', 'review': {'approved': True, 'notes': notes, 'labels': labels or {}},
            'components': [{'kind': 'procedural'}] + [{'kind': 'licensed_recording', 'original_title': t} for t in sources]}


class CleanRainTests(unittest.TestCase):
    def test_custom_mix_checked_through_sources_and_notes_not_scene_name(self):
        self.assertTrue(clean_rain(mix()))  # "music room" is a scene name, not audio content
        self.assertFalse(clean_rain(mix(sources=('Heavy Rain Forest', SIREN))))
        self.assertFalse(clean_rain(mix(notes='windy, traffic-y, light')))
        self.assertFalse(clean_rain(mix(labels={'thunder': True})))

    def test_single_recordings_checked_by_title_and_labels(self):
        self.assertTrue(clean_rain({'title': 'Steady rain', 'review': {'approved': True, 'labels': CLEAN}}))
        self.assertFalse(clean_rain({'title': SIREN, 'review': {'approved': True, 'labels': {}}}))
        self.assertFalse(clean_rain({'title': 'Rain', 'review': {'approved': True, 'labels': dict(CLEAN, voices=True)}}))

    def test_no_distractions_claim_needs_confirmed_labels(self):
        self.assertFalse(confirmed_clean(mix()))  # unknown is not absent
        self.assertTrue(confirmed_clean(mix(labels=CLEAN)))
        self.assertFalse(confirmed_clean(mix(labels=CLEAN, notes='traffic')))

    def test_live_pool_excludes_exactly_the_traffic_mixes(self):
        profile = json.loads((REPO / 'data/channel_profile.json').read_text())
        audio = {str(a['id']): a for a in json.loads((REPO / 'audio/metadata.json').read_text())}
        blocked = sorted(a for a in profile['audio_ids'] if not clean_rain(audio[a]))
        self.assertEqual(blocked, ['custom-audio:three-weeks-04-rooftop-cat', 'custom-audio:three-weeks-12-bakery-cat',
                                   'custom-audio:three-weeks-27-city-cat'])
        self.assertGreaterEqual(len(profile['audio_ids']) - len(blocked), 20)

    def test_publication_gate_rejects_traffic_audio(self):
        assets = {'selection_explanation': {'policy': 'channel_profile'}, 'video': {'asset_id': 'custom:a'},
                  'audio': dict(mix(sources=(SIREN,)), asset_id='custom-audio:x')}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir()
            (root / 'data/channel_profile.json').write_text(json.dumps(
                {'video_ids': ['custom:a'], 'audio_ids': ['custom-audio:x']}))
            self.assertFalse(publication_ready(assets, root))


class UploadBodyTests(unittest.TestCase):
    def test_ai_disclosure_and_no_paid_promotion_on_every_upload(self):
        assets = {'title': 'Rain', 'description': 'Rain', 'tags': [], 'date': '2026-10-26'}
        body = upload.upload_body(assets)
        self.assertIs(body['status']['containsSyntheticMedia'], True)
        self.assertIs(body['paidProductPlacementDetails']['hasPaidProductPlacement'], False)
        self.assertEqual(body['snippet']['categoryId'], '10')


class UploadFlowTests(unittest.TestCase):
    def run_upload(self, run, **patches):
        defaults = dict(get_credentials=Mock(), build=Mock(), verify_target_channel=Mock(),
                        upload_video=Mock(return_value={'id': 'vid'}), set_thumbnail=Mock(),
                        scheduled_release=Mock(return_value='2026-10-27T13:00:00.000Z'),
                        wait_for_processing=Mock(return_value={'privacyStatus': 'private'}))
        defaults.update(patches)
        targets = [patch.object(upload, name, value) for name, value in defaults.items()]
        targets += [patch.object(upload, 'RUN_DIR', run), patch.object(upload, 'ASSETS_PATH', run / 'assets.json'),
                    patch.object(upload, 'VIDEO_PATH', run / 'output.mp4'),
                    patch.object(upload, 'RESULT_PATH', run / 'upload_result.json')]
        for target in targets:
            target.start()
        self.addCleanup(lambda: [t.stop() for t in targets])
        upload.main()
        return defaults

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.run_dir = self.root / 'run'; self.run_dir.mkdir()
        self.assets = {'date': '2026-10-27', 'video': {'pexels_id': 1}, 'audio': {'freesound_id': 2},
                       'review_approved': True, 'thumbnail_headline': 'COZY\nRAIN',
                       'pinned_comment': 'tell us', 'title_options': ['A', 'B']}
        (self.run_dir / 'assets.json').write_text(json.dumps(self.assets))
        (self.run_dir / 'output.mp4').write_bytes(b'video')
        for target in (patch('upload_history.ROOT', self.root),
                       patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(self.root / 'summary.md')}, clear=True)):
            target.start(); self.addCleanup(target.stop)

    def test_thumbnail_is_set_even_when_processing_times_out(self):
        calls = []
        with self.assertRaises(TimeoutError):
            self.run_upload(self.run_dir, set_thumbnail=Mock(side_effect=lambda *a: calls.append('thumbnail')),
                            wait_for_processing=Mock(side_effect=TimeoutError('still processing')))
        entry = Ledger().find_video('vid')[1]
        self.assertEqual(calls, ['thumbnail'])
        self.assertEqual((entry['state'], entry['thumbnail']), ('uploaded', 'set'))

    def test_resume_after_timeout_does_not_reset_the_thumbnail(self):
        thumbnail = Mock()
        with self.assertRaises(TimeoutError):
            self.run_upload(self.run_dir, set_thumbnail=thumbnail, wait_for_processing=Mock(side_effect=TimeoutError('later')))
        with patch.dict(os.environ, {'RESUME_VIDEO_ID': 'vid'}):
            mocks = self.run_upload(self.run_dir, set_thumbnail=thumbnail)
        mocks['upload_video'].assert_not_called()
        thumbnail.assert_called_once()
        self.assertEqual(Ledger().find_video('vid')[1]['state'], 'complete')

    def test_summary_lists_studio_only_steps(self):
        self.run_upload(self.run_dir)
        summary = (self.root / 'summary.md').read_text()
        for step in ('2026-10-27T13:00:00.000Z', 'Pin the channel comment', 'End screen', 'never aired on television',
                     'Shorts remixing', 'playlist'):
            self.assertIn(step, summary)


class BrandVoiceTests(unittest.TestCase):
    REQUIRED = ('restorative', 'relaxation', 'flow', 'drift', 'calm your nervous system',
                'focus', 'improve', 'productivity')

    def descriptions(self):
        import random, re
        import select_assets
        from upload_presentation import THEMES, description_parts
        audio = {'title': 'Steady rain', 'freesound_url': 'https://freesound.org/s/7/',
                 'license': 'http://creativecommons.org/publicdomain/zero/1.0/'}
        copy = json.loads((REPO / 'data/description_copy.json').read_text())
        for headline in THEMES:
            for seed in range(len(copy[headline]['openings']) * 4):
                parts = description_parts(headline, 180, audio, random.Random(seed), True)
                yield headline, select_assets.build_description('rain', audio['title'], 180, {}, audio, parts)

    def test_every_description_uses_the_brand_words(self):
        for headline, text in self.descriptions():
            for word in self.REQUIRED:
                self.assertIn(word, text.lower(), (headline, word))

    def test_no_ai_tells_or_repeated_phrases(self):
        import re
        for headline, text in self.descriptions():
            self.assertNotIn('\u2014', text)
            brand = text.split('About Calming Rain Sounds')[0].lower()
            words = re.findall(r"[a-z']+", brand)
            grams = [' '.join(words[i:i + 4]) for i in range(len(words) - 3)]
            self.assertEqual({g for g in grams if grams.count(g) > 1}, set(), headline)

    def test_search_keyword_in_first_two_lines(self):
        for headline, text in self.descriptions():
            self.assertIn('rain sounds for', ' '.join(text.splitlines()[:2]).lower(), headline)


class ThumbnailDesignTests(unittest.TestCase):
    def test_every_locked_headline_renders_in_every_layout(self):
        from PIL import Image
        from thumbnail_design import render
        from upload_presentation import THEMES
        frame = Image.new('RGB', (1280, 720), (40, 30, 22))
        for headline in THEMES:
            for style in ('soft', 'pixel', 'stacked', 'accent', 'panel'):
                for side in ('left', 'right'):
                    self.assertEqual(render(frame, 10800, headline, style, side).size, (1280, 720))


    def test_centred_text_is_centred_and_long_headlines_fit(self):
        from PIL import Image, ImageChops
        from thumbnail_design import render
        frame = Image.new('RGB', (1280, 720), (0, 0, 0))
        for style in ('soft', 'pixel'):
            for headline in ('COZY\nRAIN', 'DEEP SLEEP\nRAIN', 'INSOMNIA\nRAIN'):
                box = ImageChops.difference(render(frame, 10800, headline, style), frame).getbbox()
                left, top, right, bottom = box
                self.assertLess(abs((left + right) / 2 - 640), 20, (style, headline))
                self.assertLess(abs((top + bottom) / 2 - 360), 40, (style, headline))
                self.assertGreater(left, 60)

    def test_live_profile_defaults_to_pixel(self):
        profile = json.loads((REPO / 'data/channel_profile.json').read_text())
        self.assertEqual((profile['thumbnail_style'], profile['thumbnail_alternate_style']), ('pixel', 'soft'))


class ThumbnailSourceTests(unittest.TestCase):
    def test_locked_scene_used_and_required_for_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'scenes').mkdir()
            assets = {'duration_seconds': 10800, 'thumbnail_background': {
                'local_path': 'scenes/mug.mp4', 'frame_seconds': 4.0}}
            with patch.object(make_thumbnail, 'ROOT', root), \
                    patch.object(make_thumbnail, 'VIDEO_PATH', root / 'run/output.mp4'):
                with self.assertRaisesRegex(RuntimeError, 'Locked thumbnail scene is missing'):
                    make_thumbnail.frame_source(assets, 'publish')
                self.assertEqual(make_thumbnail.frame_source(assets, 'preview'), (root / 'run/output.mp4', 300))
                (root / 'scenes/mug.mp4').write_bytes(b'video')
                self.assertEqual(make_thumbnail.frame_source(assets, 'publish'), ((root / 'scenes/mug.mp4').resolve(), 4.0))


class ChannelSelectionTests(unittest.TestCase):
    def test_channel_assets_carry_locked_cover_comment_and_truthful_description(self):
        import select_assets
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ('data', 'audio', 'scenes', 'run'):
                (root / folder).mkdir()
            shutil.copy(REPO / 'data/description_template.txt', root / 'data/description_template.txt')
            (root / 'data/scene_terms.json').write_text('[]')
            (root / 'data/title_templates.json').write_text('["{duration} Minutes"]')
            videos = [{'asset_id': f'custom:{n}', 'local_path': f'scenes/{n}.mp4', 'source_url': 's',
                       'license_url': 'l', 'thumbnail_text_side': side} for n, side in (('a', 'left'), ('mug', 'right'))]
            for video in videos:
                (root / video['local_path']).write_bytes(b'video')
            audio = {'id': 7, 'filename': 'rain.mp3', 'title': 'Steady rain', 'freesound_url': 'https://freesound.org/s/7/',
                     'license': 'http://creativecommons.org/publicdomain/zero/1.0/',
                     'review': {'approved': True, 'labels': CLEAN}}
            (root / 'audio/rain.mp3').write_bytes(b'audio')
            (root / 'data/video_library.json').write_text(json.dumps(videos))
            (root / 'audio/metadata.json').write_text(json.dumps([audio]))
            (root / 'data/channel_profile.json').write_text(json.dumps({
                'video_ids': ['custom:a'], 'audio_ids': ['7'], 'thumbnail_scene_id': 'custom:mug'}))
            with patch.dict(os.environ, {'PIPELINE_MODE': 'publish', 'ASSET_SELECTION': 'channel'}, clear=True), \
                    patch.object(select_assets, 'ROOT', root), patch.object(select_assets, 'DATA_DIR', root / 'data'), \
                    patch.object(select_assets, 'AUDIO_DIR', root / 'audio'), \
                    patch.object(select_assets, 'RUN_DIR', root / 'run'), \
                    patch.object(select_assets, 'Ledger') as ledger:
                ledger.return_value.entries = {}
                select_assets.main()
            assets = json.loads((root / 'run/assets.json').read_text())
        self.assertEqual(assets['video']['asset_id'], 'custom:a')
        self.assertEqual(assets['thumbnail_background']['asset_id'], 'custom:mug')
        self.assertTrue(all(v['side'] == 'right' for v in assets['thumbnail_variants']))
        self.assertTrue(assets['pinned_comment'])
        description = assets['description']
        self.assertIn('rain sounds for', description.splitlines()[0].lower())
        self.assertIn('Just steady rain. No music, no voices, no distractions.', description)  # labels confirmed
        self.assertIn('·', assets['overlay_title'])
        self.assertNotIn('🌧', assets['overlay_title'])
        self.assertIn('0:00 Settle in and breathe', description)
        self.assertIn('released under Creative Commons 0 (public domain)', description)
        self.assertNotIn('\n\n\n', description)
        self.assertNotIn('{', description)


if __name__ == '__main__':
    unittest.main()
