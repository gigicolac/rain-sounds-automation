"""Loopback-only listening and review interface for the rain audio library."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, unquote
from rain_audio_library import read_library, review, safe, generate
from asset_library import read_json, write_json, ROOT


def library_data(root):
    assets = []
    for asset in read_library(root)['assets'].values():
        record = read_json(safe(root, asset['candidate']), {})
        asset['recipe'] = record.get('recipe') or next((c.get('profile') for c in record.get('components', []) if c.get('profile')), {})
        asset['sources'] = [{k: c[k] for k in ('kind','id','source_url','license','original_title') if k in c}
                           for c in record.get('components', [])]
        assets.append(asset)
    return assets

PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rain Atelier · Audio library</title><style>
:root{color-scheme:dark;font:16px system-ui;background:#0c141b;color:#edf3f1}*{box-sizing:border-box}body{margin:0}
header,main{max-width:1320px;margin:auto;padding:32px}header{padding-top:48px}.eyebrow{color:#8caab2;letter-spacing:.17em;font-size:12px;text-transform:uppercase}
h1{font-size:42px;font-weight:580;margin:10px 0}h2{font-size:20px;font-weight:550;margin:10px 0}p{color:#aabdc2;line-height:1.6}.top{display:flex;justify-content:space-between;align-items:center;gap:24px}.local{border:1px solid #344951;padding:9px 14px;border-radius:24px;color:#acd1c5;font-size:13px}
.toolbar,.filters{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}button,select,textarea{font:inherit;background:#172630;color:#edf3f1;border:1px solid #344951;border-radius:9px;padding:10px 12px}button{cursor:pointer}button:hover{border-color:#b9d4ca}button.active{background:#d4e3d2;color:#112025;border-color:#d4e3d2}.filters select{min-width:170px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px}.card{background:#14212a;border:1px solid #293c46;border-radius:16px;padding:24px}.card.approved{border-top:3px solid #9fc2a3}.card.rejected{border-top:3px solid #b9857d}.card.pass{border-top:3px solid #d1b981}.badge{font-size:12px;letter-spacing:.05em;color:#becdc9;text-transform:uppercase}.tags{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}.tag{font-size:12px;padding:5px 8px;background:#22323b;border-radius:6px;color:#b9c9cb}.statusline{display:flex;justify-content:space-between;gap:12px}.muted{font-size:13px;color:#8ba4ae}.small{font-size:12px}audio{width:100%;height:42px;margin:8px 0}.field{margin-top:14px}textarea{display:block;width:100%;min-height:68px;resize:vertical;margin:8px 0}.checks label{display:block;margin:10px 0;font-size:13px;color:#becccc}.checks input{margin-right:8px;accent-color:#accfae}.actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:16px}.actions button{font-size:13px;padding:9px 11px}.approve{color:#b8e0b8}.reject{color:#e6aaa0}.message{font-size:13px;color:#edc689;min-height:20px;margin-top:12px}.empty{border:1px dashed #344951;padding:40px;border-radius:12px;color:#aabdc2}.summary{border-left:2px solid #bbcebc;padding-left:16px;max-width:800px}.notice{padding:16px 20px;background:#182b33;border-radius:12px;font-size:13px}.plan{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin:20px 0}.plan article{padding:16px;border:1px solid #344951;border-radius:12px}.plan p{margin:7px 0;font-size:13px}details{margin-top:16px}summary{cursor:pointer;color:#b4c9ca}.footer{padding:32px 0;color:#829da5;font-size:13px}@media(max-width:650px){header,main{padding:22px}.top{display:block}h1{font-size:32px}.local{display:inline-block}.grid{grid-template-columns:1fr}}
</style><header><div class="top"><div><div class="eyebrow">Calming Rain Sounds / Asset studio</div><h1>Rain Atelier</h1></div><span class="local">Local listening library</span></div>
<p class="summary">Create a sound, listen, then decide. Keep the rain natural, with room for light showers, changing intensity and different atmospheres.</p>
<div class="notice">Approved = accepted for the library. Pass = usable spare. Rejected = retained and excluded. New renders always start pending. Publishing remains a separate step.</div></header>
<main><div class="eyebrow">Your collection</div><div id="categories" class="toolbar"></div><div class="filters"><select id="heaviness" aria-label="Filter heaviness"></select><select id="environment" aria-label="Filter environment"></select><select id="vibe" aria-label="Filter vibe"></select><button id="clear">Clear filters</button></div><p id="count" class="muted"></p><section id="cards" class="grid"></section>
<details><summary>Create rain assets · heaviness, environment and vibe</summary><p>Recording-based starting points, using Changing Shower as the reference. Environment tags describe the intended sound until verified by listening. Each new render starts pending.</p><label>Seed <input id="seed" aria-label="Generation seed" type="number" value="123" min="0" max="2147483647" style="background:#172630;color:#edf3f1;border:1px solid #344951;border-radius:7px;padding:8px;width:140px"></label><section id="plan" class="plan"></section><p id="generation-message" class="message" role="status"></p></details><div class="footer">Files and decisions stay on this computer. Approving a sound does not publish it or change the daily audio pool.</div></main>
<script>
const TOKEN=__TOKEN__;let items=[],category='all';const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title=s=>s==='pass'?'Pass / spare':s.charAt(0).toUpperCase()+s.slice(1);
function options(id,label,values){const old=$(id).value;$(id).innerHTML=`<option value="">${label}</option>`+[...new Set(values)].filter(Boolean).sort().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');$(id).value=old}
function draw(){let categories=['all','pending','approved','pass','rejected'];$('categories').innerHTML=categories.map(c=>`<button data-category="${c}" class="${c===category?'active':''}">${title(c)} · ${items.filter(a=>c==='all'||a.status===c).length}</button>`).join('');document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{category=b.dataset.category;draw()});
let list=items.filter(a=>(category==='all'||a.status===category)&&(!$('heaviness').value||a.intent.heaviness===$('heaviness').value)&&(!$('environment').value||a.intent.environment===$('environment').value)&&(!$('vibe').value||(a.intent.vibes||[]).includes($('vibe').value)));
$('count').textContent=`${list.length} ${list.length===1?'asset':'assets'} · Listen at a consistent playback volume; light rain is intentionally quieter.`;
$('cards').innerHTML=list.length?list.map(a=>`<article class="card ${esc(a.status)}" data-id="${esc(a.id)}"><div class="statusline"><span class="badge">${title(a.status)}</span><span class="muted">${a.duration}s · ${a.target_lufs} loudness units</span></div><h2>${esc(a.title)}</h2><div class="tags">${[a.intent.heaviness,a.intent.environment,...(a.intent.vibes||[])].map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div><div class="muted small">Intended character · ${Object.keys(a.review.labels||{}).length?'reviewed labels recorded':'environment not yet verified'}</div><audio controls preload="none" src="/media/${encodeURIComponent(a.id)}/listen.mp3"></audio><details><summary>Repeat-boundary audition</summary>${a.loop?`<audio controls preload="none" src="/media/${encodeURIComponent(a.id)}/loop.mp3"></audio><p class="muted small">Last six seconds crossfaded into the first six. Listen for clicks, dips or obvious repetition.</p>`:'<p class="muted">Loop preview unavailable; check the boundary manually.</p>'}</details><label class="field muted">Review notes<textarea placeholder="Natural texture? Wind, boom, hiss, intensity, scene fit…">${esc(a.review.notes)}</textarea></label><div class="checks"><label><input class="listened" type="checkbox">I listened to this asset</label><label><input class="full" type="checkbox" ${a.review.quality?.full_playback?'checked':''}>Full source checked</label><label><input class="loop" type="checkbox" ${a.review.quality?.loop_checked?'checked':''}>Repeat boundary checked</label></div><details><summary>Confirm heard labels (optional)</summary><div class="filters"><select class="heard-setting" aria-label="Heard environment"><option value="">Environment unknown</option>${['window','forest','city','roof','tent','lake','garden'].map(v=>`<option ${a.review.labels?.setting===v?'selected':''}>${v}</option>`).join('')}</select><select class="heard-intensity" aria-label="Heard intensity"><option value="">Intensity unknown</option>${['gentle','moderate','heavy'].map(v=>`<option ${a.review.labels?.intensity===v?'selected':''}>${v}</option>`).join('')}</select></div></details><div class="actions"><button class="approve" data-status="approved">Approve</button><button data-status="pass">Pass / spare</button><button class="reject" data-status="rejected">Reject</button><button data-status="pending">Reset to pending</button></div><div class="message" role="status"></div><details><summary>Provenance &amp; decisions</summary><p class="muted small">${esc(a.id)}<br>Master checksum: ${esc(a.sha256)}<br>${a.decisions.length} recorded decisions</p><p class="muted small">${esc((a.decisions||[]).map(d=>d.notes).join(' · '))}</p><p class="muted small">${esc((a.sources||[]).map(s=>[s.kind,s.original_title,s.source_url,s.license].filter(Boolean).join(' · ')).join('\n'))}</p><pre class="muted small" style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(a.recipe,null,2))}</pre></details></article>`).join(''):'<div class="empty">No assets in this selection. Change the filters or create a new batch.</div>';
document.querySelectorAll('.card').forEach(card=>card.querySelectorAll('[data-status]').forEach(button=>button.onclick=async()=>{const message=card.querySelector('.message');let labels={};const setting=card.querySelector('.heard-setting').value,intensity=card.querySelector('.heard-intensity').value;if(setting)labels.setting=setting;if(intensity)labels.intensity=intensity;try{let response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':TOKEN},body:JSON.stringify({id:card.dataset.id,status:button.dataset.status,notes:card.querySelector('textarea').value,listened:card.querySelector('.listened').checked,full_playback:card.querySelector('.full').checked,loop_checked:card.querySelector('.loop').checked,labels})});let data=await response.json();if(!response.ok)throw Error(data.error);items=data.assets;draw()}catch(error){message.textContent=error.message}}));}
async function load(){let data=await(await fetch('/api/library')).json();items=data.assets;options('heaviness','All heaviness',items.map(a=>a.intent.heaviness));options('environment','All environments',items.map(a=>a.intent.environment));options('vibe','All vibes',items.flatMap(a=>a.intent.vibes||[]));draw();$('plan').innerHTML=data.presets.map(p=>`<article><span class="badge">${esc(p.heaviness)} · ${esc(p.environment)}</span><h2>${esc(p.title)}</h2><p>${esc(p.vibes.join(' · '))}</p>${p.notes?`<p>${esc(p.notes)}</p>`:''}<p>${p.required_source_setting?'Needs a reviewed '+esc(p.required_source_setting)+' recording':'Recording-based blend; new output needs review'}</p><button data-generate="${esc(p.id)}">Create 90-second candidate</button></article>`).join('');document.querySelectorAll('[data-generate]').forEach(button=>button.onclick=async()=>{const message=$('generation-message');button.disabled=true;message.textContent='Creating audio and checking the complete file. This can take a minute…';try{let response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':TOKEN},body:JSON.stringify({presets:[button.dataset.generate],seed:Number($('seed').value),duration:90})});let data=await response.json();if(!response.ok)throw Error(data.error);message.textContent=data.results.map(r=>r.status==='needs_source'?r.reason:'Created: '+r.preset+' · pending review').join(' · ');await load()}catch(error){message.textContent=error.message}finally{button.disabled=false}})}
['heaviness','environment','vibe'].forEach(id=>$(id).onchange=draw);$('clear').onclick=()=>{['heaviness','environment','vibe'].forEach(id=>$(id).value='');category='all';draw()};load();
</script></html>'''


def build_server(root, port=0, audio_root=ROOT / 'audio'):
    root = Path(root).resolve()
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def send(self, code, content, kind='application/json'):
            payload = content if isinstance(content, bytes) else content.encode('utf-8')
            self.send_response(code); self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload))); self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(payload)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, '{}')
            path = urlsplit(self.path).path
            if path == '/':
                return self.send(200, PAGE.replace('__TOKEN__', json.dumps(token)), 'text/html; charset=utf-8')
            if path == '/api/library':
                return self.send(200, json.dumps({'assets': library_data(root),
                    'presets': read_json(ROOT / 'data/rain_audio_presets.json', {})['presets']}))
            if path.startswith('/media/'):
                parts = path.split('/')
                if len(parts) != 4 or parts[3] not in {'listen.mp3', 'loop.mp3'}:
                    return self.send(404, '{}')
                asset = read_library(root)['assets'].get(unquote(parts[2]))
                key = 'listen' if parts[3] == 'listen.mp3' else 'loop'
                if not asset or not asset.get(key):
                    return self.send(404, '{}')
                return self.send(200, safe(root, asset[key]).read_bytes(), 'audio/mpeg')
            return self.send(404, '{}')

        def do_POST(self):
            origins = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if (not self.valid_host() or self.path not in {'/api/review','/api/generate'} or
                    self.headers.get('X-Review-Token') != token or
                    self.headers.get('Origin') not in origins | {None}):
                return self.send(403, '{"error":"Review request not authorized"}')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Review request is too large or empty')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data,dict):
                    raise ValueError('Request must be a JSON object')
                if self.path == '/api/generate':
                    duration, seed, presets = data.get('duration',90), data.get('seed',123), data.get('presets',[])
                    if type(seed) is not int or not 0 <= seed <= 2147483647:
                        raise ValueError('Seed must be a whole number from 0 to 2147483647')
                    if type(duration) is not int or not 30 <= duration <= 300:
                        raise ValueError('Review duration must be 30–300 seconds')
                    if not isinstance(presets,list) or not 1 <= len(presets) <= 10 or not all(isinstance(p,str) for p in presets):
                        raise ValueError('Choose one to ten creation presets')
                    with lock:
                        results = generate(root,presets,audio_root,duration,seed)
                    return self.send(200,json.dumps({'results':results}))
                if not isinstance(data.get('notes'),str):
                    raise ValueError('Review notes are required')
                if len(data.get('notes', '')) > 4000:
                    raise ValueError('Keep notes under 4000 characters')
                labels = data.get('labels', {})
                if set(labels) - {'setting', 'intensity'}:
                    raise ValueError('Unsupported heard labels')
                if labels.get('setting') and labels['setting'] not in {'window','forest','city','roof','tent','lake','garden'}:
                    raise ValueError('Unknown environment')
                if labels.get('intensity') and labels['intensity'] not in {'gentle','moderate','heavy'}:
                    raise ValueError('Unknown intensity')
                for key in ('listened','full_playback','loop_checked'):
                    if type(data.get(key, False)) is not bool:
                        raise ValueError('Listening checks must be true or false')
                with lock:
                    review(root, data['id'], data['status'], data['notes'], data.get('listened', False),
                           data.get('full_playback', False), data.get('loop_checked', False), labels)
                    payload = json.dumps({'assets': library_data(root)})
                return self.send(200, payload)
            except (ValueError, KeyError, OSError) as exc:
                return self.send(400, json.dumps({'error': str(exc)}))

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.review_token = token
    return server


def serve(root, port=0, audio_root=ROOT / 'audio'):
    root = Path(root)
    server = build_server(root, port, audio_root)
    write_json(root / 'review-server.json', {'url': f'http://127.0.0.1:{server.server_port}/'})
    print(f'Rain library: http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
