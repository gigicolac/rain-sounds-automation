"""Create the requested local review batch using the existing audio worktree.

No publishing, source approval, or production-catalog changes.
"""
import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-worktree', type=Path, required=True)
    args = parser.parse_args()
    dependency = args.audio_worktree.resolve()
    sys.path.insert(0, str(dependency / 'scripts'))
    from create_custom_audio import create
    from rain_audio_library import source_for, import_batch
    from asset_library import read_json, write_json
    plan = read_json(ROOT / 'data/three_week_asset_plan.json', {})
    presets = {p['id']: p for p in read_json(dependency / 'data/rain_audio_presets.json', {})['presets']}
    batch_root = ROOT / 'run' / plan['batch']
    library = batch_root / 'audio-library'
    manifest = read_json(batch_root / 'audio-manifest.json', {})
    for number, (slug, title, scene, preset_id) in enumerate(plan['scenes'], 1):
        if slug in manifest:
            continue
        preset = presets[preset_id]
        source = source_for(preset, dependency / 'audio')
        seed = 2026102300 + number
        rng = random.Random(seed)
        # Each version changes its slow density envelope, filter and balance,
        # rather than merely assigning another filename to the same waveform.
        curve = [round(max(.12, min(1, value * rng.uniform(.78, 1.18))), 3) for value in preset['curve']]
        profile = {key: preset[key] for key in ('rate', 'target', 'bed_db', 'lowpass')}
        profile.update(name='three-weeks-' + slug, source=str(source['id']),
                       intensity=preset['heaviness'], curve=curve,
                       highpass=500 if preset['heaviness'] == 'heavy' else 450)
        profile['lowpass'] = round(profile['lowpass'] * rng.uniform(.90, 1.04))
        profile['rate'] = max(4, round(profile['rate'] * rng.uniform(.75, 1.12)))
        profile['bed_db'] += round(rng.uniform(-1.5, 1), 1)
        folder = batch_root / 'audio-generation' / slug
        candidates = folder / 'candidates.json'
        if not candidates.exists():
            create(folder, dependency / 'audio', plan['duration_seconds'], seed, [profile])
        records = read_json(candidates, [])
        for record in records:
            record['title'] = f'Week {(number-1)//10+1} / {number:02d} - {title}'
            record['intent'] = {key: preset[key] for key in ('heaviness', 'environment', 'vibes')}
            record['recipe'] = {'preset': preset_id, 'seed': seed, 'profile': profile,
                                'reference': 'custom-audio:v2-changing-shower',
                                'notes': preset.get('notes', '')}
        write_json(candidates, records)
        import_batch(library, folder)
        manifest[slug] = {'week': (number-1)//10+1, 'id': records[0]['id'],
                          'sha256': records[0]['sha256'], 'status': 'pending',
                          'preset': preset_id, 'technical_pass': records[0]['technical_pass']}
        write_json(batch_root / 'audio-manifest.json', manifest)
        print(f'AUDIO COMPLETE {len(manifest)}/30 {slug}', flush=True)


if __name__ == '__main__':
    main()
