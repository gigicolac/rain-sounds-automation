"""Create a local media-review page; apply explicit human reviews from its exported file."""
import argparse
import html
import json
import shutil
import os
from datetime import datetime, timezone
from pathlib import Path
from asset_library import ROOT, read_json, write_json, review_errors

def inventory():
    return [("video", v) for v in read_json(ROOT / "data/video_library.json", [])] + [
        ("audio", a) for a in read_json(ROOT / "audio/metadata.json", [])]

def key(kind, asset):
    return asset["asset_id"] if kind == "video" else str(asset["id"])

def page(output):
    records = []
    for kind, asset in inventory():
        item = {"kind": kind, "id": key(kind, asset), "title": asset.get("title", asset.get("asset_id")),
                "review": asset.get("review", {}), "errors": review_errors(asset, kind)}
        path = asset.get("local_path") if kind == "video" else "audio/" + asset["filename"]
        item["media"] = Path(os.path.relpath((ROOT / path).resolve(), output.resolve().parent)).as_posix() if path else asset.get("download_url", "")
        item["source"] = asset.get("source_url", asset.get("freesound_url", ""))
        records.append(item)
    data = json.dumps(records).replace("<", "\\u003c")
    content = """<!doctype html><meta charset="utf-8"><title>Rain asset review</title>
<style>body{font:16px system-ui;max-width:1050px;margin:32px auto;background:#12202a;color:#eef5fa}
article{background:#203440;padding:22px;margin:20px 0;border-radius:12px}video{width:100%;max-height:420px}
audio{width:100%}textarea{width:100%;height:80px}label{display:inline-block;margin:8px 14px 8px 0}select{padding:6px}a{color:#9cdaff}button{padding:12px}pre{white-space:pre-wrap}
</style><h1>Rain asset review</h1>
<p>Play the complete source and inspect repeat boundaries. Choose labels only from what you observe. Leave uncertain fields Unknown.
Only changed cards are exported. Export your reviews when finished. The export is applied separately; this page does not publish.</p>
<p>Labels: setting (forest/city/roof/window/tent/lake/garden), intensity (gentle/moderate/heavy),
surface (leaves/glass/metal/fabric/water/ground/mixed), perspective (indoors/sheltered/outdoors).
Video style: live_action/illustrated. Audio events: thunder/traffic/animals/music/voices, each true or false.</p>
<p>Required quality checks: full_playback, loop_checked; video: sharp, stable, rain_visible;
audio: clean_recording, no_clipping. Set each true only after checking.
Video also requires rights_checked: true after checking the source license.</p>
<button id="export">Export edited reviews</button><div id="cards"></div><script>
const records=DATA;
const cards=document.getElementById('cards');
for(const r of records){
 const card=document.createElement('article');
 const h=document.createElement('h2');h.textContent=r.kind+' '+r.id+' — '+r.title;card.append(h);
 const player=document.createElement(r.kind==='video'?'video':'audio');player.controls=true;player.preload='none';player.src=r.media;card.append(player);
 const link=document.createElement('a');link.textContent='Open source / check license';link.href=r.source;link.target='_blank';card.append(link);
 const errors=document.createElement('pre');errors.textContent='Publishing gaps: '+r.errors.join('; ');card.append(errors);

 const rcopy=structuredClone(r.review);rcopy.labels=rcopy.labels||{};rcopy.quality=rcopy.quality||{};
 const controls={};
 function selectField(name,options,current,container){
   const label=document.createElement('label');label.textContent=name+' ';
   const select=document.createElement('select');
   for(const value of options){const option=document.createElement('option');option.value=value;option.textContent=value||'Unknown';select.append(option);}
   select.value=current===undefined?'':String(current);label.append(select);container.append(label);return select;
 }
 controls.status=selectField('Decision',['pending','approved','rejected'],rcopy.approved?'approved':(rcopy.status||'pending'),card);
 controls.labels={};
 const vocab={setting:['forest','city','roof','window','tent','lake','garden'],intensity:['gentle','moderate','heavy'],
 surface:['leaves','glass','metal','fabric','water','ground','mixed'],perspective:['indoors','sheltered','outdoors']};
 if(r.kind==='video')vocab.style=['live_action','illustrated'];
 else for(const event of ['thunder','traffic','animals','music','voices'])vocab[event]=['true','false'];
 for(const [key,values] of Object.entries(vocab))controls.labels[key]=selectField(key,['',...values],rcopy.labels[key],card);
 controls.quality={};
 const checks=['full_playback','loop_checked',...(r.kind==='video'?['sharp','stable','rain_visible']:['clean_recording','no_clipping'])];
 for(const key of checks){
   const label=document.createElement('label');const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=rcopy.quality[key]===true;
   label.append(checkbox,document.createTextNode(' '+key.replaceAll('_',' ')));card.append(label);controls.quality[key]=checkbox;
 }
 if(r.kind==='video')controls.rights=selectField('Source license reviewed',['','true','false'],rcopy.rights_checked,card);
 const notes=document.createElement('textarea');notes.placeholder='Describe what you checked and any defects or uncertainty';notes.value=rcopy.notes||'';card.append(notes);
 r.collect=()=>{
   const labels={};for(const [key,input] of Object.entries(controls.labels))if(input.value!=='')labels[key]=['true','false'].includes(input.value)?input.value==='true':input.value;
   return {...rcopy,approved:controls.status.value==='approved',status:controls.status.value,labels,
     quality:Object.fromEntries(Object.entries(controls.quality).map(([key,input])=>[key,input.checked])),
     rights_checked:controls.rights?controls.rights.value==='true':rcopy.rights_checked,notes:notes.value};
 };
 card.addEventListener('change',()=>{r.changed=true;});
 cards.append(card);
}
document.getElementById('export').onclick=()=>{
 try{
 const data=records.filter(r=>r.changed).map(r=>({kind:r.kind,id:r.id,review:r.collect()}));
 const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='asset-reviews.json';a.click();URL.revokeObjectURL(a.href);
 }catch(e){alert('Could not export reviews: '+e.message);}
};
</script>""".replace("DATA", data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(output)

def apply(path):
    edits = read_json(path, [])
    pools = {"video": read_json(ROOT / "data/video_library.json", []),
             "audio": read_json(ROOT / "audio/metadata.json", [])}
    seen = set()
    for edit in edits:
        kind, identifier, review = edit["kind"], str(edit["id"]), edit["review"]
        if kind not in pools or (kind, identifier) in seen:
            raise ValueError("Unknown kind or duplicate review")
        seen.add((kind, identifier))
        matches = [a for a in pools[kind] if key(kind, a) == identifier]
        if len(matches) != 1:
            raise ValueError(f"Unknown asset {kind}:{identifier}")
        if type(review.get("approved")) is not bool:
            raise ValueError("approved must be a boolean")
        if review.get("status", "pending") not in {"pending", "approved", "rejected"}:
            raise ValueError("status must be pending, approved or rejected")
        if review.get("status") == "rejected" and review["approved"]:
            raise ValueError("Rejected assets cannot be approved")
        candidate = dict(matches[0], review=review)
        if review["approved"]:
            review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            errors = review_errors(candidate, kind)
            if errors:
                raise ValueError(f"{identifier}: " + "; ".join(errors))
            review["status"] = "approved"
        matches[0]["review"] = review
    # Validate every edit before any writes.
    write_json(ROOT / "data/video_library.json", pools["video"])
    write_json(ROOT / "audio/metadata.json", pools["audio"])
    print(f"Applied {len(edits)} explicit reviews; media preserved.")

def import_candidates(folder):
    """Merge a downloaded discovery artifact without replacing existing reviews or media."""
    source = folder.resolve()
    videos = read_json(source / "data/video_library.json", [])
    audios = read_json(source / "audio/metadata.json", [])
    current_v = read_json(ROOT / "data/video_library.json", [])
    current_a = read_json(ROOT / "audio/metadata.json", [])
    known_v = {v["asset_id"] for v in current_v}
    known_a = {str(a["id"]) for a in current_a}
    added_v, added_a = 0, 0
    copies = []
    destinations = set()
    for video in videos:
        if video["asset_id"] not in known_v:
            video["review"] = {"approved": False, "labels": {}, "quality": {}, "notes": ""}
            current_v.append(video); known_v.add(video["asset_id"]); added_v += 1
    for audio in audios:
        if str(audio["id"]) in known_a:
            continue
        filename = audio["filename"]
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise ValueError("Unsafe audio filename")
        path = (source / "audio" / filename).resolve()
        path.relative_to(source)
        if not path.is_file():
            raise ValueError(f"Missing audio candidate {filename}")
        destination = ROOT / "audio" / filename
        if destination.exists() or destination in destinations:
            raise ValueError(f"Unregistered existing audio file: {filename}; resolve manually")
        copies.append((path, destination))
        destinations.add(destination)
        audio["review"] = {"approved": False, "status": "pending", "labels": {}, "quality": {}, "notes": ""}
        current_a.append(audio); known_a.add(str(audio["id"])); added_a += 1
    for source_file, destination in copies:
        shutil.copy2(source_file, destination)
    write_json(ROOT / "data/video_library.json", current_v)
    write_json(ROOT / "audio/metadata.json", current_a)
    for name in ("audio_discovery_state.json", "video_discovery_state.json"):
        path = source / "data" / name
        if path.exists():
            write_json(ROOT / "data" / name, read_json(path, {}))
    print(f"Imported {added_v} videos and {added_a} audio candidates; existing reviews preserved.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("page")
    p.add_argument("--output", type=Path, default=ROOT / "run/asset-review.html")
    a = sub.add_parser("apply"); a.add_argument("file", type=Path)
    i = sub.add_parser("import-candidates"); i.add_argument("folder", type=Path)
    args = parser.parse_args()
    if args.command == "page":
        page(args.output)
    elif args.command == "apply":
        apply(args.file)
    else:
        import_candidates(args.folder)

if __name__ == "__main__":
    main()
