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
    themes = {
        'SLEEP\nRAIN': ['Rain Sounds for Sleep', 'Drift Off With Rain', 'Rain for a Restful Night', 'Bedtime Rain Ambience', 'Wind Down With Rain', 'Rain for Your Bedtime Routine'],
        'STUDY\nRAIN': ['Rain Sounds for Studying', 'Settle Into Study With Rain', 'Rain for Reading', 'Your Rainy Study Break', 'Rain for a Focus Session', 'Rain for Your Reading Hour'],
        'UNWIND\nRAIN': ['Rain Sounds to Unwind', 'Take a Rainy Break', 'A Little Rain, A Little Rest', 'Slow Down With Rain', 'Rain for a Quiet Moment', 'Leave the Day Behind With Rain'],
        'COZY\nRAIN': ['Cozy Rain Ambience', 'A Cozy Escape With Rain', 'Stay In With Rain Sounds', 'Make Time for Rain', 'A Quiet Rainy Retreat', 'Rain Sounds for a Cozy Break'],
        'JUST\nRAIN': ['Just Rain Sounds', 'A Moment With Rain', 'Let the Rain Play', 'Rain Sounds for Your Day', 'Take Your Time With Rain', 'Rain Ambience for a Slow Day'],
        'RAIN\nBREAK': ['Your Rain Break', 'Pause With Rain Sounds', 'A Rainy Reset', 'Step Away With Rain', 'Rain for a Breathing Space', 'A Short Escape With Rain'],
    }
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
        specific = f'{detail} | {length}'
        if specific.casefold() not in used:
            options.append(specific)
    return options, headline, detail


def thumbnail_variants(headline, video, entries, rng):
    """Three alternatives for Studio review; only the first is uploaded."""
    side = video.get('thumbnail_text_side', 'left')
    if side not in {'left', 'right'}:
        raise ValueError('thumbnail_text_side must be left or right')
    styles = ['stacked', 'accent', 'panel']
    recent = sorted(entries.values(), key=lambda e: e.get('assets', {}).get('date', ''), reverse=True)
    previous = next((e['assets'].get('thumbnail_style') for e in recent
                     if e.get('assets', {}).get('thumbnail_style')), None)
    first = rng.choice([style for style in styles if style != previous])
    return [{'headline': headline, 'style': style, 'side': side}
            for style in [first] + [s for s in styles if s != first]]


def variety_record(assets):
    video, audio = assets["video"], assets["audio"]
    return {"scene_id": video.get("asset_id", video.get("pexels_id")),
            "scene_source": video.get("source_url", video.get("pexels_url")),
            "audio_id": audio.get("freesound_id"), "audio_source": audio.get("freesound_url"),
            "duration_seconds": assets.get("duration_seconds"), "title": assets.get("title"),
            "keyword": assets.get("title", "").split("|")[0].strip(),
            "thumbnail_headline": assets.get("thumbnail_headline"),
            "thumbnail_style": assets.get("thumbnail_style"),
            "description_opening": assets.get("description", "").split("\n")[0],
            "verified_video_labels": labels_for(video), "verified_audio_labels": labels_for(audio)}
