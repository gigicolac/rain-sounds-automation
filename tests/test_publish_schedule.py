from datetime import datetime, timedelta, timezone
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

    def test_release_slots_keep_at_least_24_hours(self):
        self.assertEqual(next_publish_at(utc(2026, 10, 24, 0, 0)), utc(2026, 10, 26, 16, 0))
        # A Friday upload cannot be released later the same day.
        self.assertEqual(next_publish_at(utc(2026, 10, 23, 0, 0)), utc(2026, 10, 26, 16, 0))
        self.assertEqual(next_publish_at(utc(2026, 10, 22, 0, 0)), utc(2026, 10, 23, 15, 0))

    def test_too_close_slot_moves_to_next_day(self):
        # Friday 11am is less than 24 hours from Thursday noon Eastern.
        self.assertEqual(next_publish_at(utc(2026, 10, 22, 16, 0)), utc(2026, 10, 26, 16, 0))

    def test_exact_boundary_and_occupied_slot(self):
        self.assertEqual(next_publish_at(utc(2026, 11, 1, 17)), utc(2026, 11, 2, 17))
        self.assertEqual(next_publish_at(utc(2026, 11, 1, 17, 0, 1)), utc(2026, 11, 4, 17))
        self.assertEqual(next_publish_at(utc(2026, 11, 1, 13), excluded=[utc(2026, 11, 2, 17)]), utc(2026, 11, 4, 17))

    def test_workflow_starts_28_hours_before_release_in_both_dst_seasons(self):
        from zoneinfo import ZoneInfo
        zone = ZoneInfo('America/New_York')
        # Sunday/Tuesday 08:00 and Thursday 07:00 Eastern.
        for year, month, day, hour in ((2026, 11, 1, 8), (2026, 11, 3, 8), (2026, 11, 5, 7),
                                      (2027, 3, 14, 8), (2027, 3, 16, 8), (2027, 3, 18, 7)):
            start = datetime(year, month, day, hour, tzinfo=zone).astimezone(timezone.utc)
            self.assertEqual(next_publish_at(start) - start, timedelta(hours=28))
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/daily-video.yml').read_text()
        self.assertIn('cron: "0 8 * * 0,2"', workflow)
        self.assertIn('cron: "0 7 * * 4"', workflow)
        self.assertIn('timezone: "America/New_York"', workflow)

    def test_daylight_saving_change(self):
        # Monday noon is EST (UTC-5) after the Sunday change.
        self.assertEqual(next_publish_at(utc(2026, 11, 1, 0, 0)), utc(2026, 11, 2, 17, 0))

    def test_api_timestamp_format(self):
        self.assertEqual(api_timestamp(utc(2026, 10, 24, 15, 0)), '2026-10-24T15:00:00.000Z')


