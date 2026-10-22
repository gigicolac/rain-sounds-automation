"""Truthful presentation choices and additive variety records for upload history."""
import json
from pathlib import Path

from asset_matching import labels_for

COPY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'description_copy.json'
CHANNEL_URL = 'https://www.youtube.com/@calmingrainsoundssss'
HASHTAGS = '#rainsounds #rainsoundsforsleeping #sleepsounds #rainasmr #rainforstudy #rainforfocus'
TAGS = ['rain sounds for sleeping', 'rain sounds for sleep', 'rain sounds', 'sleep sounds',
        'calming rain sounds', 'rain ambience', 'cozy rain', 'rain for insomnia',
        'deep sleep rain', 'rain asmr']
# Highest-volume searches (vidIQ, Oct 2026): every middle carries one of these.
KEYWORDS = ('Rain Sounds for Sleeping', 'Rain Sounds for Sleep')
EMOJI = '🌧️'
# Winners lead with the outcome: "{opener} 🌧️ {middle} & {benefit} | {length}".
# Each locked thumbnail headline owns wording that matches its promise.
THEMES = {
    'COZY\nRAIN': {
        'openers': ('Fall Asleep Fast', 'Unwind and Drift Off', 'Let the Day Melt Away',
                    'Slow Down and Drift Off', 'Fall Asleep Fast Tonight'),
        'middles': ('Cozy Night Rain Sounds for Sleeping', 'Cozy Rain Sounds for Sleep'),
        'benefits': ('Deep Relaxation', 'Restorative Rest', 'a Calm Mind'),
    },
    'DEEP SLEEP\nRAIN': {
        'openers': ('Fall Asleep Fast', 'Drift Into Deep Sleep', 'Sleep Deeply Tonight',
                    'Rest Deeply Tonight', 'Fall Asleep Fast Tonight'),
        'middles': ('Calming Rain Sounds for Sleeping', 'Rain Sounds for Sleep'),
        'benefits': ('Restorative Rest', 'Deep Relaxation', 'a Nervous System Reset'),
    },
    'INSOMNIA\nRAIN': {
        'openers': ('Stop Overthinking', 'Calm a Racing Mind', 'Quiet Your Thoughts',
                    "Can't Sleep?", 'Switch Off Your Mind'),
        'middles': ('Rain Sounds for Sleeping', 'Calming Rain Sounds for Sleep'),
        'benefits': ('Insomnia Nights', 'Restless Nights', 'a Nervous System Reset'),
    },
}
RECENT_WINDOW = 7
CHAPTER_NAMES = ('Settle in and breathe', 'Drift deeper', 'Deep, restorative rest')


def length_label(minutes):
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} Hour" + ("s" if hours != 1 else "")
    return f"{minutes} Minute" + ("s" if minutes != 1 else "")


def unique_title(options, entries, rng, override=""):
    used = {e.get("assets", {}).get("title", "").strip().casefold() for e in entries.values()}
    if override:
        if override.casefold() in used:
            raise ValueError("Title already exists in upload history; choose a distinct title.")
        return override
    available = [t for t in options if t.casefold() not in used]
    if available:
        return rng.choice(available)
    raise ValueError('All eligible titles have been used; add new truthful titles before publishing.')


def theme_titles(headline, length):
    theme = THEMES[headline]
    return [f'{o} {EMOJI} {m} & {b} | {length}'
            for o in theme['openers'] for m in theme['middles'] for b in theme['benefits']]


def _outcome(title):
    # "Fall Asleep Fast" and "Fall Asleep Fast Tonight" count as the same opener.
    if EMOJI not in title:
        return ''
    return ' '.join(title.split(EMOJI)[0].casefold().split()[:3])


def overlay_title(title):
    """Short, emoji-free version for the on-screen title (the video font has no emoji)."""
    if EMOJI not in title:
        return title
    opener, rest = (part.strip() for part in title.split(EMOJI, 1))
    return f"{opener} · {rest.split(' & ')[0]}"


def presentation(video, audio, minutes, entries, rng):
    length = length_label(minutes)
    a, v = labels_for(audio), labels_for(video)
    detail = "Cozy Rain Ambience"
    if a.get("setting") == v.get("setting") and a.get("setting") in {"window", "forest", "roof", "tent", "lake", "city"}:
        detail = {"window": "Rain on a Window", "forest": "Forest Rain", "roof": "Rain on a Roof",
                  "tent": "Rain on a Tent", "lake": "Lakeside Rain", "city": "City Rain"}[a["setting"]]
    used = {e.get('assets', {}).get('title', '').strip().casefold() for e in entries.values()}
    recent = sorted(entries.values(), key=lambda e: e.get("assets", {}).get("date", ""), reverse=True)
    previous = next((e.get("assets", {}).get("thumbnail_headline") for e in recent
                     if e.get("assets", {}).get("thumbnail_headline")), None)
    # Near-identical titles on consecutive days compete with each other in search.
    recent_outcomes = {_outcome(e.get('assets', {}).get('title', '')) for e in recent[:RECENT_WINDOW]}
    eligible = {h: [t for t in theme_titles(h, length) if t.casefold() not in used] for h in THEMES}
    eligible = {h: titles for h, titles in eligible.items() if titles}
    if not eligible:
        raise ValueError('Title catalogue exhausted; add new truthful titles before publishing.')
    headline = rng.choice([h for h in eligible if h != previous] or list(eligible))
    fresh = [t for t in eligible[headline] if _outcome(t) not in recent_outcomes]
    return fresh or eligible[headline], headline, detail


