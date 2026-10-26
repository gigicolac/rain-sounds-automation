from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_schedule import api_timestamp, load_schedule, next_publish_at
import upload_youtube


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class ScheduleTests(unittest.TestCase):
    def test_repository_schedule_is_valid(self):
        self.assertEqual(load_schedule()['timezone'], 'America/New_York')

    def test_daily_run_releases_next_eastern_day(self):
        # 11am Sydney Saturday = 8pm Eastern Friday; release Saturday 9am EDT.
        self.assertEqual(next_publish_at(utc(2026, 10, 24, 0, 0)), utc(2026, 10, 24, 13, 0))
        # 11am Sydney Friday = 8pm Eastern Thursday; release Friday 11am EDT.
        self.assertEqual(next_publish_at(utc(2026, 10, 23, 0, 0)), utc(2026, 10, 23, 15, 0))
        # 11am Sydney Thursday = 8pm Eastern Wednesday; release Thursday 9am EDT.
        self.assertEqual(next_publish_at(utc(2026, 10, 22, 0, 0)), utc(2026, 10, 22, 13, 0))

    def test_too_close_slot_moves_to_next_day(self):
        # Thursday 8:30am EDT is within the 60-minute lead of 9am.
        self.assertEqual(next_publish_at(utc(2026, 10, 22, 12, 30)), utc(2026, 10, 23, 15, 0))

    def test_daylight_saving_change(self):
        # Sunday 1 Nov 2026 9am is EST (UTC-5) after the change.
        self.assertEqual(next_publish_at(utc(2026, 11, 1, 0, 0)), utc(2026, 11, 1, 14, 0))

    def test_api_timestamp_format(self):
        self.assertEqual(api_timestamp(utc(2026, 10, 24, 15, 0)), '2026-10-24T15:00:00.000Z')


class UploadSchedulingTests(unittest.TestCase):
    def test_only_public_scheduled_runs_get_release_time(self):
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'), patch.dict(os.environ, {'PUBLISH_TIMING': ''}):
            self.assertRegex(upload_youtube.scheduled_release(), r'^\d{4}-\d\d-\d\dT\d\d:00:00\.000Z$')
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'), patch.dict(os.environ, {'PUBLISH_TIMING': 'now'}):
            self.assertIsNone(upload_youtube.scheduled_release())
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'unlisted'), patch.dict(os.environ, {'PUBLISH_TIMING': 'schedule'}):
            self.assertIsNone(upload_youtube.scheduled_release())

    def test_scheduled_upload_is_private_with_publish_at(self):
        youtube = Mock()
        youtube.videos.return_value.insert.return_value.next_chunk.return_value = (None, {'id': 'abc'})
        assets = {'title': 'Rain', 'description': 'Rain', 'tags': []}
        with patch.object(upload_youtube, 'MediaFileUpload'), patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'):
            upload_youtube.upload_video(youtube, assets, '2026-10-24T15:00:00.000Z')
            status = youtube.videos.return_value.insert.call_args.kwargs['body']['status']
            self.assertEqual(status['privacyStatus'], 'private')
            self.assertEqual(status['publishAt'], '2026-10-24T15:00:00.000Z')
            upload_youtube.upload_video(youtube, assets)
            status = youtube.videos.return_value.insert.call_args.kwargs['body']['status']
            self.assertEqual(status['privacyStatus'], 'public')
            self.assertNotIn('publishAt', status)


if __name__ == '__main__':
    unittest.main()
