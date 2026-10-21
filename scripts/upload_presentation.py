"""Truthful presentation choices and additive variety records for upload history."""
from asset_matching import labels_for


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


def presentation(video, audio, minutes, entries, rng):
    length = length_label(minutes)
    a, v = labels_for(audio), labels_for(video)
    detail = "Cozy Rain Ambience"
    if a.get("setting") == v.get("setting") and a.get("setting") in {"window", "forest", "roof", "tent", "lake", "city"}:
        detail = {"window": "Rain on a Window", "forest": "Forest Rain", "roof": "Rain on a Roof",
                  "tent": "Rain on a Tent", "lake": "Lakeside Rain", "city": "City Rain"}[a["setting"]]
    # Keep the searchable purpose first; vary truthful ambience wording only.
    purposes = {
        'SLEEP\nRAIN': 'Rain Sounds for Sleeping',
        'STUDY\nRAIN': 'Rain Sounds for Studying',
        'UNWIND\nRAIN': 'Rain Sounds for Relaxation',
        'COZY\nRAIN': 'Rain Sounds for Sleep',
        'JUST\nRAIN': 'Rain Sounds for Rest',
        'RAIN\nBREAK': 'Rain Sounds for Reading',
    }
    moods = ['Cozy Ambience', 'Rain Ambience', 'Cozy Rain',
             'Rainy Escape', 'Rainy Retreat', 'Rainy Atmosphere']
    themes = {headline: [f'{keyword} | {mood}' for mood in moods]
              for headline, keyword in purposes.items()}
    used = {e.get('assets', {}).get('title', '').strip().casefold() for e in entries.values()}
    recent = sorted(entries.values(), key=lambda e: e.get("assets", {}).get("date", ""), reverse=True)
    previous = next((e.get("assets", {}).get("thumbnail_headline") for e in recent
                     if e.get("assets", {}).get("thumbnail_headline")), None)
    eligible = {h: [f'{t} | {length}' for t in titles if f'{t} | {length}'.casefold() not in used]
                for h, titles in themes.items()}
    eligible = {h: titles for h, titles in eligible.items() if titles}
    if not eligible:
        raise ValueError('Title catalogue exhausted; add new truthful titles before publishing.')
    headline = rng.choice([h for h in eligible if h != previous] or list(eligible))
    options = eligible[headline]
    if detail != 'Cozy Rain Ambience':
        specific = f'{purposes[headline]} | {detail} | {length}'
        if specific.casefold() not in used:
            options.append(specific)
    return options, headline, detail


def thumbnail_variants(headline, video, entries, rng):
    """Three alternatives for Studio review; only the first is uploaded."""
    side = video.get('thumbnail_text_side', 'left')
    if side not in {'left', 'right'}:
        raise ValueError('thumbnail_text_side must be left or right')
    # The published cover always uses the same layout. Alternatives remain
    # local review artifacts and do not rotate the channel's visual identity.
    return [{'headline': headline, 'style': style, 'side': side}
            for style in ['stacked', 'accent', 'panel']]


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
