# Asset quality and illustrated scenes

Implemented on `codex/asset-quality`, based on `origin/main` at `fe4d2ce`.
Pending review; not deployed. No video was uploaded during implementation.

## Resulting behavior

- Curated selection uses exact records in `data/video_library.json`. Pexels links
  are refreshed by the same identifier; unavailable sources fail without substitution.
- `asset_selection=search` is preview-only. `video_id` and `audio_id` pin the source
  pair. `visual_style` filters reviewed illustrated/live_action labels.
- Native source minimum: 1920 by 1080 pixels and 10 seconds. Metadata is filtered
  during discovery/import; the downloaded video is checked again before rendering.
- Publication requires dated notes, complete labels, full playback and loop checks,
  media-quality checks and video source/license review. Legacy approvals remain
  preserved but incomplete records cannot qualify for automatic publication.
- Matching uses setting, intensity, audible surface and perspective. Rotation favors
  fewer individual repeats in the last seven uploads, then less-used settings,
  then lower lifetime usage. Existing reserved pairs and history remain protected.
- Preview no longer enforces the one-new-upload-per-date rule or reserves history.
  Curated selection still excludes previously reserved pairs.
- Audio discovery adds up to 12 candidates per run across six categories, with
  rotating queries/pages, even when the old pool has reached 28. Candidates stay
  unapproved. Existing files and reviews are preserved.
- Audio repeats use two-second crossfades and measured two-pass loudness
  normalization, with opening/ending fades. Reports include source/output
  measurements, near-full-scale peak warnings and silence intervals.
- Video repeats use a one-second dissolve. `VIDEO_CROSSFADE_SECONDS=0` disables it
  for authored seamless loops; allowed range is 0–2. Dissolves can ghost moving
  objects, so inspect the rendered loop before approving.
- No new production Python dependency. Local rendering requires FFmpeg and ffprobe.

## Illustrated sources

Pexels has [animated lofi](https://www.pexels.com/search/videos/animated%20lofi/)
and [anime rain](https://www.pexels.com/search/videos/anime%20rain/) searches.
Search terms are hints, not proof of style or quality.

Specific external candidate, NOT downloaded or approved:
[Pixabay illustrated study-room loop](https://pixabay.com/videos/anime-cozy-rain-rainy-night-330062/).
Its page marks it as AI-generated and lists 2560 by 1440 resolution. Chrome
blocked the download during this session. Download, playback, loop and license
review are still required. Do not assume actual Lofi Girl channel footage is reusable.

## Discovery and review

Run commands from this task checkout, using its Python environment:

```powershell
python scripts/discover_assets.py discover --style illustrated --limit 12
python scripts/fetch_audio_pool.py
python scripts/review_assets.py page
```

Discovery requires `PEXELS_API_KEY` and `FREESOUND_API_KEY`. The review page does not.
Never put credential values in chat or Git.

The new **Discover Review Candidates** workflow uses existing repository secrets
and returns catalogs/audio as an artifact, without publishing or committing them.
It must be available on GitHub before use. Extract its artifact into a separate
folder, then merge new candidates without replacing existing reviews:

```powershell
python scripts/review_assets.py import-candidates "C:\path\to\extracted-candidates"
python scripts/review_assets.py page
```

The monthly audio workflow will add up to 12 new candidates per run after merge,
rather than topping up to 28. It still commits additions, now including the
discovery cursor. Repository storage can grow; this implementation deletes nothing.

Open `run/asset-review.html`. Play complete sources and inspect loop boundaries.
The form provides labels, explicit checks, notes and decisions. Only changed cards
are exported. Apply the downloaded review file with:

```powershell
python scripts/review_assets.py apply "C:\path\to\asset-reviews.json"
```

Incomplete approvals fail with the missing requirements. Pending/rejected records
may keep unknown fields. Rejected assets are excluded even from automatic preview.

Labels:
- setting: forest, city, roof, window, tent, lake, garden
- intensity: gentle, moderate, heavy
- surface: leaves, glass, metal, fabric, water, ground, mixed
- perspective: indoors, sheltered, outdoors
- video style: illustrated, live_action
- audio events: thunder, traffic, animals, music, voices; true/false, with unknown omitted

Video surface/perspective describe the sound appropriate to the depicted view.
They do not describe an unchecked original soundtrack. A sheltered window view
should not automatically pair with an exposed outdoor recording.

Measure a complete recording separately:

```powershell
python scripts/media_quality.py audio/695619.mp3 --output run/695619-quality.json
```

Measurements cannot certify setting, absence of voices, or clean content.
The initial target of 12 reviewed videos and 12 recordings across four categories
is NOT yet completed.

## Import a separately licensed animation

Save the downloaded file under this checkout, e.g. `scenes/study-room.mp4`:

```powershell
python scripts/discover_assets.py import-local --file scenes/study-room.mp4 --asset-id local:study-room --source-url "https://source-page" --license-url "https://license-page"
python scripts/review_assets.py page
```

Video files remain ignored by Git. Local imports support local previews; hosted
runners need a separately arranged asset storage/download step because ignored
local files are not present there. Curated Pexels records work remotely.

## Exact local preview

```powershell
$env:PIPELINE_MODE = "preview"
$env:ASSET_SELECTION = "curated"
$env:VIDEO_ID = "local:study-room"
$env:AUDIO_ID = "695619"
$env:DURATION_MINUTES = "2"
$env:VIDEO_FONT = "C:/Windows/Fonts/arialbd.ttf"
python scripts/select_assets.py
python scripts/build_video.py
python scripts/make_thumbnail.py
```

Set `FFMPEG` and `FFPROBE` if the executables are not on PATH. `run/assets.json`
explains the matched labels and rotation score. Pinning identifiers fixes the
source pair, not upstream bytes forever; re-review changed source content.

## Validation and limitations, 2026-09-29

- Existing recovery/authorization tests and new quality/discovery/rotation tests
  pass; final count is reported in the completion message. All four workflow files
  also parse successfully. The parser was installed only under ignored test output.
- Real local FFmpeg render: 20 seconds, 1920 by 1080, video and audio. Synthetic
  motion and an eight-second noise recording exercised multiple audio repeats
  and a video repeat. Inspected the rendered title frame.
- Measured full existing recording 695619: no detected silence intervals or
  near-full-scale peak warnings. This is NOT listening approval.
- Review form opened in Chrome with the six preserved recordings.
- Live discovery not run: local credentials are absent. Pixabay download blocked
  by Chrome. No illustrated clip is approved or included yet.
- No hosted preview, live upload or live resume test was run.
- Portable media tools, reports and test media remain under ignored `run/`.
