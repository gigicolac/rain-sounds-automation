#!/usr/bin/env python3
"""Pick today's scene, audio track, title, description and duration.

Deterministic per calendar day (UTC) via seeded RNGs, so the same day always
picks the same combination if re-run, but consecutive days rotate through
different scenes/audio/titles/durations. Writes the result to
run/assets.json for build_video.py and upload_youtube.py to consume.

This rotation isn't just cosmetic variety: YouTube's monetisation policy
treats channels that post reused, repetitive or duplicative content as
ineligible for the Partner Program. Deliberately varying scene/audio/title/
duration every day is what keeps each upload distinct enough to stay
clear of that.
"""
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AUDIO_DIR = ROOT / "audio"
RUN_DIR = ROOT / "run"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Duration options in minutes, matching the brief's 1-2hr target.
DURATION_OPTIONS_MIN = [60, 75, 90, 105, 120]

# Distinct large primes to decorrelate the rotation across categories so
# scene/audio/title/duration don't all cycle in lockstep.
SEED_SCENE = 7919
SEED_AUDIO = 104729
SEED_TITLE = 15485863
SEED_DURATION = 32452867

HASHTAGS = "#rainsounds #rain #sleep #relaxation #ambience #whitenoise #study"

TAGS = [
    "rain sounds", "rain sounds for sleeping", "rain ambience", "sleep sounds",
    "relaxing rain", "study music", "white noise", "thunderstorm sounds",
    "rain sounds for studying", "calming rain", "ambient rain", "deep sleep",
]

CHANNEL_NAME = "Calming Rain Sounds"
CHANNEL_HANDLE = "@calmingrainsoundssss"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def day_number(date=None):
    date = date or datetime.now(timezone.utc).date()
    return date.toordinal()


def pick_scene_video(scene_terms, rng, api_key):
    """Query Pexels for the day's scene term, trying a few fallback terms
    if a search comes back empty, and return the chosen video's metadata."""
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY is not set")

    ordered_terms = scene_terms[:]
    rng.shuffle(ordered_terms)

    headers = {"Authorization": api_key}
    for term in ordered_terms[:5]:
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers=headers,
            params={"query": term, "per_page": 10, "orientation": "landscape"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("videos", [])
        if not results:
            continue

        video = rng.choice(results)
        video_files = [
            vf for vf in video.get("video_files", [])
            if vf.get("file_type") == "video/mp4" and vf.get("width")
        ]
        if not video_files:
            continue

        # Prefer the largest file that's at or under 1080p width; otherwise
        # fall back to the smallest available (better than failing outright).
        under_1080 = [vf for vf in video_files if vf["width"] <= 1920]
        chosen_file = (
            max(under_1080, key=lambda vf: vf["width"])
            if under_1080
            else min(video_files, key=lambda vf: vf["width"])
        )

        return {
            "scene_term": term,
            "pexels_id": video["id"],
            "pexels_url": video["url"],
            "download_url": chosen_file["link"],
            "width": chosen_file["width"],
            "height": chosen_file["height"],
        }

    raise RuntimeError(
        f"No usable Pexels video found after trying {len(ordered_terms[:5])} scene terms"
    )


def pick_audio_track(rng):
    metadata_path = AUDIO_DIR / "metadata.json"
    if not metadata_path.exists():
        raise RuntimeError(
            "audio/metadata.json not found. Run the audio-cache workflow "
            "(scripts/fetch_audio_pool.py) at least once before the daily job."
        )
    pool = load_json(metadata_path)
    if not pool:
        raise RuntimeError(
            "audio/metadata.json is empty. Run the audio-cache workflow to "
            "populate the cached track pool before the daily job."
        )
    track = rng.choice(pool)
    audio_path = AUDIO_DIR / track["filename"]
    if not audio_path.exists():
        raise RuntimeError(f"Audio file listed in metadata but missing on disk: {audio_path}")
    return track


def build_description(scene_term, audio_title, duration_hours):
    template = (DATA_DIR / "description_template.txt").read_text(encoding="utf-8")
    return template.format(
        duration=duration_hours,
        scene_term=scene_term,
        channel_name=CHANNEL_NAME,
        channel_handle=CHANNEL_HANDLE,
        hashtags=HASHTAGS,
        audio_title=audio_title,
    )


def format_duration_hours(minutes):
    hours = minutes / 60
    # Show "1" or "1.5" / "2" rather than "1.0" / "1.5" / "2.0".
    return f"{hours:g}"


def main():
    date = datetime.now(timezone.utc).date()
    day = day_number(date)

    scene_terms = load_json(DATA_DIR / "scene_terms.json")
    title_templates = load_json(DATA_DIR / "title_templates.json")

    rng_scene = random.Random(day * SEED_SCENE)
    rng_audio = random.Random(day * SEED_AUDIO)
    rng_title = random.Random(day * SEED_TITLE)
    rng_duration = random.Random(day * SEED_DURATION)

    video = pick_scene_video(scene_terms, rng_scene, PEXELS_API_KEY)
    audio = pick_audio_track(rng_audio)
    duration_minutes = rng_duration.choice(DURATION_OPTIONS_MIN)
    duration_hours = format_duration_hours(duration_minutes)

    title_template = rng_title.choice(title_templates)
    title = title_template.format(duration=duration_hours)
    description = build_description(video["scene_term"], audio.get("title", "rain sounds"), duration_hours)

    assets = {
        "date": date.isoformat(),
        "day_number": day,
        "scene_term": video["scene_term"],
        "video": video,
        "audio": {
            "filename": audio["filename"],
            "path": str((AUDIO_DIR / audio["filename"]).relative_to(ROOT)),
            "title": audio.get("title"),
            "freesound_id": audio.get("id"),
        },
        "duration_minutes": duration_minutes,
        "duration_seconds": duration_minutes * 60,
        "title": title,
        "description": description,
        "tags": TAGS,
        "category_id": "10",  # Music
    }

    RUN_DIR.mkdir(exist_ok=True)
    out_path = RUN_DIR / "assets.json"
    out_path.write_text(json.dumps(assets, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(assets, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - surface clearly in Actions logs
        print(f"select_assets.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
