# Generated-only channel migration

Prepared on 29 October 2026 for `UCaMtUdYVy9bIW1xYsWJHjXg`
(`@calming_rain_soundss`). This branch is not deployed. Main and live settings
have not been changed; the old daily schedule may still run until deployment.

## Requested behavior

- Keep three-hour videos, illustrated visuals, render/thumbnail/title settings,
  review workflow, private storage, upload recovery and processing verification.
- Build Monday, Wednesday and Friday at 11am Australia/Sydney. Public release
  uses the existing America/New_York slots: Monday/Wednesday noon, Friday 11am.
  Other days are skipped even after a delayed or manual scheduled build.
  Manual immediate/private/unlisted controls remain explicit overrides.
- Use generated visuals and entirely procedural audio. Recording-based custom
  mixes and stock downloads are excluded. Monthly stock-audio fetching is disabled.
- Each visual and audio source is single-use across both channels, even in a
  different pairing. Reservations and uncertain transfers also count as used.
  Within-video looping/crossfades are preserved.

## Persistent exclusions and provenance

`data/content_exclusions.json` quarantines all 45 existing catalogue visuals,
all 42 existing audio entries and assets from all 27 recorded uploads/reservations
at history revision `eacf8d73c5ec8670168e7e9122f76d085590955a`. This deliberately
also excludes existing unused catalogue items until their history can be verified.
No media, source catalogue, review decision or upload reservation was deleted.
The user's approximate 121 external clips were not verified as a catalogue count;
all external clips are rejected by the provenance gate regardless of count.

New selection and upload reservation both enforce exclusions. Checks use asset
identities, recorded file hashes, visual master hashes and procedural seed plus
generator hashes. Upload additionally verifies actual source file hashes and dated
full-playback/loop approval. Renaming a file or changing its partner does not clear
exclusions. This is exact-content and recorded-lineage protection, not perceptual
similarity detection: new candidates still need human review for close similarity.

Legacy search/curated controls cannot bypass this gate, including private tests.
Old or unidentified uploads cannot resume or receive comments from the new channel.
The original shared upload ledger remains in use; changing/deleting channels does
not reset it. New reservations record the target channel explicitly.

## Current review batch

Theme: **dense rain heard from a sheltered window**. These are sound-design
intentions, not verified field-recording claims. Three original, 90-second stereo
candidates compare soft/dense, full/steady and closer rain detail. Each uses fresh
procedural events with no downloaded recording layers. Each has a full listening
copy, lossless master, two-second crossfade audition, checksum, recipe and technical
report. All three passed duration/peak checks, with no detected silence warnings.
No listening approval has been inferred from those measurements.

Reproduce into a new directory:

```powershell
python scripts/create_window_rain_review.py --output run/window-rain-review-NEW
python scripts/rain_audio_library.py --library run/window-rain-library-NEW import run/window-rain-review-NEW
python scripts/rain_audio_library.py --library run/window-rain-library-NEW serve --audio-root run/no-recording-sources
```

The current preserved local review collection is `run/window-rain-library-20261029`.
Use the existing Rain Atelier controls to listen, write notes and choose approve,
pass/spare or reject. Full playback and repeat-boundary checks are separate.
Nothing is staged or published by a review decision.

### Review outcome, 29 October

The user rejected all three sheltered-window candidates. Their files and decision
history remain preserved in the local library, with status `rejected`.
The preferred direction is now **heavy, dense forest rain**. Two existing exact
references were copied into the same review library, preserving their previously
recorded approvals and full-playback/loop checks:

- `custom-audio:three-weeks-20-ranger-storm`: Ranger cabin shelter;
  historical notes "heavy, dense, foresty".
- `custom-audio:three-weeks-30-woodland-night`: Woodland night shelter;
  historical notes "heavy, forest, great".

Both have intended heaviness `heavy` and environment `forest`. Both include
downloaded recording `651189`. They are explicitly marked **reference only** and
remain quarantined from new-channel publishing. The source recording itself has
reviewed heavy/forest labels and the note "sounds solid". This preference does not
authorize lifting the generated-only or already-used exclusions.
The audio direction in the channel profile records this preference. Seven timed
publishing tests passed again: the next enabled public-release slot is used,
including after delays and daylight-saving changes; scheduled public uploads
carry private visibility plus `publishAt`. No live schedule or visibility changed.

### Original forest synthesis attempt

