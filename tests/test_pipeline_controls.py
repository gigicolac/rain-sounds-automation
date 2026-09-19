import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from asset_matching import compatible, title_allowed
from upload_history import Ledger, fingerprint
from upload_youtube import wait_for_processing


def asset(labels, approved=True):
    return {'review': {'approved': approved, 'labels': labels}}


class MatchingTests(unittest.TestCase):
    def test_unknown_is_not_thunder_free(self):
        self.assertFalse(title_allowed('No Thunder, Pure Rain', {}, {}))
        self.assertTrue(title_allowed('5 Minutes of Rain Ambience', {}, {}))

    def test_unapproved_labels_cannot_support_claims(self):
        self.assertFalse(title_allowed('Heavy Rain', asset({'intensity':'heavy'}, False), {}))

    def test_matching_and_conflicting_settings(self):
        self.assertFalse(compatible(asset({'setting':'forest'}), asset({'setting':'city'})))
        self.assertTrue(compatible(asset({'setting':'forest'}), asset({'setting':'forest'})))

    def test_pure_rain_requires_all_absences(self):
        labels = dict.fromkeys(['thunder','traffic','animals','music','voices'], False)
        self.assertTrue(title_allowed('No Thunder, Pure Rain', asset(labels), {}))
        labels['traffic'] = True
        self.assertFalse(title_allowed('Pure Rain', asset(labels), {}))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        self.root = patch('upload_history.ROOT', Path(self.temp.name))
        self.root.start(); self.addCleanup(self.root.stop)
        self.assets = {'date':'2026-09-19', 'video':{'pexels_id':123}, 'audio':{'freesound_id':456}}

    def test_reservation_survives_restart(self):
        Ledger().reserve(self.assets)
        with self.assertRaisesRegex(RuntimeError, 'already reserved'):
            Ledger().reserve(self.assets)

    def test_title_duration_cannot_evade_duplicate(self):
        self.assertEqual(fingerprint(self.assets), fingerprint(dict(self.assets,title='New title',duration_minutes=8)))

    def test_same_day_different_pair_blocked(self):
        Ledger().reserve(self.assets)
        changed = dict(self.assets, video={'pexels_id':999})
        with self.assertRaisesRegex(RuntimeError, 'this date'):
            Ledger().check_new(changed)

    def test_resume_only_known_upload(self):
        ledger=Ledger(); key=ledger.reserve(self.assets)
        ledger.entries[key]['video_id']='known'; ledger.save()
        self.assertEqual(Ledger().find_video('known')[0],key)
        with self.assertRaises(RuntimeError):
            Ledger().find_video('unknown')

    def test_remote_history_requires_credentials(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY':'owner/repo'}):
            with self.assertRaisesRegex(RuntimeError,'GH_TOKEN'):
                Ledger()


class ProcessingTests(unittest.TestCase):
    def response(self, **status):
        return {'items':[{'status':status}]}

    def test_rejection_fails(self):
        youtube=Mock()
        youtube.videos.return_value.list.return_value.execute.return_value=self.response(uploadStatus='rejected',rejectionReason='length')
        with self.assertRaisesRegex(RuntimeError,'length'):
            wait_for_processing(youtube,'v',timeout=0)

    def test_pending_is_not_success(self):
        youtube=Mock()
        youtube.videos.return_value.list.return_value.execute.return_value=self.response(uploadStatus='uploaded')
        with self.assertRaises(TimeoutError):
            wait_for_processing(youtube,'v',timeout=0)

    def test_waits_until_processed(self):
        youtube=Mock()
        youtube.videos.return_value.list.return_value.execute.side_effect=[self.response(uploadStatus='uploaded'),self.response(uploadStatus='processed',privacyStatus='private')]
        with patch('upload_youtube.time.sleep'):
            self.assertEqual(wait_for_processing(youtube,'v')['privacyStatus'],'private')


class UploadRecoveryTests(unittest.TestCase):
    def test_thumbnail_failure_then_resume_never_reinserts(self):
        import upload_youtube as upload
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'ALLOW_UNREVIEWED':'true'}, clear=True):
            root=Path(temp); run=root/'run'; run.mkdir()
            assets={'date':'2026-09-19','video':{'pexels_id':1},'audio':{'freesound_id':2},'review_approved':True}
            (run/'assets.json').write_text(json.dumps(assets))
            (run/'output.mp4').write_bytes(b'test')
            with patch('upload_history.ROOT',root), patch.object(upload,'RUN_DIR',run), patch.object(upload,'ASSETS_PATH',run/'assets.json'), patch.object(upload,'VIDEO_PATH',run/'output.mp4'), patch.object(upload,'RESULT_PATH',run/'upload_result.json'), patch.object(upload,'get_credentials'), patch.object(upload,'build'), patch.object(upload,'verify_target_channel'), patch.object(upload,'wait_for_processing',return_value={'privacyStatus':'unlisted'}), patch.object(upload,'upload_video',return_value={'id':'existing'}) as insert, patch.object(upload,'set_thumbnail',side_effect=RuntimeError('thumbnail failed')):
                with self.assertRaisesRegex(RuntimeError,'thumbnail failed'):
                    upload.main()
                self.assertEqual(json.loads((run/'upload_result.json').read_text())['video_id'],'existing')
                self.assertEqual(Ledger().find_video('existing')[1]['state'],'processed')
                with patch.dict(os.environ,{'RESUME_VIDEO_ID':'existing'}), patch.object(upload,'set_thumbnail'):
                    upload.main()
                insert.assert_called_once()
                self.assertEqual(Ledger().find_video('existing')[1]['state'],'complete')

    def test_reservation_failure_prevents_upload(self):
        import upload_youtube as upload
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'assets.json'; path.write_text(json.dumps({'review_approved':True}))
            with patch.object(upload,'ASSETS_PATH',path), patch.object(upload,'VIDEO_PATH',path), patch.object(upload,'Ledger') as ledger, patch.object(upload,'get_credentials'), patch.object(upload,'build'), patch.object(upload,'verify_target_channel'), patch.object(upload,'upload_video') as insert, patch.dict(os.environ,{},clear=True):
                ledger.return_value.reserve.side_effect=RuntimeError('history unavailable')
                with self.assertRaisesRegex(RuntimeError,'history unavailable'):
                    upload.main()
                insert.assert_not_called()

