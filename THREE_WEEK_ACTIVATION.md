# Three-week approved asset activation

This activation selects the 27 approved scenes and 27 approved sounds from the
23 October 2026 review batch for future scheduled videos. Pass/spare candidates
remain recorded but are excluded from the active profile. The previous media,
catalogue records and private releases are preserved for recovery.

Video exclusions:
- 03 Greenhouse: awkward rain on the smaller panes.
- 18 Orchard: awkward fruit trees.
- 25 Cottage dog: mug has two handles.

Audio exclusions: 14 Cedar bedroom, 16 Station cottage dog and 25 Cottage dog.
The user separately confirmed complete 90-second playback and repeat-boundary
review for all 27 approved sounds before export. The library records the new
confirmation without removing earlier decisions or changing media.
`data/three_week_review_decisions.json` preserves the exact checksums and reviews.

## Bundle and selection

The staged bundle contains 69 files: 27 new scene loops, 27 new lossless audio
masters and the 15 existing scene/audio files. The active profile contains only
the new approved collection. Existing catalogue entries and original audio
records remain present; pass/spare media stays in the local review library.

The private destination is the existing `shmop/rain-sounds-assets` repository,
release `three-week-approved-2026-10-23`. Bundle size: 679,340,707 bytes.
SHA-256: `22a7ca3a535f24bb0d64e7fc7c2000f203cce3a72ba19bf5fbd5e9c2bccea987`.
The uploaded asset is `668577853`, recorded in `data/channel_storage.json`. The private upload completed successfully; hosted restore verification follows.

`package_custom_scenes.py` now verifies the master file selected by each package,
including `master-clean.png`, and preserves existing manifest members when
building the combined archive. It still rejects altered approved media and
exports only explicit approved, package-checked scenes.

## Verification and deployment

Local validation passed 113 tests, including new clean-master and legacy-bundle
preservation regressions. The bundle restored into a clean staging folder;
all member checksums, 27-by-27 eligible source combinations and pass exclusions
were checked. The earlier user-reviewed video revisions and audio masters are
used directly, without regeneration. Hosted preview and deployment evidence
will be recorded here after completion.

The existing schedule, duration, upload visibility, reservations and history
remain unchanged. Preview mode creates no YouTube upload. Activation changes
future default selections after the activation pull request merges into main.

For recovery, revert this activation's catalogue/profile/storage changes to
return to the previous immutable bundle. Do not delete upload reservations or
restore old history. Local review media remains under
`run/20261023-three-weeks/`; activation staging and verification records are in
`run/activate-three-week-20261023/` in the generating checkout.
