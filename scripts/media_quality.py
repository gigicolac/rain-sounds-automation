"""Media measurements and seamless audio preparation. Requires FFmpeg and ffprobe."""
import json
import os
import re
import subprocess
from pathlib import Path
from asset_library import write_json

def ffmpeg():
    return os.environ.get("FFMPEG", "ffmpeg")

def probe(path):
    result = subprocess.run([os.environ.get("FFPROBE", "ffprobe"), "-v", "error",
                             "-show_streams", "-show_format", "-of", "json", str(path)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def audio_report(path):
    command = [ffmpeg(), "-hide_banner", "-i", str(path), "-af",
               "astats=metadata=0:reset=0,silencedetect=noise=-50dB:d=1,loudnorm=I=-20:TP=-2:LRA=7:print_format=json",
               "-f", "null", "-"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    match = re.search(r'\{\s*"input_i"[\s\S]*?\}', result.stderr)
    if not match:
        raise RuntimeError("FFmpeg did not return loudness measurements")
    loudness = json.loads(match.group())
    peaks = re.findall(r"Peak level dB:\s*([-\w.]+)", result.stderr)
    peak = max((float(p) for p in peaks), default=None)
    silence = [float(v) for v in re.findall(r"silence_duration:\s*([\d.]+)", result.stderr)]
    warnings = []
    if peak is not None and peak >= -0.1:
        warnings.append("Near-full-scale peaks: inspect for clipping")
    if silence:
        warnings.append("Silence detected: inspect gaps")
    if float(loudness["input_i"]) == float("-inf"):
        warnings.append("No measurable loudness")
    return {"source": str(path), "loudness": loudness, "peak_db": peak,
            "silence_seconds": silence, "warnings": warnings,
            "limitation": "Measurements do not identify setting, thunder, voices or prove a clean recording."}

def prepare_audio(source, destination, duration, fade=2.0):
    """Crossfade repeated copies, then measure and normalize the finished loop in two passes."""
    info = probe(source)
    print(f'Preparing {duration} seconds of crossfaded audio', flush=True)
    length = float(info["format"]["duration"])
    if length <= 2 * fade:
        raise ValueError("Audio is too short for the configured crossfade")
    if length >= duration:
        count = 1
    else:
        import math
        count = max(2, math.ceil((duration - fade) / (length - fade)))
    raw = destination.with_name("audio-loop.wav")
    command = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    # Independent decoders avoid older FFmpeg builds truncating chained acrossfade
    # inputs when every branch is fed by the same asplit output.
    for _ in range(count):
        command += ["-i", str(source)]
    graph = []
    if count == 1:
        graph.append(f"[0:a]atrim=duration={duration},asetpts=PTS-STARTPTS[out]")
    else:
        for i in range(count):
            graph.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        previous = "a0"
        for i in range(1, count):
            output = f"x{i}"
            graph.append(f"[{previous}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[{output}]")
            previous = output
        graph.append(f"[{previous}]atrim=duration={duration},asetpts=PTS-STARTPTS[out]")
    if duration >= 3600 and count > 1:
        # Build one lossless cyclic crossfade rather than opening hundreds of
        # decoders for hours of audio. Independent inputs work on older FFmpeg.
        cycle = destination.with_name('audio-cycle.flac')
        graph = (
            f'[0:a]atrim=start={fade}:end={length-fade},asetpts=PTS-STARTPTS[b];'
            f'[1:a]atrim=start={length-fade}:end={length},asetpts=PTS-STARTPTS[t];'
            f'[2:a]atrim=start=0:end={fade},asetpts=PTS-STARTPTS[h];'
            f'[t][h]acrossfade=d={fade}:c1=tri:c2=tri[x];'
            '[b][x]concat=n=2:v=0:a=1[out]')
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(source),
                        '-i', str(source), '-i', str(source), '-filter_complex', graph,
                        '-map', '[out]', '-ar', '48000', '-c:a', 'flac', str(cycle)], check=True)
        subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-stream_loop', '-1',
                        '-i', str(cycle), '-t', str(duration), '-ar', '48000',
                        '-c:a', 'pcm_s24le', '-rf64', 'auto', str(raw)], check=True)
    else:
        subprocess.run(command + ["-filter_complex", ";".join(graph), "-map", "[out]", "-ar", "48000",
                                  "-c:a", "pcm_s24le", '-rf64', 'auto', str(raw)], check=True)
    print('Measuring the complete audio loop', flush=True)
    source_report = audio_report(source)
    report = audio_report(raw)
    report["original_source"] = source_report
    measured = report["loudness"]
    if any(str(measured[k]).lower() in {"-inf", "inf", "nan"} for k in ("input_i", "input_tp", "input_lra", "input_thresh")):
        raise ValueError("Audio is silent or invalid; cannot normalize")
    normalization = (f"loudnorm=I=-20:TP=-2:LRA=7:measured_I={measured['input_i']}:"
                     f"measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
                     f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:"
                     "linear=true")
    print('Normalizing the complete audio loop', flush=True)
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
                    "-af", normalization + f",afade=t=in:d=3,afade=t=out:st={max(0,duration-3)}:d=3",
                    "-ar", "48000", "-c:a", "pcm_s24le", '-rf64', 'auto', str(destination)], check=True)
    print('Checking normalized audio loudness and peaks', flush=True)
    report["normalized_output"] = audio_report(destination)
    actual = float(probe(destination)['format']['duration'])
    report['output_duration_seconds'] = actual
    if abs(actual - duration) > 0.1:
        raise ValueError(f'Prepared audio duration {actual} does not match target {duration}')
    write_json(destination.with_suffix(".quality.json"), report)
    raw.unlink()  # Reclaim the multi-gigabyte intermediate before video muxing.

def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("run/audio-quality.json"))
    args = parser.parse_args()
    write_json(args.output, audio_report(args.file))
    print(args.output)

if __name__ == "__main__":
    main()
