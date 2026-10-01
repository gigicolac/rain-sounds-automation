"""Simple local channel library and preview plan. Does not approve assets or publish."""
import argparse
import html
import random
from pathlib import Path
from asset_library import ROOT, read_json, write_json


def pool(root):
    profile = read_json(root / 'data/channel_profile.json', {})
    videos = [v for v in read_json(root / 'data/video_library.json', [])
              if v['asset_id'] in profile.get('video_ids', [])]
    audios = [a for a in read_json(root / 'audio/metadata.json', [])
              if str(a['id']) in profile.get('audio_ids', [])]
    return profile, videos, audios


def select(root, rng):
    profile, videos, audios = pool(root)
    if not audios:
        raise ValueError('Choose one default rain recording in channel_profile.json first. No asset tags are required.')
    def exists(relative):
        path = (root / relative).resolve()
        path.relative_to(root.resolve())
        return path.is_file()
    videos = [v for v in videos if v.get('local_path') and exists(v['local_path'])
              and v.get('review', {}).get('status') != 'rejected']
    audios = [a for a in audios if exists('audio/' + a['filename'])
              and a.get('review', {}).get('status') != 'rejected']
    if not videos or not audios:
        raise ValueError('Selected channel files are missing or excluded; no unrelated fallback is used.')
    return {'scope': 'local preview only', 'profile': profile['name'],
            'video': rng.choice(videos), 'audio': rng.choice(audios),
            'review_approved': False, 'duration_seconds': 30}


def page(root):
    profile, videos, audios = pool(root)
    esc = html.escape
    cards = []
    for video in videos:
        source = video.get('source_url', '')
        link = '<a href="'+esc(source, quote=True)+'">Source</a>' if source else 'Source link still missing'
        cards.append('<article><h2>'+esc(video['asset_id'])+'</h2><video controls preload="none" src="../'+
                     esc(video.get('local_path',''), quote=True)+'"></video><p>'+link+'</p></article>')
    body = '<!doctype html><meta charset="utf-8"><title>Channel library</title><style>body{font:17px system-ui;background:#12202a;color:#eef5fa;max-width:1000px;margin:32px auto}article{padding:20px;background:#203440;margin:20px 0}video{width:100%;max-height:400px}a{color:#9cdaff}</style>'
    body += '<h1>'+esc(profile['name'])+'</h1><p>'+esc(profile['visual_direction'])+'</p><p>'+esc(profile['audio_direction'])+'</p>'
    body += '<p>No tagging or review export needed for this local channel workspace.</p><p>Default audio: '+('configured' if audios else 'one-time selection needed')+'</p>'
    body += '<p>Publishing remains separate. Short clips are included here for local evaluation.</p>'+''.join(cards)
    output = root / 'run/channel-library.html'
    output.parent.mkdir(exist_ok=True)
    output.write_text(body, encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='Save an isolated local preview plan')
    args = parser.parse_args()
    if args.plan:
        write_json(ROOT / 'run/channel-preview/plan.json', select(ROOT, random.Random()))
    print(page(ROOT))
