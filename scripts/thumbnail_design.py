"""Short, readable text treatments over the actual video frame."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parents[1] / 'fonts/nunito/Nunito.ttf'
CREAM = (255, 239, 201, 255)
AMBER = (255, 192, 91, 255)
INK = (15, 24, 45, 255)
MAX_TEXT_WIDTH = 520


def font(size):
    result = ImageFont.truetype(str(FONT), size)
    result.set_variation_by_axes([1000])
    return result


def render(frame, seconds, headline, style='stacked', side='left'):
    if style not in {'stacked', 'accent', 'panel'} or side not in {'left', 'right'}:
        raise ValueError('Unknown thumbnail treatment or side')
    words = headline.split()
    if not 2 <= len(words) <= 3:
        raise ValueError('Thumbnail requires two or three words')
    lines = headline.splitlines()
    if len(lines) == 1:
        lines = [' '.join(words[:-1]), words[-1]]
    if len(lines) != 2:
        raise ValueError('Thumbnail requires two lines')
    image = frame.convert('RGBA').resize((1280, 720), Image.Resampling.LANCZOS)
    overlay = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(overlay)
    left = 56 if side == 'left' else 704
    headline_font = font(144)
    fits = lambda candidate: max(draw.textlength(line, font=headline_font) for line in candidate) <= MAX_TEXT_WIDTH
    # Stack a wide two-word line (DEEP SLEEP) rather than shrinking the whole headline.
    stacked = [word for line in lines for word in line.split()]
    if not fits(lines) and len(stacked) == 3 and fits(stacked):
        lines = stacked
    while not fits(lines):
        headline_font = font(headline_font.size-2)
    step = round(headline_font.size * 0.99)
    if style == 'panel':
        draw.rounded_rectangle((left-22, 108, left+MAX_TEXT_WIDTH, 225+len(lines)*step+30), radius=32, fill=(15, 24, 45, 210))
    else:
        for x in range(740):
            coordinate = x if side == 'left' else 1279-x
            draw.line((coordinate, 0, coordinate, 720), fill=(8, 14, 34, int(155*(1-x/740))))
    badge_font = font(38)
    minutes = int(seconds // 60)
    badge = (f'{minutes//60} HOUR' + ('S' if minutes != 60 else '')) if minutes >= 60 and minutes % 60 == 0 else f'{minutes} MIN'
    width = draw.textlength(badge, font=badge_font)
    draw.rounded_rectangle((left, 136, left+width+40, 199), radius=30, fill=AMBER)
    draw.text((left+20, 141), badge, font=badge_font, fill=INK)
    for index, line in enumerate(lines):
        position = (left-3, 225+index*step)
        if style == 'accent' and index == 0:
            draw.text(position, line, font=headline_font, fill=AMBER, stroke_width=3, stroke_fill=INK)
        else:
            draw.text(position, line, font=headline_font, fill=CREAM,
                      stroke_width=2, stroke_fill=INK)
    return Image.alpha_composite(image, overlay).convert('RGB')
