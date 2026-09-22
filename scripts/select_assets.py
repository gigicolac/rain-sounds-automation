#!/usr/bin/env python3
"""Pick today's scene, audio track, title, description and duration.

Date-seeded selection with explicit overrides and conservative reviewed labels.
"""
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from asset_matching import compatible, title_allowed
from upload_history import Ledger

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AUDIO_DIR = ROOT / "audio"
RUN_DIR = ROOT / "run"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Short videos while testing the end-to-end pipeline.
DURATION_OPTIONS_MIN = [5, 6, 7, 8]

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


# Pexels text search matches loosely (any keyword, not the full phrase), so
# a term like "stormy sea waves rain" can return generic sunny-beach ocean
# footage with no rain in it at all. Before accepting a candidate, require
# its own Pexels URL slug (a human-written description, e.g.
# "heavy-rain-falling-on-window-1234567") to actually mention rain/weather,
# as a cheap sanity check against exactly that kind of mismatch.
RAIN_KEYWORDS = ("rain", "storm", "thunder", "drizzle", "downpour", "shower")


def _looks_rain_related(video):
    slug = video.get("url", "").lower()
    return any(keyword in slug for keyword in RAIN_KEYWORDS)


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

        # Prefer candidates that actually look rain-related; only fall back
        # to the unfiltered set if none of them do (better than failing the
        # whole run over one unlucky term).
        rain_results = [v for v in results if _looks_rain_related(v)]
        if not rain_results:
            continue
        reviews = load_json(DATA_DIR / "scene_reviews.json")
        reviewed = [v for v in rain_results if reviews.get(str(v["id"]), {}).get("approved") is True]
        video = rng.choice(reviewed or rain_results)
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


def pick_audio_track(rng, video=None):
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
    requested = os.environ.get("AUDIO_ID", "").strip()
    if requested:
        pool = [t for t in pool if str(t["id"]) == requested]
    if not pool:
        raise RuntimeError("Requested audio identifier is not in the cache")
    if video is not None:
        pool = [t for t in pool if compatible(t, video)]
    if not pool:
        raise RuntimeError("No audio matches the reviewed scene labels")
    reviewed = [t for t in pool if t.get("review", {}).get("approved") is True]
    track = rng.choice(reviewed or pool)
    audio_path = AUDIO_DIR / track["filename"]
    if not audio_path.exists():
        raise RuntimeError(f"Audio file listed in metadata but missing on disk: {audio_path}")
    return track


def build_description(scene_term, audio_title, duration_minutes):
    template = (DATA_DIR / "description_template.txt").read_text(encoding="utf-8")
    return template.format(
        duration=duration_minutes,
        scene_term=scene_term,
        channel_name=CHANNEL_NAME,
        channel_handle=CHANNEL_HANDLE,
        hashtags=HASHTAGS,
        audio_title=audio_title,
    )


def main():
    resume = os.environ.get("RESUME_VIDEO_ID", "").strip()
    if resume:
        _, entry = Ledger().find_video(resume)
        RUN_DIR.mkdir(exist_ok=True)
        (RUN_DIR / "assets.json").write_text(json.dumps(entry["assets"], indent=2), encoding="utf-8")
        return
    date = datetime.now(timezone.utc).date()
    day = day_number(date)

    scene_terms = load_json(DATA_DIR / "scene_terms.json")
    title_templates = load_json(DATA_DIR / "title_templates.json")

    rng_scene = random.Random(day * SEED_SCENE)
    rng_audio = random.Random(day * SEED_AUDIO)
    rng_title = random.Random(day * SEED_TITLE)
    rng_duration = random.Random(day * SEED_DURATION)

    override = os.environ.get("SCENE_QUERY", "").strip()
    if override:
        scene_terms = [override]
    video = pick_scene_video(scene_terms, rng_scene, PEXELS_API_KEY)
    scene_reviews = load_json(DATA_DIR / "scene_reviews.json")
    video["review"] = scene_reviews.get(str(video["pexels_id"]), {"approved": False, "labels": {}})
    audio = pick_audio_track(rng_audio, video)
    override_duration = os.environ.get("DURATION_MINUTES", "").strip()
    duration_minutes = int(override_duration) if override_duration else rng_duration.choice(DURATION_OPTIONS_MIN)
    if not 1 <= duration_minutes <= 8:
        raise ValueError("Duration must be between 1 and 8 minutes during testing")
    if not compatible(audio, video):
        raise RuntimeError("Reviewed audio and scene labels conflict; choose a compatible pair")

    title_templates = [t for t in title_templates if title_allowed(t, audio, video)]
    if not title_templates:
        raise RuntimeError("No title is compatible with the reviewed asset labels")
    title_template = rng_title.choice(title_templates)
    title = title_template.format(duration=duration_minutes)
    title = os.environ.get("TITLE_OVERRIDE", "").strip() or title
    if len(title) > 100 or not title_allowed(title, audio, video):
        raise ValueError("Title exceeds 100 characters or makes unsupported claims about the assets")
    description = build_description("rain ambience", audio.get("title", "rain sounds"), duration_minutes)

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
            "review": audio.get("review", {}),
        },
        "duration_minutes": duration_minutes,
        "duration_seconds": duration_minutes * 60,
        "title": title,
        "description": description,
        "tags": [t for t in TAGS if "thunder" not in t],
        "review_approved": audio.get("review", {}).get("approved") is True and video["review"].get("approved") is True,
        "category_id": "10",  # Music
    }

    Ledger().check_new(assets)
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
