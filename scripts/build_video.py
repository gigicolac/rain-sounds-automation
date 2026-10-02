#!/usr/bin/env python3
"""Assemble the day's video: loop the Pexels scene + cached audio to the
target duration, overlay the title for the first ~12s, and export an mp4.

Reads run/assets.json (written by select_assets.py) and produces
run/output.mp4.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from media_quality import probe, prepare_audio, ffmpeg

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "run"
ASSETS_PATH = RUN_DIR / "assets.json"
SCENE_PATH = RUN_DIR / "scene.mp4"
OUTPUT_PATH = RUN_DIR / "output.mp4"

FONT_PATH = os.environ.get("VIDEO_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
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
    font = escape_drawtext(FONT_PATH.replace("\\", "/"))
    fade_start = TITLE_OVERLAY_SECONDS - TITLE_FADE_SECONDS
    return (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        f"drawtext=fontfile='{font}':text='{overlay_text}':"
        "fontcolor=white@0.9:fontsize=48:x=(w-text_w)/2:y=80:"
        "box=1:boxcolor=black@0.45:boxborderw=24:"
        f"enable='between(t,0,{TITLE_OVERLAY_SECONDS})':"
        f"alpha='if(lt(t,{fade_start}),1,if(lt(t,{TITLE_OVERLAY_SECONDS}),"
        f"({TITLE_OVERLAY_SECONDS}-t)/{TITLE_FADE_SECONDS},0))'[v]"
    )


def run_ffmpeg(assets):
    audio_path = ROOT / assets["audio"]["path"]
    duration_seconds = assets["duration_seconds"]
    prepared = RUN_DIR / "prepared-audio.wav"
    prepare_audio(audio_path, prepared, duration_seconds)
    info = probe(SCENE_PATH)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    length = float(info["format"]["duration"])
    channel = assets.get('selection_explanation', {}).get('policy') == 'channel_profile'
    minimum = (1280, 720, 5) if channel else (1920, 1080, 10)
    if stream["width"] < minimum[0] or stream["height"] < minimum[1] or length < minimum[2]:
        raise ValueError(f'Source requires {minimum[0]}x{minimum[1]} or better and at least {minimum[2]} seconds')
    if channel:
        from preflight_assets import measure
        from asset_library import write_json
        source_report = measure(SCENE_PATH, 'video')
        if not source_report.get('decode_ok'):
            raise ValueError('Source video failed automatic decoding checks')
        write_json(RUN_DIR / 'channel-source-quality.json', source_report)
    scene = SCENE_PATH
    fade = float(os.environ.get("VIDEO_CROSSFADE_SECONDS", "1"))
    if not 0 <= fade <= 2 or (fade and length <= 2 * fade):
        raise ValueError("Video crossfade must be 0–2 seconds and shorter than half the source")
    if fade:
        scene = RUN_DIR / "scene-loop.mp4"
        graph = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            "fps=30,settb=AVTB,format=yuv420p,split=3[body][tail][head];"
            f"[body]trim=start={fade}:end={length-fade},setpts=PTS-STARTPTS[b];"
            f"[tail]trim=start={length-fade}:end={length},setpts=PTS-STARTPTS[t];"
            f"[head]trim=start=0:end={fade},setpts=PTS-STARTPTS[h];"
            f"[t][h]xfade=transition=fade:duration={fade}:offset=0[x];"
            "[b][x]concat=n=2:v=1:a=0[out]")
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(SCENE_PATH),
                        "-filter_complex", graph, "-map", "[out]", "-an", "-c:v", "libx264",
                        "-preset", "fast", "-crf", "18", str(scene)], check=True)

    if duration_seconds >= 3600:
        # Encode the short seamless cycle once. Copy its compressed frames for
        # long videos rather than re-encoding 324,000 frames for a three-hour run.
        if not fade:
            raise ValueError('Long-form videos require a prepared seamless scene cycle')
        cmd = [ffmpeg(), '-y', '-stream_loop', '-1', '-i', str(scene),
               '-i', str(prepared), '-map', '0:v:0', '-map', '1:a:0',
               '-t', str(duration_seconds), '-c:v', 'copy', '-c:a', 'aac',
               '-b:a', '192k', '-movflags', '+faststart', '-loglevel', 'warning', str(OUTPUT_PATH)]
        subprocess.run(cmd, check=True)
        return

    cmd = [
        ffmpeg(), "-y",
        "-stream_loop", "-1", "-i", str(scene),
        "-i", str(prepared),
        "-filter_complex", build_filter_complex(assets["title"]),
        "-map", "[v]", "-map", "1:a",
        "-t", str(duration_seconds),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
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

    local = assets["video"].get("local_path")
    if local:
        source = (ROOT / local).resolve()
        source.relative_to(ROOT.resolve())
        shutil.copyfile(source, SCENE_PATH)
    else:
        download_file(assets["video"]["download_url"], SCENE_PATH)

    run_ffmpeg(assets)
    if assets.get('selection_explanation', {}).get('policy') == 'channel_profile':
        from channel_profile import digest
        from asset_library import write_json, read_json
        from preflight_assets import measure
        report = measure(OUTPUT_PATH, 'video')
        audio_quality = read_json(RUN_DIR / 'prepared-audio.quality.json', {})
        normalized = audio_quality.get('normalized_output', {})
        peak = normalized.get('peak_db')
        final_info = probe(OUTPUT_PATH)
        audio_streams = [s for s in final_info['streams'] if s['codec_type'] == 'audio']
        audio_duration = float(audio_streams[0].get('duration', 0)) if audio_streams else 0
        report['audio_duration_seconds'] = audio_duration
        report.update(video_id=assets['video']['asset_id'], audio_id=str(assets['audio']['freesound_id']),
                      output_sha256=digest(OUTPUT_PATH))
        report['passed'] = bool(report.get('decode_ok') and report.get('width') == 1920
            and report.get('height') == 1080
            and abs(report['duration_seconds'] - assets['duration_seconds']) < 0.1
            and abs(audio_duration - assets['duration_seconds']) < 0.1
            and peak is not None and peak <= -0.1)
        write_json(RUN_DIR / 'channel-quality.json', report)
        if not report['passed']:
            raise ValueError('Rendered video/audio failed automatic channel checks')
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"build_video.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
