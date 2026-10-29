import copy
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_profile import digest, choose
from content_policy import tokens, generated, check_assets, check_history_audit, check_resume
from upload_history import Ledger


class GeneratedContentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for directory in ('data', 'audio', 'scenes'):
            (self.root / directory).mkdir()
        self.settings = dict(generated_only=True, youtube_channel_id='UCnew', history_reconciled=True,
                             video_ids=['custom:new'], audio_ids=['custom-audio:new'])
        self.write('data/channel_profile.json', self.settings)
        self.write('data/content_exclusions.json', dict(version=1, video=[], audio=[]))
        (self.root / 'scenes/new.mp4').write_bytes(b'new visual')
        (self.root / 'audio/new.flac').write_bytes(b'new audio')
        review = dict(approved=True, status='approved', notes='Full playback and seam reviewed',
                      reviewed_at='2026-10-29', quality=dict(full_playback=True, loop_checked=True))
        self.video = dict(asset_id='custom:new', local_path='scenes/new.mp4',
                          sha256=digest(self.root / 'scenes/new.mp4'), generator='built-in image_gen',
                          custom_scene=dict(master_sha256='master-new'), review=copy.deepcopy(review),
                          source_url='generated-source', license_url='terms')
        self.audio = dict(asset_id='custom-audio:new', id='custom-audio:new', filename='new.flac',
                          sha256=digest(self.root / 'audio/new.flac'), generator_sha256='generator',
                          components=[dict(kind='procedural', seed=123, method='synthesis', profile=dict(source=None))],
                          source_url='code', license='Original', review=copy.deepcopy(review))
        self.assets = dict(channel_id='UCnew', date='2026-10-29', video=self.video, audio=self.audio,
                           selection_explanation=dict(policy='channel_profile'))
        self.env = patch.dict(os.environ, {}, clear=True); self.env.start(); self.addCleanup(self.env.stop)
        self.patch = patch('upload_history.ROOT', self.root); self.patch.start(); self.addCleanup(self.patch.stop)

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def test_new_original_assets_pass_and_pending_cannot_publish(self):
        check_assets(self.root, self.assets, {})
        self.audio['review']['approved'] = False
        with self.assertRaisesRegex(RuntimeError, 'approval'):
            check_assets(self.root, self.assets, {})

    def test_external_and_recording_based_blends_never_pass(self):
        for component in (dict(kind='licensed_recording', id=123), dict(kind='unknown')):
            candidate = copy.deepcopy(self.audio)
            candidate['components'].append(component)
            self.assertFalse(generated(candidate, 'audio'))
        self.assertFalse(generated(dict(self.video, generator='stock download'), 'video'))
        self.audio['components'][0]['profile']['source'] = '651189'
        self.assertFalse(generated(self.audio, 'audio'))

    def test_each_used_source_blocks_different_pair_and_reservations_count(self):
        for kind in ('video', 'audio'):
            with self.subTest(kind=kind):
                previous = copy.deepcopy(self.assets)
                previous['date'] = '2026-10-28'
                other = 'audio' if kind == 'video' else 'video'
                previous[other]['asset_id'] = 'different'
                ledger = Ledger()
                ledger.entries = {'old': dict(state='reserved', assets=previous)}
                with self.assertRaisesRegex(RuntimeError, 'previously used'):
                    ledger.check_new(self.assets)

    def test_renamed_files_and_shared_visual_masters_remain_excluded(self):
        for kind in ('video', 'audio'):
            old = copy.deepcopy(self.assets[kind]); old['asset_id'] = 'old-name'
            self.write('data/content_exclusions.json', dict(version=1, video=[], audio=[], **{}) | {kind: sorted(tokens(old, kind))})
            with self.assertRaisesRegex(RuntimeError, 'previously used'):
                check_assets(self.root, self.assets, {})
        old = dict(self.video, asset_id='old-render', sha256='different-render')
        self.write('data/content_exclusions.json', dict(version=1, audio=[], video=sorted(tokens(old, 'video'))))
        with self.assertRaisesRegex(RuntimeError, 'previously used'):
            check_assets(self.root, self.assets, {})

    def test_modified_file_missing_provenance_and_legacy_override_blocked(self):
        (self.root / 'audio/new.flac').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'changed on disk'):
            check_assets(self.root, self.assets, {})
        self.assets['selection_explanation']['policy'] = 'curated'
        with self.assertRaisesRegex(RuntimeError, 'legacy overrides'):
            check_assets(self.root, self.assets, {})

    def test_missing_snapshot_and_unreconciled_history_fail_closed(self):
        (self.root / 'data/content_exclusions.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'snapshot'):
            check_assets(self.root, self.assets, {})
        self.settings['history_reconciled'] = False
        self.write('data/channel_profile.json', self.settings)
        with self.assertRaisesRegex(RuntimeError, 'reconcile both channels'):
            check_history_audit(self.root)

    def test_channel_selection_has_no_used_or_external_fallback(self):
        self.write('data/video_library.json', [self.video])
        self.write('audio/metadata.json', [self.audio])
        self.assertEqual(choose(self.root, {}, random.Random(1), 'preview')[0], self.video)
        used = {'one': dict(assets=self.assets)}
        with self.assertRaisesRegex(RuntimeError, 'No unused generated-only'):
            choose(self.root, used, random.Random(1), 'preview')

    def test_wrong_channel_rejected_before_any_upload(self):
        self.assets['channel_id'] = 'UCold'
        with self.assertRaisesRegex(RuntimeError, 'different channel'):
            check_assets(self.root, self.assets, {})

    def test_missing_remote_ledger_is_not_empty_history(self):
        response = Mock(status_code=404)
        with patch.dict(os.environ, dict(GITHUB_REPOSITORY='owner/repo', GH_TOKEN='fake')), patch.object(Ledger, 'request', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'history is missing'):
                Ledger()

    def test_old_or_unidentified_resumes_are_blocked_but_new_channel_can_resume(self):
        for channel in (None, 'UCold'):
            with self.assertRaisesRegex(RuntimeError, 'Cannot resume'):
                check_resume(self.root, dict(channel_id=channel, assets={}))
        check_resume(self.root, dict(channel_id='UCnew', assets={}))

    def test_reencoding_same_procedural_seed_does_not_create_unused_source(self):
        previous = dict(self.audio, asset_id='another-name', sha256='another-encoding')
        self.write('data/content_exclusions.json', dict(version=1, video=[], audio=sorted(tokens(previous, 'audio'))))
        with self.assertRaisesRegex(RuntimeError, 'previously used'):
            check_assets(self.root, self.assets, {})

    def test_only_explicitly_allowed_recording_can_be_reused_in_new_mix(self):
        from content_policy import approved_recording_mix, exclusion_tokens, allowed
        self.settings.update(generated_only=False,recording_based_mixes=True,
                             allowed_recording_sources={'651189':'verified-source'})
        self.write('data/channel_profile.json',self.settings)
        self.audio['components'][0]['profile']['source']='651189'
        recording=dict(kind='licensed_recording',id='651189',source_sha256='verified-source',
                       license='http://creativecommons.org/publicdomain/zero/1.0/')
        self.audio['components'].append(recording)
        self.write('data/content_exclusions.json',dict(version=1,video=[],audio=['sha256:verified-source']))
        self.assertTrue(approved_recording_mix(self.root,self.audio))
        self.assertTrue(allowed(self.root,self.audio,'audio',exclusion_tokens(self.root,{})))
        recording['id']='695619'
        self.assertFalse(approved_recording_mix(self.root,self.audio))

    def test_automatic_approval_requires_authorization_and_technical_check_without_false_listening_flags(self):
        from content_policy import approved_review
        review=dict(approved=True,status='approved',reviewed_at='2026-10-29',notes='Authorized automatic approval',
                    approval_method='user_authorized_automatic',approval_authorization='User request in chat',
                    quality=dict(technical_checked=True,full_playback=False,loop_checked=False))
        self.assertTrue(approved_review(review))
        self.assertFalse(review['quality']['full_playback'])
        review.pop('approval_authorization')
        self.assertFalse(approved_review(review))
