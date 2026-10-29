"""Original sheltered-window rain review; all candidates remain pending."""
import argparse
from pathlib import Path
import subprocess
from create_custom_audio import create
from media_quality import ffmpeg
from asset_library import read_json, write_json

PROFILES = [
    dict(name='window-01-soft-dense', source=None, rate=350, target=-25,
         bed_db=-60, intensity='moderate', lowpass=4200, curve=[.80,.88,.78,.90,.80]),
    dict(name='window-02-full-steady', source=None, rate=650, target=-23,
         bed_db=-60, intensity='heavy', lowpass=6000, curve=[.86,.94,.88,.96,.86]),
    dict(name='window-03-close-texture', source=None, rate=1000, target=-23,
         bed_db=-60, intensity='heavy', lowpass=7600, curve=[.82,.96,.85,.93,.82]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=int, default=90)
    parser.add_argument('--seed', type=int, default=2026102901)
    args = parser.parse_args()
    create(args.output, args.output / 'no-recording-sources', args.duration, args.seed, PROFILES)
    records = read_json(args.output / 'candidates.json', [])
    for record in records:
        record['intent'] = dict(heaviness=record['design_intensity'], environment='window', vibes=['cozy', 'sheltered', 'sleep'])
    write_json(args.output / 'candidates.json', records)
    for profile in PROFILES:
        folder = args.output / profile['name']
        source = folder / (profile['name'] + '.flac')
        # Same two-second crossfade as the production loop, exposing the seam
        # in a short review clip (the full candidate is also provided).
        graph = (f'[0:a]atrim=start={args.duration-8},asetpts=PTS-STARTPTS[a];'
                 '[1:a]atrim=end=8,asetpts=PTS-STARTPTS[b];'
                 '[a][b]acrossfade=d=2:c1=tri:c2=tri[out]')
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(source),
                        '-i', str(source), '-filter_complex', graph, '-map', '[out]',
                        '-c:a', 'libmp3lame', '-b:a', '192k', str(folder / 'boundary.mp3')], check=True)


if __name__ == '__main__':
    main()
