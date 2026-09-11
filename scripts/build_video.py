#!/usr/bin/env python3
"""Assemble the day's video: loop the Pexels scene + cached audio to the
target duration, overlay the title for the first ~12s, and export an mp4.

Reads run/assets.json (written by select_assets.py) and produces
run/output.mp4.
"""
import json
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "run"
ASSETS_PATH = RUN_DIR / "assets.json"
SCENE_PATH = RUN_DIR / "scene.mp4"
OUTPUT_PATH = RUN_DIR / "output.mp4"

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TITLE_OVERLAY_SECONDS = 12
TITLE_FADE_SECONDS = 2
AUDIO_FADE_SECONDS = 3
MAX_OVERLAY_TITLE_LEN = 70


def download_file(url, dest_path, chunk_size=1 << 20):
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)


def escape_drawtext(text):
    """Escape text for safe use inside ffmpeg's drawtext text='...' argument."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\\\''")
    text = text.replace(":", "\\:")
    return text


def truncate(text, max_len=MAX_OVERLAY_TITLE_LEN):
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def build_filter_complex(title):
    overlay_text = escape_drawtext(truncate(title))
    fade_start = TITLE_OVERLAY_SECONDS - TITLE_FADE_SECONDS
    return (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        f"drawtext=fontfile={FONT_PATH}:text='{overlay_text}':"
        "fontcolor=white@0.9:fontsize=48:x=(w-text_w)/2:y=80:"
        "box=1:boxcolor=black@0.45:boxborderw=24:"
        f"enable='between(t,0,{TITLE_OVERLAY_SECONDS})':"
        f"alpha='if(lt(t,{fade_start}),1,if(lt(t,{TITLE_OVERLAY_SECONDS}),"
        f"({TITLE_OVERLAY_SECONDS}-t)/{TITLE_FADE_SECONDS},0))'[v]"
    )


def run_ffmpeg(assets):
    audio_path = ROOT / assets["audio"]["path"]
    duration_seconds = assets["duration_seconds"]
    fade_out_start = duration_seconds - AUDIO_FADE_SECONDS

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(SCENE_PATH),
        "-stream_loop", "-1", "-i", str(audio_path),
        "-filter_complex", build_filter_complex(assets["title"]),
        "-map", "[v]", "-map", "1:a",
        "-t", str(duration_seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-af", f"afade=t=in:st=0:d={AUDIO_FADE_SECONDS},afade=t=out:st={fade_out_start}:d={AUDIO_FADE_SECONDS}",
        "-movflags", "+faststart",
        "-loglevel", "warning", "-stats",
        str(OUTPUT_PATH),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    if not ASSETS_PATH.exists():
        raise RuntimeError(f"{ASSETS_PATH} not found — run select_assets.py first")
    assets = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))

    print(f"Downloading scene video from {assets['video']['download_url']}")
    download_file(assets["video"]["download_url"], SCENE_PATH)

    run_ffmpeg(assets)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"build_video.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