class UploadSchedulingTests(unittest.TestCase):
    def test_only_public_scheduled_runs_get_release_time(self):
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'), patch.dict(os.environ, {'PUBLISH_TIMING': ''}):
            self.assertRegex(upload_youtube.scheduled_release(), r'^\d{4}-\d\d-\d\dT\d\d:00:00\.000Z$')
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'), patch.dict(os.environ, {'PUBLISH_TIMING': 'now'}):
            with self.assertRaisesRegex(RuntimeError, '24-hour buffer'):
                upload_youtube.scheduled_release()
        with patch.object(upload_youtube, 'PRIVACY_STATUS', 'unlisted'), patch.dict(os.environ, {'PUBLISH_TIMING': 'schedule'}):
            self.assertIsNone(upload_youtube.scheduled_release())

    def test_insert_never_sets_public_visibility_or_provisional_publish_at(self):
        youtube = Mock()
        youtube.videos.return_value.insert.return_value.next_chunk.return_value = (None, {'id': 'abc'})
        assets = {'title': 'Rain', 'description': 'Rain', 'tags': []}
        with patch.object(upload_youtube, 'MediaFileUpload'), patch.object(upload_youtube, 'PRIVACY_STATUS', 'public'):
            upload_youtube.upload_video(youtube, assets, '2026-10-24T15:00:00.000Z')
            status = youtube.videos.return_value.insert.call_args.kwargs['body']['status']
            self.assertEqual(status['privacyStatus'], 'private')
            self.assertNotIn('publishAt', status)
            upload_youtube.upload_video(youtube, assets)
            status = youtube.videos.return_value.insert.call_args.kwargs['body']['status']
            self.assertEqual(status['privacyStatus'], 'private')
            self.assertNotIn('publishAt', status)

    def test_schedule_after_processing_preserves_settings_and_skips_occupied_slot(self):
        entry = {'requested_privacy': 'public', 'channel_id': 'new',
                 'upload_completed_at': '2026-11-01T13:30:00Z',
                 'upload_status': {'containsSyntheticMedia': False}}
        ledger = Mock(entries={'test': entry, 'other': {'channel_id': 'new', 'publish_at': '2026-11-02T17:00:00Z'}})
        youtube = Mock()
        youtube.videos.return_value.update.return_value.execute.return_value = {
            'status': {'privacyStatus': 'private', 'publishAt': '2026-11-04T17:00:00Z'}}
        status = {'privacyStatus': 'private', 'license': 'creativeCommon', 'embeddable': False,
                  'publicStatsViewable': False, 'selfDeclaredMadeForKids': False}
        with patch.object(upload_youtube, 'save_result'):
            result = upload_youtube.schedule_publication(youtube, 'test', entry, ledger, status, utc(2026, 11, 1, 14))
        self.assertEqual(result['publishAt'], '2026-11-04T17:00:00Z')
        body = youtube.videos.return_value.update.call_args.kwargs['body']['status']
        for key, value in status.items():
            self.assertEqual(body[key], value)
        self.assertIs(body['containsSyntheticMedia'], False)
        self.assertEqual(entry['publish_at'], '2026-11-04T17:00:00.000Z')
        ledger.save.assert_called_once()

    def test_long_processing_delay_uses_later_release(self):
        entry = {'requested_privacy': 'public', 'upload_completed_at': '2026-11-01T13:30:00Z'}
        ledger = Mock(entries={'test': entry})
        youtube = Mock()
        youtube.videos.return_value.update.return_value.execute.return_value = {
            'status': {'privacyStatus': 'private', 'publishAt': '2026-11-04T17:00:00Z'}}
        with patch.object(upload_youtube, 'save_result'):
            upload_youtube.schedule_publication(youtube, 'test', entry, ledger, {'privacyStatus': 'private'}, utc(2026, 11, 1, 18))
        self.assertEqual(entry['publish_at'], '2026-11-04T17:00:00.000Z')

    def test_resume_reconciles_schedule_without_moving_it_or_updating_youtube(self):
        entry = {'requested_privacy': 'public', 'upload_completed_at': '2026-11-01T13:30:00Z',
                 'publish_at': '2026-11-02T17:00:00.000Z'}
        youtube = Mock()
        status = {'privacyStatus': 'private', 'publishAt': '2026-11-02T17:00:00Z'}
        upload_youtube.schedule_publication(youtube, 'test', entry, Mock(), status, utc(2026, 11, 2, 16))
        youtube.videos.assert_not_called()

    def test_missing_completion_or_short_existing_schedule_fails_closed(self):
        youtube = Mock()
        with self.assertRaisesRegex(RuntimeError, 'Missing upload completion'):
            upload_youtube.schedule_publication(youtube, 'test', {'requested_privacy': 'public'}, Mock(), {'privacyStatus': 'private'})
        entry = {'requested_privacy': 'public', 'upload_completed_at': '2026-11-02T13:30:00Z',
                 'publish_at': '2026-11-02T17:00:00Z'}
        with self.assertRaisesRegex(RuntimeError, '24-hour schedule'):
            upload_youtube.schedule_publication(youtube, 'test', entry, Mock(), {'privacyStatus': 'private', 'publishAt': entry['publish_at']})
        youtube.videos.assert_not_called()

    def test_private_test_stays_private_and_unscheduled(self):
        youtube = Mock()
        self.assertEqual(upload_youtube.schedule_publication(youtube, 'test', {'requested_privacy': 'private'}, Mock(), {'privacyStatus': 'private'}), {'privacyStatus': 'private'})
        youtube.videos.assert_not_called()

    def test_failed_history_save_cannot_schedule_video(self):
        entry = {'requested_privacy': 'public', 'upload_completed_at': '2026-11-01T13:30:00Z'}
        ledger = Mock(entries={'test': entry})
        ledger.save.side_effect = RuntimeError('history unavailable')
        youtube = Mock()
        with patch.object(upload_youtube, 'save_result'), self.assertRaisesRegex(RuntimeError, 'history unavailable'):
            upload_youtube.schedule_publication(youtube, 'test', entry, ledger, {'privacyStatus': 'private'}, utc(2026, 11, 1, 14))
        youtube.videos.assert_not_called()


if __name__ == '__main__':
    unittest.main()
