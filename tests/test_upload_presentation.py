import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from upload_presentation import presentation, unique_title, variety_record


class PresentationTests(unittest.TestCase):
    def test_unknown_labels_do_not_invent_setting_or_events(self):
        video = {'source_url': 'https://example.com/heavy-thunder-window'}
        options, headline, detail = presentation(video, {}, 180, {}, random.Random(1))
        self.assertEqual(detail, 'Cozy Rain Ambience')
        self.assertTrue(all(t.startswith('Rain Sounds for ') and '3 Hours' in t for t in options))
        self.assertNotIn('thunder', ' '.join(options).lower())
        self.assertNotIn('window', ' '.join(options).lower())

    def test_setting_requires_both_approved_labels(self):
        reviewed = {'review': {'approved': True, 'labels': {'setting': 'window'}}}
        self.assertEqual(presentation(reviewed, reviewed, 180, {}, random.Random(1))[2], 'Rain on a Window')
        self.assertEqual(presentation(reviewed, {}, 180, {}, random.Random(1))[2], 'Cozy Rain Ambience')

    def test_reserved_and_legacy_titles_count_and_exhaustion_stays_unique(self):
        options = ['Rain Sounds for Sleeping | 3 Hours of Cozy Rain Ambience']
        entries = {'old': {'state': 'reserved', 'assets': {'title': options[0]}}}
        next_title = unique_title(options, entries, random.Random(1))
        self.assertNotEqual(next_title, options[0])
        entries['next'] = {'assets': {'title': next_title}}
        self.assertNotEqual(unique_title(options, entries, random.Random(1)), next_title)
        with self.assertRaises(ValueError):
            unique_title(options, entries, random.Random(1), options[0].upper())

    def test_thumbnail_avoids_last_recorded_headline(self):
        entries = {'old': {'assets': {'date': '2026-10-01', 'thumbnail_headline': 'SLEEP\nRAIN'}}}
        for seed in range(10):
            self.assertNotEqual(presentation({}, {}, 180, entries, random.Random(seed))[1], 'SLEEP\nRAIN')

    def test_variety_record_preserves_sources_and_unknowns(self):
        record = variety_record({'video': {'asset_id': 'local:a', 'source_url': 'source'},
            'audio': {'freesound_id': 1, 'freesound_url': 'audio-source'},
            'duration_seconds': 10800, 'title': 'Rain Sounds for Sleeping | 3 Hours',
            'description': 'Opening\nCredits', 'thumbnail_headline': 'SLEEP\nRAIN'})
        self.assertEqual(record['audio_source'], 'audio-source')
        self.assertEqual(record['verified_audio_labels'], {})
        self.assertEqual(record['description_opening'], 'Opening')
