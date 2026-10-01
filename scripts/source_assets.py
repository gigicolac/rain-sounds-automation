"""Bounded Pixabay/Freesound sourcing into a private, provenance-backed candidate queue."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from asset_library import ROOT, read_json, write_json
from channel_storage import ASSET_REPOSITORY
from media_quality import probe, ffmpeg

CC0 = 'https://creativecommons.org/publicdomain/zero/1.0/'
PIXABAY_LICENSE = 'https://pixabay.com/service/license-summary/'
API = 'https://api.github.com/repos/' + ASSET_REPOSITORY
UPLOADS = 'https://uploads.github.com/repos/' + ASSET_REPOSITORY
MAX_BYTES = 80 * 1024 * 1024


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def allowed_url(url, domains):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and any(host == d or host.endswith('.' + d) for d in domains))


def video_candidate(hit):
    tags = str(hit.get('tags', '')).lower()
    if not ('rain' in tags and any(w in tags for w in ('anime', 'lofi', 'lo-fi'))
            and any(w in tags for w in ('cat', 'study', 'girl', 'room', 'window'))):
        return None
    if not 5 <= float(hit.get('duration', 0)) <= 180:
        return None
    files = [f for f in hit.get('videos', {}).values()
             if f.get('width', 0) >= 1920 and f.get('height', 0) >= 1080
             and 0 < f.get('size', 0) <= MAX_BYTES
             and allowed_url(f.get('url', ''), ['pixabay.com'])]
    if not files or not allowed_url(hit.get('pageURL', ''), ['pixabay.com']):
        return None
    chosen = min(files, key=lambda f: f['size'])
    return dict(kind='video', asset_id='pixabay:' + str(int(hit['id'])),
                source_url=hit['pageURL'], license_url=PIXABAY_LICENSE,
                creator=hit.get('user'), download_url=chosen['url'], extension='.mp4',
                discovery_tags=hit.get('tags'), provider_record=hit)


def audio_candidate(hit):
    license_url = str(hit.get('license', '')).replace('http://', 'https://')
    text = (str(hit.get('name', '')) + ' ' + ' '.join(hit.get('tags', []))).lower()
    excluded = ('thunder', 'storm', 'traffic', 'voice', 'speech', 'music', 'tent',
                'tin roof', 'metal roof', 'forest', 'leaves')
    url = hit.get('previews', {}).get('preview-hq-mp3', '')
    if (license_url != CC0 or not 45 <= float(hit.get('duration', 0)) <= 900
            or 'rain' not in text or any(word in text for word in excluded)
            or not allowed_url(url, ['freesound.org'])):
        return None
    return dict(kind='audio', asset_id='freesound:' + str(int(hit['id'])),
                source_url='https://freesound.org/s/' + str(int(hit['id'])) + '/',
                license_url=CC0, creator=hit.get('username'), download_url=url,
                extension='.mp3', download_kind='hq_mp3_preview',
                discovery_tags=hit.get('tags', []), provider_record=hit)


def cached_search(state, kind, query, page, key, now=None):
    now = time.time() if now is None else now
    cache_key = json.dumps([kind, query, page])
    cached = state.setdefault('search_cache', {}).get(cache_key)
    if cached and 0 <= now - cached['time'] < 86400:
        return cached['data']
    if kind == 'video':
        url = 'https://pixabay.com/api/videos/'
        params = dict(key=key, q=query, video_type='animation', safesearch='true',
                      min_width=1920, min_height=1080, order='latest', per_page=20, page=page)
        headers = {}
    else:
        url = 'https://freesound.org/apiv2/search/text/'
        params = dict(query=query, page=page, page_size=15, sort='created_desc',
                      filter='duration:[45 TO 900] AND license:"Creative Commons 0"',
                      fields='id,name,license,previews,tags,duration,username')
        headers = {'Authorization': 'Token ' + key}
    response = requests.get(url, params=params, headers=headers, timeout=(10, 30))
    # Never print request exceptions: the Pixabay request URL includes the secret key.
    response.raise_for_status()
    data = response.json()
    state['search_cache'][cache_key] = {'time': now, 'data': data}
    return data


def download(url, target, kind):
    domains = ['pixabay.com'] if kind == 'video' else ['freesound.org']
    current = url
    # Validate each redirect before following it. No provider credentials go to media hosts.
    for _ in range(5):
        if not allowed_url(current, domains):
            raise ValueError('Unapproved media download host')
        with requests.get(current, stream=True, allow_redirects=False,
                          timeout=(10, 30)) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                current = urljoin(current, response.headers['Location'])
                continue
            response.raise_for_status()
            if int(response.headers.get('Content-Length', 0)) > MAX_BYTES:
                raise ValueError('Source exceeds download size limit')
            size = 0
            with target.open('xb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('Source exceeds download size limit')
                    output.write(chunk)
            return
    raise ValueError('Too many media redirects')


def technical_check(path, kind):
    info = probe(path)
    duration = float(info['format']['duration'])
    stream = next(s for s in info['streams'] if s['codec_type'] == kind)
    if kind == 'video':
        if stream['width'] < 1920 or stream['height'] < 1080 or not 5 <= duration <= 180:
            raise ValueError('Video below required quality or outside duration limit')
    elif not 45 <= duration <= 900:
        raise ValueError('Audio outside duration limit')
    subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'passed': True, 'duration': duration,
            'width': stream.get('width'), 'height': stream.get('height'),
            'limitation': 'Decode and dimensions only; content/style/rights are not certified.'}


def baseline(root):
    known = set()
    for v in read_json(root / 'data/video_library.json', []):
        match = re.search(r'-(\d+)/?$', v.get('source_url', ''))
        if match:
            known.add('pixabay:' + match[1])
        known.add(v['asset_id'])
    known.update('freesound:' + str(a['id']) for a in read_json(root / 'audio/metadata.json', []))
    hashes = {a['media_sha256'] for a in read_json(
        root / 'data/asset_rights_evidence.json', {}).get('assets', []) if a.get('media_sha256')}
    # Include every local cached recording, not only the channel's accepted recordings.
    hashes.update(sha(p) for p in (root / 'audio').glob('*.mp3'))
    return known, hashes


def private_headers(token):
    return {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'}


def private_state(token):
    headers = private_headers(token)
    response = requests.get(API, headers=headers, timeout=30)
    response.raise_for_status()
    if response.json().get('private') is not True:
        raise ValueError('Source storage must be the confirmed private repository')
    response = requests.get(API + '/releases', headers=headers,
                            params={'per_page': 100}, timeout=30)
    response.raise_for_status()
    releases = response.json()
    releases = [r for r in releases if r['tag_name'].startswith('sourcing-') and not r['draft']]
    if not releases:
        return {'schema': 1, 'assets': [], 'cursors': {}, 'search_cache': {}}
    latest = max(releases, key=lambda r: r['created_at'])
    asset = next(a for a in latest['assets'] if a['name'] == 'sourcing-state.json')
    url = API + '/releases/assets/' + str(int(asset['id']))
    response = requests.get(url, headers=dict(headers, Accept='application/octet-stream'), timeout=60)
    response.raise_for_status()
    if asset.get('digest') and asset['digest'] != 'sha256:' + hashlib.sha256(response.content).hexdigest():
        raise ValueError('Private state checksum mismatch')
    state = response.json()
    if state.get('schema') != 1 or not isinstance(state.get('assets'), list):
        raise ValueError('Unsupported sourcing state')
    return state


def publish_batch(token, folder, run_id):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', run_id):
        raise ValueError('Invalid batch identifier')
    headers = private_headers(token)
    response = requests.post(API + '/releases', headers=headers, timeout=30,
                             json={'tag_name': 'sourcing-' + run_id, 'name': 'Sourcing batch ' + run_id,
                                   'draft': True, 'body': 'Candidate media and provenance; not publishing approval.'})
    response.raise_for_status()
    release_id = int(response.json()['id'])
    # Publish the checkpoint only after both files are stored successfully.
    for name in ('sourced-assets.zip', 'sourcing-state.json'):
        path = folder / name
        with path.open('rb') as payload:
            response = requests.post(UPLOADS + '/releases/' + str(release_id) + '/assets',
                                     params={'name': name}, data=payload,
                                     headers=dict(headers, **{'Content-Type': 'application/octet-stream'}),
                                     timeout=(15, 300))
        response.raise_for_status()
    response = requests.patch(API + '/releases/' + str(release_id), headers=headers,
                              json={'draft': False, 'make_latest': 'false'}, timeout=30)
    response.raise_for_status()


def source(root, folder, state, kinds, limit, keys):
    folder.mkdir(parents=True, exist_ok=True)
    known, hashes = baseline(root)
    known.update(a['asset_id'] for a in state['assets'])
    hashes.update(a['sha256'] for a in state['assets'])
    added = []
    failures = []
    search_failures = []
    deadline = time.monotonic() + 900
    for kind in kinds:
        config = read_json(root / ('data/video_discovery.json' if kind == 'video'
                                  else 'data/audio_discovery.json'), {})
        queries = config['illustrated'] if kind == 'video' else [q for group in config.values() for q in group]
        cursors = state.setdefault('cursors', {})
        cursor = cursors.get(kind, {'query': 0, 'pages': {}})
        # At most two searches per provider per run; rotate queries and pages.
        count = 0
        for _ in range(min(2, len(queries))):
            if time.monotonic() >= deadline:
                break
            query = queries[cursor['query'] % len(queries)]
            page = cursor['pages'].get(query, 1)
            try:
                data = cached_search(state, kind, query, page, keys[kind])
            except requests.RequestException as exc:
                search_failures.append({'provider': kind, 'error_type': type(exc).__name__})
                break
            hits = data.get('hits' if kind == 'video' else 'results', [])
            more = page * 20 < data.get('totalHits', 0) if kind == 'video' else bool(data.get('next'))
            cursor['pages'][query] = page + 1 if more else 1
            cursor['query'] += 1
            cursors[kind] = cursor
            for hit in hits:
                if time.monotonic() >= deadline:
                    break
                candidate = video_candidate(hit) if kind == 'video' else audio_candidate(hit)
                if not candidate or candidate['asset_id'] in known:
                    continue
                path = folder / (candidate['asset_id'].replace(':', '-') + candidate.pop('extension'))
                try:
                    download(candidate['download_url'], path, kind)
                    digest = sha(path)
                    if digest in hashes:
                        path.unlink()
                        continue
                    report = technical_check(path, kind)
                except (requests.RequestException, ValueError, subprocess.SubprocessError,
                        KeyError, StopIteration) as exc:
                    path.unlink(missing_ok=True)
                    failures.append({'asset_id': candidate['asset_id'], 'error_type': type(exc).__name__})
                    continue
                evidence = folder / (path.stem + '.source.json')
                write_json(evidence, {'captured_at_utc': stamp(), 'query': query,
                                     'source_url': candidate['source_url'],
                                     'license_url': candidate['license_url'],
                                     'provider_record': candidate.pop('provider_record'),
                                     'license_origin': 'Provider API; not independent rights clearance'})
                candidate.update(filename=path.name, sha256=digest, bytes=path.stat().st_size,
                                 evidence_file=evidence.name, evidence_sha256=sha(evidence),
                                 discovered_at_utc=stamp(), technical_check=report,
                                 status='candidate', batch_id=folder.name,
                                 content_verified=False, publication_approved=False)
                added.append(candidate); state['assets'].append(candidate)
                hashes.add(digest); known.add(candidate['asset_id']); count += 1
                if count >= limit:
                    break
            if count >= limit:
                # Keep the partially consumed result page for the next query rotation.
                cursor['pages'][query] = page
                break
    state['updated_at_utc'] = stamp()
    write_json(folder / 'sourcing-state.json', state)
    summary = {'new_videos': sum(a['kind'] == 'video' for a in added),
               'new_audio': sum(a['kind'] == 'audio' for a in added),
               'total_candidates': len(state['assets']), 'failed_downloads': failures,
               'failed_searches': search_failures,
               'publication_pool_changed': False,
               'limitations': 'Tags are discovery hints. Candidate count is not ready-upload capacity.'}
    write_json(folder / 'summary.json', summary)
    write_json(folder / 'batch.json', added)
    with zipfile.ZipFile(folder / 'sourced-assets.zip', 'w', zipfile.ZIP_STORED) as archive:
        for path in sorted(folder.iterdir()):
            if path.name != 'sourced-assets.zip':
                archive.write(path, path.name)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--providers', choices=['video', 'audio', 'both'], default='video')
    parser.add_argument('--limit', type=int, choices=range(1, 8), default=3)
    parser.add_argument('--store-private', action='store_true')
    args = parser.parse_args()
    kinds = ['video', 'audio'] if args.providers == 'both' else [args.providers]
    keys = {'video': os.environ.get('PIXABAY_API_KEY'), 'audio': os.environ.get('FREESOUND_API_KEY')}
    if any(not keys[kind] for kind in kinds):
        raise ValueError('Add the provider key(s): PIXABAY_API_KEY / FREESOUND_API_KEY')
    if 'audio' in kinds and os.environ.get('FREESOUND_COMMERCIAL_ACCESS_CONFIRMED') != 'true':
        raise ValueError('Confirm commercial Freesound API access before automated sourcing')
    run_id = os.environ.get('GITHUB_RUN_ID', datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    folder = ROOT / 'run/sourcing' / (run_id + '-' + attempt)
    if folder.exists():
        raise ValueError('Batch directory already exists; preserve previous files')
    token = os.environ.get('SOURCING_ASSET_TOKEN')
    if args.store_private:
        if not token:
            raise ValueError('SOURCING_ASSET_TOKEN needs Contents: read/write on the private asset repository')
        state = private_state(token)
    else:
        state = read_json(ROOT / 'run/sourcing-state.json',
                          {'schema': 1, 'assets': [], 'cursors': {}, 'search_cache': {}})
    summary = source(ROOT, folder, state, kinds, args.limit, keys)
    if args.store_private:
        publish_batch(token, folder, folder.name)
    else:
        write_json(ROOT / 'run/sourcing-state.json', state)
    print(json.dumps(summary))
    print('Saved candidate batch to private storage.' if args.store_private else str(folder))
    if summary['failed_searches']:
        raise RuntimeError('One or more provider searches failed; completed downloads were preserved')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Requests can contain API keys in URLs; do not print exception text/tracebacks.
        if isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        else:
            print('Sourcing failed: ' + type(exc).__name__ + '; no credentials logged.', file=sys.stderr)
        sys.exit(1)