THUMBNAIL_STYLES = ('pixel', 'soft', 'stacked')


def choose_thumbnail_style(profile, entries, rng):
    """Mostly the default style, sometimes the alternate, never the alternate twice running."""
    style = profile.get('thumbnail_style', 'pixel')
    alternate = profile.get('thumbnail_alternate_style')
    share = float(profile.get('thumbnail_alternate_share', 0))
    recent = sorted(entries.values(), key=lambda e: e.get('assets', {}).get('date', ''), reverse=True)
    last = next((e['assets']['thumbnail_style'] for e in recent if e.get('assets', {}).get('thumbnail_style')), None)
    if alternate and last != alternate and rng.random() < share:
        return alternate
    return style


def thumbnail_variants(headline, video, entries, rng, style='pixel'):
    """Three alternatives for Studio review; only the first is uploaded."""
    side = video.get('thumbnail_text_side', 'left')
    if side not in {'left', 'right'}:
        raise ValueError('thumbnail_text_side must be left or right')
    if style not in THUMBNAIL_STYLES:
        raise ValueError(f'thumbnail_style must be one of {THUMBNAIL_STYLES}')
    # The published cover always uses the configured style. Alternatives remain
    # local review artifacts and do not rotate the channel's visual identity.
    return [{'headline': headline, 'style': s, 'side': side}
            for s in [style] + [s for s in THUMBNAIL_STYLES if s != style]]


def timestamp(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f'{hours}:{minutes:02}:{secs:02}' if hours else f'{minutes}:{secs:02}'


def chapters(minutes):
    # YouTube needs three or more chapters starting at 0:00, each 10 seconds or longer.
    if minutes < 30:
        return ''
    marks = [index * minutes * 60 // len(CHAPTER_NAMES) for index in range(len(CHAPTER_NAMES))]
    return 'Chapters\n' + '\n'.join(f'{timestamp(m)} {name}' for m, name in zip(marks, CHAPTER_NAMES))


def audio_credit(audio):
    source = audio.get('source_url') or audio.get('freesound_url') or ''
    where = 'Freesound.org' if 'freesound.org' in source else (source or 'an unrecorded source')
    license_text = audio.get('license') or 'a license that was not recorded'
    if 'publicdomain/zero' in license_text:
        license_text = 'Creative Commons 0 (public domain)'
    return f'sourced from {where}, released under {license_text}'


def theme_copy(headline):
    return json.loads(COPY_PATH.read_text(encoding='utf-8'))[headline]


def description_parts(headline, minutes, audio, rng, clean):
    """Brand-voice copy. Audio claims appear only when listening review confirmed them."""
    copy = theme_copy(headline)
    return {
        'opening': rng.choice(copy['openings']).format(length=length_label(minutes).lower()),
        'body': '\n\n'.join(copy['body']),
        'clean_line': 'Just steady rain. No music, no voices, no distractions.' if clean else '',
        'chapters': chapters(minutes),
        'audio_credit': audio_credit(audio),
        'channel_url': CHANNEL_URL,
    }


def pinned_comment(headline, rng):
    return rng.choice(theme_copy(headline)['pinned_comments'])


def variety_record(assets):
    video, audio = assets["video"], assets["audio"]
    return {"scene_id": video.get("asset_id", video.get("pexels_id")),
            "scene_source": video.get("source_url", video.get("pexels_url")),
            "audio_id": audio.get("asset_id") or audio.get("freesound_id"),
            "audio_source": audio.get("source_url") or audio.get("freesound_url"),
            "audio_components": audio.get("components", []),
            "duration_seconds": assets.get("duration_seconds"), "title": assets.get("title"),
            "keyword": assets.get("title", "").split("|")[0].strip(),
            "thumbnail_headline": assets.get("thumbnail_headline"),
            "thumbnail_style": assets.get("thumbnail_style"),
            "description_opening": assets.get("description", "").split("\n")[0],
            "verified_video_labels": labels_for(video), "verified_audio_labels": labels_for(audio)}
