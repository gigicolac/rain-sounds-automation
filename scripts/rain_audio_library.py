"""Local rain asset creation/review library. No publishing or automatic approvals."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from functools import wraps
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from asset_library import ROOT, read_json, write_json
from channel_profile import digest

DEFAULT_LIBRARY = ROOT / 'run/rain-audio-library'
STATES = ('pending', 'approved', 'pass', 'rejected')


@contextmanager
def registry_lock(root):
    """Serialize browser and command-line review writes across processes."""
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    with (root / '.review.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        deadline = time.monotonic()+10
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError('Another library update is in progress; retry shortly')
                time.sleep(.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def transaction(function):
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        with registry_lock(root):
            return function(root, *args, **kwargs)
    return wrapped


def safe(root, relative):
    path = (Path(root) / str(relative).replace('\\', '/')).resolve()
    path.relative_to(Path(root).resolve())
    return path


def read_library(root):
    return read_json(Path(root) / 'library.json', {'version': 1, 'assets': {}})


def save_library(root, library):
    write_json(Path(root) / 'library.json', library)


def checked_asset(root, asset):
    master = safe(root, asset['master'])
    listen = safe(root, asset['listen'])
    if not master.is_file() or not listen.is_file() or digest(master) != asset['sha256']:
        raise ValueError('Missing or changed reviewed media: ' + asset['id'])
    if digest(listen) != asset['listen_sha256']:
        raise ValueError('Listening copy changed: ' + asset['id'])
    if asset.get('loop') and digest(safe(root, asset['loop'])) != asset['loop_sha256']:
        raise ValueError('Loop preview changed: ' + asset['id'])
    quality = read_json(safe(root, asset['quality']), {})
    if not quality.get('technical_pass'):
        raise ValueError('Technical checks did not pass: ' + asset['id'])
    return master


@transaction
def import_batch(root, batch, decisions=None):
    root, batch = Path(root), Path(batch)
    records = read_json(batch / 'candidates.json', [])
    if not records:
        raise ValueError('Batch needs a non-empty candidates.json')
    library = read_library(root)
    decisions = decisions or {}
    for record in records:
        asset_id = record['id']
        slug = asset_id.split(':')[-1]
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,100}', slug):
            raise ValueError('Invalid asset identifier')
        if asset_id in library['assets']:
            if library['assets'][asset_id]['sha256'] != record['sha256']:
                raise ValueError('Identifier already has different media; create a new revision: ' + asset_id)
            checked_asset(root, library['assets'][asset_id])
            continue  # Never overwrite local review decisions during re-import.
        duplicate = next((a['id'] for a in library['assets'].values() if a['sha256'] == record['sha256']), None)
        if duplicate:
            raise ValueError('Audio content already exists as ' + duplicate + '; change seed or recipe')
        master = safe(batch, record['path'])
        if not master.is_file() or digest(master) != record['sha256'] or not record.get('technical_pass'):
            raise ValueError('Unverified candidate: ' + asset_id)
        listen = master.parent / 'listen.mp3'
        quality = read_json(master.parent / 'quality.json', {})
        if not listen.is_file() or not quality.get('technical_pass'):
            raise ValueError('Missing listening copy or technical report: ' + asset_id)
        folder = root / 'assets' / slug
        if folder.exists():
            raise ValueError('Unregistered package already exists; preserve and resolve: ' + str(folder))
        folder.mkdir(parents=True)
        shutil.copy2(master, folder / 'master.flac')
        shutil.copy2(listen, folder / 'listen.mp3')
        write_json(folder / 'quality.json', quality)
        write_json(folder / 'candidate.json', record)
        from media_quality import ffmpeg
        tail_start = max(0, record['duration']-6)
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-ss', str(tail_start), '-i', str(master),
            '-i', str(master), '-filter_complex',
            '[0:a]atrim=duration=6,asetpts=PTS-STARTPTS[t];[1:a]atrim=duration=6,asetpts=PTS-STARTPTS[h];'
            '[t][h]acrossfade=d=2:c1=tri:c2=tri[out]', '-map', '[out]',
            '-c:a', 'libmp3lame', '-b:a', '192k', str(folder / 'loop.mp3')], check=True)
        intent = record.get('intent', {'heaviness': record.get('design_intensity', 'unknown'),
                                       'environment': 'unlabelled', 'vibes': []})
        asset = {'id': asset_id, 'title': record['title'], 'status': 'pending',
            'master': f'assets/{slug}/master.flac', 'listen': f'assets/{slug}/listen.mp3',
            'quality': f'assets/{slug}/quality.json', 'candidate': f'assets/{slug}/candidate.json',
            'sha256': record['sha256'], 'listen_sha256': digest(listen), 'duration': record['duration'],
            'loop': f'assets/{slug}/loop.mp3', 'loop_sha256': digest(folder / 'loop.mp3'),
            'intent': intent, 'target_lufs': record.get('target_lufs', -20),
            'review': {'approved': False, 'status': 'pending', 'notes': '', 'labels': {}, 'quality': {}},
            'decisions': []}
        library['assets'][asset_id] = asset
        decision = decisions.get(asset_id)
        if decision and decision['sha256'] == asset['sha256']:
            asset['status'] = decision['status']
            asset['review'].update(approved=decision['status'] == 'approved', status=decision['status'],
                                   notes=decision['notes'], reviewed_at=decision['reviewed_at'],
                                   acceptance_scope='User sound approval; full playback and loop checks not inferred')
            asset['decisions'].append(decision)
        save_library(root, library)
    return library


@transaction
def review(root, asset_id, status, notes, listened=False, full_playback=False, loop_checked=False,
           labels=None):
    if status not in STATES or not notes.strip():
        raise ValueError('Choose a valid status and supply review notes')
    library = read_library(root)
    if asset_id not in library['assets']:
        raise ValueError('Unknown audio asset')
    asset = library['assets'][asset_id]
    if status in {'approved', 'pass'}:
        if not listened:
            raise ValueError('Listen to the candidate before approving or passing it')
        checked_asset(root, asset)
    timestamp = datetime.now(timezone.utc).isoformat()
    decision = {'status': status, 'notes': notes.strip(), 'reviewed_at': timestamp,
                'sha256': asset['sha256'], 'listened': listened,
                'full_playback': full_playback, 'loop_checked': loop_checked}
    asset['status'] = status
    asset['review'] = {'approved': status == 'approved', 'status': status, 'notes': notes.strip(),
        'reviewed_at': timestamp, 'labels': asset['review'].get('labels', {}) if labels is None else labels,
        'quality': {'full_playback': full_playback, 'loop_checked': loop_checked}}
    asset['decisions'].append(decision)
    save_library(root, library)
    return asset


def pool(root, status='approved', heaviness='', environment='', vibe='', used=()):
    if status not in STATES:
        raise ValueError('Unknown review category')
    matches = []
    for asset in read_library(root)['assets'].values():
        intent = asset['intent']
        if (asset['status'] != status or asset['id'] in used or
                heaviness and intent.get('heaviness') != heaviness or
                environment and intent.get('environment') != environment or
                vibe and vibe not in intent.get('vibes', [])):
            continue
        checked_asset(root, asset)
        matches.append(asset)
    return matches


def source_for(preset, audio_root):
    if not preset.get('source_ids') and not preset.get('required_source_setting'):
        raise ValueError('Preset needs explicit source identifiers or a reviewed environment')
    metadata = read_json(Path(audio_root) / 'metadata.json', [])
    choices = []
    for source in metadata:
        key = str(source['id'])
        if key in preset.get('excluded_source_ids', []):
            continue
        if preset.get('source_ids') and key not in preset['source_ids']:
            continue
        review_info = source.get('review', {})
        if preset.get('required_source_setting') and review_info.get('labels', {}).get('setting') != preset['required_source_setting']:
            continue
        if review_info.get('approved') is not True or review_info.get('status') == 'rejected':
            continue
        if not safe(audio_root, source['filename']).is_file():
            continue
        if source.get('license', '').rstrip('/') not in {
                'http://creativecommons.org/publicdomain/zero/1.0', 'https://creativecommons.org/publicdomain/zero/1.0'}:
            continue
        choices.append(source)
    if not choices:
        raise ValueError('Needs a compatible reviewed source recording: ' + preset['id'])
    return sorted(choices, key=lambda s: str(s['id']))[0]


def generate(root, preset_ids, audio_root, duration=90, seed=123):
    from create_custom_audio import create
    presets = read_json(ROOT / 'data/rain_audio_presets.json', {})['presets']
    selected = [p for p in presets if p['id'] in preset_ids]
    if not preset_ids or {p['id'] for p in selected} != set(preset_ids):
        raise ValueError('Choose preset identifiers from the plan')
    results = []
    for preset in selected:
        try:
            source = source_for(preset, audio_root)
        except ValueError as exc:
            results.append({'preset': preset['id'], 'status': 'needs_source', 'reason': str(exc)})
            continue
        suffix = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        name = f"{preset['id']}-{seed}-{suffix}"
        folder = Path(root) / 'batches' / name
        profile = {k: preset[k] for k in ('rate', 'target', 'bed_db', 'lowpass', 'curve')}
        profile.update(name=name, source=str(source['id']), intensity=preset['heaviness'], highpass=450)
        create(folder, audio_root, duration, seed, profiles=[profile])
        records = read_json(folder / 'candidates.json', [])
        for record in records:
            record['title'] = preset['title']
            record['intent'] = {k: preset[k] for k in ('heaviness', 'environment', 'vibes')}
            record['recipe'] = {'preset': preset['id'], 'reference': 'custom-audio:v2-changing-shower',
                                'seed': seed, 'source_id': str(source['id']), 'profile': profile,
                                'notes': preset.get('notes', ''), 'source_labels': source.get('review', {}).get('labels', {})}
        write_json(folder / 'candidates.json', records)
        import_batch(root, folder)
        results.append({'preset': preset['id'], 'status': 'pending', 'id': records[0]['id']})
    write_json(Path(root) / 'last-generation.json', results)
    return results


@transaction
def export_ready(root, destination, ids=()):
    root, destination = Path(root), Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Export folder must be new or empty')
    assets = pool(root)
    if ids:
        assets = [a for a in assets if a['id'] in ids]
        if {a['id'] for a in assets} != set(ids):
            raise ValueError('Only approved assets can be exported')
    ready = [a for a in assets if all(a['review']['quality'].get(k) is True
                                     for k in ('full_playback', 'loop_checked'))]
    if ids and len(ready) != len(assets):
        raise ValueError('Full playback and loop review still required')
    if not ready:
        raise ValueError('No approved assets have full playback and loop checks')
    records = []
    destination.mkdir(parents=True, exist_ok=True)
    for asset in ready:
        master = checked_asset(root, asset)
        folder = destination / master.parent.name; folder.mkdir()
        shutil.copy2(master, folder / 'master.flac')
        shutil.copy2(safe(root, asset['listen']), folder / 'listen.mp3')
        shutil.copy2(safe(root, asset['quality']), folder / 'quality.json')
        record = read_json(safe(root, asset['candidate']), {})
        record.update(path=f'{folder.name}/master.flac', review=asset['review'], sha256=asset['sha256'])
        records.append(record)
    write_json(destination / 'candidates.json', records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=DEFAULT_LIBRARY)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    imp = sub.add_parser('import'); imp.add_argument('batch', type=Path)
    gen = sub.add_parser('generate'); gen.add_argument('presets', nargs='+')
    gen.add_argument('--audio-root', type=Path, default=ROOT / 'audio')
    gen.add_argument('--duration', type=int, default=90); gen.add_argument('--seed', type=int, default=123)
    rev = sub.add_parser('review'); rev.add_argument('id'); rev.add_argument('status', choices=STATES)
    rev.add_argument('--notes', required=True); rev.add_argument('--listened', action='store_true')
    rev.add_argument('--full-playback', action='store_true'); rev.add_argument('--loop-checked', action='store_true')
    listing = sub.add_parser('pool'); listing.add_argument('--status', choices=STATES, default='approved')
    listing.add_argument('--heaviness', default=''); listing.add_argument('--environment', default='')
    listing.add_argument('--vibe', default=''); listing.add_argument('--used', nargs='*', default=[])
    exp = sub.add_parser('export-ready'); exp.add_argument('destination', type=Path); exp.add_argument('--ids', nargs='*', default=[])
    serve = sub.add_parser('serve'); serve.add_argument('--port', type=int, default=0)
    serve.add_argument('--audio-root', type=Path, default=ROOT / 'audio')
    args = parser.parse_args()
    if args.command == 'init':
        with registry_lock(args.library):
            save_library(args.library, read_library(args.library))
        print(args.library)
    elif args.command == 'import':
        decisions = read_json(ROOT / 'data/rain_audio_review_decisions.json', {})
        print(json.dumps(import_batch(args.library, args.batch, decisions), indent=2))
    elif args.command == 'generate':
        print(json.dumps(generate(args.library, args.presets, args.audio_root, args.duration, args.seed), indent=2))
    elif args.command == 'review':
        print(json.dumps(review(args.library, args.id, args.status, args.notes, args.listened,
                                args.full_playback, args.loop_checked), indent=2))
    elif args.command == 'pool':
        print(json.dumps(pool(args.library, args.status, args.heaviness, args.environment, args.vibe, args.used), indent=2))
    elif args.command == 'export-ready':
        print(json.dumps(export_ready(args.library, args.destination, args.ids), indent=2))
    else:
        from rain_audio_review import serve
        serve(args.library, args.port, args.audio_root)


if __name__ == '__main__':
    main()
