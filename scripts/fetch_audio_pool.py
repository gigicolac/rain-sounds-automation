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
import signal
import sys
import time
from datetime import datetime, timezone
from asset_library import read_json, write_json
from pathlib import Path

import requests


class HardTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise HardTimeout("Hard wall-clock timeout exceeded")


def with_hard_timeout(seconds, func, *args, **kwargs):
    """Force-interrupt func after `seconds` real wall-clock time, no matter
    what it's blocked on. requests' own timeout parameter only bounds the
    connect/read phases of an established socket — it does NOT cover DNS
    resolution, which can hang indefinitely on some hosts and silently
    defeats a normal timeout= argument. SIGALRM interrupts regardless of
    where execution is actually stuck.
    """
    if not hasattr(signal, "SIGALRM"):
        return func(*args, **kwargs)
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(seconds)
    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
METADATA_PATH = AUDIO_DIR / "metadata.json"

FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY")
SEARCH_URL = "https://freesound.org/apiv2/search/text/"

MIN_DURATION_S = 45
MAX_DURATION_S = 900
FIELDS = "id,name,previews,duration,license,tags,username"


def load_metadata():
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_metadata(pool):
    METADATA_PATH.write_text(json.dumps(pool, indent=2), encoding="utf-8")


def search_tag(tag, api_key, page=1):
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
        "page": page,
    }
    # (connect, read) tuple rather than one flat number, so a slow/hanging
    # connection to a single sound's server fails fast instead of silently
    # consuming a large chunk of the job's total runtime.
    resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=(10, 15))
    resp.raise_for_status()
    return resp.json()


def download_preview(sound, dest_path):
    preview_url = sound.get("previews", {}).get("preview-hq-mp3")
    if not preview_url:
        return False
    resp = requests.get(preview_url, timeout=(10, 20))
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    return True


def main():
    if not FREESOUND_API_KEY:
        raise RuntimeError("FREESOUND_API_KEY is not set")

    AUDIO_DIR.mkdir(exist_ok=True)
    pool = load_metadata()
    existing_ids = {track["id"] for track in pool}

    # Per-request timeouts alone don't bound total runtime: if every
    # candidate in a tag's results systematically fails, that's up to
    # page_size (15) x download-timeout (25s) per tag before moving on —
    # over an hour in the worst case across all tags. This wall-clock
    # budget caps the whole fetch phase regardless of how many individual
    # attempts fail, so the job always finishes in bounded time.
    deadline = time.monotonic() + float(os.environ.get("FETCH_BUDGET_SECONDS", "240"))

    added = 0
    new_limit = int(os.environ.get("AUDIO_NEW_LIMIT", "12"))
    categories = read_json(ROOT / "data/audio_discovery.json", {})
    state_path = ROOT / "data/audio_discovery_state.json"
    state = read_json(state_path, {})
    # Balance observed inventory coverage; query hints are never treated as verified labels.
    def coverage(category):
        return sum(1 for t in pool if t.get("review", {}).get("status") != "rejected"
                   and t.get("discovery_category") == category)
    categories = sorted(categories, key=coverage)
    queues = {}
    queries_by_category = {}
    for category in categories:
        if time.monotonic() > deadline:
            break
        queries = read_json(ROOT / "data/audio_discovery.json", {})[category]
        cursor = state.get(category, {"query": 0, "page": 1})
        query = queries[cursor["query"] % len(queries)]
        queries_by_category[category] = query
        try:
            data = with_hard_timeout(20, search_tag, query, FREESOUND_API_KEY, cursor["page"])
        except (requests.RequestException, HardTimeout) as exc:
            print(f"Search failed for {category}: {exc}", file=sys.stderr)
            continue
        state[category] = {"query": cursor["query"] + 1,
                           "page": cursor["page"] + (1 if (cursor["query"] + 1) % len(queries) == 0 else 0)}
        queues[category] = data.get("results", [])
        if not queues[category]:
            state[category]["page"] = 1
    while added < new_limit and any(queues.values()) and time.monotonic() <= deadline:
        progressed = False
        for category in sorted(queues, key=coverage):
            if added >= new_limit or time.monotonic() > deadline:
                break
            queue = queues[category]
            while queue:
                sound = queue.pop(0)
                if sound["id"] in existing_ids:
                    continue
                name = (sound.get("name") or "").lower()
                if not any(word in name for word in ("rain", "storm", "thunder", "drizzle", "downpour")):
                    continue
                # Defense in depth: handle both URL and display-name license forms.
                license_name = str(sound.get("license", "")).lower()
                if not ("creativecommons.org/publicdomain/zero/" in license_name or license_name == "creative commons 0"):
                    continue
                filename = f"{sound['id']}.mp3"
                try:
                    ok = with_hard_timeout(25, download_preview, sound, AUDIO_DIR / filename)
                except (requests.RequestException, HardTimeout) as exc:
                    print(f"Download {sound['id']} failed: {exc}", file=sys.stderr)
                    continue
                if not ok:
                    continue
                pool.append({"id": sound["id"], "filename": filename, "title": sound.get("name"),
                             "duration": sound.get("duration"), "license": sound.get("license"),
                             "tags": sound.get("tags", []), "username": sound.get("username"),
                             "freesound_url": f"https://freesound.org/s/{sound['id']}/",
                             "download_kind": "hq_mp3_preview",
                             "download_url": sound.get("previews", {}).get("preview-hq-mp3"),
                             "discovery_query": queries_by_category[category],
                             "discovery_category": category,
                             "discovered_at": datetime.now(timezone.utc).isoformat(),
                             "review": {"approved": False, "status": "pending", "labels": {},
                                        "quality": {}, "notes": ""}})
                existing_ids.add(sound["id"]); added += 1; progressed = True
                save_metadata(pool)
                break
        if not progressed:
            break
    write_json(state_path, state)
    save_metadata(pool)
    print(f"Pool size now {len(pool)} (added {added} new tracks this run)", flush=True)

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
        print(f"fetch_audio_pool.py failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