At the user's request, `scripts/create_forest_rain_review.py` now prepares three
new 90-second experiments: broad steady downpour, denser leaf texture and deeper
canopy rain. A continuous spectrally shaped wash, overlapping unpitched splash
grains and irregular density envelopes replace the prior transient-only approach.
The script reads no recording files. It uses the already available local NumPy
installation; no dependency was installed or added to the publishing environment.

Masters, listening copies and recipes are preserved in
`run/forest-rain-attempt-20261029`. All three were imported into the existing
Rain Atelier library as **pending**, each with a repeat-boundary audition.
Historical reference approvals and the three rejected window candidates remain
unchanged. These experiments have not been heard/approved by the assistant or user.

Verification: all three masters are 90 seconds, have distinct hashes, procedural
provenance, no detected silence or measurement warnings, and measured peaks below
-11 dBFS (decibels relative to full scale). A small synthesis check confirmed
finite stereo output, exact length, deterministic same-seed output, distinct
different-seed output and independent stereo variation. `git diff --check` passed.
These measurements do not establish perceptual quality. Timed publishing and the
publishing pool were not changed by this generation/review operation.

### Droplet-detail revision

The user found the forest attempt better, but too constant/static-like. The target
is dense rain with audible individual droplets, as in the approved references.
That feedback is saved on the three earlier forest candidates; their status stays
pending. It does not imply rejection, full-playback/loop approval or publishing
approval. The channel audio direction now records the requested droplet detail.

`create_forest_rain_review.py --revision droplets --seed 2026102920` adds three
alternatives (4–6): layered individual droplets, clearer close leaf droplets and
dense varied droplets. The bed is quieter, with fewer/more distinct foreground
events, fast varied attacks, varied noisy splash tails, event-to-event loudness
variation and shared stereo panning. No recording files or pitched oscillators
are used. Each new candidate is 90 seconds and remains pending.

Final packages are in `run/forest-droplet-revision-v2-20261029` and imported into
the same local library under vibe `droplet-revision`. Earlier packages remain
preserved. An initial render exposed pre-master PCM (Pulse Code Modulation)
clipping on sharp impacts; it was not imported. The final render scales peaks
before conversion, then measures and masters normally. All three final source
waveforms stayed below 0.951 full scale before mastering. Duration, procedural
provenance, final peak/silence checks and `git diff --check` passed. Listening and
loop approval remain required; scheduled publishing is unchanged.

## Required before activation

1. Inventory both channels, including private, unlisted and scheduled videos.
   Match uploads to asset sources or keep uncertain items excluded. The new public
   channel page showed no content on 29 October; that does not establish the private
   inventory. Preserve the exclusion snapshot even if the old channel is deleted.
   `history_reconciled` deliberately remains false until this is evidenced.
2. Review this audio batch and create/review fresh matching visuals. Existing
   catalogue media is quarantined; no complete eligible publishing pair exists yet.
3. Export/stage only approved candidates, restore/check the source bundle, upload
   the updated private bundle and update its configuration through normal review.
4. Authorize the new channel using the existing local login helper, with
   `--expected-channel-id UCaMtUdYVy9bIW1xYsWJHjXg`. Replace the three `YT_*`
   repository secrets together and update the expected-channel repository variable.
   Do not paste credentials into chat. Both publishing workflows explicitly target
   the new ID and reject credentials belonging to a different channel.
5. Run verify and a non-publishing preview on the task branch after new assets and
   storage are ready; inspect/listen to the rendered artifacts. Merge requires the
   user's explicit approval. A live upload also requires authorization.

