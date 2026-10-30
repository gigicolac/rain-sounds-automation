"""Layered, entirely procedural forest-rain listening experiments.

No source recordings are read. Recipes describe intentions, not heard labels.
NumPy is used locally for synthesis; publishing code does not depend on it.
"""
import argparse
import math
from pathlib import Path
import subprocess
import wave
import numpy as np
from asset_library import write_json
from channel_profile import digest
from media_quality import ffmpeg, audio_report, probe

RATE = 24000
FINE_PROFILES = [
    dict(slug='09-fine-forest-detail', title='Forest revision 9 - fine forest detail',
         wash=.85, leaves=.32, rate=135, brightness=2.0, target=-22, fine=True),
    dict(slug='10-gently-shifting-rain', title='Forest revision 10 - gently shifting rain',
         wash=.78, leaves=.40, rate=180, brightness=1.8, target=-22, fine=True),
]
PROFILES = [
    dict(slug='01-broad-forest', title='Forest attempt 1 - broad, steady downpour',
         wash=1.0, leaves=.24, rate=210, brightness=1.0, target=-22),
    dict(slug='02-dense-leaves', title='Forest attempt 2 - dense rain on leaves',
         wash=.9, leaves=.43, rate=390, brightness=1.12, target=-22),
    dict(slug='03-deep-canopy', title='Forest attempt 3 - deeper canopy rain',
         wash=1.1, leaves=.20, rate=280, brightness=.72, target=-23),
]

DROPLET_PROFILES = [
    dict(slug='04-layered-droplets', title='Forest revision 4 - layered individual droplets',
         wash=.38, leaves=.88, rate=105, brightness=1.0, target=-22, individual=True),
    dict(slug='05-close-leaf-drops', title='Forest revision 5 - clearer close leaf droplets',
         wash=.24, leaves=1.0, rate=65, brightness=1.08, target=-22, individual=True),
    dict(slug='06-dense-varied-drops', title='Forest revision 6 - dense rain with varied droplets',
         wash=.30, leaves=.95, rate=150, brightness=.9, target=-22, individual=True),
]

TRICKLE_PROFILES = [
    dict(slug='07-soft-leaf-trickles', title='Forest revision 7 - soft leaf trickles',
         wash=.10, leaves=1.0, rate=22, brightness=.65, target=-24, trickle=True, resonance=.10),
    dict(slug='08-rounded-water', title='Forest revision 8 - rounded water droplets',
         wash=.045, leaves=1.0, rate=16, brightness=.58, target=-24, trickle=True, resonance=.24),
]


def soft_trickles(count, rng, profile):
    """Soft clustered water-like events with rounded envelopes and muted tops."""
    result = np.zeros((count, 2), dtype=np.float32)
    cluster = 0.0
    while True:
        cluster += rng.exponential(RATE / profile['rate'])
        if cluster >= count - 2:
            break
        start = int(cluster)
        pan = rng.uniform(.12, .88)
        for _ in range(int(rng.integers(2, 7))):
            start += int(rng.uniform(.004, .028) * RATE)
            if start >= count - 40:
                break
            length = min(int(rng.uniform(.035, .10) * RATE), count - start)
            t = np.arange(length, dtype=np.float32) / RATE
            attack = rng.uniform(.003, .008)
            decay = rng.uniform(.010, .026)
            # Smooth each event before its envelope; exclude the dry broadband snap.
            width = int(rng.integers(7, 23))
            kernel = np.hanning(width); kernel /= kernel.sum()
            water = np.convolve(rng.standard_normal(length), kernel, mode='same')
            water /= max(float(np.std(water)), .0001)
            shape = (1 - np.exp(-t / attack)) ** 2 * np.exp(-t / decay)
            # Quiet, short, inharmonic water resonances; never a sustained note.
            f = rng.uniform(650, 1900)
            phase = 2 * np.pi * (f * t + rng.uniform(-1200, 1200) * t * t)
            resonance = np.sin(phase) + .35 * np.sin(phase * rng.uniform(1.35, 1.7))
            drop = (water + profile['resonance'] * resonance) * shape
            drop *= rng.uniform(.45, 1.35)
            offset = min(.95, max(.05, pan + rng.uniform(-.08, .08)))
            result[start:start + length, 0] += drop * math.sqrt(1 - offset)
            result[start:start + length, 1] += drop * math.sqrt(offset)
    for channel in range(2):
        result[:, channel] = color(result[:, channel], profile['brightness'])
    result /= max(float(np.std(result)), .0001)
    return result


