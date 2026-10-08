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
    # Never infer a new environment from an unreviewed source name.
    base = options[0]
    number = 2
    while True:
        suffix = f" | Session {number}"
        candidate = base[:100-len(suffix)].rstrip() + suffix
        if candidate.casefold() not in used:
            return candidate
        number += 1


def presentation(video, audio, minutes, entries, rng):
    length = length_label(minutes)
    a, v = labels_for(audio), labels_for(video)
    detail = "Cozy Rain Ambience"
    if a.get("setting") == v.get("setting") and a.get("setting") in {"window", "forest", "roof", "tent", "lake", "city"}:
        detail = {"window": "Rain on a Window", "forest": "Forest Rain", "roof": "Rain on a Roof",
                  "tent": "Rain on a Tent", "lake": "Lakeside Rain", "city": "City Rain"}[a["setting"]]
    options = [f"Rain Sounds for Sleeping | {length} of {detail}",
               f"Rain Sounds for Studying | {length} of {detail}",
               f"Rain Sounds for Relaxation | {length} of {detail}"]
    headlines = ["SLEEP\nRAIN", "STUDY\nRAIN", "UNWIND\nRAIN"]
    recent = sorted(entries.values(), key=lambda e: e.get("assets", {}).get("date", ""), reverse=True)
    previous = next((e.get("assets", {}).get("thumbnail_headline") for e in recent
                     if e.get("assets", {}).get("thumbnail_headline")), None)
    headline = rng.choice([h for h in headlines if h != previous])
    return options, headline, detail


def variety_record(assets):
    video, audio = assets["video"], assets["audio"]
    return {"scene_id": video.get("asset_id", video.get("pexels_id")),
            "scene_source": video.get("source_url", video.get("pexels_url")),
            "audio_id": audio.get("freesound_id"), "audio_source": audio.get("freesound_url"),
            "duration_seconds": assets.get("duration_seconds"), "title": assets.get("title"),
            "keyword": assets.get("title", "").split("|")[0].strip(),
            "thumbnail_headline": assets.get("thumbnail_headline"),
            "description_opening": assets.get("description", "").split("\n")[0],
            "verified_video_labels": labels_for(video), "verified_audio_labels": labels_for(audio)}
