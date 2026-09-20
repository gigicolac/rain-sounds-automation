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

### Quick preview: no YouTube upload

1. Open [Actions → Daily Rain Video](https://github.com/gigicolac/rain-sounds-automation/actions/workflows/daily-video.yml).
2. Click **Run workflow** and select branch **codex/pipeline-review-controls**.
3. Set **mode** to **preview**.
4. For a quick check, enter **2** in **duration_minutes**. Leave the other fields
   blank and **allow_unreviewed** unchecked. You can preview unreviewed assets.
5. Click **Run workflow**, then open the new run and wait for it to finish.
6. On the run's **Summary** page, scroll to **Artifacts**. Download
   **preview-<run number>** (the actual name contains the numeric run identifier).
7. In Windows, right-click the downloaded archive → **Extract All**, then open
   **output.mp4** in Media Player. You can watch and listen locally; no YouTube
   link is created. GitHub provides a download, not an embedded video player.
8. Also download **run-debug-<run identifier>-<attempt>**. Extract it and open
   **thumbnail.jpg** to review the cover, and **assets.json** to see the selected
   scene, recording, title, duration and source references. The latter is a
   JSON (JavaScript Object Notation) text file; Notepad can open it.

You must be signed into GitHub with access to the repository to download the
artifacts. Preview videos expire after **3 days**; debugging files after **14
days**. Save a local copy before expiry. If the artifact is missing, check
**Build video**, **Generate thumbnail**, and **Save preview video** in the job
logs. Verify-only runs do not generate previews. Expired artifacts require a
new preview run.

### Every Run workflow field

| Field | What it does / what happens when blank | Example |
|---|---|---|
| `mode` | Defaults to `preview`. `verify` checks credentials only; `preview` renders downloadable files; `publish` uploads a new video; `resume` retries processing and the thumbnail for a recorded upload. | `preview` for visual and audio review without posting. |
| `scene_query` | Optional Pexels search phrase, not a video link or exact clip selector. Blank rotates through `data/scene_terms.json`. Search results must pass the weather-keyword filter, but still need visual review. | `rain on window glass` |
| `audio_id` | Optional numeric Freesound identifier from `audio/metadata.json`. The recording must already be cached; this does not download an arbitrary sound. Blank selects a compatible cached recording, preferring reviewed ones. | `651189` selects the cached recording named “Heavy Rain Regen Starkregen Raining Atmosphere Ambient Forest Wald”. Its name is not proof of its contents. |
| `title` | Optional exact title, up to 100 characters. Blank chooses an eligible template and fills in the duration. Manual titles are literal: do not enter `{duration}`. Known unsupported claims such as “No Thunder” are rejected. | `2 Minutes of Rain Ambience` when duration is `2`. |
| `duration_minutes` | Optional whole number from **1 to 8**. Blank chooses **5, 6, 7, or 8**. Do not enter seconds, decimals or units. | `2` for a quick preview; `8` for a longer loop check. |
| `allow_unreviewed` | Checkbox, unchecked by default. Only needed when publishing assets that lack approval. Checked permits those assets only when the repository variable `UPLOAD_PRIVACY_STATUS` is `unlisted` or `private`. Does not bypass title rules, matching or duplicate checks, and does not approve the assets. | Leave unchecked for preview; check for an explicitly intended unlisted test upload. |
| `resume_video_id` | Leave blank except in `resume` mode, where it is required. Copy the `video_id` from a recorded entry in `uploads.json` on `pipeline-history`, or its upload-result artifact. Supply just the identifier, not a full link. Videos uploaded before this ledger existed cannot be resumed this way. | For a recorded link ending in `watch?v=AbCdEf12345`, enter `AbCdEf12345` (illustration only). |

Scene, audio, title and duration overrides apply to `preview` and `publish`.
`verify` does not use them. `resume` restores the original selection from history
and ignores those overrides; it does not change the original title or visibility.
Leave unused fields blank to keep each run easy to understand.

### Example combinations

**Fast automatic preview:** mode `preview`, duration_minutes `2`; leave everything
else blank or unchecked.

**Preview with specific choices:** mode `preview`, scene_query `rain on window
glass`, audio_id `651189`, title `2 Minutes of Rain Ambience`, duration_minutes
`2`. A known conflict between reviewed scene/audio labels will stop selection;
change the choices rather than mislabeling them.

**Unlisted test upload after reviewing:** set the repository variable
`UPLOAD_PRIVACY_STATUS` to `unlisted`; choose mode `publish`, duration_minutes
`5`, and check allow_unreviewed only if the assets still lack formal approval.
This makes a new selection; it does not upload a previously downloaded preview
file. Live search results may have changed since the preview, so this is not an
exact-preview approval mechanism yet.

### What to review

- Watch the opening title: accurate wording, readable text, no clipping.
- Watch full screen: sharpness, rain actually visible, scene fits the audio.
- Listen with headphones: thunder, traffic, voices, music or animals that the
  title should not contradict; abrupt loud sounds or clipping.
- Watch/listen for several repeat boundaries: noticeable jumps, clicks or gaps.
- Check the ending fade and whether the thumbnail remains readable when small.
- Note the run identifier and playback time for each issue, for example:
  “Run 12345, 00:48: obvious audio click when the recording repeats.”

A two-minute preview helps find defects but does not establish that a longer
source recording is clean throughout. Listen to the complete cached recording
before marking it approved.

Preview creates no history reservation and uploads nothing to YouTube. It does
currently read and enforce the same history checks as publication: if that date
or source pair is already reserved/uploaded, preview can stop before rendering.
Repeated previews are possible while no matching history entry blocks them.
Do not delete upload history just to bypass that limitation.

Resume rebuilds the original video/thumbnail from saved asset metadata, then
retries processing and thumbnail setting without inserting another video.
Source links can expire, in which case rebuilding must be repaired manually.

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