class SelectionTests(unittest.TestCase):
    def test_manual_controls_reach_generated_assets(self):
        import select_assets as select
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'SCENE_QUERY':'rain window', 'AUDIO_ID':'651189', 'TITLE_OVERRIDE':'My Rain Preview',
            'DURATION_MINUTES':'2'}, clear=True), patch.object(select,'RUN_DIR',Path(temp)), \
                patch.object(select,'pick_scene_video',return_value={'pexels_id':123,'scene_term':'rain window'}) as pick, \
                patch.object(select,'Ledger'):
            select.main()
            data=json.loads((Path(temp)/'assets.json').read_text())
            self.assertEqual(data['duration_seconds'],120)
            self.assertEqual(data['audio']['freesound_id'],651189)
            self.assertEqual(data['title'],'My Rain Preview')
            self.assertFalse(data['review_approved'])
            self.assertEqual(pick.call_args.args[0],['rain window'])

    def test_resume_restores_original_selection(self):
        import select_assets as select
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'RESUME_VIDEO_ID':'known'},clear=True), \
                patch.object(select,'RUN_DIR',Path(temp)), patch.object(select,'Ledger') as ledger, \
                patch.object(select,'pick_scene_video') as pick:
            ledger.return_value.find_video.return_value=('key',{'assets':{'title':'original'}})
            select.main()
            self.assertEqual(json.loads((Path(temp)/'assets.json').read_text()),{'title':'original'})
            pick.assert_not_called()


if __name__ == '__main__':
    unittest.main()
