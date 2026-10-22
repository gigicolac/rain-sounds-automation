import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import make_thumbnail
import upload_youtube as upload
from channel_profile import clean_rain, publication_ready
from googleapiclient.errors import HttpError
from publish_schedule import next_publish_time
from upload_history import Ledger

CLEAN = {'traffic': False, 'voices': False, 'music': False, 'thunder': False, 'animals': False}
REPO = Path(__file__).resolve().parents[1]


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


class CleanRainTests(unittest.TestCase):
    def test_siren_recording_and_unknown_labels_are_not_clean(self):
        self.assertTrue(clean_rain({'title': 'Steady rain', 'review': {'approved': True, 'labels': CLEAN}}))
        traffic = {'title': 'Rain With City Traffic And A Siren',
                   'review': {'approved': True, 'labels': dict(CLEAN, traffic=True)}}
        self.assertFalse(clean_rain(traffic))
        # A siren in the title is enough even if a label was missed.
        self.assertFalse(clean_rain({'title': 'Rain and a siren', 'review': {'approved': True, 'labels': CLEAN}}))
        # Unknown does not mean absent.
        unknown = dict(CLEAN); del unknown['voices']
        self.assertFalse(clean_rain({'title': 'Rain', 'review': {'approved': True, 'labels': unknown}}))
        self.assertFalse(clean_rain({'title': 'Rain', 'review': {'approved': False, 'labels': CLEAN}}))

    def test_live_channel_pool_contains_only_confirmed_clean_rain(self):
        profile = json.loads((REPO / 'data/channel_profile.json').read_text())
        audio = {str(a['id']): a for a in json.loads((REPO / 'audio/metadata.json').read_text())}
        self.assertNotIn('788146', profile['audio_ids'])
        for audio_id in profile['audio_ids']:
            self.assertTrue(clean_rain(audio[audio_id]), audio_id)

    def test_publication_gate_rejects_traffic_audio(self):
        assets = {'selection_explanation': {'policy': 'channel_profile'},
                  'video': {'asset_id': 'custom:a'},
                  'audio': {'freesound_id': 788146, 'title': 'City Traffic And A Siren',
                            'review': {'approved': True, 'labels': dict(CLEAN, traffic=True)}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir()
            (root / 'data/channel_profile.json').write_text(json.dumps(
                {'video_ids': ['custom:a'], 'audio_ids': ['788146']}))
            self.assertFalse(publication_ready(assets, root))


class ScheduleTests(unittest.TestCase):
    def test_evening_render_publishes_in_next_day_window(self):
        # Tue 20:30 EDT; Tuesday's window has closed, Wednesday opens at 12:00 EDT.
        self.assertEqual(next_publish_time(utc(2026, 10, 21, 0, 30)), utc(2026, 10, 21, 16, 0))

    def test_upload_inside_a_window_keeps_two_hour_processing_lead(self):
        # Wed 13:07 EDT + 2 hours = 15:07, rounded to 15:15 inside Wednesday's 12:00-21:00 window.
        self.assertEqual(next_publish_time(utc(2026, 10, 21, 17, 7)), utc(2026, 10, 21, 19, 15))

    def test_skips_a_window_that_would_close_within_thirty_minutes(self):
        # Thu 11:45 EDT + 2 hours leaves under 30 minutes of Thursday's window; Friday opens 11:00 EDT.
        self.assertEqual(next_publish_time(utc(2026, 10, 22, 15, 45)), utc(2026, 10, 23, 15, 0))

    def test_weekend_evening_window(self):
        # Sat 18:00 EDT + 2 hours: morning window gone, evening window opens 21:00 EDT.
        self.assertEqual(next_publish_time(utc(2026, 10, 24, 22, 0)), utc(2026, 10, 25, 1, 0))

    def test_daylight_saving_change(self):
        # Sun 1 Nov 20:00 EST (after US clocks change) + 2 hours = 22:00, inside Sunday 21:00-23:00.
        self.assertEqual(next_publish_time(utc(2026, 11, 2, 1, 0)), utc(2026, 11, 2, 3, 0))


class UploadBodyTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((REPO / 'data/upload_settings.json').read_text())
        self.assets = {'title': 'Rain Sounds for Sleep | Calm a Racing Mind | 3 Hours',
                       'description': 'Rain sounds for sleep.', 'tags': ['rain sounds']}

    def test_every_upload_carries_channel_defaults(self):
        body = upload.video_body(self.assets, self.settings, today=date(2026, 10, 22))
        self.assertEqual(body['snippet']['categoryId'], '10')
        self.assertEqual(body['snippet']['defaultLanguage'], 'en-AU')
        self.assertEqual(body['snippet']['defaultAudioLanguage'], 'en-AU')
        self.assertIs(body['status']['containsSyntheticMedia'], True)
        self.assertIs(body['status']['selfDeclaredMadeForKids'], False)
        self.assertIs(body['paidProductPlacementDetails']['hasPaidProductPlacement'], False)
        self.assertEqual(body['recordingDetails']['recordingDate'], '2026-10-22T00:00:00Z')
        self.assertEqual(body['recordingDetails']['locationDescription'], 'Melbourne, Australia')

    def test_scheduled_release_is_private_until_publish_time(self):
        with patch.object(upload, 'PRIVACY_STATUS', 'public'):
            body = upload.video_body(self.assets, self.settings, utc(2026, 10, 21, 16, 0), date(2026, 10, 21))
        self.assertEqual(body['status']['privacyStatus'], 'private')
        self.assertEqual(body['status']['publishAt'], '2026-10-21T16:00:00Z')

    def test_only_public_scheduled_runs_get_a_publish_time(self):
        cases = [('public', 'scheduled', True), ('public', 'immediate', False),
                 ('unlisted', 'scheduled', False), ('private', 'scheduled', False)]
        for privacy, timing, expected in cases:
            with patch.object(upload, 'PRIVACY_STATUS', privacy), patch.object(upload, 'PUBLISH_TIMING', timing):
                self.assertEqual(upload.scheduled_publish_at(utc(2026, 10, 21, 0, 30)) is not None, expected)

    def test_playlist_scope_only_requested_once_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            settings = dict(self.settings, playlists={'COZY\nRAIN': ''})
            path.write_text(json.dumps(settings))
            with patch.object(upload, 'SETTINGS_PATH', path):
                self.assertNotIn(upload.MANAGE_SCOPE, upload.runtime_scopes())
                path.write_text(json.dumps(dict(settings, playlists={'COZY\nRAIN': 'PL123'})))
                self.assertIn(upload.MANAGE_SCOPE, upload.runtime_scopes())
                self.assertEqual(upload.playlist_for({'thumbnail_headline': 'COZY\nRAIN'}), 'PL123')
                self.assertEqual(upload.playlist_for({'thumbnail_headline': 'INSOMNIA\nRAIN'}), '')

    def test_channel_without_youtube_signup_explains_reauthorization(self):
        youtube = Mock()
        response = Mock(status=401, reason='Unauthorized')
        youtube.channels.return_value.list.return_value.execute.side_effect = HttpError(
            response, b'{"error": {"code": 401, "message": "Unauthorized", '
                      b'"errors": [{"message": "Unauthorized", "domain": "youtube.header", "reason": "youtubeSignupRequired"}]}}')
        with patch.dict(os.environ, {'EXPECTED_YOUTUBE_CHANNEL_ID': 'UCexpected'}):
            with self.assertRaisesRegex(RuntimeError, 'has no channel'):
                upload.verify_target_channel(youtube)


class UploadFlowTests(unittest.TestCase):
    def run_upload(self, run, **patches):
        defaults = dict(get_credentials=Mock(), build=Mock(), verify_target_channel=Mock(),
                        upload_video=Mock(return_value={'id': 'vid'}), set_thumbnail=Mock(),
                        add_to_playlist=Mock(), playlist_for=Mock(return_value=''),
                        scheduled_publish_at=Mock(return_value=utc(2026, 10, 21, 16, 0)),
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
        self.assets = {'date': '2026-10-21', 'video': {'pexels_id': 1}, 'audio': {'freesound_id': 2},
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
        self.assertEqual(entry['publish_at'], '2026-10-21T16:00:00Z')

    def test_scheduled_release_blocks_a_second_upload_that_day(self):
        mocks = self.run_upload(self.run_dir)
        entry = Ledger().find_video('vid')[1]
        self.assertEqual((entry['state'], entry['actual_privacy']), ('complete', 'private'))
        mocks['upload_video'].assert_called_once()
        with self.assertRaisesRegex(RuntimeError, 'this date'):
            Ledger().check_new(dict(self.assets, video={'pexels_id': 999}))
        summary = (self.root / 'summary.md').read_text()
        self.assertIn('2026-10-21T16:00:00Z', summary)
        self.assertIn('tell us', summary)
        self.assertIn('never aired on television', summary)

    def test_playlist_added_once_and_resume_skips_finished_steps(self):
        thumbnail, playlist = Mock(), Mock()
        with self.assertRaises(TimeoutError):
            self.run_upload(self.run_dir, playlist_for=Mock(return_value='PL1'), set_thumbnail=thumbnail,
                            add_to_playlist=playlist, wait_for_processing=Mock(side_effect=TimeoutError('later')))
        self.assertEqual(Ledger().find_video('vid')[1]['playlist'], 'PL1')
        with patch.dict(os.environ, {'RESUME_VIDEO_ID': 'vid'}):
            mocks = self.run_upload(self.run_dir, playlist_for=Mock(return_value='PL1'), set_thumbnail=thumbnail,
                                    add_to_playlist=playlist)
        mocks['upload_video'].assert_not_called()
        thumbnail.assert_called_once()
        playlist.assert_called_once()
        self.assertEqual(Ledger().find_video('vid')[1]['state'], 'complete')


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
        self.assertTrue(description.lower().startswith('rain sounds for'))
        self.assertIn('Just steady rain. No music, no voices, no distractions.', description)
        self.assertIn('·', assets['overlay_title'])
        self.assertNotIn('🌧', assets['overlay_title'])
        self.assertIn('0:00 Settle in and breathe', description)
        self.assertIn('released under Creative Commons 0 (public domain)', description)
        self.assertNotIn('\n\n\n', description)
        self.assertNotIn('{', description)


if __name__ == '__main__':
    unittest.main()
