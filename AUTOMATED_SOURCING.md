# Automated anime rain asset sourcing

The new `Source Anime Rain Assets` workflow finds and downloads candidates without
manual browser downloads or tagging forms. It is separate from daily publishing.
The existing monthly audio-cache workflow and legacy Pexels discovery workflow
remain unchanged. This implementation is on codex/asset-quality, not deployed.

## What runs automatically

- Pixabay animation searches use the exact-reference-inspired illustrated queries.
  Candidates must have rain/anime and study/cat/room/window hints, native 1080p,
  a 5–180 second duration and a selected download no larger than 80 MiB.
- Freesound searches use the indoor/window/soft-rain queries and CC0-only filters.
  Candidate recordings must be 45–900 seconds. Titles/tags mentioning thunder,
  voices, music, traffic, forest/leaves, tents or metal roofs are excluded. These
  filters do not prove the absence of those sounds. HQ MP3 previews are downloaded;
  these are compressed previews, not the original recordings.
- Each provider gets at most two searches per run. Queries/pages rotate and
  responses are cached for 24 hours. The default limit is three new files per
  provider, adjustable to seven. The acquisition budget is 15 minutes; full decode
  checks have individual time limits. This does not guarantee finding enough
  matching assets for daily use. Do not use it for mass harvesting; Pixabay's
  [API rules](https://pixabay.com/api/docs/) prohibit systematic mass downloads.
- Existing source IDs and exact file checksums are skipped, including renamed
  duplicates. The cumulative private checkpoint prevents repeat downloads on
  subsequent successful hosted runs. This is exact duplicate detection, not
  perceptual detection of re-encoded copies.
- Every download gets a complete decode check, measured dimensions/duration,
  source URL, creator, provider metadata snapshot, licence URL and checksums.
  Metadata evidence is not a downloadable licence certificate or ownership proof.
- Media and evidence go into a new release in the confirmed private repository
  `shmop/rain-sounds-assets`. The checkpoint is published only after both the
  media/evidence bundle and state have transferred. Failed transfers leave a draft
  release and do not advance the next run's checkpoint. Old releases are preserved.
  No source-media artifact is uploaded to the public pipeline repository.

## One-time setup

In gigicolac/rain-sounds-automation → Settings → Secrets and variables → Actions:

1. Secret `PIXABAY_API_KEY`: the user's Pixabay API key (presence verified
   2026-10-01; its live validity has not yet been tested).
2. Secret `SOURCING_ASSET_TOKEN`: a separate fine-grained GitHub token restricted
   to `shmop/rain-sounds-assets`, with repository Contents read/write. Keep the
   existing `CHANNEL_ASSET_TOKEN` read-only for the daily rendering workflow.
3. For audio: secret `FREESOUND_API_KEY` (already present), and variable
   `FREESOUND_COMMERCIAL_ACCESS_CONFIRMED=true` only after applicable commercial
   API access has been arranged. The [API access terms](https://freesound.org/help/tos_api/)
   are separate from each recording's CC0 licence. Until then, select video only.

After workflow deployment, a manual run defaults to video-only and three new
files. A scheduled run is skipped unless variable `SOURCING_ENABLED=true`.
Once enabled it runs Mondays at 02:00 UTC, or Monday 12:00 Sydney standard time /
13:00 Sydney daylight-saving time. Variable `SOURCING_PROVIDERS` chooses video,
audio or both; default video. Scheduled runs still require merge approval because
GitHub schedules use the default branch. No variables or schedule activation were
changed during implementation.

Local use, with provider keys supplied through environment variables:

```powershell
python scripts/source_assets.py --providers video --limit 3
```

Local batches/state stay in ignored `run/sourcing/` and `run/sourcing-state.json`.
Add `--store-private` to restore the hosted checkpoint and upload a private release.
Source results always link to the provider's source page, as Pixabay requests.

## Candidate queue versus publication

New finds are labelled candidates with content verification and publication
approval false. Existing chosen assets and their reviews are untouched. This
implements sourcing, downloads, provenance and technical checks; it does not
automatically add arbitrary search results to the fixed channel profile or alter
the daily publisher. No per-item tagging form is introduced. Search tags cannot
reliably identify the exact art style or detect voices, music or thunder.

The 30-day ready-upload queue and strict component non-repetition remain separate
proposals in ASSET_SOURCING.md. This candidate cache must not be presented as that
ready queue. The publisher still prevents reuse of a source pair; sourcing
prevents repeat acquisition of the same ID/file. New candidates need a content
selection mechanism before unattended publication can use them.

## Validation

56 project tests passed, including six new sourcing tests covering 24-hour cache,
licence filtering, ID/file duplicate handling, original-library preservation,
private-destination checks, redirect checks and failed-transfer checkpoints.
All five workflow files parsed. Real decode checks passed for study-room.mp4 and
695619.mp3. Provider search/download and private transfer are not yet live-tested;
the writing token and commercial audio-access setup are still pending.
