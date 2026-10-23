# Three-week asset batch — 23 October 2026

Requested scope: **30 new animated scene assets and 30 new rain-sound assets**,
grouped into three weeks with ten of each per week. These are reviewable source
loops, not thirty completed three-hour uploads.

## Local outputs

The collection is under `run/20261023-three-weeks/` in this checkout:

- `index.html`: paired weekly gallery, with video, full sound and boundary players.
- `week-1-contact.jpg` through `week-3-contact.jpg`: ten scenes per sheet.
- `scenes/`: original image masters, clean revisions where needed, animation
  settings, 1920 × 1080 ten-second silent loops at 24 frames per second,
  frame samples, checksums and package reports.
- `audio-library/`: Rain Atelier collection with thirty reviewed sounds, each
  including a 90-second lossless master, listening copy, ten-second repeat
  audition, source provenance, exact recipe and technical report.
- `manifest.json`, `audio-manifest.json`, `validation.json`: inventory and checks.
- `audio-generation/`: preserved generation inputs and intermediate outputs.

Original image masters remain intact when a clean revision is selected. The
cleanup replaces visible flames with electric lamps and removes baked-in rain
marks so animated weather is not mixed with frozen streaks.

## Sound range and provenance

The batch has **13 light, 9 moderate, 5 changing and 3 heavy** candidates.
Each week includes light, moderate, changing and heavy recipes. Intent labels
cover window, cabin, forest, lake and city treatments and several moods.

These are thirty new custom mixes using **three previously approved Creative
Commons Zero recordings**, with generated sparse texture, distinct seeds,
different density curves, filtering and balance. They are not thirty new field
recordings. Environment and heaviness labels remain design intentions pending
listening. City material can contain traffic and a siren. No roof/tent source
was substituted where a suitable approved recording was missing. The rejected
pure-synthetic Light Shower and Sparse Drizzle recipes were not used.

## Review

### Future sound preference — user feedback, 23 October 2026

Prioritize more sounds like **10 — Library in the downpour**
(`custom-audio:three-weeks-10-storm-library`). The user specifically likes
its **heaviness and full, dense sound**. Use this exact candidate as a sonic
reference for future batches while varying environments and intensity movement.
Fullness is the desired texture; retain the earlier avoidance of unnatural
static-like droplets and excessive wind/boomy rumble.

The user further requested **fewer light, puddle-like and traffic-heavy
sounds**. Weight future batches toward full, dense rain like sound 10;
reduce sparse/light treatments, prominent puddle splashes and urban traffic
textures. This is a preference for fewer of those styles, not a blanket ban
or a rejection of existing assets. Preserve variation in environments and
intensity movement within the fuller rain direction.

Reference recipe: `forest-downpour`, source `651189`, seed `2026102310`,
rate `60`, recording balance `-7.6 dB`, target `-22` loudness units relative
to full scale, high-pass `500 Hz`, low-pass `8101 Hz`, density curve
`[0.597, 0.853, 0.524, 0.901, 0.746]`. Master checksum:
`94a6c0477e5bd1346846cc9ca9a952618dfd7a8141b63bb24f8778bd51ba6336`.

This feedback records a future generation preference; it does not establish
full-track or repeat-boundary checks or change the current approval state.

All new video and audio assets start **pending**. Technical checks do not imply
visual or listening approval. Sound decisions save through Rain Atelier; check
full-track and repeat-boundary review separately. Video decisions use the
existing scene-library command or can be supplied by scene ID in chat.

The video registry is `run/image-scene-library.json`. Its existing review CLI
(command-line interface) is in the scene dependency below; pass this checkout
as `--root`, the scene ID, decision and notes. Approve/pass requires
`--package-checked` after the visual and loop inspection. Rebuild the gallery
after video decisions to refresh displayed states.

For convenience, the paired gallery includes sound players; its audio status
is a snapshot. Rain Atelier is the authoritative live audio decision display.

## Reproduction and dependencies

This branch starts from main commit `80f1735`. It does not merge the pending
audio activation pull request #8 or unrelated title/retry pull request #10.
Local generation reuses these existing checkouts without modifying them:

- Audio: `../rain-audio-refinement`, commit
  `aedd67a34ae95286b88ebed8384769028c1cba5f`.
- Scene animation originally used `../layered-scene-workflow`, commit
  `2d649437e4fbb7b63e6f745e26447e66bedaa0eb`. The pane correction now uses
  the branch-local `scripts/animate_review_scene.py`, adapted from that engine.

Use the root project's Python environment and installed FFmpeg tools:

```powershell
python scripts/create_three_week_audio.py --audio-worktree ../rain-audio-refinement
python scripts/render_three_week_scenes.py --revision panes-v2
python scripts/build_three_week_review.py
python ../rain-audio-refinement/scripts/rain_audio_library.py --library run/20261023-three-weeks/audio-library serve --port 0 --audio-root ../rain-audio-refinement/audio
```

