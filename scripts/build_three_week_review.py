"""Validate the 60 local assets and build a portable weekly review gallery."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = read(ROOT / 'data/three_week_asset_plan.json')
    batch = ROOT / 'run' / plan['batch']
    audio = read(batch / 'audio-library/library.json')['assets']
    registry_path = ROOT / 'run/image-scene-library.json'
    registry = read(registry_path) if registry_path.exists() else {}
    cards, manifest = [], []
    video_hashes, audio_hashes = set(), set()
    sheets = {w: Image.new('RGB', (960, 5*300), '#0d1720') for w in (1,2,3)}
    for index, (slug, title, description, preset) in enumerate(plan['scenes']):
        week = index//10+1
        folder = batch / 'scenes' / slug
        spec = read(folder / 'package.json')
        for key, digest_key in [('master','master_sha256'),('preview','preview_sha256')]:
            if sha(folder / spec[key]) != spec[digest_key]:
                raise ValueError('Scene checksum mismatch: ' + slug)
        if spec.get('animation_sha256') and sha(folder / spec['animation_settings']) != spec['animation_sha256']:
            raise ValueError('Scene motion settings changed: ' + slug)
        if not all(spec['validation'].values()):
            raise ValueError('Scene validation incomplete: ' + slug)
        if spec['master_sha256'] in video_hashes:
            raise ValueError('Duplicate scene master: ' + slug)
        video_hashes.add(spec['master_sha256'])
        record = audio['custom-audio:three-weeks-' + slug]
        library = batch / 'audio-library'
        for key, digest_key in [('master','sha256'),('listen','listen_sha256'),('loop','loop_sha256')]:
            if sha(library / record[key]) != record[digest_key]:
                raise ValueError('Audio checksum mismatch: ' + slug)
        quality = read(library / record['quality'])
        if not quality['technical_pass'] or record['sha256'] in audio_hashes:
            raise ValueError('Invalid or duplicate audio: ' + slug)
        audio_hashes.add(record['sha256'])
        registry.setdefault(slug, {'status':'pending','package_checked':False,
                                  'package':str(folder.relative_to(ROOT)).replace('\\','/'),'notes':''})
        status = registry[slug]['status']
        master_rel = f'scenes/{slug}/{spec["master"]}'
        thumb = ImageOps.fit(Image.open(folder/spec['master']).convert('RGB'), (480,270))
        x, y = (index%2)*480, ((index%10)//2)*300
        sheets[week].paste(thumb, (x,y))
        ImageDraw.Draw(sheets[week]).text((x+12,y+278), f'{slug} | {status}', fill='#e8ddd0')
        intensity = record['intent']['heaviness']
        vibes = ', '.join(record['intent']['vibes'])
        cards.append(f'''<article data-week="{week}" data-intensity="{intensity}">
<div class="label">Week {week} / {slug} / Video: {html.escape(status)}</div><h2>{html.escape(title)}</h2>
<video controls loop muted playsinline preload="none" poster="{master_rel}" src="scenes/{slug}/{spec['preview']}"></video>
<p class="tags">{intensity} · {html.escape(record['intent']['environment'])} · {html.escape(vibes)}</p>
<label>Complete rain track · 90 seconds</label><audio controls preload="none" src="audio-library/{record['listen']}"></audio>
<label>Repeat-boundary audition · 10 seconds</label><audio controls preload="none" src="audio-library/{record['loop']}"></audio>
<p class="small">Audio: {record['status']}. <a href="{master_rel}" target="_blank">Full artwork</a> · <a href="scenes/{slug}/package.json">Video package</a></p></article>''')
        manifest.append({'week':week,'slot':index%10+1,'scene_id':slug,'scene_title':title,
                         'video':f'scenes/{slug}/{spec["preview"]}','video_sha256':spec['preview_sha256'],
                         'master_sha256':spec['master_sha256'],'video_status':status,
                         'audio_id':record['id'],'audio_sha256':record['sha256'],
                         'audio_status':record['status'],'intent':record['intent']})
    if len(manifest)!=30 or len(audio)!=30:
        raise ValueError('Expected exactly 30 assets of each type')
    save(registry_path, registry)
    save(batch / 'manifest.json', manifest)
    save(ROOT / 'data/image_scene_plan.json', {'scenes':[{'id':s[0],'title':s[1]} for s in plan['scenes']]})
    for week, sheet in sheets.items():
        sheet.save(batch / f'week-{week}-contact.jpg', quality=90)
    session = batch / 'audio-library/review-server.json'
    audio_url = read(session)['url'] if session.exists() else '#audio-review'
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three weeks · Rain asset review</title><style>
:root{color-scheme:dark;font:16px system-ui;background:#0d1720;color:#eee6d9}body{max-width:1320px;margin:auto;padding:32px}h1{font-size:40px;margin-bottom:12px}p{line-height:1.6;color:#b6c3c8}a{color:#d8b57b}nav{display:flex;gap:8px;flex-wrap:wrap;position:sticky;top:0;background:#0d1720;padding:14px 0;z-index:1}button,select{font:inherit;padding:10px 16px;background:#22313c;color:#eee6d9;border:1px solid #53616a;border-radius:8px;cursor:pointer}.active{background:#dfc394;color:#17212a}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{background:#14232d;border:1px solid #324650;border-radius:14px;overflow:hidden;padding:20px}h2{font-size:23px;margin:10px 0 18px}.label{font-size:12px;letter-spacing:.05em;color:#b3c4c7}video{width:100%;aspect-ratio:16/9;background:#080d11;border-radius:8px}audio{width:100%;display:block;margin:10px 0 18px}label,.small{font-size:13px;color:#b7c6c9}.tags{color:#e1c89e}.notice{border-left:3px solid #dfc394;padding:10px 18px;max-width:1000px}footer{padding:32px 0;color:#a6bac2}@media(max-width:760px){body{padding:18px}main{grid-template-columns:1fr}h1{font-size:32px}}</style>
<header><p>CALMING RAIN SOUNDS / LOCAL REVIEW</p><h1>Three weeks of new assets</h1><p>30 animated video loops + 30 custom rain mixes. Ten of each per week.</p>
<p class="notice">All new assets start pending. Watch the complete 10-second video and its repeat. Listen to each complete rain track and its separate boundary audition. Tags describe design intent, not verified recording locations. These are loop assets for later long videos.</p>
<p id="audio-review"><a href="AUDIO_URL" target="_blank">Open Rain Atelier to approve, pass or reject sounds</a>. For video decisions, send the scene IDs with approve / pass / reject and notes.</p>
<p><a href="week-1-contact.jpg">Week 1 contact sheet</a> · <a href="week-2-contact.jpg">Week 2 contact sheet</a> · <a href="week-3-contact.jpg">Week 3 contact sheet</a> · <a href="manifest.json">Batch manifest</a></p></header>
<nav><button class="active" data-week="all">All three weeks</button><button data-week="1">Week 1</button><button data-week="2">Week 2</button><button data-week="3">Week 3</button><select aria-label="Rain intensity"><option value="all">All intensities</option><option>light</option><option>moderate</option><option>changing</option><option>heavy</option></select></nav><p id="count"></p><main>CARDS</main><footer>Local-only review assets. No video uploads, schedule changes or production activation.</footer>
<script>let week='all';const select=document.querySelector('select');function filter(){let n=0;document.querySelectorAll('article').forEach(a=>{a.hidden=!((week==='all'||a.dataset.week===week)&&(select.value==='all'||a.dataset.intensity===select.value));if(!a.hidden)n++;if(a.hidden)a.querySelectorAll('video,audio').forEach(m=>m.pause())});document.getElementById('count').textContent=n+' video + sound pairs shown'}document.querySelectorAll('button').forEach(b=>b.onclick=()=>{week=b.dataset.week;document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));filter()});select.onchange=filter;document.addEventListener('play',e=>{document.querySelectorAll('audio,video').forEach(m=>{if(m!==e.target)m.pause()})},true);filter()</script></html>'''
    (batch / 'index.html').write_text(page.replace('AUDIO_URL',html.escape(audio_url)).replace('CARDS','\n'.join(cards)), encoding='utf-8')
    report = {'checked_at':datetime.now(timezone.utc).isoformat(),'video_count':len(video_hashes),
              'audio_count':len(audio_hashes),'all_checksums_verified':True,
              'all_technical_checks_passed':True,'audio_intensity':dict(Counter(a['intent']['heaviness'] for a in audio.values())),
              'per_week':{str(w):sum(m['week']==w for m in manifest) for w in (1,2,3)},
              'human_review':'pending; technical validation is not listening or visual approval'}
    save(batch / 'validation.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
