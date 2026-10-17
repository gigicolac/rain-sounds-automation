"""Reproducible synthetic rain and licensed-recording blends for listening review.

Candidates remain outside the publishing pool until explicitly reviewed.
No music, voices or thunder recordings are added; generated texture is sound
design, not a claim to be a new field recording.
"""
import argparse
from array import array
import json
import math
from pathlib import Path
import random
import subprocess
import wave
from asset_library import ROOT, read_json, write_json
from channel_profile import digest
from media_quality import ffmpeg, probe, audio_report, prepare_audio

PROFILES = [
    ('synthetic-soft', None, 1800, 0.65, 0.35),
    ('synthetic-full', None, 6500, 0.85, 0.65),
    ('blend-muted', '695619', 1400, 0.35, 0.15),
    ('blend-broad', '651189', 6500, 0.45, 0.25),
    ('blend-soft', '651189', 2200, 0.25, 0.2),
    ('blend-distant', '695619', 3000, 0.5, 0.1),
]


def droplets(path, duration, seed, rate=12):
    """Seeded short, damped noise bursts at independent stereo positions."""
    sample_rate = 48000
    samples = array('f', [0.0]) * (int(duration * sample_rate) * 2)
    rng = random.Random(seed)
    for _ in range(int(duration * rate)):
        start = rng.randrange(int((duration-.04) * sample_rate))
        length = rng.randrange(240, 1400)
        amplitude = rng.uniform(.02, .11)
        pan = rng.uniform(.15, .85)
        frequency = rng.uniform(900, 7000)
        for offset in range(length):
            envelope = math.exp(-7*offset/length) * min(1, offset/24)
            value = amplitude * envelope * (rng.uniform(-1, 1)*.7 + .3*math.sin(2*math.pi*frequency*offset/sample_rate))
            position = (start+offset)*2
            samples[position] += value * (1-pan)
            samples[position+1] += value * pan
    pcm = array('h', (max(-32767, min(32767, int(v*32767))) for v in samples))
    with wave.open(str(path), 'wb') as target:
        target.setnchannels(2); target.setsampwidth(2); target.setframerate(sample_rate)
        target.writeframes(pcm.tobytes())


def create(output, audio_root, duration=90, seed=20261017):
    output, audio_root = Path(output), Path(audio_root)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output directory; existing candidates are preserved')
    if not 30 <= duration <= 300:
        raise ValueError('Review candidates must be 30–300 seconds')
    output.mkdir(parents=True, exist_ok=True)
    metadata = read_json(audio_root / 'metadata.json', [])
    records = []
    prepared = {}
    for source_id in sorted({p[1] for p in PROFILES if p[1]}):
        source = next(t for t in metadata if str(t['id']) == source_id)
        if source.get('review', {}).get('approved') is not True or source.get('review', {}).get('status') == 'rejected':
            raise ValueError('Blend requires an approved source')
        if source.get('license', '').rstrip('/') not in {
                'http://creativecommons.org/publicdomain/zero/1.0',
                'https://creativecommons.org/publicdomain/zero/1.0'}:
            raise ValueError('Blend requires a recorded Creative Commons Zero licence')
        folder = output / ('source-' + source_id); folder.mkdir()
        prepared[source_id] = folder / 'crossfaded.wav'
        prepare_audio(audio_root / source['filename'], prepared[source_id], duration)
    drops = output / 'procedural-droplets.wav'
    droplets(drops, duration, seed)
    for index, (name, source_id, cutoff, texture, detail) in enumerate(PROFILES):
        print('Rendering ' + name, flush=True)
        folder = output / name; folder.mkdir()
        destination = folder / (name + '.flac')
        command = [ffmpeg(), '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                   f'anoisesrc=color=pink:sample_rate=48000:duration={duration}:seed={seed+index}',
                   '-i', str(drops)]
        components = [{'kind': 'procedural', 'seed': seed+index,
                       'method': 'filtered pink noise and seeded damped droplets', 'droplets_seed': seed}]
        graph = [f'[0:a]highpass=f=100,lowpass=f={cutoff},volume={texture},'
                 'aformat=sample_rates=48000:channel_layouts=stereo[texture]',
                 f'[1:a]volume={detail}[drops]']
        inputs = '[texture][drops]'
        if source_id:
            source = next(t for t in metadata if str(t['id']) == source_id)
            if source.get('review', {}).get('approved') is not True or source.get('review', {}).get('status') == 'rejected':
                raise ValueError('Blend requires an approved source')
            source_path = audio_root / source['filename']
            command += ['-i', str(prepared[source_id])]
            graph.append(f'[2:a]highpass=f=80,lowpass=f={cutoff},volume=0.85,'
                         'aformat=sample_rates=48000:channel_layouts=stereo[recording]')
            inputs += '[recording]'
            components.append({'kind': 'licensed_recording', 'id': source_id,
                'source_url': source['freesound_url'], 'license': source['license'],
                'source_sha256': digest(source_path), 'original_title': source['title']})
        graph.append(f'{inputs}amix=inputs={3 if source_id else 2}:duration=first:normalize=0,'
                     f'atrim=duration={duration},loudnorm=I=-20:TP=-2:LRA=7,'
                     f'afade=t=in:d=1,afade=t=out:st={duration-1}:d=1[out]')
        subprocess.run(command + ['-filter_complex', ';'.join(graph), '-map', '[out]',
                       '-t', str(duration), '-ar', '48000', '-c:a', 'flac', str(destination)], check=True)
        report = audio_report(destination)
        info = probe(destination)
        report['duration_seconds'] = float(info['format']['duration'])
        report['technical_pass'] = (abs(report['duration_seconds']-duration)<.1 and
                                    report['peak_db'] is not None and report['peak_db'] <= -.1)
        write_json(folder / 'quality.json', report)
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(destination),
                        '-c:a', 'libmp3lame', '-b:a', '192k', str(folder / 'listen.mp3')], check=True)
        records.append({'id': 'custom-audio:' + name, 'title': name.replace('-', ' ').title(),
                        'path': str(destination.relative_to(output)), 'sha256': digest(destination),
                        'duration': duration, 'components': components,
                        'review': {'approved': False, 'status': 'pending', 'labels': {},
                                   'notes': 'Listening and repeat-boundary review required; not in the public pool'},
                        'technical_pass': report['technical_pass']})
    write_json(output / 'candidates.json', records)
    print(f'{len(records)} candidates saved for listening review: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audio-root', type=Path, default=ROOT / 'audio')
    parser.add_argument('--duration', type=int, default=90)
    parser.add_argument('--seed', type=int, default=20261017)
    args = parser.parse_args()
    create(args.output, args.audio_root, args.duration, args.seed)
