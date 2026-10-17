"""Reproducible synthetic rain and licensed-recording blends for listening review.

Candidates remain outside the publishing pool until explicitly reviewed.
Use rain_audio_library.py for normal asset creation. This lower-level tool also
retains the earlier six experimental profiles for reproducible comparisons.
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
    dict(name='v2-sparse-drizzle', source=None, rate=5, target=-30, bed_db=-60, intensity='light', curve=[.3,.55,.25,.7,.35]),
    dict(name='v2-light-shower', source=None, rate=22, target=-27, bed_db=-60, intensity='light', curve=[.45,.8,.35,.65,.4]),
    dict(name='v2-light-blend', source='695619', rate=12, target=-29, bed_db=-20, intensity='light', curve=[.3,.6,.25,.7,.4]),
    dict(name='v2-changing-shower', source='695619', rate=28, target=-26, bed_db=-16, intensity='light-to-moderate', curve=[.2,.45,.9,.4,.25]),
    dict(name='v2-building-rain', source='651189', rate=55, target=-24, bed_db=-13, intensity='light-to-moderate', curve=[.15,.3,.65,1,.4]),
    dict(name='v2-moderate-rain', source='651189', rate=80, target=-22, bed_db=-10, intensity='moderate', curve=[.5,.8,.4,.9,.55]),
]


def density_at(time, duration, curve):
    position = min(max(time / duration, 0), 1) * (len(curve)-1)
    index = min(int(position), len(curve)-2)
    blend = position-index
    blend = blend*blend*(3-2*blend)
    return curve[index]*(1-blend)+curve[index+1]*blend


def density_expression(duration, curve):
    """The same slow smooth curve for the recording bed and droplet density."""
    span = duration/(len(curve)-1)
    expression = str(curve[-1])
    for index in reversed(range(len(curve)-1)):
        x = f'((t-{index*span})/{span})'
        smooth = f'({x}*{x}*(3-2*{x}))'
        value = f'({curve[index]}+({curve[index+1]-curve[index]})*{smooth})'
        expression = f'if(lt(t,{(index+1)*span}),{value},{expression})'
    return f'if(isnan(t),{curve[0]},{expression})'


def droplets(path, duration, seed, rate=12, curve=None):
    """Seeded stereo rain transients with changing density; no continuous noise bed."""
    sample_rate = 48000
    samples = array('f', [0.0]) * (int(duration * sample_rate) * 2)
    rng = random.Random(seed)
    curve = curve or [.45,.8,.3,.9,.5]
    events = []
    for _ in range(int(duration * rate)):
        time = rng.uniform(0, max(0, duration-.04))
        density = density_at(time, duration, curve)
        if rng.random() > density:
            continue
        start = int(time * sample_rate)
        length = min(rng.randrange(180, 1100), int(duration*sample_rate)-start)
        amplitude = rng.uniform(.035, .12) * (.65+.35*density)
        pan = rng.uniform(.1, .9)
        events.append(time)
        previous = 0.0
        for offset in range(length):
            envelope = math.exp(-6*offset/max(1,length)) * min(1, offset/32)
            # Smooth individual noise bursts; remove the pitched sine in v1.
            previous = .45*previous + .55*rng.uniform(-1,1)
            value = amplitude * envelope * previous
            position = (start+offset)*2
            samples[position] += value * (1-pan)
            samples[position+1] += value * pan
    pcm = array('h', (max(-32767, min(32767, int(v*32767))) for v in samples))
    with wave.open(str(path), 'wb') as target:
        target.setnchannels(2); target.setsampwidth(2); target.setframerate(sample_rate)
        target.writeframes(pcm.tobytes())
    return events


def create(output, audio_root, duration=90, seed=20261017, profiles=None):
    output, audio_root = Path(output), Path(audio_root)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output directory; existing candidates are preserved')
    if not 30 <= duration <= 300:
        raise ValueError('Review candidates must be 30–300 seconds')
    output.mkdir(parents=True, exist_ok=True)
    metadata = read_json(audio_root / 'metadata.json', [])
    records = []
    profiles = PROFILES if profiles is None else profiles
    if not profiles:
        raise ValueError('At least one audio profile is required')
    prepared = {}
    for source_id in sorted({p['source'] for p in profiles if p['source']}):
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
    for index, profile in enumerate(profiles):
        name, source_id = profile['name'], profile['source']
        print('Rendering ' + name, flush=True)
        folder = output / name; folder.mkdir()
        destination = folder / (name + '.flac')
        raw = folder / 'unmastered.flac'
        drops = folder / 'droplets.wav'
        events = droplets(drops, duration, seed+index, profile['rate'], profile['curve'])
        command = [ffmpeg(), '-y', '-loglevel', 'error', '-i', str(drops)]
        components = [{'kind': 'procedural', 'seed': seed+index,
                       'method': 'sparse unpitched stereo rain transients; no continuous noise generator',
                       'profile': profile, 'event_times_seconds': sorted(round(t,4) for t in events)}]
        highpass = profile.get('highpass', 450)
        lowpass = profile.get('lowpass', 7200)
        if not 250 <= highpass <= 1000 or not 1200 <= lowpass <= 12000:
            raise ValueError('Profile filters must retain rain detail and suppress rumble')
        graph = [f'[0:a]highpass=f=600:p=2,lowpass=f={min(lowpass,7800)}:p=2[drops]']
        inputs = '[drops]'
        if source_id:
            source = next(t for t in metadata if str(t['id']) == source_id)
            if source.get('review', {}).get('approved') is not True or source.get('review', {}).get('status') == 'rejected':
                raise ValueError('Blend requires an approved source')
            source_path = audio_root / source['filename']
            command += ['-i', str(prepared[source_id])]
            graph.append(f'[1:a]highpass=f={highpass}:p=2,highpass=f={highpass}:p=2,'
                         f'lowpass=f={lowpass}:p=2,volume={profile["bed_db"]}dB,'
                         f"volume='{density_expression(duration, profile['curve'])}':eval=frame,"
                         'aformat=sample_rates=48000:channel_layouts=stereo[recording]')
            inputs += '[recording]'
            components.append({'kind': 'licensed_recording', 'id': source_id,
                'source_url': source['freesound_url'], 'license': source['license'],
                'source_sha256': digest(source_path), 'original_title': source['title']})
        graph.append(f'{inputs}amix=inputs={2 if source_id else 1}:duration=first:normalize=0,'
                     f'atrim=duration={duration}[out]')
        subprocess.run(command + ['-filter_complex', ';'.join(graph), '-map', '[out]',
                       '-t', str(duration), '-ar', '48000', '-c:a', 'flac', str(raw)], check=True)
        measured = audio_report(raw)
        loudness = float(measured['loudness']['input_i'])
        if not math.isfinite(loudness):
            raise ValueError('Candidate is silent or invalid')
        # One fixed gain preserves changing rain density; different loudness
        # targets preserve the range across profiles instead of equalizing it.
        gain = profile['target'] - loudness
        peak_limit = 10 ** ((-12 if profile['intensity']=='light' else -7)/20)
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(raw),
                        '-af', f'volume={gain}dB,alimiter=limit={peak_limit}:level=false,'
                        f'afade=t=in:d=1,afade=t=out:st={duration-1}:d=1',
                        '-ar', '48000', '-c:a', 'flac', str(destination)], check=True)
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
                        'design_intensity': profile['intensity'], 'design_target_lufs': profile['target'],
                        'target_lufs': float(report['loudness']['input_i']),
                        'generator_sha256': digest(Path(__file__)),
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