def individual_drops(count, rng, profile):
    """Discrete shared stereo events: varied noisy impacts and diffuse splash tails."""
    result = np.zeros((count, 2), dtype=np.float32)
    position = 0.0
    while True:
        position += rng.exponential(RATE / profile['rate'])
        start = int(position)
        if start >= count - 2:
            break
        large = rng.random() < .16
        length = min(int(rng.uniform(.025, .095) * RATE) if large
                     else int(rng.uniform(.007, .035) * RATE), count - start)
        t = np.arange(length, dtype=np.float32) / RATE
        attack = rng.uniform(.0002, .0012)
        decay = rng.uniform(.007, .025) if large else rng.uniform(.0015, .008)
        noise = rng.standard_normal(length).astype(np.float32)
        # Each drop has a different broad spectral texture; no pitched oscillators.
        width = int(rng.integers(2, 9))
        softened = np.convolve(noise, np.ones(width) / width, mode='same')
        impact = rng.uniform(.25, .85) * noise + rng.uniform(.3, .8) * softened
        shape = np.minimum(t / attack, 1) * np.exp(-t / decay)
        splash = noise * (1 - np.exp(-t / .003)) * np.exp(-t / (decay * 2.8))
        amplitude = min(3.5, rng.lognormal(-.4, .65)) * (1.35 if large else 1)
        drop = (impact * shape + .18 * splash) * amplitude
        pan = rng.uniform(.06, .94)
        result[start:start + length, 0] += drop * math.sqrt(1 - pan)
        result[start:start + length, 1] += drop * math.sqrt(pan)
    for channel in range(2):
        result[:, channel] = color(result[:, channel], profile['brightness'])
    result /= max(float(np.std(result)), .0001)
    return result


def color(signal, brightness=1):
    """Broad rain spectrum: suppress rumble and brittle top-end without tones."""
    freq = np.fft.rfftfreq(len(signal), 1 / RATE)
    anchors = np.array([0, 60, 140, 300, 650, 1200, 2200, 4000, 6500, 9500, 12000])
    levels = np.array([-90, -45, -22, -9, -3, 0, -1, -4, -10, -23, -55], dtype=float)
    levels += 20 * math.log10(brightness) * np.clip(freq_at_anchors(anchors), 0, 1)
    gain = 10 ** (np.interp(freq, anchors, levels) / 20)
    return np.fft.irfft(np.fft.rfft(signal) * gain, n=len(signal)).astype(np.float32)


def freq_at_anchors(anchors):
    return (anchors - 800) / 5000


def envelope(count, rng, step_seconds, spread):
    # Random, smoothly changing density with equal endpoints for loop review.
    positions = np.linspace(0, count - 1, max(3, int(count / RATE / step_seconds) + 2))
    values = rng.uniform(1 - spread, 1 + spread, len(positions))
    values[-1] = values[0]
    return np.interp(np.arange(count), positions, values).astype(np.float32)


def synthesize(duration, seed, profile):
    rng = np.random.default_rng(seed)
    count = int(duration * RATE)
    shared = color(rng.standard_normal(count).astype(np.float32), profile['brightness'])
    slow = envelope(count, rng, 4.5 if profile.get('fine') else 7, .16 if profile.get('fine') else .12)
    result = np.zeros((count, 2), dtype=np.float32)
    detailed = individual_drops(count, rng, profile) if profile.get('individual') else None
    if profile.get('trickle'):
        detailed = soft_trickles(count, rng, profile)
    for channel in range(2):
        wash = color(rng.standard_normal(count).astype(np.float32), profile['brightness'])
        wash = (.78 * wash + .22 * shared) * slow * envelope(count, rng, .7, .06)
        leaves = np.zeros(count, dtype=np.float32)
        for _ in range(0 if detailed is not None else int(duration * profile['rate'])):
            start = int(rng.integers(0, max(1, count - 1)))
            length = min(int(rng.integers(int(.012 * RATE), int(.12 * RATE))), count - start)
            if length < 2:
                continue
            t = np.arange(length) / RATE
            attack = np.minimum(t / .004, 1)
            decay = np.exp(-t / rng.uniform(.006, .028))
            grain = rng.standard_normal(length).astype(np.float32)
            # Broad unpitched splashes, avoiding isolated pitched drip sounds.
            leaves[start:start + length] += grain * attack * decay * rng.uniform(.2, 1)
        if detailed is not None:
            leaves = detailed[:, channel]
        else:
            leaves = color(leaves, profile['brightness'])
            leaves /= max(float(np.std(leaves)), .0001)
        wash /= max(float(np.std(wash)), .0001)
        result[:, channel] = profile['wash'] * wash + profile['leaves'] * leaves * slow
    result *= .15 / max(float(np.std(result)), .0001)
    return result


