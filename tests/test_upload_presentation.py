import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from upload_presentation import (presentation, unique_title, variety_record, thumbnail_variants,
                                 chapters, description_parts, pinned_comment, overlay_title,
                                 theme_titles, KEYWORDS, EMOJI, THEMES, TAGS)


class PresentationTests(unittest.TestCase):
    def test_unknown_labels_do_not_invent_setting_or_events(self):
        video = {'source_url': 'https://example.com/heavy-thunder-window'}
        options, headline, detail = presentation(video, {}, 180, {}, random.Random(1))
        self.assertEqual(detail, 'Cozy Rain Ambience')
        self.assertTrue(all(t.endswith(' | 3 Hours') and len(t) <= 100 for t in options))
        self.assertNotIn('thunder', ' '.join(options).lower())
        self.assertNotIn('window', ' '.join(options).lower())
        self.assertTrue(all(EMOJI in t for t in options))
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
            self.assertEqual(variants[0]['style'], 'pixel')
            self.assertTrue(all(v['headline'] == 'STUDY\nRAIN' and v['side'] == 'right' for v in variants))

    def test_catalogue_generates_distinct_titles_until_exhausted(self):
        entries = {}
        for seed in range(90):
            options, headline, _ = presentation({}, {}, 180, entries, random.Random(seed))
            title = unique_title(options, entries, random.Random(seed))
            self.assertNotIn(title, [e['assets']['title'] for e in entries.values()])
            self.assertLessEqual(len(title), 100)
            entries[str(seed)] = {'assets': {'date': str(seed).zfill(3), 'title': title, 'thumbnail_headline': headline}}
        with self.assertRaisesRegex(ValueError, 'catalogue exhausted'):
            presentation({}, {}, 180, entries, random.Random(100))


class PackagingTests(unittest.TestCase):
    def test_titles_lead_with_outcome_then_keyword_then_length(self):
        # Like the channel's winners: "Fall Asleep Fast 🌧️ Cozy Night Rain Sounds for Sleeping & ...".
        for headline, theme in THEMES.items():
            for title in theme_titles(headline, '3 Hours'):
                opener, rest = [p.strip() for p in title.split(EMOJI)]
                self.assertIn(opener, theme['openers'])
                self.assertTrue(any(k in rest for k in KEYWORDS), title)
                self.assertTrue(title.endswith(' | 3 Hours'))
                # Mobile search shows roughly the first 60 characters.
                self.assertLess(min(title.find(k) for k in KEYWORDS if k in title), 45, title)
                self.assertLessEqual(len(title), 100)

    def test_recent_opener_is_not_reused_while_alternatives_remain(self):
        entries = {'old': {'assets': {'date': '2026-10-21', 'thumbnail_headline': 'INSOMNIA\nRAIN',
                                      'title': f'Fall Asleep Fast {EMOJI} Rain Sounds for Sleep & Deep Relaxation | 3 Hours'}}}
        for seed in range(20):
            options, _, _ = presentation({}, {}, 180, entries, random.Random(seed))
            self.assertTrue(options)
            # "Fall Asleep Fast Tonight" counts as the same opener.
            self.assertFalse(any(t.startswith('Fall Asleep Fast') for t in options))

    def test_on_screen_title_is_short_and_has_no_emoji(self):
        title = f'Fall Asleep Fast {EMOJI} Cozy Night Rain Sounds for Sleeping & Restorative Rest | 3 Hours'
        self.assertEqual(overlay_title(title), 'Fall Asleep Fast · Cozy Night Rain Sounds for Sleeping')
        for headline in THEMES:
            for t in theme_titles(headline, '3 Hours'):
                self.assertLessEqual(len(overlay_title(t)), 70)
                self.assertTrue(overlay_title(t).isascii() or set(overlay_title(t)) - set(map(chr, range(128))) == {'·'})
        self.assertEqual(overlay_title('Old Style | 3 Hours'), 'Old Style | 3 Hours')

    def test_chapters_start_at_zero_and_skip_short_tests(self):
        self.assertEqual(chapters(180).splitlines(),
                         ['Chapters', '0:00 Settle in and breathe', '1:00:00 Drift deeper', '2:00:00 Deep, restorative rest'])
        self.assertEqual(chapters(5), '')

    def test_description_only_claims_clean_audio_when_confirmed(self):
        audio = {'freesound_url': 'https://freesound.org/s/1/', 'license': 'http://creativecommons.org/publicdomain/zero/1.0/'}
        for headline in THEMES:
            confirmed = description_parts(headline, 180, audio, random.Random(1), clean=True)
            unconfirmed = description_parts(headline, 180, audio, random.Random(1), clean=False)
            self.assertIn('no distractions', confirmed['clean_line'])
            self.assertEqual(unconfirmed['clean_line'], '')
            self.assertIn('3 hours', confirmed['opening'])
            self.assertIn('rain sounds', confirmed['opening'].lower())
            self.assertIn('Creative Commons 0', confirmed['audio_credit'])
            text = ' '.join(confirmed.values()).lower()
            for unsupported in ('thunder', 'gentle', 'heavy', 'no ads', 'black screen', '\u2014'):
                self.assertNotIn(unsupported, text)
            self.assertTrue(pinned_comment(headline, random.Random(1)).startswith('\U0001f4ac'))

    def test_configured_style_is_published_first(self):
        variants = thumbnail_variants('COZY\nRAIN', {}, {}, random.Random(1), 'pixel')
        self.assertEqual([v['style'] for v in variants], ['pixel', 'soft', 'stacked'])
        variants = thumbnail_variants('COZY\nRAIN', {}, {}, random.Random(1), 'soft')
        self.assertEqual([v['style'] for v in variants], ['soft', 'pixel', 'stacked'])
        with self.assertRaises(ValueError):
            thumbnail_variants('COZY\nRAIN', {}, {}, random.Random(1), 'neon')

    def test_pixel_by_default_soft_sometimes_never_twice_running(self):
        from upload_presentation import choose_thumbnail_style
        profile = {'thumbnail_style': 'pixel', 'thumbnail_alternate_style': 'soft', 'thumbnail_alternate_share': 0.25}
        entries, styles = {}, []
        for day in range(400):
            style = choose_thumbnail_style(profile, entries, random.Random(day))
            styles.append(style)
            entries[str(day)] = {'assets': {'date': f'{day:04}', 'thumbnail_style': style}}
        self.assertTrue(0.12 < styles.count('soft') / len(styles) < 0.3)
        self.assertNotIn(('soft', 'soft'), list(zip(styles, styles[1:])))
        self.assertEqual(choose_thumbnail_style({}, {}, random.Random(1)), 'pixel')

    def test_tags_stay_within_youtube_guidance(self):
        self.assertTrue(5 <= len(TAGS) <= 10)
        self.assertFalse(any('black screen' in t or 'thunder' in t or 'music' in t for t in TAGS))
