import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import source_assets as sourcing


class SourcingTests(unittest.TestCase):
    def video(self, ident=123):
        return {'id': ident, 'tags': 'anime, rain, study, window', 'duration': 10,
                'pageURL': f'https://pixabay.com/videos/study-{ident}/',
                'videos': {'medium': {'width': 1920, 'height': 1080, 'size': 100,
                                     'url': 'https://cdn.pixabay.com/video/test.mp4'}}}

    def test_filters_do_not_approve_tags_or_noncommercial_audio(self):
        record = sourcing.video_candidate(self.video())
        self.assertEqual(record['asset_id'], 'pixabay:123')
        self.assertIsNone(sourcing.video_candidate(dict(self.video(), tags='cat, cartoon')))
        hit = {'id': 1, 'name': 'gentle rain window', 'tags': [], 'duration': 60,
               'license': sourcing.CC0,
               'previews': {'preview-hq-mp3': 'https://cdn.freesound.org/previews/1.mp3'}}
        self.assertIsNotNone(sourcing.audio_candidate(hit))
        self.assertIsNone(sourcing.audio_candidate(dict(hit, license='Attribution Noncommercial')))
        self.assertIsNone(sourcing.audio_candidate(dict(hit, name='rain thunder')))

    def test_cache_avoids_repeat_requests_and_contains_no_key(self):
        state = {}
        with patch('source_assets.requests.get') as request:
            request.return_value.json.return_value = {'hits': [self.video()]}
            sourcing.cached_search(state, 'video', 'anime rain', 1, 'secret', now=100)
            sourcing.cached_search(state, 'video', 'anime rain', 1, 'secret', now=101)
            self.assertEqual(request.call_count, 1)
            self.assertNotIn('secret', json.dumps(state))
            sourcing.cached_search(state, 'video', 'anime rain', 1, 'secret', now=86501)
            self.assertEqual(request.call_count, 2)

    def test_cross_id_duplicate_content_and_existing_pool_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'data').mkdir(); (root / 'audio').mkdir()
            (root / 'data/video_library.json').write_text(json.dumps([
                {'asset_id': 'local:pixabay-123', 'source_url': 'https://pixabay.com/videos/study-123/'}]))
            (root / 'data/video_discovery.json').write_text(json.dumps({'illustrated': ['anime rain']}))
            original = (root / 'data/video_library.json').read_bytes()
            state = {'schema': 1, 'assets': [], 'cursors': {}}
            def download(url, path, kind):
                path.write_bytes(b'same-content')
            with patch('source_assets.cached_search', return_value={
                    'hits': [self.video(123), self.video(124), self.video(125)]}), \
                    patch('source_assets.download', side_effect=download), \
                    patch('source_assets.technical_check', return_value={'passed': True}):
                summary = sourcing.source(root, root / 'batch', state, ['video'], 3, {'video': 'key'})
            self.assertEqual(summary['new_videos'], 1)
            self.assertEqual(state['assets'][0]['asset_id'], 'pixabay:124')
            self.assertFalse(state['assets'][0]['publication_approved'])
            self.assertEqual((root / 'data/video_library.json').read_bytes(), original)
            self.assertTrue((root / 'batch/sourced-assets.zip').exists())

    def test_private_store_rejects_public_destination(self):
        with patch('source_assets.requests.get') as request:
            request.return_value.json.return_value = {'private': False}
            with self.assertRaisesRegex(ValueError, 'private repository'):
                sourcing.private_state('secret')
            self.assertEqual(request.call_count, 1)

    def test_untrusted_redirect_is_rejected_before_second_request(self):
        response = Mock(status_code=302, headers={'Location': 'https://evil.example/media'})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('source_assets.requests.get', return_value=response) as request:
            with self.assertRaisesRegex(ValueError, 'Unapproved'):
                sourcing.download('https://cdn.pixabay.com/video/test.mp4', Path('unused'), 'video')
            self.assertEqual(request.call_count, 1)

    def test_checkpoint_is_published_only_after_both_uploads(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ('sourced-assets.zip', 'sourcing-state.json'):
                (folder / name).write_bytes(b'candidate')
            with patch('source_assets.requests.post') as post, patch('source_assets.requests.patch') as publish:
                post.return_value.json.return_value = {'id': 9}
                post.side_effect = [post.return_value, post.return_value,
                                    sourcing.requests.ConnectionError('upload failed')]
                with self.assertRaises(sourcing.requests.ConnectionError):
                    sourcing.publish_batch('secret', folder, '123-1')
                publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
