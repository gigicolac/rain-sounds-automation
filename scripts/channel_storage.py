"""Restore selected scenes from a locally available, checksum-verified asset bundle."""
import argparse
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
import requests
from asset_library import ROOT, read_json
from channel_profile import digest

ASSET_REPOSITORY = 'shmop/rain-sounds-assets'


def download(root=ROOT):
    config = read_json(root / 'data/channel_storage.json', {})
    url = config.get('asset_api_url', '')
    if config.get('repository') != ASSET_REPOSITORY or not re.fullmatch(
            r'https://api\.github\.com/repos/' + re.escape(ASSET_REPOSITORY) + r'/releases/assets/\d+', url):
        raise ValueError('Storage must use the confirmed private shmop/rain-sounds-assets repository')
    token = os.environ.get('CHANNEL_ASSET_TOKEN')
    if not token:
        raise ValueError('Add CHANNEL_ASSET_TOKEN to Actions secrets with Contents: read access to shmop/rain-sounds-assets')
    root.joinpath('run').mkdir(exist_ok=True)
    output = root / 'run/channel-assets.zip'
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream'}
    # Verify private storage; credentials are sent only to the confirmed GitHub repository.
    response = requests.get('https://api.github.com/repos/' + ASSET_REPOSITORY,
                            headers=dict(headers, Accept='application/vnd.github+json'), timeout=30)
    response.raise_for_status()
    if response.json().get('private') is not True:
        raise ValueError('Source asset repository must remain private')
    with requests.get(url, headers=headers, stream=True, timeout=(15, 120)) as response:
        response.raise_for_status()
        # requests strips Authorization on redirects to a different host.
        with output.open('wb') as target:
            for chunk in response.iter_content(1024 * 1024):
                target.write(chunk)
    restore(output, root)


def restore(bundle_path, root=ROOT):
    config = read_json(root / 'data/channel_storage.json', {})
    if digest(bundle_path) != config.get('bundle_sha256'):
        raise ValueError('Bundle checksum mismatch')
    manifest = read_json(root / 'data/channel_asset_manifest.json', [])
    expected = {item['path']: item for item in manifest}
    if not expected or len(expected) != len(manifest):
        raise ValueError('Missing or duplicate asset manifest')
    root.joinpath('run').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / 'run') as temp:
        staging = Path(temp)
        with zipfile.ZipFile(bundle_path) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError('Bundle contents differ from the asset manifest')
            for index, (name, item) in enumerate(expected.items()):
                destination = (root / name).resolve()
                destination.relative_to((root / 'scenes').resolve())
                info = bundle.getinfo(name)
                if info.file_size != item['bytes'] or info.is_dir():
                    raise ValueError('Unexpected asset size')
                staged = staging / str(index)
                with bundle.open(name) as source, staged.open('wb') as target:
                    shutil.copyfileobj(source, target)
                if digest(staged) != item['sha256']:
                    raise ValueError('Asset checksum mismatch: ' + name)
                if destination.exists() and digest(destination) != item['sha256']:
                    raise ValueError('Existing media differs; preserve and resolve manually: ' + name)
                item['_staged'] = staged
            # Validate all files before copying; never replace different existing media.
            for name, item in expected.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copy2(item['_staged'], destination)
    print(f'Restored {len(expected)} verified scenes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path, nargs='?')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    if args.download:
        download()
    elif args.file:
        restore(args.file)
    else:
        parser.error('Supply a local bundle file or --download')
