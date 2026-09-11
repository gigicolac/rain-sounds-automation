#!/usr/bin/env python3
"""Grab a frame from the built video and overlay a styled title to make a
custom 1280x720 YouTube thumbnail (better click-through than an
auto-selected frame).

Reads run/assets.json + run/output.mp4, writes run/thumbnail.jpg.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "run"
ASSETS_PATH = RUN_DIR / "assets.json"
VIDEO_PATH = RUN_DIR / "output.mp4"
RAW_FRAME_PATH = RUN_DIR / "thumb_raw.jpg"
THUMBNAIL_PATH = RUN_DIR / "thumbnail.jpg"

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
THUMB_SIZE = (1280, 720)
FONT_SIZE = 64
MARGIN_X = 80
LINE_SPACING = 12
MAX_LINES = 3


def extract_frame(duration_seconds):
    # A frame a few minutes in tends to look better than t=0 (title-overlay
    # frame) or the very end; clamp so it also works on short test videos.
    timestamp = max(1, min(300, duration_seconds // 3))
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(VIDEO_PATH),
        "-frames:v", "1", "-q:v", "2",
        "-loglevel", "warning",
        str(RAW_FRAME_PATH),
    ]
    subprocess.run(cmd, check=True)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:MAX_LINES]


def compose_thumbnail(title):
    image = Image.open(RAW_FRAME_PATH).convert("RGB").resize(THUMB_SIZE, Image.LANCZOS)
    overlay = Image.new("RGBA", THUMB_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    max_text_width = THUMB_SIZE[0] - 2 * MARGIN_X
    lines = wrap_text(draw, title, font, max_text_width)

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    block_height = sum(line_heights) + LINE_SPACING * (len(lines) - 1)
    band_top = THUMB_SIZE[1] - block_height - 100
    draw.rectangle([(0, band_top - 40), (THUMB_SIZE[0], THUMB_SIZE[1])], fill=(0, 0, 0, 150))

    y = band_top
    for line, h in zip(lines, line_heights):
        w = draw.textlength(line, font=font)
        x = (THUMB_SIZE[0] - w) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=3, stroke_fill=(0, 0, 0, 200))
        y += h + LINE_SPACING

    composed = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    composed.save(THUMBNAIL_PATH, "JPEG", quality=88)


def main():
    if not ASSETS_PATH.exists():
        raise RuntimeError(f"{ASSETS_PATH} not found — run select_assets.py first")
    if not VIDEO_PATH.exists():
        raise RuntimeError(f"{VIDEO_PATH} not found — run build_video.py first")

    assets = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))
    extract_frame(assets["duration_seconds"])
    compose_thumbnail(assets["title"])
    print(f"Wrote {THUMBNAIL_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"make_thumbnail.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
