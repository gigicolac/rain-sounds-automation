"""Persistent upload ledger, isolated from source branches. Fail closed on uncertainty."""
import base64
import hashlib
import json
import os
from pathlib import Path
import requests

BRANCH = 'pipeline-history'
ROOT = Path(__file__).resolve().parents[1]


def fingerprint(assets):
    # Title/duration edits must not disguise reuse of the same source pair.
    pair = [str(assets['video']['pexels_id']), str(assets['audio']['freesound_id'])]
    return hashlib.sha256(json.dumps(pair).encode()).hexdigest()


class Ledger:
    def __init__(self):
        self.repo = os.environ.get('GITHUB_REPOSITORY')
        self.token = os.environ.get('GH_TOKEN')
        self.path = ROOT / 'run' / 'history.json'
        self.sha = None
        self.entries = {}
        if self.repo:
            if not self.token:
                raise RuntimeError('GH_TOKEN required to read upload history; refusing to assume it is empty.')
            self.base = f'https://api.github.com/repos/{self.repo}'
            ref = self.request('GET', f'/git/ref/heads/{BRANCH}')
            if ref.status_code == 404:
                return
            ref.raise_for_status()
            response = self.request('GET', f'/contents/uploads.json?ref={BRANCH}')
            if response.status_code == 404:
                return
            response.raise_for_status()
            data = response.json()
            self.sha = data['sha']
            self.entries = json.loads(base64.b64decode(data['content']))
        elif self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding='utf-8'))

    def request(self, method, path, **kwargs):
        return requests.request(method, self.base + path, headers={
            'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json'
        }, timeout=30, **kwargs)

    def save(self):
        text = json.dumps(self.entries, indent=2)
        if self.repo:
            ref = self.request('GET', f'/git/ref/heads/{BRANCH}')
            if ref.status_code == 404:
                created = self.request('POST', '/git/refs', json={
                    'ref': f'refs/heads/{BRANCH}', 'sha': os.environ['GITHUB_SHA']})
                created.raise_for_status()
            else:
                ref.raise_for_status()
            body = {'message': 'Record rain video upload state', 'branch': BRANCH,
                    'content': base64.b64encode(text.encode()).decode()}
            if self.sha:
                body['sha'] = self.sha
            response = self.request('PUT', '/contents/uploads.json', json=body)
            response.raise_for_status()  # Conflicts must stop publication, never overwrite another writer.
            self.sha = response.json()['content']['sha']
        self.path.parent.mkdir(exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(text, encoding='utf-8')
        temp.replace(self.path)

    def check_new(self, assets):
        key = fingerprint(assets)
        if key in self.entries:
            raise RuntimeError('This source video/audio pair is already reserved or uploaded. Use resume_video_id for an existing upload.')
        if any(e['assets']['date'] == assets['date'] for e in self.entries.values()):
            raise RuntimeError('An upload is already reserved for this date. Review history or resume it before starting another.')
        return key

    def reserve(self, assets):
        key = self.check_new(assets)
        self.entries[key] = {'state': 'reserved', 'assets': assets,
                             'run_id': os.environ.get('GITHUB_RUN_ID')}
        self.save()  # Must succeed before contacting YouTube upload endpoint.
        return key

    def find_video(self, video_id):
        for key, entry in self.entries.items():
            if entry.get('video_id') == video_id:
                return key, entry
        raise RuntimeError('Video is not in upload history; refusing to resume an unrelated upload.')
