import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from upload_presentation import (presentation, unique_title, variety_record, thumbnail_variants,
                                 chapters, description_parts, pinned_comment, THEMES, TAGS)


class PresentationTests(unittest.TestCase):
    def test_unknown_labels_do_not_invent_setting_or_events(self):
        video = {'source_url': 'https://example.com/heavy-thunder-window'}
        options, headline, detail = presentation(video, {}, 180, {}, random.Random(1))
        self.assertEqual(detail, 'Cozy Rain Ambience')
        # Keyword | Outcome | Length stays readable in desktop search results.
        self.assertTrue(all(t.endswith(' | 3 Hours') and len(t) <= 70 for t in options))
        self.assertNotIn('thunder', ' '.join(options).lower())
        self.assertNotIn('window', ' '.join(options).lower())
        self.assertTrue(all(t.startswith('Rain Sounds for ') for t in options))
        self.assertNotIn('black screen', ' '.join(options).lower())

    def test_setting_requires_both_approved_labels(self):
        reviewed = {'review': {'approved': True, 'labels': {'setting': 'window'}}}
        self.assertEqual(presentation(reviewed, reviewed, 180, {}, random.Random(1))[2], 'Rain on a Window')
        self.assertEqual(presentation(reviewed, {}, 180, {}, random.Random(1))[2], 'Cozy Rain Ambience')

    def test_reserved_and_legacy_titles_count_and_exhaustion_stays_unique(self):
        options = ['Rain Sounds for Sleeping | 3 Hours of Cozy Rain Ambience']
        entries = {'old': {'state': 'reserved', 'assets': {'title': options[0]}}}
        with self.assertRaisesRegex(ValueError, 'All eligible titles'):
            unique_title(options, entries, random.Random(1))
        with self.assertRaises(ValueError):
            unique_title(options, entries, random.Random(1), options[0].upper())

    def test_thumbnail_avoids_last_recorded_headline(self):
        entries = {'old': {'assets': {'date': '2026-10-01', 'thumbnail_headline': 'COZY\nRAIN'}}}
        for seed in range(10):
            headline = presentation({}, {}, 180, entries, random.Random(seed))[1]
            self.assertNotEqual(headline, 'COZY\nRAIN')
            self.assertIn(headline, THEMES)

    def test_variety_record_preserves_sources_and_unknowns(self):
        record = variety_record({'video': {'asset_id': 'local:a', 'source_url': 'source'},
            'audio': {'freesound_id': 1, 'freesound_url': 'audio-source'},
            'duration_seconds': 10800, 'title': 'Rain Sounds for Sleeping | 3 Hours',
            'description': 'Opening\nCredits', 'thumbnail_headline': 'SLEEP\nRAIN'})
        self.assertEqual(record['audio_source'], 'audio-source')
        self.assertEqual(record['verified_audio_labels'], {})
        self.assertEqual(record['description_opening'], 'Opening')

    def test_published_layout_stays_consistent_with_review_variants(self):
        entries = {'old': {'assets': {'date': '2026-10-16', 'thumbnail_style': 'stacked'}}}
        for seed in range(10):
            variants = thumbnail_variants('STUDY\nRAIN', {'thumbnail_text_side': 'right'}, entries, random.Random(seed))
            self.assertEqual(len({v['style'] for v in variants}), 3)
            self.assertEqual(variants[0]['style'], 'stacked')
            self.assertTrue(all(v['headline'] == 'STUDY\nRAIN' and v['side'] == 'right' for v in variants))

    def test_catalogue_generates_distinct_titles_until_exhausted(self):
        entries = {}
        for seed in range(30):
            options, headline, _ = presentation({}, {}, 180, entries, random.Random(seed))
            title = unique_title(options, entries, random.Random(seed))
            self.assertNotIn(title, [e['assets']['title'] for e in entries.values()])
            self.assertLessEqual(len(title), 70)
            entries[str(seed)] = {'assets': {'date': str(seed).zfill(3), 'title': title, 'thumbnail_headline': headline}}
        with self.assertRaisesRegex(ValueError, 'catalogue exhausted'):
            presentation({}, {}, 180, entries, random.Random(40))


class PackagingTests(unittest.TestCase):
    def test_titles_follow_keyword_outcome_length_formula(self):
        options, headline, _ = presentation({}, {}, 180, {}, random.Random(3))
        for title in options:
            keyword, outcome, length = [p.strip() for p in title.split('|')]
            self.assertIn(keyword, ('Rain Sounds for Sleeping', 'Rain Sounds for Sleep'))
            self.assertIn(outcome, THEMES[headline])
            self.assertEqual(length, '3 Hours')

    def test_recent_outcome_is_not_reused_while_alternatives_remain(self):
        outcome = THEMES['DEEP SLEEP\nRAIN'][0]
        entries = {'old': {'assets': {'date': '2026-10-21', 'thumbnail_headline': 'COZY\nRAIN',
                                      'title': f'Rain Sounds for Sleep | {outcome} | 3 Hours'}}}
        for seed in range(20):
            options, headline, _ = presentation({}, {}, 180, entries, random.Random(seed))
            if headline == 'DEEP SLEEP\nRAIN':
                self.assertTrue(options)
                self.assertFalse(any(f'| {outcome} |' in t for t in options))

    def test_chapters_start_at_zero_and_skip_short_tests(self):
        self.assertEqual(chapters(180).splitlines(),
                         ['Chapters', '0:00 Settle in and breathe', '1:00:00 Drift deeper', '2:00:00 Deep, restorative rest'])
        self.assertEqual(chapters(5), '')

    def test_description_only_claims_clean_audio_when_confirmed(self):
        audio = {'freesound_url': 'https://freesound.org/s/1/', 'license': 'http://creativecommons.org/publicdomain/zero/1.0/'}
        for headline in THEMES:
            confirmed = description_parts(headline, 180, audio, random.Random(1), clean=True)
            unconfirmed = description_parts(headline, 180, audio, random.Random(1), clean=False)
            self.assertIn('no traffic', confirmed['clean_line'])
            self.assertEqual(unconfirmed['clean_line'], '')
            self.assertIn('3 hours', confirmed['opening'])
            self.assertIn('rain sounds', confirmed['opening'].lower())
            self.assertIn('Creative Commons 0', confirmed['audio_credit'])
            text = ' '.join(confirmed.values()).lower()
            for unsupported in ('thunder', 'gentle', 'heavy', 'no ads', 'black screen', '\u2014'):
                self.assertNotIn(unsupported, text)
            self.assertTrue(pinned_comment(headline, random.Random(1)).startswith('\U0001f4ac'))

    def test_tags_stay_within_youtube_guidance(self):
        self.assertTrue(5 <= len(TAGS) <= 10)
        self.assertFalse(any('black screen' in t or 'thunder' in t or 'music' in t for t in TAGS))
