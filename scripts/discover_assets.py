"""Discover exact Pexels candidates or import a separately licensed local animation."""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
import requests
from asset_library import ROOT, read_json, write_json

URL = "https://api.pexels.com/videos"

def video_record(video):
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"
             and f.get("width", 0) >= 1920 and f.get("height", 0) >= 1080]
    if video.get("duration", 0) < 10 or not files:
        return None
    # Smallest native Full HD-or-better version; avoid needless 4K transfers.
    chosen = min(files, key=lambda f: f["width"] * f["height"])
    return {"asset_id": f"pexels:{video['id']}", "pexels_id": video["id"],
            "source_url": video["url"], "pexels_url": video["url"],
            "license_url": "https://www.pexels.com/license/",
            "creator": video.get("user", {}).get("name"), "download_url": chosen["link"],
            "width": chosen["width"], "height": chosen["height"], "duration": video["duration"],
            "review": {"approved": False, "labels": {}, "notes": "", "quality": {}}}

def refresh_video(asset, key):
    if not key:
        raise RuntimeError("PEXELS_API_KEY required to refresh an exact approved clip")
    r = requests.get(f"{URL}/videos/{asset['pexels_id']}", headers={"Authorization": key}, timeout=30)
    r.raise_for_status()
    fresh = video_record(r.json())
    if fresh is None or fresh["pexels_id"] != asset["pexels_id"]:
        raise RuntimeError("Reviewed source is unavailable or below quality requirements")
    # Preserve the original review; metadata is refreshed only for the same source identifier.
    return dict(asset, download_url=fresh["download_url"], width=fresh["width"],
                height=fresh["height"], duration=fresh["duration"])

def discover(style, limit, root=ROOT):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY is required for discovery")
    path = root / "data/video_library.json"
    pool = read_json(path, [])
    known = {v["asset_id"] for v in pool}
    state_path = root / "data/video_discovery_state.json"
    state = read_json(state_path, {})
    queries = read_json(root / "data/video_discovery.json", {})[style]
    added = 0
    # One candidate per query per pass prevents the first search filling the library.
    queues = []
    for query in queries:
        page = state.get(query, 1)
        response = requests.get(URL + "/search", headers={"Authorization": key},
                                params={"query": query, "orientation": "landscape",
                                        "per_page": 30, "page": page}, timeout=30)
        response.raise_for_status()
        data = response.json()
        state[query] = page + 1 if data.get("next_page") else 1
        queue = []
        for video in data.get("videos", []):
            record = video_record(video)
            if record and record["asset_id"] not in known:
                record.update(discovery_query=query, discovery_style=style,
                              discovered_at=datetime.now(timezone.utc).isoformat())
                queue.append(record)
        queues.append(queue)
    while added < limit and any(queues):
        for queue in queues:
            if not queue or added >= limit:
                continue
            candidate = queue.pop(0)
            if candidate["asset_id"] in known:
                continue
            pool.append(candidate); known.add(candidate["asset_id"]); added += 1
    write_json(path, pool)
    write_json(state_path, state)
    print(f"Added {added} unreviewed candidates. Search style is a hint, not an approved label.")

def import_local(args):
    from media_quality import probe
    path = Path(args.file).resolve()
    relative = path.relative_to(ROOT.resolve())
    info = probe(path)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    candidate = {"asset_id": args.asset_id, "local_path": relative.as_posix(),
                 "source_url": args.source_url, "license_url": args.license_url,
                 "width": stream["width"], "height": stream["height"],
                 "duration": float(info["format"]["duration"]),
                 "review": {"approved": False, "labels": {}, "quality": {}, "notes": ""}}
    if candidate["width"] < 1920 or candidate["height"] < 1080 or candidate["duration"] < 10:
        raise ValueError("Imported video must be native 1920x1080 or better and at least 10 seconds")
    if not args.asset_id.startswith("local:"):
        raise ValueError("Use a stable local: identifier for external clips")
    library = read_json(ROOT / "data/video_library.json", [])
    if any(v["asset_id"] == args.asset_id for v in library):
        raise ValueError("Identifier already exists; preserve its review and upload history")
    library.append(candidate)
    write_json(ROOT / "data/video_library.json", library)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--style", choices=["live_action", "illustrated"], default="illustrated")
    d.add_argument("--limit", type=int, default=12)
    i = sub.add_parser("import-local")
    for field in ("file", "asset-id", "source-url", "license-url"):
        i.add_argument("--" + field, required=True)
    args = parser.parse_args()
    if args.command == "discover":
        if not 1 <= args.limit <= 60:
            parser.error("limit must be 1–60")
        discover(args.style, args.limit)
    else:
        import_local(args)

if __name__ == "__main__":
    main()
