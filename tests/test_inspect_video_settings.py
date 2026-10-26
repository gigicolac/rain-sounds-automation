from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inspect_video_settings import video_settings


class InspectTests(unittest.TestCase):
    def test_report_collects_settings_and_playlists(self):
        youtube = Mock()
        youtube.videos.return_value.list.return_value.execute.return_value = {'items': [{
            'snippet': {'title': 'Rain', 'categoryId': '10', 'defaultLanguage': 'en'},
            'status': {'license': 'youtube', 'containsSyntheticMedia': False}}]}
        youtube.playlists.return_value.list.return_value.execute.return_value = {
            'items': [{'id': 'PL1', 'snippet': {'title': 'Sleep'}, 'status': {'privacyStatus': 'public'}},
                      {'id': 'PL2', 'snippet': {'title': 'Other'}}]}
        youtube.playlistItems.return_value.list.return_value.execute.side_effect = [{'items': [{'id': 'x'}]}, {'items': []}]
        settings = video_settings(youtube, 'abc')
        self.assertEqual(settings['defaultLanguage'], 'en')
        self.assertEqual(settings['status']['license'], 'youtube')
        self.assertEqual(settings['playlists'], [{'id': 'PL1', 'title': 'Sleep', 'privacy': 'public'}])


if __name__ == '__main__':
    unittest.main()
