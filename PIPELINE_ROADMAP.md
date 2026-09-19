# Pipeline roadmap and review guide

Work on `codex/pipeline-review-controls`; do not merge until reviewed.
Based on the authorization repair and 5–8 minute test changes.

## Six major steps

1. Manual controls — implemented: scene query, cached audio identifier, title, duration.
2. Reviewed asset labels — structure implemented; listening and visual review still required.
3. Compatible selection and titles — conservative rules implemented, not machine understanding.
4. Permanent upload history — implemented on a dedicated `pipeline-history` branch.
5. Duplicate protection and safe recovery — reservation, source-pair blocking, one new upload per date, shared concurrency, and resume implemented.
6. Processing verification — implemented: rejection fails; pending times out after 15 minutes; success includes actual visibility.

## Reviewing without publishing

Run Daily Rain Video on this branch with mode `preview` (default).
Optional fields: scene_query, audio_id, title, duration_minutes (whole number 1–8).
Blank duration chooses 5–8 minutes. Preview creates no history reservation and
uploads nothing to YouTube. Download the preview artifact to watch the video;
it expires after three days. Debug artifacts last fourteen days.

`verify` checks credentials only. `publish` creates a new upload. `resume`
requires resume_video_id from history and never calls the video insert endpoint.
Do not enter a resume identifier in other modes. Resume rebuilds the original
video/thumbnail from saved asset metadata and retries processing and thumbnail
setting; it does not edit the original title or visibility. Source links can
expire, in which case rebuilding must be repaired manually.

Inputs pass through environment variables, never interpolated into shell code.
The branch needs repository contents write permission for history commits.
Scheduled runs use publish mode, but currently stop before rendering because
assets have not been reviewed. Explicit allow_unreviewed permits private or
unlisted manual test uploads; it cannot permit public uploads.

## Asset review

Listen through each recording, including loop boundaries. Then edit its review
object in audio/metadata.json. Do not infer approval from filenames or tags.
New recordings without a review object are treated as unreviewed.

Example format (not a claim about an existing recording):

```json
{"approved": true, "labels": {"intensity": "heavy", "setting": "forest", "thunder": false, "traffic": false, "animals": false, "music": false, "voices": false}, "notes": "Describe what was actually checked"}
```

Use intensity `heavy` or `gentle`; setting forest/city/roof/window/tent/lake.
Omit unknown fields. Add the same review structure to data/scene_reviews.json,
keyed by the Pexels video identifier shown in assets.json. Existing scene review
map is intentionally empty. Approved candidates are preferred. Known conflicting
settings/intensity are rejected, and audio selection filters incompatible tracks.
Unknowns do not prove compatibility; they only permit generic preview content.

Specific title claims (thunder, pure rain, intensity and listed settings) require
supporting reviewed labels. This is a limited vocabulary rule system: custom
wording still needs human review. Descriptions avoid asserting the search query
is what the footage actually depicts. Pexels fallback to non-weather results is
removed, but a weather word in a source description is still not visual proof.

## History and recovery

uploads.json on pipeline-history is the shared ledger, separate from source
branches. It contains source references, metadata, date, run identifier, video
identifier, processing state and errors, never credentials. Changing a title or
duration does not bypass source-pair blocking. One new reservation per date also
prevents a changed search response on a rerun from producing a second upload.
This intentionally limits repeated upload tests; previews remain repeatable.

History begins with the first upload through this new implementation. Existing
channel uploads are NOT imported and cannot be resumed through this mode yet.
Older workflow versions do NOT honor this ledger; avoid running those while
reviewing it. Repository-wide protection needs all publishing workflows upgraded.

A reservation is committed before upload. A successful response is saved locally
immediately, then committed to history before processing/thumbnail work. If an
upload fails with an uncertain outcome, the reservation stays blocked. Inspect
YouTube Studio and debug artifacts before repairing history; do not blindly
remove it. The system prioritizes avoiding duplicates over automatic retry.
Two services cannot provide an atomic exactly-once transaction here.

If a video identifier is recorded, use resume. A processing timeout may succeed
later. A permanent rejection needs manual resolution and a deliberate ledger
repair before a replacement is possible. No automatic deletion or re-upload.
If the upload succeeded but history persistence failed, recover the identifier
from run/upload_result.json in artifacts before repairing the ledger.

## Remaining work before merge

- Listen to audio and approve a small matched scene/audio collection.
- Run a preview on GitHub, then one explicitly approved unlisted publish/resume test.
- Import old upload history if it should count toward duplicate prevention.
- Decide whether one upload per date is too restrictive for ongoing tests.
- Add crossfades, loudness checks and broader semantic matching in later work.

Automated tests exercise claim gating, conflicts, persistent reservations,
duplicate attempts, resume lookup, processing rejection/timeout/success, and
authorization. They use simulated services; they do not prove live upload recovery.
