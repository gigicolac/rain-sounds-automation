"""Restore selected scenes from a locally available, checksum-verified asset bundle."""
import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from asset_library import ROOT, read_json
from channel_profile import digest


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
    parser.add_argument('file', type=Path)
    restore(parser.parse_args().file)
