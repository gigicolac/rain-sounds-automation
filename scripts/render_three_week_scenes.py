"""Render new local scene packages with the established source-warp engine."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageOps
from rain_window_masks import rain_mask, pane_masks

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene-worktree', type=Path, help='Retained for old commands; renderer is now local')
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--revision', default='panes-v2')
    parser.add_argument('--overlays-only', action='store_true')
    args = parser.parse_args()
    if not args.revision.replace('-', '').isalnum():
        parser.error('Use an alphanumeric revision name')
    from animate_review_scene import render, motion_mesh, VERSIONS
    plan = json.loads((ROOT / 'data/three_week_asset_plan.json').read_text())
    profiles = json.loads((ROOT / 'data/three_week_scene_motion.json').read_text())
    masks = json.loads((ROOT / 'data/three_week_window_masks.json').read_text())
    batch = ROOT / 'run' / plan['batch']

    def one(scene):
        slug, title, _, _ = scene
        if args.ids and slug not in args.ids:
            return
        folder = batch / 'scenes' / slug
        master = folder / 'master.png'
        if (folder / 'master-clean.png').exists():
            master = folder / 'master-clean.png'
        if not master.exists() or slug not in profiles or slug not in masks:
            return
        settings = dict(VERSIONS[8], body=0, head=0, head_roll=0,
                        cat=0, cat_back=0, independent_light=True,
                        light=22, glow_blur=75)
        settings.update(profiles[slug])
        settings.update(masks[slug])
        settings['rain_exclusions'] = masks[slug].get('rain_exclusions', [])
        revision = '-' + args.revision
        preview = folder / ('preview' + revision + '.mp4')
        report = folder / 'package.json'
        animation = folder / ('animation' + revision + '.json')
        if preview.exists() and animation.exists() and json.loads(animation.read_text()) != settings:
            raise ValueError('Motion changed; preserve the old loop and choose a new output revision: ' + slug)
        if preview.exists() and report.exists():
            previous = json.loads(report.read_text())
            if previous['preview'] == preview.name and previous['master_sha256'] != digest(master):
                raise ValueError('Master changed; choose a new output revision: ' + slug)
        mask = rain_mask((1920,1080), settings)
        mask_path = folder / f'rain-mask-{args.revision}.png'
        mask.save(mask_path)
        artwork = ImageOps.fit(Image.open(master).convert('RGB'), (1920,1080)).convert('RGBA')
        tint = Image.new('RGBA', artwork.size, (0,220,235,0))
        tint.putalpha(mask.point(lambda p:round(p*.33)))
        overlay = Image.alpha_composite(artwork,tint)
        draw = ImageDraw.Draw(overlay)
        for number, pane in enumerate(pane_masks(artwork.size,settings),1):
            box = pane.getbbox()
            if box:
                draw.text(((box[0]+box[2])/2,(box[1]+box[3])/2),str(number),fill='white',stroke_width=2,stroke_fill='black')
        overlay.convert('RGB').save(folder / f'rain-mask-overlay-{args.revision}.jpg',quality=95)
        if args.overlays_only:
            print(f'MASK {slug}: {len(settings["windows"])} panes',flush=True)
            return
        mesh = motion_mesh((1920, 1080), settings)
        if any(abs(x-y)>1e-7 for a,b in zip(mesh(0),mesh(1)) for x,y in zip(a[1],b[1])):
            raise ValueError('Non-periodic motion: ' + slug)
        animation.write_text(json.dumps(settings, indent=2)+'\n')
        if not preview.exists():
            render(master, preview, duration=10, fps=24, settings=settings)
        subprocess.run(['ffmpeg','-v','error','-i',str(preview),'-f','null','-'], check=True)
        probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(preview)]))
        stream = probe['streams'][0]
        if stream['width'] != 1920 or stream['height'] != 1080 or abs(float(probe['format']['duration'])-10)>.1:
            raise ValueError('Unexpected preview format: ' + slug)
        for time in (0, 2.5, 5, 7.5):
            frame = folder / f'frame{revision}-{time:g}.jpg'
            if not frame.exists():
                subprocess.run(['ffmpeg','-v','error','-y','-ss',str(time),'-i',str(preview),'-frames:v','1',str(frame)], check=True)
        package = {'scene_id':slug,'title':title,'status':'pending','render_method':'source_warp',
                   'generator':'built-in image_gen','master':master.name,'master_sha256':digest(master),
                   'preview':preview.name,'preview_sha256':digest(preview),'animation_settings':animation.name,
                   'animation_sha256':digest(animation),
                   'rain_mask':mask_path.name,'rain_mask_sha256':digest(mask_path),
                   'rain_mask_overlay':f'rain-mask-overlay-{args.revision}.jpg','pane_count':len(settings['windows']),
                   'duration_seconds':10,'width':1920,'height':1080,'fps':24,
                   'validation':{'full_decode':True,'periodic_motion':True},
                   'notes':'New asset: human visual and loop approval required.'}
        report.write_text(json.dumps(package, indent=2)+'\n')
        print('VIDEO COMPLETE ' + slug, flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, plan['scenes']))


if __name__ == '__main__':
    main()
