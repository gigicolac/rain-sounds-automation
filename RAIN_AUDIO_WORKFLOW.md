# Rain asset creation and review

This is the audio counterpart to the custom scene library: create a package,
listen, categorize it, keep the exact accepted file, then export separately for
publishing. The local browser interface is **Rain Atelier**.

## Open the library

From this task checkout, use the project's Python environment:

```powershell
python scripts/rain_audio_library.py serve
```

Open the local address printed in the terminal. The server listens only on
127.0.0.1. Leave that process running while using the page; stop it with Ctrl+C.
To use another cached source directory, add `--audio-root PATH`. The optional
`--library PATH` goes before `serve` and selects another local collection.
No new Python dependency is required; rendering requires the existing FFmpeg tools.

## Creation and review cycle

1. Expand **Create rain assets**. Pick a preset and a seed, then click
   **Create 90-second candidate**. Change the seed for a different version.
2. The generated package includes a lossless master, listening copy, source
   provenance, recipe, seed, mastering level and technical report. A new render
   always starts **pending**, even if its recipe is based on an approved asset.
3. Listen to the complete player and the separate repeat-boundary audition.
   Note wind-like hiss, boomy bass, unnatural drops, distracting events, intensity
   and scene fit. Technical checks are not a substitute for listening.
4. Write notes, check the listening boxes that were actually completed, then
   choose **Approve**, **Pass / spare**, or **Reject**. Decisions save immediately.
5. Filter the collection by category, heaviness, environment or vibe. Previous
   decisions, rejected files and earlier revisions remain available.

| Category | Meaning |
|---|---|
| Pending | Not yet accepted; excluded from the approved pool. |
| Approved | Accepted sound for the active library. Publishing still requires full-playback and repeat checks. |
| Pass / spare | Usable spare, kept separate from the approved pool. Never silently substituted. |
| Rejected | Retained for reference, excluded from selection and export. |

The two explicit user decisions from this conversation are seeded by exact file
checksum: **Changing Shower approved**; **Light Shower rejected** for static-like,
unnatural drops. Full-playback and repeat checks are not inferred from sound
approval. Other previous candidates remain pending.

## Range and presets

The plan in `data/rain_audio_presets.json` has ten recording-based presets:

- Heaviness: light, moderate, heavy, changing.
- Environments: window, cabin, forest, lake, city, roof and tent.
- Vibes: cozy, sleep, warm, unwind, calm, focus, immersive, dramatic, urban,
  evening and sheltered.

Changing Shower is the reference. The default workflow has no pure synthetic
droplet or continuous pink-noise preset. It blends reviewed recordings with
subtle texture, varies intensity, suppresses low rumble, and preserves each
candidate's quieter mastering level. New output must still pass listening review.

Environment/vibe/heaviness tags are **design intentions**. A window/cabin preset
changes the acoustic treatment; it does not establish that a source was recorded
there. Confirm heard labels separately in the review card. Unknown stays unknown.
Names do not authorize environment claims in public titles.

Forest, lake and city presets use the existing reviewed source records. The city
recording contains traffic and a siren; it must not be described as traffic-free.
Roof and tent presets require suitable reviewed recordings and show **needs
source** until those exist. The old static-like tent recording is excluded.
There is no fallback to unrelated audio. Sources must have recorded Creative
Commons Zero rights, approval and an available local file.

Add/edit presets in the plan to expand the library. Use `source_ids` for exact
cached recordings, or `required_source_setting` to require a reviewed environment.
The existing source catalogue and review tools manage `audio/metadata.json`;
do not approve a recording merely from its filename or search tags.

## Command-line equivalents

```powershell
# Import a previously generated batch; preserve existing decisions.
python scripts/rain_audio_library.py import run/audio-review-v2-final

# Create several variants without touching the publishing pool.
python scripts/rain_audio_library.py generate window-drizzle forest-steady --seed 417 --duration 90

# Record a decision after listening; ASSET_ID is shown in the card details.
python scripts/rain_audio_library.py review ASSET_ID approved --notes "Natural rain; full source and repeat checked" --listened --full-playback --loop-checked
python scripts/rain_audio_library.py review ASSET_ID pass --notes "Usable spare" --listened
python scripts/rain_audio_library.py review ASSET_ID rejected --notes "Unnatural drops"

# Approved pool filtered by intended character; spares must be requested explicitly.
python scripts/rain_audio_library.py pool --heaviness light --environment window --vibe cozy
python scripts/rain_audio_library.py pool --status pass

# Export only approved assets with complete listening and repeat checks.
python scripts/rain_audio_library.py export-ready run/ready-rain-batch
```

## Files, preservation and publishing

The default collection is `run/rain-audio-library/`. `library.json` contains the
review registry and decision history; `assets/` contains each immutable master,
listening copy, loop audition, candidate metadata and quality report. `batches/`
retains generation inputs and outputs. Copy the whole collection to preserve it;
regenerating also requires its original source recordings. Generated media and
local review files are ignored by Git.

Import verifies checksums. Re-import does not reset decisions. Changed files are
blocked; identical audio cannot acquire another identifier to disguise reuse.
Cross-process locks serialize browser/command-line registry writes.

`export-ready` creates a separate candidate batch compatible with
`scripts/stage_custom_audio.py`. Pass/rejected/pending assets cannot be exported
as ready. Staging builds a reviewed media bundle; private upload, storage
configuration and normal merge approval remain separate operations. This library
does not modify the daily audio pool, upload to YouTube, or change reservations.

## Validation

All 89 automated tests passed. The suite covers review-state transitions,
re-import preservation, checksum and duplicate protection, filtered pools,
ready-only export, source requirements, and the local review/generation API.

The local collection was populated with the six earlier candidates and four new
90-second variants. The browser created the cabin variant through the actual
creation button. Full-track playback was checked in the browser; this verifies
player operation, not an additional sound approval. Missing roof audio produced
an explicit needs-source result. User-approved/rejected decisions were retained.

## Completed sound review

The user completed the collection review on 17 October 2026: eight approved,
two rejected, no pending or spare assets. Exact checksums and the user's notes
are saved in `data/rain_audio_review_decisions.json`.

Sparse Drizzle was rejected as too sparse/odd; Light Shower was rejected for
static-like, unnatural droplets. The recording-based blends were accepted,
including muffled puddle sounds, leaves, closer rain and the urban variant's
wind/traffic. Use those notes when creating future candidates; wind/traffic is
context-specific rather than universally forbidden. Full-source and loop boxes
were unchecked at this snapshot; publishing readiness remains unconfirmed.
