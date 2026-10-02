"""User-selected channel pool, source records and automatic publication checks."""
import hashlib
import re
from asset_library import read_json, identity


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def source_complete(video, audio):
    return all((video.get('source_url'), video.get('license_url'),
                audio.get('freesound_url'), audio.get('license')))


def choose(root, entries, rng, mode, video_id='', audio_id=''):
    profile = read_json(root / 'data/channel_profile.json', {})
    videos = [v for v in read_json(root / 'data/video_library.json', [])
              if v['asset_id'] in profile.get('video_ids', []) and (not video_id or v['asset_id'] == video_id)]
    audios = [a for a in read_json(root / 'audio/metadata.json', [])
              if str(a['id']) in profile.get('audio_ids', []) and (not audio_id or str(a['id']) == audio_id)]
    used, counts = set(), {}
    recent = sorted(entries.values(), key=lambda e: e['assets']['date'], reverse=True)[:7]
    recent_ids = {identity(e['assets']['video'], 'video') for e in recent}
    for entry in entries.values():
        v, a = entry['assets']['video'], entry['assets']['audio']
        used.add((identity(v, 'video'), identity(a, 'audio')))
        counts[identity(v, 'video')] = counts.get(identity(v, 'video'), 0) + 1
    pairs = []
    for video in videos:
        for audio in audios:
            if any(x.get('review', {}).get('status') == 'rejected' for x in (video, audio)):
                continue
            relative = video.get('local_path')
            if not relative:
                continue
            path = (root / relative).resolve()
            path.relative_to(root.resolve())
            if not path.is_file() or not (root / 'audio' / audio['filename']).is_file():
                continue
            if mode == 'publish' and not source_complete(video, audio):
                continue
            vid = identity(video, 'video')
            if (vid, identity(audio, 'audio')) in used:
                continue
            pairs.append((int(vid in recent_ids), counts.get(vid, 0), rng.random(), video, audio))
    if not pairs:
        raise RuntimeError('No unused channel pair with available files and required source records. Check storage, source links and history; no unrelated fallback is used.')
    # Reconstruct the current scene cycle from the persistent ledger. Reservations
    # count too: an uncertain upload must not make its scene look unused.
    available_ids = {identity(p[3], 'video') for p in pairs}
    cycle_used = set()
    for entry in sorted(entries.values(), key=lambda e: e['assets']['date']):
        vid = identity(entry['assets']['video'], 'video')
        if vid in available_ids:
            cycle_used.add(vid)
            if cycle_used == available_ids:
                cycle_used.clear()
    pairs = [p for p in pairs if identity(p[3], 'video') not in cycle_used]
    _, _, _, video, audio = min(pairs, key=lambda p: p[:3])
    return video, audio


def title_allowed(title):
    # No categorical event-absence, intensity or environment claims from the profile.
    return not re.search(r'thunder|traffic|pure rain|gentle|heavy|forest|tent|roof|voices|music', title, re.I)


def publication_ready(assets, root):
    if assets.get('selection_explanation', {}).get('policy') != 'channel_profile':
        return assets.get('review_approved') is True
    profile = read_json(root / 'data/channel_profile.json', {})
    video, audio = assets['video'], assets['audio']
    if video.get('asset_id') not in profile.get('video_ids', []) or str(audio.get('freesound_id')) not in profile.get('audio_ids', []):
        return False
    if not source_complete(video, audio):
        return False
    report = read_json(root / 'run/channel-quality.json', {})
    output = root / 'run/output.mp4'
    return bool(report.get('passed') is True and output.is_file()
                and report.get('video_id') == video.get('asset_id')
                and report.get('audio_id') == str(audio.get('freesound_id'))
                and report.get('output_sha256') == digest(output))
