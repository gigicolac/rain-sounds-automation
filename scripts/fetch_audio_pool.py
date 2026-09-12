#!/usr/bin/env python3
"""Batch-refresh the cached pool of CC0 rain/ambient tracks from Freesound.

Run on a slow cadence (weekly/monthly via its own GitHub Actions workflow) —
NOT by the daily job. This is what keeps the daily pipeline immune to
Freesound downtime: it only ever reads from the local audio/ cache that this
script populates.

Uses Freesound's search API (simple token auth) and downloads the HQ preview
file for each sound. Previews (not the raw original upload) are used
deliberately: Freesound's raw-file /download/ endpoint requires a full OAuth2
user-login flow, while previews are high quality (up to 128kbps mp3) and
reachable with plain API-key auth, which keeps this fully unattended.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
METADATA_PATH = AUDIO_DIR / "metadata.json"

FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY")
SEARCH_URL = "https://freesound.org/apiv2/search/text/"

SEARCH_TAGS = [
    "rain", "heavy rain", "rain ambience", "rainstorm", "gentle rain",
    "rain on window", "rainforest rain", "thunderstorm rain", "rain forest",
    "rain on roof",
]

POOL_TARGET = int(os.environ.get("AUDIO_POOL_TARGET", "28"))
MIN_DURATION_S = 45
MAX_DURATION_S = 900
FIELDS = "id,name,previews,duration,license,tags,username"
CC0_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"


def load_metadata():
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_metadata(pool):
    METADATA_PATH.write_text(json.dumps(pool, indent=2), encoding="utf-8")


def is_cc0(license_value):
    return license_value == CC0_LICENSE_URL


def search_tag(tag, api_key):
    headers = {"Authorization": f"Token {api_key}"}
    params = {
        "query": tag,
        # Needs an explicit AND: Freesound's query parser doesn't reliably
        # imply it between space-separated clauses, and silently returns
        # zero results instead of erroring on the ambiguous form.
        "filter": f'duration:[{MIN_DURATION_S} TO {MAX_DURATION_S}] AND (license:"Creative Commons 0")',
        "fields": FIELDS,
        "sort": "rating_desc",
        "page_size": 15,
    }
    resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=30)
    print(f"DEBUG tag={tag!r} url={resp.url} status={resp.status_code}", file=sys.stderr)
    resp.raise_for_status()
    body = resp.json()
    print(f"DEBUG tag={tag!r} count={body.get('count')} raw_keys={list(body.keys())}", file=sys.stderr)
    if not body.get("results"):
        print(f"DEBUG tag={tag!r} full_body={body}", file=sys.stderr)
    return body.get("results", [])


def download_preview(sound, dest_path):
    preview_url = sound.get("previews", {}).get("preview-hq-mp3")
    if not preview_url:
        return False
    resp = requests.get(preview_url, timeout=60)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    return True


def main():
    if not FREESOUND_API_KEY:
        raise RuntimeError("FREESOUND_API_KEY is not set")

    AUDIO_DIR.mkdir(exist_ok=True)
    pool = load_metadata()
    existing_ids = {track["id"] for track in pool}

    added = 0
    for tag in SEARCH_TAGS:
        if len(pool) >= POOL_TARGET:
            break
        try:
            results = search_tag(tag, FREESOUND_API_KEY)
        except requests.RequestException as exc:
            print(f"Search for '{tag}' failed, skipping: {exc}", file=sys.stderr)
            continue

        for sound in results:
            if len(pool) >= POOL_TARGET:
                break
            if sound["id"] in existing_ids:
                continue
            if not is_cc0(sound.get("license")):
                continue

            filename = f"{sound['id']}.mp3"
            dest_path = AUDIO_DIR / filename
            try:
                ok = download_preview(sound, dest_path)
            except requests.RequestException as exc:
                print(f"Download failed for sound {sound['id']}: {exc}", file=sys.stderr)
                continue
            if not ok:
                continue

            pool.append({
                "id": sound["id"],
                "filename": filename,
                "title": sound.get("name"),
                "duration": sound.get("duration"),
                "license": sound.get("license"),
                "tags": sound.get("tags", []),
                "username": sound.get("username"),
                "freesound_url": f"https://freesound.org/s/{sound['id']}/",
            })
            existing_ids.add(sound["id"])
            added += 1
            print(f"Added {filename} ({sound.get('name')!r})")
            time.sleep(0.5)  # be polite to the API

    save_metadata(pool)
    print(f"Pool size now {len(pool)} (added {added} new tracks this run)")

    if not pool:
        raise RuntimeError(
            "Pool is empty after this run — every Freesound search returned "
            "zero usable results. Failing loudly instead of leaving the "
            "daily job to discover an empty cache."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"fetch_audio_pool.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
