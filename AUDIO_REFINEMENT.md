# Rain audio revision — 17 October 2026

User listening review of the first six candidates: most sounded windy,
static-like and boomy, and the batch was mostly heavy rain without enough
intensity variety. This is revision feedback, not approval to publish them.
Original candidates remain under the custom-channel-launch checkout for comparison.

The revision removes the continuous pink-noise generator and pitched droplet
component. Procedural candidates use seeded unpitched stereo transients with
smoothly changing event density. Blends retain the two licensed recordings,
crossfade their repeats, reduce their contribution, and filter rumble below
450 Hz with two cascaded high-pass filters. The recording bed follows the same
slow intensity curve as the droplet density. Light tracks have lower peak caps
to keep isolated drops from becoming startling.

Six 90-second candidates cover sparse drizzle, a light shower, a light blend,
a changing shower, building rain and moderate rain. Intended integrated levels
range from approximately -36 to -22 LUFS (Loudness Units relative to Full Scale). Candidate
labels describe the design; they are not verified content labels.

The staging and video preparation path now carries an optional `target_lufs`
field for custom tracks. Otherwise the builder would raise every quiet mix to
the existing -20 target. The saved mastering target is the measured candidate loudness after peak limiting, so a quiet approved candidate is not raised later. Legacy tracks retain the default target. Allowed custom
targets are -40 through -20. Targets survive metadata staging, selected-asset
snapshots and preparation reports. Pending candidates remain excluded from public
selection.

Generate a fresh review batch without overwriting earlier outputs:

```powershell
python scripts/create_custom_audio.py --output run/audio-review-v2-final --duration 90
```

Review all six complete listening copies, including changes in density and source
repeat boundaries. Technical measurements can verify reduced low-frequency energy,
level differences and file integrity; they cannot verify that the result sounds
like convincing rain. Filtering the existing heavy recordings may still retain
their heavy-rain texture. If those blends remain unsuitable, lighter source
recordings are needed rather than stronger filtering.

No new media is uploaded or added to the public audio pool by this revision.
Listening acceptance and normal merge approval are still required.

## Validation

- All 81 automated tests passed, including distinct intensity/density settings,
  deterministic seeds, preserved approval gates, staged loudness targets,
  invalid-target rejection and final audio preparation.
- Six complete 90-second stereo files decoded and passed duration/peak checks.
  Measured levels: -36.43, -31.96, -29.07, -26.07, -24.02 and -22.01 LUFS.
- Filtered energy below 200 Hz was approximately 30–34 decibels below each
  file's overall mean level. This verifies the lack of strong low rumble, not
  the absence of every wind-like sound.
- A real 45-second preparation check targeting -36.43 measured -36.57 after
  preparation. No video was rendered or uploaded for this audio-only review.
- Local listening review: `run/REVIEW-AUDIO-V2.md`; lossless files, listening
  copies, component records and measurements: `run/audio-review-v2-final/`.
