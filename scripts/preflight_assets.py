"""Measure local assets and suggest metadata labels without changing human reviews."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from asset_library import ROOT, read_json, write_json, identity
from media_quality import probe, ffmpeg, audio_report

VERSION = 1


def suggestions(asset):
    # Discovery text is a hint only; never infer absence of audible events.
    text = ' '.join(str(asset.get(k, '')) for k in
                    ('title', 'name', 'description', 'tags', 'discovery_query', 'source_url')).lower()
    groups = {
        'setting': {'window': ['window'], 'forest': ['forest'], 'city': ['city'],
                    'tent': ['tent'], 'lake': ['lake'], 'roof': ['roof'], 'garden': ['garden']},
        'intensity': {'gentle': ['gentle', 'light rain'], 'heavy': ['heavy rain']},
        'surface': {'glass': ['glass'], 'fabric': ['fabric'], 'metal': ['metal'], 'leaves': ['leaves']},
        'perspective': {'indoors': ['indoors', 'indoor'], 'outdoors': ['outdoors', 'outdoor']},
        'style': {'illustrated': ['anime', 'illustrated', 'animation']},
    }
    result = {}
    for key, values in groups.items():
        matches = {value: term for value, terms in values.items() for term in terms
                   if re.search(r'\b' + re.escape(term) + r'\b', text)}
        if len(matches) == 1:
            value, term = next(iter(matches.items()))
            result[key] = {'value': value, 'evidence': 'Source metadata contains: ' + term}
    return result


def measure(path, kind):
    info = probe(path)
    report = {'duration_seconds': float(info['format']['duration']), 'warnings': []}
    if kind == 'audio':
        report.update(audio_report(path))
        report['decode_ok'] = True
    else:
        stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
        report.update(width=stream['width'], height=stream['height'])
        result = subprocess.run([ffmpeg(), '-hide_banner', '-nostdin', '-i', str(path),
            '-map', '0:v:0', '-vf', 'blackdetect=d=0.5:pix_th=0.10', '-an', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=max(600, report['duration_seconds'] / 4))
        # A zero exit code alone can still accompany recoverable decode errors.
        suspicious = [line for line in result.stderr.splitlines()
                      if re.search(r'error|corrupt|invalid', line, re.I)]
        report['decode_ok'] = result.returncode == 0 and not suspicious
        report['black_intervals'] = re.findall(r'black_start:[^\r\n]+', result.stderr)
        if not report['decode_ok']:
            report['warnings'].append('Decoding needs inspection: ' + ' '.join(suspicious)[:500])
        if report['black_intervals']:
            report['warnings'].append('Dark/black intervals detected; may be intentional night scenes.')
        if stream['width'] < 1920 or stream['height'] < 1080 or report['duration_seconds'] < 10:
            report['warnings'].append('Below current video resolution/duration minimum.')
    return report


def run(root=ROOT):
    output = root / 'run/asset-preflight.json'
    previous = read_json(output, {}).get('assets', {})
    reports = {}
    for kind, catalog in [('video', 'data/video_library.json'), ('audio', 'audio/metadata.json')]:
        for asset in read_json(root / catalog, []):
            key = identity(asset, kind)
            relative = asset.get('local_path') if kind == 'video' else 'audio/' + asset['filename']
            row = {'suggestions': suggestions(asset), 'warnings': []}
            try:
                if not relative:
                    raise ValueError('Download required before technical checks.')
                path = (root / relative).resolve()
                path.relative_to(root.resolve())
                with path.open('rb') as source:
                    digest = hashlib.file_digest(source, 'sha256').hexdigest()
                old = previous.get(key, {})
                if old.get('sha256') == digest and old.get('version') == VERSION and 'measurements' in old:
                    row['measurements'] = old['measurements']
                else:
                    row['measurements'] = measure(path, kind)
                row.update(sha256=digest, version=VERSION)
            except Exception as exc:
                row['warnings'].append(str(exc))
            reports[key] = row
            print(key + ': ' + ('checked' if 'measurements' in row else 'needs attention'), flush=True)
    write_json(output, {'generated_at': datetime.now(timezone.utc).isoformat(), 'assets': reports})
    return output


if __name__ == '__main__':
    print(run())
