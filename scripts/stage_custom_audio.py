"""Stage explicitly reviewed audio candidates for the channel media bundle.

First record approved=true, status=approved, dated review notes and labels in
the selected candidate's review object after full listening and loop review.
This command never grants review approval itself. Upload the resulting bundle
to private storage and update channel_storage.json before deploying the changes.
"""
import argparse
from pathlib import Path
import shutil
import zipfile
from asset_library import ROOT, read_json, write_json
from channel_profile import digest


def catalogue_components(components):
    """Keep seed/recipe provenance; full event schedules remain in library packages."""
    result = []
    for component in components:
        item = {key: value for key, value in component.items() if key != 'event_times_seconds'}
        if 'event_times_seconds' in component:
            item['event_count'] = len(component['event_times_seconds'])
        result.append(item)
    return result


def stage(candidates, ids, root=ROOT):
    candidates = Path(candidates).resolve()
    records = read_json(candidates / 'candidates.json', [])
    selected = [r for r in records if r['id'] in ids]
    if not ids or {r['id'] for r in selected} != set(ids):
        raise ValueError('Supply exact candidate identifiers from candidates.json')
    staged = []
    for record in selected:
        target_lufs = record.get('target_lufs', -20)
        if not isinstance(target_lufs, (int, float)) or not -40 <= target_lufs <= -20:
            raise ValueError('Candidate loudness target must be between -40 and -20 LUFS')
        review = record.get('review', {})
        from content_policy import approved_review
        if not approved_review(review):
            raise ValueError('Full listening and loop approval with dated notes required: ' + record['id'])
        source = (candidates / record['path']).resolve(); source.relative_to(candidates)
        if not record.get('technical_pass') or digest(source) != record['sha256']:
            raise ValueError('Candidate changed or did not pass technical checks')
        filename = 'custom/' + record['id'].split(':')[-1] + '.flac'
        destination = (root / 'audio' / filename).resolve()
        destination.relative_to((root / 'audio/custom').resolve())
        if destination.exists() and digest(destination) != record['sha256']:
            raise ValueError('Existing audio differs; preserve and resolve manually')
        staged.append((source, destination, {'id': record['id'], 'asset_id': record['id'],
            'filename': filename, 'title': record['title'], 'duration': record['duration'],
            'source_url': record.get('generator_source_url') or 'https://github.com/gigicolac/rain-sounds-automation/blob/main/scripts/create_custom_audio.py',
            **{k: record[k] for k in ('generator_sha256', 'generator_source_url') if k in record},
            'license': ('Original procedural sound design; no recording components'
                        if all(c.get('kind') == 'procedural' for c in record['components'])
                        else 'Original procedural sound design; licensed recording components are Creative Commons Zero (see component records)'),
            'components': catalogue_components(record['components']), 'sha256': record['sha256'], 'review': review,
            'target_lufs': target_lufs}))
    # Check every existing manifest item before changing the catalogue or profile.
    manifest = read_json(root / 'data/channel_asset_manifest.json', [])
    for item in manifest:
        source = (root / item['path']).resolve(); source.relative_to(root.resolve())
        if digest(source) != item['sha256']:
            raise ValueError('Existing bundle source changed: ' + item['path'])
    metadata = read_json(root / 'audio/metadata.json', [])
    existing = {r['id']: r for r in metadata}
    for source, destination, record in staged:
        if record['id'] in existing and existing[record['id']].get('sha256') != record['sha256']:
            raise ValueError('Existing custom audio identifier has different content')
    for source, destination, record in staged:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        existing[record['id']] = record
        relative = destination.relative_to(root.resolve()).as_posix()
        manifest = [m for m in manifest if m['path'] != relative]
        manifest.append({'path': relative, 'sha256': record['sha256'], 'bytes': destination.stat().st_size})
    bundle = root / 'run/reviewed-channel-assets.zip'; bundle.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_STORED) as archive:
        for item in manifest:
            archive.write(root / item['path'], item['path'])
    write_json(root / 'audio/metadata.json', list(existing.values()))
    write_json(root / 'data/channel_asset_manifest.json', manifest)
    profile = read_json(root / 'data/channel_profile.json', {})
    profile['audio_ids'] = sorted(set(profile['audio_ids']) | set(ids))
    write_json(root / 'data/channel_profile.json', profile)
    print('Staged reviewed audio. Upload the new private bundle and update storage configuration before deployment: ' + str(bundle))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidates', type=Path)
    parser.add_argument('ids', nargs='+')
    args = parser.parse_args()
    stage(args.candidates, args.ids)
