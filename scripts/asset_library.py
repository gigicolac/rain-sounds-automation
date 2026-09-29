"""Reviewed libraries, strict publication eligibility and history-aware pairing."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {"forest", "city", "roof", "window", "tent", "lake", "garden"}
INTENSITIES = {"gentle", "moderate", "heavy"}
SURFACES = {"leaves", "glass", "metal", "fabric", "water", "ground", "mixed"}
PERSPECTIVES = {"indoors", "sheltered", "outdoors"}
STYLES = {"live_action", "illustrated"}
EVENTS = ("thunder", "traffic", "animals", "music", "voices")

def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp.replace(path)

def identity(asset, kind):
    if kind == "video":
        return str(asset.get("asset_id") or "pexels:" + str(asset["pexels_id"]))
    return str(asset.get("asset_id") or "freesound:" + str(asset.get("freesound_id", asset.get("id"))))

def review_errors(asset, kind):
    review = asset.get("review", {})
    labels = review.get("labels", {})
    errors = []
    if review.get("status") == "rejected":
        errors.append("rejected")
    if review.get("approved") is not True:
        errors.append("not approved")
    if not str(review.get("notes", "")).strip() or not review.get("reviewed_at"):
        errors.append("dated review notes required")
    for key, allowed in (("setting", SETTINGS), ("intensity", INTENSITIES),
                         ("surface", SURFACES), ("perspective", PERSPECTIVES)):
        if labels.get(key) not in allowed:
            errors.append(f"missing/invalid {key}")
    quality = review.get("quality", {})
    for key in ("full_playback", "loop_checked"):
        if quality.get(key) is not True:
            errors.append(f"{key} must be checked")
    if kind == "audio":
        for key in EVENTS:
            if type(labels.get(key)) is not bool:
                errors.append(f"{key} must be true or false (unknown cannot publish)")
        for key in ("clean_recording", "no_clipping"):
            if quality.get(key) is not True:
                errors.append(f"{key} must be checked")
    else:
        if labels.get("style") not in STYLES:
            errors.append("missing/invalid style")
        for key in ("sharp", "stable", "rain_visible"):
            if quality.get(key) is not True:
                errors.append(f"{key} must be checked")
        if asset.get("width", 0) < 1920 or asset.get("height", 0) < 1080:
            errors.append("source must be at least 1920x1080")
        if asset.get("duration", 0) < 10:
            errors.append("source must be at least 10 seconds")
        if not asset.get("source_url") or not asset.get("license_url") or review.get("rights_checked") is not True:
            errors.append("source/license and rights review required")
    return errors

def pair_reasons(audio, video, strict=False):
    from asset_matching import labels_for
    a, v = labels_for(audio), labels_for(video)
    problems = []
    for key in ("setting", "intensity", "surface", "perspective"):
        if a.get(key) and v.get(key) and a[key] != v[key]:
            problems.append(f"{key}: audio={a[key]}, video={v[key]}")
    if strict:
        problems += ["audio: " + e for e in review_errors(audio, "audio")]
        problems += ["video: " + e for e in review_errors(video, "video")]
    return problems

def choose_pair(videos, audios, entries, rng, strict=True):
    """Minimize recent repeats and total individual reuse, excluding reserved pairs."""
    used_pairs, video_uses, audio_uses = set(), {}, {}
    recent = sorted(entries.values(), key=lambda e: e["assets"].get("date", ""), reverse=True)[:7]
    recent_videos = {identity(e["assets"]["video"], "video") for e in recent}
    recent_audios = {identity(e["assets"]["audio"], "audio") for e in recent}
    recent_settings = [e["assets"]["video"].get("review", {}).get("labels", {}).get("setting") for e in recent]
    for entry in entries.values():
        assets = entry["assets"]
        v, a = identity(assets["video"], "video"), identity(assets["audio"], "audio")
        used_pairs.add((v, a))
        video_uses[v] = video_uses.get(v, 0) + 1
        audio_uses[a] = audio_uses.get(a, 0) + 1
    candidates = []
    for video in videos:
        for audio in audios:
            if any(x.get("review", {}).get("status") == "rejected" for x in (video, audio)):
                continue
            v, a = identity(video, "video"), identity(audio, "audio")
            if (v, a) in used_pairs or pair_reasons(audio, video, strict):
                continue
            setting = video.get("review", {}).get("labels", {}).get("setting")
            score = (int(v in recent_videos) + int(a in recent_audios),
                     recent_settings.count(setting) if setting else 0,
                     video_uses.get(v, 0) + audio_uses.get(a, 0))
            candidates.append((score, rng.random(), video, audio))
    if not candidates:
        raise RuntimeError("No unused compatible pair. Discover/review more assets; do not delete history.")
    score, _, video, audio = min(candidates, key=lambda c: (c[0], c[1]))
    labels = video.get("review", {}).get("labels", {})
    explanation = {"matching_labels": {k: labels.get(k) for k in ("setting", "intensity", "surface", "perspective")},
                   "strict_review": strict, "rotation_score": list(score),
                   "policy": "Fewest repeats in last 7 uploads, then category repetition, then lifetime reuse."}
    return video, audio, explanation

def curated_videos(root=ROOT):
    return read_json(root / "data" / "video_library.json", [])