Deleting the old channel is not a prerequisite for reuse of content you own:
[YouTube permits manual re-upload to another channel you manage](https://support.google.com/youtube/answer/2404846).
However deletion does not provide a copyright or monetization clearance; original
and materially varied content is still required by
[YouTube's monetization policies](https://support.google.com/youtube/answer/1311392).
No deletion or reuse has been authorized here.

## Validation

The 148-test suite passed with UTF-8 enabled and local network access for the
existing review-server tests. After the final changes, all 26 affected tests
passed: 11 generated-content safeguards, 10 comment/settings tests and five
audio generation/staging tests. `git diff --check` also passed. Rain Atelier was
opened and visibly showed the three pending candidates and loop-audition controls.
The first sandbox run was limited by local socket permissions and Windows text
encoding; those environmental failures were resolved for the verified run.
No hosted video preview or live upload has been performed: the lack of an eligible
pair is an intentional safety stop, not a successful rendering/publishing claim.

### Soft trickles revision

The user rejected revisions 4-6 for harsh, tarp-like impacts and static. Their
statuses and exact feedback are saved; the media remains preserved. The new
request is for softer, rounder, trickling water-like droplets.

Two 90-second experiments (7 and 8) are now pending in the same local library,
under vibe `soft-trickles`: soft leaf trickles and rounded water droplets.
The synthesis uses smoother event envelopes, muted noise textures, clustered
arrival patterns, quiet damped water resonances and a minimal continuous bed.
It does not read or blend downloaded recordings. Unlike the earlier unpitched
noise-only attempts, this experiment includes short synthesized water resonances.

Reproduce using `create_forest_rain_review.py --revision trickles --seed 2026102930`
with a fresh output directory. Current packages are preserved in
`run/forest-soft-trickles-20261029`. Both passed duration, peak, silence, raw
pre-master headroom, procedural-provenance and unique-checksum checks. A small
synthesis check also passed for deterministic output, different seeds, finite
samples and stereo duration. Technical checks do not establish naturalness.
Full listening and loop approval remain pending. Timed publishing is unchanged.

### Return to forest attempts 1-3

The user rejected soft-trickle revisions 7-8 and requested comparison of the
original forest attempts 1-3 against approved Ranger cabin shelter and Woodland
night shelter. Revisions 7-8 are now rejected in the local library. The original
forest attempts remain pending; no approval was inferred. Those five comparison
assets now share the local library vibe `comparison`. No new sounds were generated.

Objective measurements over seconds 10-40, decoded to mono at 24 kHz, are in
`run/forest-reference-comparison.json`. The references have about 20.4 percent of
spectral energy above 6 kHz versus 3.4-5.8 percent in forest attempts 1-3. Their
10-millisecond energy variation is modestly greater: 95th-percentile/median ratios
1.183-1.197 versus 1.154-1.171. Both reference mixes share recording 651189, so they
are not independent examples of natural rain. These measurements support retaining
fine spectral detail and subtle variation; they do not establish naturalness or
prove that a particular synthesis method will match the references. Increasing
sharp foreground impacts or simply darkening the whole sound did not satisfy the
user's listening review. The current baseline is attempts 1-3, not revisions 4-8.
Scheduled publishing and all source-use exclusions remain unchanged.

### Archive rejected candidates and retry from the original forest baseline

At the user's request, eight rejected candidates were removed from the active
Rain Atelier registry. Their complete records and decisions are preserved in
`run/window-rain-library-20261029/archived-rejections.json`; their media packages
remain available on disk. The approved references and original forest attempts
1-3 remain active. Nothing was permanently deleted or marked approved.

Two new 90-second candidates (9: fine forest detail; 10: gently shifting rain)
were created using `create_forest_rain_review.py --revision fine --seed 2026102940`.
These return to the original spectral wash and softly enveloped splash approach,
with more fine high-frequency detail, a modestly larger texture contribution,
and slightly more varied slow density. The sharp-impact and water-resonance
approaches of the rejected revisions are not used. Source recordings are not read.
Packages are in `run/forest-fine-retry-20261029`. Both passed duration, final peak,
silence, procedural provenance and pre-master headroom checks. Both are pending
in the active library under `fine-forest` and `comparison`. This remains an
experimental attempt requiring listening and loop review. Timed publishing and
publishing eligibility have not changed.

### Measurement-driven synthesis

The user requested approved-reference and YouTube audio analysis after finding
revisions 9-10 still too static-like. See `RAIN_PROFILE_ANALYSIS.md` for methods,
source links, measured differences, limitations and new candidates 11-12.
Both are pending in the local library under `measured-rain`. No recordings are
embedded in the output; only statistical targets guide fresh stochastic synthesis.
Revisions 9-10 remain pending with the user's feedback preserved. No new approval
or rejection was inferred. Publishing configuration and eligibility are unchanged.

## Final launch setup

See NEW_CHANNEL_LAUNCH.md for the current recording-based plan, the explicit
651189 reuse/automatic-approval authorization, completed old-channel pause,
new media pool/storage, verified preview, weekly generation automation and
owner-only authorization/activation checklist. Earlier generated-only notes
in this document are historical and superseded by that explicit user decision.
