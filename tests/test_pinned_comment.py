from datetime import datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from post_pinned_comment import due, post_due_comments
from publish_schedule import DAYS, load_schedule
from upload_history import Ledger
import upload_youtube

NOW = datetime(2026, 10, 24, 13, 20, tzinfo=timezone.utc)


def entry(**extra):
    return dict({'state': 'complete', 'video_id': 'vid', 'publish_at': '2026-10-24T13:00:00.000Z',
                 'assets': {'date': '2026-10-24'}}, **extra)


def youtube_with(privacy='public', threads=()):
    youtube = Mock()
    youtube.videos.return_value.list.return_value.execute.return_value = {'items': [{'status': {'privacyStatus': privacy}}]}
    youtube.commentThreads.return_value.insert.return_value.execute.return_value = {
        'id': 'thread', 'snippet': {'topLevelComment': {'id': 'comment1'}}}
    youtube.commentThreads.return_value.list.return_value.execute.return_value = {'items': list(threads)}
    return youtube


class CommentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for p in (patch.dict(os.environ, {}, clear=True), patch('upload_history.ROOT', Path(temp.name))):
            p.start(); self.addCleanup(p.stop)

    def test_due_skips_unreleased_commented_and_unscheduled(self):
        entries = {'a': entry(), 'b': entry(comment_id='x'), 'c': entry(publish_at='2026-10-25T13:00:00.000Z'),
                   'd': {k: v for k, v in entry().items() if k != 'publish_at'}, 'e': entry(state='uploaded')}
        self.assertEqual([k for k, _ in due(entries, NOW)], ['a'])

    def test_posts_once_and_records_link(self):
        ledger = Ledger(); ledger.entries = {'a': entry()}
        youtube = youtube_with()
        links, errors = post_due_comments(youtube, ledger, 'Hi', 'UC1', NOW)
        self.assertEqual((links, errors), (['https://www.youtube.com/watch?v=vid&lc=comment1'], []))
        self.assertEqual(Ledger().entries['a']['comment_id'], 'comment1')
        self.assertEqual(Ledger().entries['a']['actual_privacy'], 'public')
        self.assertEqual(post_due_comments(youtube, Ledger(), 'Hi', 'UC1', NOW), ([], []))
        youtube.commentThreads.return_value.insert.assert_called_once()

    def test_waits_while_still_private(self):
        ledger = Ledger(); ledger.entries = {'a': entry()}
        youtube = youtube_with('private')
        self.assertEqual(post_due_comments(youtube, ledger, 'Hi', 'UC1', NOW), ([], []))
        youtube.commentThreads.return_value.insert.assert_not_called()

    def test_interrupted_post_is_recovered_not_duplicated(self):
        ledger = Ledger(); ledger.entries = {'a': entry(comment_state='posting')}
        thread = {'snippet': {'topLevelComment': {'id': 'old', 'snippet': {
            'authorChannelId': {'value': 'UC1'}, 'textOriginal': 'Hi'}}}}
        youtube = youtube_with(threads=[thread])
        links, _ = post_due_comments(youtube, ledger, 'Hi', 'UC1', NOW)
        self.assertEqual(links, ['https://www.youtube.com/watch?v=vid&lc=old'])
        youtube.commentThreads.return_value.insert.assert_not_called()

    def test_comment_text_links_to_channel(self):
        text = (ROOT / 'data/pinned_comment.txt').read_text(encoding='utf-8')
        self.assertIn('youtube.com/@calmingrainsoundssss', text)
        self.assertLess(len(text), 10000)

    def test_workflow_runs_after_every_release_time(self):
        schedule = load_schedule()
        workflow = (ROOT / '.github/workflows/pinned-comment.yml').read_text(encoding='utf-8')
        runs = set()
        for minute, hour, days in re.findall(r'cron: "(\d+) (\d+) \* \* ([\d,*]+)"', workflow):
            for day in (range(7) if days == '*' else map(int, days.split(','))):
                runs.add((DAYS[(int(day) - 1) % 7], int(hour), int(minute)))
        self.assertIn('timezone: "America/New_York"', workflow)
        for day, value in schedule['times'].items():
            release = datetime.combine(datetime(2026, 1, 1), time.fromisoformat(value)) + timedelta(minutes=15)
            self.assertIn((day, release.hour, release.minute), runs, day)


class SettingsTests(unittest.TestCase):
    def test_reference_settings_applied_without_overriding_controls(self):
        assets = {'title': 'Rain', 'description': 'Rain', 'tags': [], 'date': '2026-10-24'}
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'):
            body = upload_youtube.upload_body(assets, '2026-10-24T13:00:00.000Z')
        self.assertEqual(body['snippet']['defaultLanguage'], 'en-AU')
        self.assertEqual(body['snippet']['defaultAudioLanguage'], 'en-AU')
        self.assertEqual(body['status']['license'], 'youtube')
        self.assertTrue(body['status']['embeddable'] and body['status']['publicStatsViewable'])
        self.assertEqual(body['status']['privacyStatus'], 'private')
        self.assertFalse(body['status']['selfDeclaredMadeForKids'])
        self.assertEqual(body['recordingDetails']['locationDescription'], 'Melbourne')
        self.assertEqual(body['recordingDetails']['recordingDate'], '2026-10-24T00:00:00Z')
        self.assertEqual(','.join(body), 'snippet,status,recordingDetails')

    def test_presets_cannot_set_visibility(self):
        settings = json.loads((ROOT / 'data/upload_settings.json').read_text(encoding='utf-8'))
        self.assertFalse({'privacyStatus', 'publishAt', 'selfDeclaredMadeForKids', 'madeForKids'} & set(settings['status']))


if __name__ == '__main__':
    unittest.main()
