"""Explicit pane masks shared by rendering, overlays and containment checks.

Coordinates use the established 1672 by 941 reference canvas. Each polygon
traces visible glass, with separate exclusions for indoor foreground objects.
"""
from PIL import Image, ImageDraw, ImageChops, ImageFilter


def rain_drops(size, seed=42):
    import random
    rng = random.Random(seed)
    sx, sy = size[0]/1672, size[1]/941
    drops = []
    for count, speeds, lengths, opacity, width in [
            (300, (7, 8, 9), (12, 24), (65, 115), 1),
            (150, (10, 11, 12), (25, 44), (100, 165), 1),
            (60, (13, 14, 15), (40, 65), (125, 200), 2)]:
        for _ in range(count):
            drops.append((rng.uniform(-40, 1712)*sx, rng.random(),
                          rng.choice(speeds), rng.uniform(*lengths)*sy,
                          rng.randrange(*opacity), width))
    return drops


def pane_masks(size, settings):
    sx, sy = size[0]/1672, size[1]/941
    def points(polygon):
        return [(round(x*sx), round(y*sy)) for x,y in polygon]
    exclusions = Image.new('L', size)
    for polygon in settings.get('rain_exclusions', []):
        ImageDraw.Draw(exclusions).polygon(points(polygon), fill=255)
    result = []
    for polygon in settings['windows']:
        mask = Image.new('L', size)
        ImageDraw.Draw(mask).polygon(points(polygon), fill=255)
        mask = ImageChops.subtract(mask, exclusions)
        # A one-pixel inset keeps antialiasing/encoding away from wood edges.
        result.append(mask.filter(ImageFilter.MinFilter(3)))
    return result


def rain_mask(size, settings):
    mask = Image.new('L', size)
    for pane in pane_masks(size, settings):
        mask = ImageChops.lighter(mask, pane)
    return mask


def rain_layer(size, settings, phase, drops):
    import math
    phase %= 1
    sx, sy = size[0]/1672, size[1]/941
    rain = Image.new('RGBA', size)
    draw = ImageDraw.Draw(rain)
    gust = .10+.07*math.sin(2*math.pi*phase)
    for x, offset, speed, length, alpha, width in drops:
        # Span the full output height, with enough overscan for entering drops.
        y = ((offset+speed*phase)%1)*(size[1]+160*sy)-80*sy
        drift = 18*sx*math.sin(2*math.pi*(phase+offset))
        draw.line([(x+drift,y),(x+drift-length*gust,y+length)],
                  fill=(185,207,240,alpha),width=width)
    rain.putalpha(ImageChops.multiply(rain.getchannel('A'),settings['_rain_mask']))
    return rain
