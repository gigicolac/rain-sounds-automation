"""User-authorized recording-based variations of the two approved forest mixes."""
import argparse
from datetime import datetime, timezone
import random
from pathlib import Path
from asset_library import ROOT, read_json, write_json
from create_custom_audio import create
from channel_profile import digest
from rain_audio_library import import_batch, read_library, transaction, save_library

SOURCE_SHA = '035c23de195d1bfd5a44d6b6dac92501fd132c55b68dd26c5d1d78c3fec71d66'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audio-root',type=Path,required=True)
    parser.add_argument('--library',type=Path,default=ROOT/'run/window-rain-library-20261029')
    parser.add_argument('--count',type=int,default=10)
    parser.add_argument('--seed',type=int,required=True)
    args=parser.parse_args()
    if not 1 <= args.count <= 10: raise ValueError('Batch count must be 1-10')
    source=next(a for a in read_json(args.audio_root/'metadata.json',[]) if str(a['id'])=='651189')
    if digest(args.audio_root/source['filename']) != SOURCE_SHA: raise ValueError('Approved forest source changed')
    catalogue=read_json(ROOT/'audio/metadata.json',[])
    bases=[next(a for a in catalogue if a['id']=='custom-audio:three-weeks-'+slug)['components'][0]['profile']
           for slug in ('20-ranger-storm','30-woodland-night')]
    rng=random.Random(args.seed); profiles=[]
    for i in range(args.count):
        which=0 if i < (args.count+1)//2 else 1
        p=dict(bases[which])
        p.update(name=f'forest-launch-{args.seed}-{i+1:02d}',source='651189')
        p['rate']=round(p['rate']*rng.uniform(.82,1.15))
        p['lowpass']=round(p['lowpass']*rng.uniform(.94,1.04))
        p['bed_db']=round(p['bed_db']+rng.uniform(-.7,.7),2)
        p['curve']=[round(min(1,max(.4,v*rng.uniform(.93,1.07))),3) for v in p['curve']]
        profiles.append(p)
    create(args.output,args.audio_root,90,args.seed,profiles)
    records=read_json(args.output/'candidates.json',[])
    decisions={}
    for i,r in enumerate(records):
        if not r['technical_pass']: raise RuntimeError('Technical check failed; automatic approval withheld')
        if any(c.get('kind')=='licensed_recording' and (str(c.get('id'))!='651189' or c.get('source_sha256')!=SOURCE_SHA) for c in r['components']):
            raise RuntimeError('Unexpected source in batch')
        r['title']=f'Launch forest {i+1:02d} - '+('Ranger shelter variation' if i<(args.count+1)//2 else 'Woodland night variation')
        r['intent']=dict(heaviness='heavy',environment='forest',vibes=['new-channel-batch','recording-based','dense'])
        r['review']=dict(approved=True,status='approved',approval_method='user_authorized_automatic',
            approval_authorization='User explicitly authorized automatic approval and reuse of source 651189 on 29 October 2026',
            reviewed_at=datetime.now(timezone.utc).isoformat(),notes='Automatically approved at user direction after technical checks; no new listening assessment asserted.',
            labels={},quality=dict(full_playback=False,loop_checked=False,technical_checked=True))
        decisions[r['id']]=dict(r['review'],sha256=r['sha256'],intent=r['intent'])
    write_json(args.output/'candidates.json',records)
    import_batch(args.library,args.output,decisions=decisions)
    @transaction
    def record_authorization(root):
        lib=read_library(root)
        for r in records: lib['assets'][r['id']]['review']=r['review']
        save_library(root,lib)
    record_authorization(args.library)
    print(f'Completed {len(records)} technically checked, user-auto-approved recording-based mixes.',flush=True)


if __name__=='__main__': main()
