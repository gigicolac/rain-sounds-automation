# Upload settings and packaging

Prepared on `claude/improve-upload-process` (October 2026). Not deployed until merged.
Supersedes the title, thumbnail and description parts of FUTURE_UPLOAD_PACKAGING.md.

## What every upload now does

| Area | Behaviour | Where to change it |
|---|---|---|
| Audio | Channel publishing requires listening review to confirm no traffic, voices, music, thunder or animals (unknown is not absent), plus no siren/traffic/horn words in the title. Previews are not restricted, so new recordings can still be reviewed. | `CLEAN_RAIN_ABSENT` in `scripts/channel_profile.py` |
| Audio pool | 788146 (city rain with traffic and a siren, used on Oct 20) removed. Pool is 7 scenes × 2 recordings = 14 pairs; 3 were used by Oct 20, so about 11 uploads remain before new clean audio is needed. | `data/channel_profile.json` |
| Titles | `Keyword | Outcome | Length`, e.g. `Rain Sounds for Sleeping | Fall Asleep Fast Tonight | 3 Hours`. 30 titles, at most 70 characters. Exact titles never repeat; an outcome is not reused within the last 7 uploads while alternatives remain. | `KEYWORDS`, `THEMES` in `scripts/upload_presentation.py` |
| Thumbnail | Always the stacked Nunito layout and 3 HOURS badge over a frame of `custom:10-mug-window` (4.0 s), whatever scene the video shows. Headlines rotate between COZY RAIN, DEEP SLEEP RAIN and INSOMNIA RAIN; DEEP SLEEP stacks onto three lines at full size. | `thumbnail_scene_id`, `thumbnail_frame_seconds` in `data/channel_profile.json` |
| Description | Brand-voice copy per headline with search keywords in the first two lines, chapters for videos of 30 minutes or more, CC0 credit, relaxation disclaimer and hashtags. "No music, no voices, no traffic" appears only when listening review confirmed it. | `data/description_copy.json`, `data/description_template.txt` |
| Tags | 10 tags from the top keyword searches. | `TAGS` in `scripts/upload_presentation.py` |
| Upload fields | Category Music, language English (Australia), AI disclosure yes (scenes are AI-generated), paid promotion no, recording date = today in Melbourne, location Melbourne, Australia. | `data/upload_settings.json` |
| Timing | Public runs upload as private with `publishAt` set to the next US Eastern posting window that starts at least 2 hours later (HD processing and checks). Manual runs can choose `publish_timing: immediate`. | `WINDOWS` in `scripts/publish_schedule.py` |
| Thumbnail timing | The cover is set straight after upload, before the processing wait. Previously a processing timeout (Oct 20) left YouTube's auto-picked frame. Processing wait raised from 15 to 60 minutes. | `PROCESSING_TIMEOUT_SECONDS` |
| Playlists | Added automatically once a playlist ID is filled in for the video's headline. This needs the extra "manage" permission, so redo the refresh-token helper (it now requests it) before filling in IDs. | `playlists` in `data/upload_settings.json` |

Black Screen and No Ads are deliberately left out of titles: the videos show animated
scenes, and ad placement is not something the channel controls.

## Still manual in YouTube Studio

The YouTube Data API has no fields for these (checked against the API discovery document).
Each publish run lists them in the job summary with that video's pinned-comment text:

- Pin the generated comment once the video is public.
- End screen pointing to the most relevant playlist or video.
- Caption certification: "This content has never aired on television in the U.S."
- Shorts remixing allowed.
- Optional title A/B test (Test & Compare) using the three recorded `title_options`.

## Validation

- 102 unit tests pass with simulated YouTube and GitHub services.
- Every new upload field name was checked against the discovery document bundled with
  google-api-python-client 2.201.0.
- Thumbnails rendered locally on a placeholder background; COZY RAIN is pixel-identical
  to the previous renderer. The real mug-window frame was not available locally.
- Not yet done: a hosted preview and a live private upload. The API accepting `en-AU`,
  recording location and scheduled publishing is not proven until that test runs.