Start the audio server before rebuilding the gallery to include its current
listening-library address. The generated images used the built-in image
generation tool, with a separate call for each scene and cleanup revision.
The prompt set is `data/three_week_image_prompts.json`; the batch brief is
`data/three_week_asset_plan.json`. Master images must be present before rendering.

Generation is resumable; existing candidates are preserved. If a master or
motion settings change after a loop is rendered, use a new revision/output
name rather than treating the old loop as a fresh render.

## Validation and publication boundary

The audio generator checks duration, loudness and peaks. The scene renderer
checks full decoding, dimensions, duration and periodic motion. The gallery
builder verifies exact master/listen/loop/video checksums, unique scene/audio
content, thirty assets of each type and ten pairs per week. It writes the
current evidence to `validation.json`. Frame inspection remains separate from
complete human playback approval.

No media is committed to Git. This batch does not change publishing pools,
private release settings, upload reservations, schedules or YouTube videos.
Nothing in this batch is approved or activated automatically.

### Completed validation

All thirty video loops decoded successfully at 1920 × 1080 and ten seconds,
with periodic motion checked. All thirty 90-second audio candidates passed
their duration/peak checks. The final inventory verified unique image and
audio masters, all media checksums, and ten pairs in each week. The three
contact sheets were inspected. Browser checks confirmed the thirty pending
audio cards, 90-second sound playback, the ten-pair Week 1 filter, and playback
of a ten-second 1080p video. These playback checks did not mark any listening
or visual-review boxes complete.

Current local session links (valid while the servers run):

- Paired gallery: <http://127.0.0.1:60995/>
- Sound decisions: <http://127.0.0.1:58684/>

## Pane correction after video review

The user completed audio decisions: **27 approved and 3 pass/spare**, with no
pending or rejected sounds. `audio-review-completed-snapshot.json` preserves
the registry before animation changes. Its SHA-256 digest is
`8d1b88206f95555ff56eeb93e7e398867b270fc88518b4be239b30f54f5a91a3`.
This correction leaves listening flags, decisions, audio media and artwork alone.

The first video batch used approximate window polygons and a rain particle
field confined to part of the canvas. That left side, lower and transom panes
dry and put some rain over frames. `data/three_week_window_masks.json` now
traces the panes separately for all thirty scenes, including small rear windows
and glazed roof sections. Foreground exclusions protect indoor lamps, plants,
furniture and people. Fully obscured lower panes remain dry. The rain field
spans the whole image and is clipped through the union of these masks.

`preview-panes-v2.mp4` and `animation-panes-v2.json` preserve the previous loops.
Scenes 06, 10, 16 and 27 have a further `panes-v3` edge refinement. Reproduce those with
`python scripts/render_three_week_scenes.py --ids 06-forest-loft 10-storm-library 16-train-dog 27-city-cat --revision panes-v3`;
the remaining scenes use `panes-v2`. Package reports select the current revision.
For a complete fresh rerender with the final geometry, choose an unused revision
name for the entire batch. Reusing an older name with changed geometry fails
before replacing its masks or previews.
Each package includes the binary mask and its checksum, plus a numbered cyan
coverage overlay. `--overlays-only` regenerates the geometry views without
encoding video. Review the artwork against those overlays when adjusting panes;
technical containment proves clipping to the supplied geometry, not that the
geometry matches the artwork. Four sampled frames per rendered loop support
visual checks, while complete playback approval remains a user review step.

Targeted regression checks in `tests/test_rain_window_masks.py` cover every
visible pane, dry frame gaps and foreground exclusions, full-canvas rain and
the periodic rain boundary. The paired gallery preserves current audio states
and links each video to its coverage overlay.

The final thirty packages decoded fully at 1920 × 1080, ten seconds and
24 frames per second. All thirty masks and their encoded 2.5-second samples
were visually inspected. Three targeted tests passed at output resolution;
the old-revision protection was also exercised against an existing mask.
The gallery checksum audit passed for all sixty assets and confirmed ten
pairs per week. Browser verification confirmed revised video playback and
the ten-pair Week 1 filter. `pane-revision-validation.json` records the final
selected revisions, unchanged artwork hashes and unchanged audio registry.
At that check all thirty revised videos were pending human playback approval.

### User video decisions — 23 October 2026

The user approved every revised video except these three pass/spare scenes:

- **03 — Greenhouse tea corner:** rain on the smaller panes looks slightly awkward.
- **18 — Orchard window tea:** fruit trees look slightly awkward.
- **25 — Cottage dog beside the rain:** mug has two handles.

Final video decisions: **27 approve, 3 pass/spare, 0 reject, 0 pending**.
The scene-library review command recorded those decisions and package checks;
`video-review-decisions.json` binds the local decisions to the selected preview
checksums. The paired gallery displays the recorded states. Audio remains
**27 approved and 3 pass/spare**. Approval records the review decision only;
no asset upload, production activation or publication was performed.