def create(output, duration=90, seed=2026102910, profiles=None):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output folder; existing media is preserved')
    if not 30 <= duration <= 300:
        raise ValueError('Review duration must be 30–300 seconds')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for index, profile in enumerate(PROFILES if profiles is None else profiles):
        actual_seed = seed + index
        slug = f'forest-{actual_seed}-' + profile['slug']
        folder = output / slug; folder.mkdir()
        print('Synthesizing ' + profile['title'], flush=True)
        samples = synthesize(duration, actual_seed, profile)
        # Preserve sharp droplet attacks before conversion to 16-bit audio.
        # Final limiting happens only after loudness measurement, never by clipping PCM.
        samples *= min(1.0, .95 / max(float(np.max(np.abs(samples))), .0001))
        raw = folder / 'synthesized.wav'
        with wave.open(str(raw), 'wb') as stream:
            stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(RATE)
            stream.writeframes((np.clip(samples, -.98, .98) * 32767).astype('<i2').tobytes())
        initial = audio_report(raw)
        gain = profile['target'] - float(initial['loudness']['input_i'])
        destination = folder / (slug + '.flac')
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(raw), '-af',
                        f'volume={gain}dB,alimiter=limit=0.63:level=false,afade=t=in:d=0.1,afade=t=out:st={duration-.1}:d=0.1',
                        '-ar', '48000', '-c:a', 'flac', str(destination)], check=True)
        report = audio_report(destination)
        report['duration_seconds'] = float(probe(destination)['format']['duration'])
        report['technical_pass'] = bool(abs(report['duration_seconds'] - duration) < .1
            and report['peak_db'] is not None and report['peak_db'] < -.1 and not report['silence_seconds'])
        write_json(folder / 'quality.json', report)
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(destination),
                        '-c:a', 'libmp3lame', '-b:a', '192k', str(folder / 'listen.mp3')], check=True)
        records.append(dict(id='custom-audio:' + slug, title=profile['title'],
            path=str(destination.relative_to(output)), sha256=digest(destination), duration=duration,
            generator_sha256=digest(Path(__file__)), generator_source_url='local:scripts/create_forest_rain_review.py',
            components=[dict(kind='procedural', seed=actual_seed,
                method=('Seeded soft clustered trickles, rounded attack/decay, muted noisy water textures and quiet damped water resonances, minimal continuous bed; no recorded audio'
                        if profile.get('trickle') else 'Seeded individually shaped noisy droplet impacts, variable size/attack/decay/amplitude, shared stereo panning and quieter continuous rain bed; no recorded audio'
                        if profile.get('individual') else 'Seeded continuous spectral rain wash, independently synthesized overlapping leaf splashes, irregular density envelopes; no recorded audio'),
                profile=dict(profile, source=None))],
            intent=dict(heaviness='heavy', environment='forest', vibes=['fine-forest' if profile.get('fine') else 'soft-trickles' if profile.get('trickle') else 'droplet-revision' if profile.get('individual') else 'forest-attempt', 'dense', 'immersive']),
            design_intensity='heavy', target_lufs=float(report['loudness']['input_i']),
            technical_pass=report['technical_pass'],
            review=dict(approved=False, status='pending', labels={}, notes='Full listening and repeat-boundary review required')))
    write_json(output / 'candidates.json', records)
    print(f'Saved {len(records)} pending original candidates: ' + str(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=int, default=90)
    parser.add_argument('--seed', type=int, default=2026102910)
    parser.add_argument('--revision', choices=['wash', 'droplets', 'trickles', 'fine'], default='wash')
    args = parser.parse_args()
    profiles = {'wash': PROFILES, 'droplets': DROPLET_PROFILES, 'trickles': TRICKLE_PROFILES, 'fine': FINE_PROFILES}
    create(args.output, args.duration, args.seed, profiles[args.revision])
