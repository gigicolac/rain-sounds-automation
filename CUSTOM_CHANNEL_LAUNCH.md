# Custom scene launch — 17 October 2026

Branch: `codex/custom-channel-launch`, based on `origin/main` at `2d64943`.
Includes the previously unmerged presentation work from `26ac22d`.

## Resulting behaviour

Channel selection uses seven custom animation clips whose exact files were
approved in the local scene library: 01-girl-apartment (source-warp v5),
02-girl-cabin, 03-boy-attic, 04-boy-library, 05-girl-cat, 09-cat-dog and
10-mug-window. Rejected scenes and the spare hearth scene are excluded.
`package_custom_scenes.py` verifies the master and approved preview checksums
before copying. No new content labels or rights-review claims are inferred.

The new bundle is stored in the existing private `shmop/rain-sounds-assets`
repository under release `custom-scenes-2026-10-17`. The user explicitly
approved this private upload. Old bundles and catalogue records remain intact.
The checked-in profile selects only the custom scenes; missing custom files
fail without falling back to the previous pool. The existing restore step and
checksum manifest supply the clips to the daily runner.

Titles have six themes and 36 short options at each duration, checked against
all recorded and reserved titles. Themes are sleep, study, unwind, cozy, just
rain and rain breaks. No numbered-session fallback or invented setting is used.
Exhaustion stops selection until the catalogue is expanded. At three hours,
all generic titles are at most 60 characters. Titles and headlines share a theme.

Thumbnail text uses two words and a duration badge over the actual video frame.
Three treatments are produced: cream lettering, amber accent lettering and a
dark panel. Text side is recorded per scene to keep subjects clear. The selected
treatment avoids the previous recorded treatment; all three JPEG alternatives
are included in debug artifacts. Only the selected thumbnail is uploaded.
This does not start a native YouTube title/thumbnail experiment.

Scheduling, three-hour defaults, visibility controls, upload reservations,
processing verification and source-pair duplicate checks retain their existing
behaviour. Seven scenes with three current audio tracks provide at most 21 new
source pairs; reservations also count. Expand reviewed assets before exhaustion.

## New audio candidates

`create_custom_audio.py` creates two wholly procedural rain sound designs and
four blends of procedural texture with approved Creative Commons Zero recordings
695619 and 651189. It reuses the existing crossfade/normalization preparation for
recording loops, and saves seeds, component provenance, source/output checksums,
technical reports, lossless masters and MP3 listening copies. No new dependency.

These are listening candidates, not approved rain recordings. They are not in
`audio/metadata.json` or the channel's `audio_ids`, so public runs still use the
three existing tracks. Listen through the full 90-second candidates, including
the 59- and 75-second source boundaries; approve preferred mixes before adding
them to the private media bundle and publishing pool. `stage_custom_audio.py` requires explicit dated full-playback and loop approval, preserves legacy metadata, adds distinct custom audio identities, and builds a combined scene/audio bundle. Pending derived audio is blocked from public selection even if accidentally added to the profile. Upload the staged bundle to the same private store and update the storage checksum before deployment. Do not transfer source
review approval automatically to a derived mix.

Reproduce locally, using a fresh output folder:

```powershell
python scripts/create_custom_audio.py --output run/audio-review-new --duration 90
```

## Validation and deployment status

- 77 automated tests passed with the project's Python environment. Windows
  sandbox temporary-directory permissions prevented the first run; the same
  suite passed outside that restriction.
- Local 60-second custom apartment preview: complete decoding, 1920x1080,
  exactly 60-second audio and video, no black intervals, final quality gate passed.
- Thumbnail contact sheets and the actual preview thumbnail inspected visually;
  text moved to the right for six scenes to preserve subjects.
- Audio candidates require human listening; technical measurements cannot
  establish realism or an audible improvement.
- Hosted preview [38985344992](https://github.com/gigicolac/rain-sounds-automation/actions/runs/38985344992) succeeded at scene/packaging commit `647990d`. It restored the new private bundle and rendered the custom apartment scene without uploading to YouTube.
- Pull request [7](https://github.com/gigicolac/rain-sounds-automation/pull/7) awaits merge approval. Scheduled production is unchanged until merge.

After merge, scheduled runs use the custom pool and new presentation system.
Before merging, fetch current main and rerun affected checks if it changed.
For recovery, use the previous profile, storage configuration and manifest from
`2d64943` together. Preserve the shared `pipeline-history` ledger in all cases.
