"""Export only the exact approved scene previews into the existing channel pipeline."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path
from asset_library import ROOT, read_json, write_json
from channel_profile import digest
from media_quality import probe


def package(library, root=ROOT, tag='custom-scenes-2026-10-17'):
    library = Path(library).resolve()
    registry = read_json(library / 'run/image-scene-library.json', {})
    if not registry:
        raise ValueError('Missing reviewed scene registry')
    records = []
    manifest = read_json(root / 'data/channel_asset_manifest.json', [])
    for item in manifest:
        source = (root / item['path']).resolve()
        source.relative_to(root.resolve())
        if digest(source) != item['sha256']:
            raise ValueError('Existing bundle source changed: ' + item['path'])
    root.joinpath('run').mkdir(exist_ok=True)
    bundle_path = root / 'run/custom-channel-assets.zip'
    with zipfile.ZipFile(bundle_path, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for item in manifest:
            bundle.write(root / item['path'], item['path'])
        for scene_id, entry in registry.items():
            if entry.get('status') != 'approve' or entry.get('package_checked') is not True:
                continue
            folder = (library / entry['package']).resolve()
            folder.relative_to(library)
            spec = read_json(folder / 'package.json', {})
            preview = spec.get('approved_preview') or spec.get('preview')
            expected = spec.get('approved_preview_sha256') or spec.get('preview_sha256')
            if not preview or not expected:
                raise ValueError(f'{scene_id}: approved preview and checksum required')
            source = (folder / preview).resolve()
            source.relative_to(folder)
            master = (folder / spec.get('master', 'master.png')).resolve()
            master.relative_to(folder)
            if digest(source) != expected or digest(master) != spec.get('master_sha256'):
                raise ValueError(f'{scene_id}: reviewed media changed')
            info = probe(source)
            stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
            if stream['width'] < 1920 or stream['height'] < 1080 or float(info['format']['duration']) < 5:
                raise ValueError(f'{scene_id}: preview does not meet channel requirements')
            relative = f'scenes/custom-{scene_id}.mp4'
            target = root / relative
            target.parent.mkdir(exist_ok=True)
            if target.exists() and digest(target) != expected:
                raise ValueError(f'Preserve and resolve existing changed media: {relative}')
            if not target.exists():
                shutil.copy2(source, target)
            previous = next((item for item in manifest if item['path'] == relative), None)
            if previous and previous['sha256'] != expected:
                raise ValueError('Existing manifest differs: ' + relative)
            if not previous:
                bundle.write(source, relative)
                manifest.append({'path': relative, 'sha256': expected, 'bytes': source.stat().st_size})
            records.append({'asset_id': f'custom:{scene_id}', 'local_path': relative,
                'source_url': f'https://github.com/shmop/rain-sounds-assets/releases/tag/{tag}',
                'license_url': 'https://openai.com/policies/terms-of-use/',
                'source_record_origin': 'User-created image_gen scene and exact user-approved animation preview',
                'generator': spec.get('generator'), 'sha256': expected,
                'width': stream['width'], 'height': stream['height'], 'duration': float(info['format']['duration']),
                'thumbnail_text_side': 'left' if scene_id == '04-boy-library' else 'right',
                'review': {'approved': True, 'status': 'approved', 'labels': {},
                           'notes': entry['notes'], 'approval_scope': 'master and exact animation preview; content labels remain unknown'},
                'custom_scene': {'scene_id': scene_id, 'preview': preview, 'master_sha256': spec['master_sha256']}})
    if not records:
        raise ValueError('No approved checked custom scenes')
    catalogue = read_json(root / 'data/video_library.json', [])
    ids = {r['asset_id'] for r in records}
    catalogue = [r for r in catalogue if r['asset_id'] not in ids] + records
    write_json(root / 'data/video_library.json', catalogue)
    profile = read_json(root / 'data/channel_profile.json', {})
    profile.update(name='Custom illustrated rain scenes', video_ids=sorted(ids),
                   visual_direction='User-approved custom animated scenes; original scene pool retained in the catalogue for recovery')
    write_json(root / 'data/channel_profile.json', profile)
    write_json(root / 'data/channel_asset_manifest.json', manifest)
    write_json(root / 'run/custom-scene-provenance.json', records)
    print(json.dumps({'scenes': len(records), 'bundle': str(bundle_path), 'sha256': digest(bundle_path)}))
    return bundle_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--tag', default='custom-scenes-2026-10-17')
    args = parser.parse_args()
    package(args.library, tag=args.tag)
