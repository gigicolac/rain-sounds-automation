"""Local review renderer: masked rain, steam, lamp glow and body motion.

Adapted from the layered scene prototype. Batch settings provide each scene's
pane polygons, foreground exclusions and motion coordinates.
Writes a silent preview only; does not select assets, reserve history or upload.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
from rain_window_masks import rain_mask, rain_layer, rain_drops
from PIL import Image, ImageDraw, ImageFilter, ImageOps


VERSIONS = {
    4: {'body': 3.0, 'cat': 2.2, 'head': 0, 'body_cycles': 2, 'cat_cycles': 3},
    5: {'body': 3.0, 'cat': 2.2, 'head': 4.0, 'body_cycles': 2, 'cat_cycles': 3,
        'light': 38},
    6: {'body': 2.8, 'cat': 1.8, 'head': 3.5, 'body_cycles': 2, 'cat_cycles': 3,
        'light': 32, 'head_plateau': .35},
    7: {'body': 3.8, 'cat': 2.2, 'head': 4.5, 'body_cycles': 2, 'cat_cycles': 3,
        'light': 32, 'head_plateau': .35, 'harmonic': .20, 'head_lag': .025},
    8: {'body': 3.4, 'cat': 1.8, 'head': 4.0, 'body_cycles': 2, 'cat_cycles': 3,
        'light': 26, 'head_plateau': .35, 'harmonic': .12, 'head_lag': .015,
        'head_roll': .30},
    9: {'body': 3.4, 'cat': 2.8, 'cat_back': 2.8, 'head': 4.0,
        'body_cycles': 2, 'cat_cycles': 3, 'light': 26,
        'head_plateau': .35, 'harmonic': .12, 'head_lag': .015,
        'head_roll': .30, 'independent_light': True},
}
VERSIONS[10] = dict(VERSIONS[9], cat_upper=2.8)

SCENE01 = dict(VERSIONS[8], body=4.0, head=2.6, cat=0, cat_back=0,
               body_region=(535, 535, 125, 95),
               head_region=(600, 325, 155, 180), head_pivot=(600, 325),
               light=30, independent_light=True, cup=(385, 657),
               glow_bounds=[(-30, 170), (470, 620)], glow_blur=75,
               windows=[[(674, 0), (958, 0), (958, 581), (835, 581),
                         (780, 500), (740, 430), (780, 350), (760, 245), (674, 210)],
                        [(1010, 0), (1458, 0), (1458, 605), (1010, 595)],
                        [(1504, 0), (1672, 0), (1672, 615), (1504, 609)]])

PARIS = dict(VERSIONS[10],
             body_region=(409, 539, 115, 95),
             head_region=(497, 326, 169, 178),
             cat_region=(1320, 714, 85, 46),
             back_region=(1335, 665, 100, 34),
             upper_region=(1430, 666, 70, 20),
             head_pivot=(497, 326), cup=(325, 650),
             windows=[[(617, 0), (1005, 0), (1005, 638), (674, 620),
                       (674, 370), (655, 280), (617, 220)],
                      [(1080, 0), (1650, 0), (1650, 655), (1080, 644)]])


def motion_mesh(size, settings):
    """One continuous warp: shared vertices avoid overlapping patch seams."""
    sx, sy = size[0] / 1672, size[1] / 941
    def weight(x, y, cx, cy, rx, ry, plateau=0):
        radius = ((x / sx - cx) / rx) ** 2 + ((y / sy - cy) / ry) ** 2
        if radius >= 1:
            return 0
        if plateau:
            t = max(0, (radius - plateau) / (1 - plateau))
            return 1 - t * t * (3 - 2 * t)
        return (1 - radius) ** 2
    vertices = {}
    xs = list(range(0, size[0], 24)) + [size[0]]
    ys = list(range(0, size[1], 24)) + [size[1]]
    for y in ys:
        for x in xs:
            vertices[x, y] = (
                weight(x, y, *settings.get('body_region', (428, 539, 125, 100))),
                weight(x, y, *settings.get('cat_region', (1278, 722, 85, 48))),
                weight(x, y, *settings.get('head_region', (522, 319, 176, 184)),
                       settings.get('head_plateau', 0)),
                weight(x, y, *settings.get('back_region', (1278, 676, 85, 38))),
                weight(x, y, *settings.get('upper_region', (1382, 675, 84, 20))))
    cells = [(x0, y0, x1, y1) for y0, y1 in zip(ys, ys[1:])
             for x0, x1 in zip(xs, xs[1:])]
    def at_phase(phase):
        def wave(cycles, offset=0):
            angle = 2 * math.pi * (phase * cycles + offset)
            harmonic = settings.get('harmonic', 0)
            return (math.sin(angle) + harmonic * math.sin(2 * angle)) / (1 + harmonic)
        body = wave(settings['body_cycles'])
        cat = wave(settings['cat_cycles'], .23)
        head = wave(settings['body_cycles'], -settings.get('head_lag', 0))
        roll = math.radians(settings.get('head_roll', 0)) * head
        pivot_x, pivot_y = settings.get('head_pivot', (522, 319))
        mapped = {}
        for (x, y), (bw, cw, hw, backw, upperw) in vertices.items():
            dy = (bw * settings['body'] * body + cw * settings['cat'] * cat
                  + backw * settings.get('cat_back', 0) * cat
                  + upperw * settings.get('cat_upper', 0) * cat
                  + hw * settings['head'] * head) * sy
            dx = hw * settings['head'] * .25 * head * sx
            dx += hw * roll * (y - pivot_y * sy)
            dy -= hw * roll * (x - pivot_x * sx)
            mapped[x, y] = (x - dx, y - dy)
        mesh = []
        for x0, y0, x1, y1 in cells:
            quad = sum((mapped[p] for p in [(x0, y0), (x0, y1),
                                            (x1, y1), (x1, y0)]), ())
            mesh.append(((x0, y0, x1, y1), quad))
        return mesh
    return at_phase


def render(source, output, binary='ffmpeg', duration=10, fps=24, version=None, scene='original', settings=None):
    version = max(VERSIONS) if version is None else version
    size = (1920, 1080)
    base = ImageOps.fit(Image.open(source).convert('RGB'), size).convert('RGBA')
    if settings is None:
        settings = SCENE01 if scene == 'scene01' else PARIS if scene == 'paris' else VERSIONS[version]
    # Reference coordinates in the original 1672x941 composition.
    sx, sy = size[0] / 1672, size[1] / 941
    def points(coords):
        return [(round(x * sx), round(y * sy)) for x, y in coords]
    settings = dict(settings)
    settings['_rain_mask'] = rain_mask(size, settings)
    # Integer travel periods make the motion periodic at the loop boundary.
    drops = rain_drops(size)
    glow = Image.new('RGBA', size)
    gd = ImageDraw.Draw(glow)
    gd.ellipse(points(settings.get('glow_bounds', [(-100, 190), (610, 900)])),
               fill=(255, 176, 75, settings.get('light', 58)))
    glow = glow.filter(ImageFilter.GaussianBlur(settings.get('glow_blur', 95)))
    glow_alpha = glow.getchannel('A')
    mesh = motion_mesh(size, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, '-y', '-loglevel', 'error', '-f', 'rawvideo',
               '-pix_fmt', 'rgb24', '-s', '1920x1080', '-r', str(fps), '-i', '-',
               '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame in range(round(duration * fps)):
            phase = frame / (duration * fps)
            living = base.transform(size, Image.Transform.MESH, mesh(phase),
                                    resample=Image.Resampling.BICUBIC)
            rain = rain_layer(size, settings, phase, drops)
            steam = Image.new('RGBA', size)
            sd = ImageDraw.Draw(steam)
            cup_x, cup_y = settings.get('cup', (321, 644))
            for strand in range(4):
                curve = []
                for step in range(65):
                    height = step / 64
                    wave = math.sin(2 * math.pi * (height * 1.1 - phase * 3 + strand * .19))
                    x = (cup_x + strand * settings.get('steam_spacing', 7) + wave * (2 + height * 12)) * sx
                    y = (cup_y - height * settings.get('steam_height', 128)) * sy
                    curve.append((x, y))
                for step in range(1, len(curve)):
                    height = step / (len(curve) - 1)
                    alpha = int(60 * math.sin(math.pi * height) ** .6)
                    sd.line(curve[step-1:step+1], fill=(242, 235, 224, alpha), width=settings.get('steam_width', 6))
            steam = steam.filter(ImageFilter.GaussianBlur(3))
            result = Image.alpha_composite(Image.alpha_composite(living, rain), steam)
            pulse = .55 + .45 * math.sin(2 * math.pi * phase * 2)
            if settings.get('independent_light'):
                # Two offset frequencies avoid following either breathing rhythm.
                pulse = (.55 + .25 * math.sin(2 * math.pi * (phase + .17))
                         + .15 * math.sin(2 * math.pi * (phase * 4 + .63)))
            glow.putalpha(glow_alpha.point(lambda value: round(value * pulse)))
            result = Image.alpha_composite(result, glow)
            process.stdin.write(result.convert('RGB').tobytes())
            if frame % fps == 0:
                print(f'Rendering {frame // fps + 1}/{duration} seconds', flush=True)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('FFmpeg encoding failed')
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--version', type=int, choices=sorted(VERSIONS), default=max(VERSIONS))
    parser.add_argument('--scene', choices=['original', 'paris', 'scene01'], default='scene01')
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--settings', type=Path, help='Scene-specific animation JSON; overrides built-in scene settings.')
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text(encoding='utf-8')) if args.settings else None
    render(args.source, args.output, args.ffmpeg, fps=args.fps, version=args.version, scene=args.scene, settings=settings)
