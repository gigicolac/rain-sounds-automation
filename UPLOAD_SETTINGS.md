# Upload packaging: titles, thumbnails, descriptions

Prepared on `claude/improve-upload-process` (October 2026). Not deployed until merged.
Supersedes the title, thumbnail and description parts of FUTURE_UPLOAD_PACKAGING.md.
Scheduling (`data/publish_schedule.json`), upload presets (`data/upload_settings.json`) and
comment posting (`scripts/post_pinned_comment.py`) come from main and are unchanged except
where noted below.

## What changes

| Area | Behaviour | Where to change it |
|---|---|---|
| Titles | Outcome first, like the channel's winners: `{Opener} 🌧️ {Rain Sounds for Sleeping/Sleep phrase} & {benefit} | 3 Hours`, e.g. `Fall Asleep Fast 🌧️ Cozy Night Rain Sounds for Sleeping & Restorative Rest | 3 Hours`. 90 titles (30 per thumbnail headline), at most 95 characters, search keyword within the first 45. Exact titles never repeat; an opener is not reused within 7 uploads. A warning appears when 14 or fewer remain. | `THEMES` in `scripts/upload_presentation.py` |
| On-screen title | The first 12 seconds show a short, emoji-free version (the video font cannot draw emoji), e.g. `Can't Sleep? · Rain Sounds for Sleeping`. | `overlay_title` in `scripts/upload_presentation.py` |
| Thumbnail | Lo-fi style: centred white headline with a soft shadow and a small "3 hours" line, no badge or panel, always over a frame of `custom:10-mug-window` (4.0 s) whatever scene the video shows. Pixelify Sans in Title Case by default; about 1 upload in 4 uses Nunito lowercase, never two in a row. Headlines: cozy, deep sleep, insomnia rain. Fonts are SIL Open Font License, bundled in `fonts/`. | `thumbnail_*` keys in `data/channel_profile.json` |
| Description | Brand voice from the channel's own examples, search keyword in the first two lines. Every description includes restorative, relaxation, flow, drift, calm your nervous system, focus, improve and productivity; tests reject em dashes and repeated phrases. Chapters, CC0 credits, volume tip, disclaimer, hashtags. "No music, no voices, no distractions" appears only when listening labels confirm it (none of the current mixes have labels yet). | `data/description_copy.json`, `data/description_template.txt` |
| Tags | 10 tags from the top keyword searches. | `TAGS` in `scripts/upload_presentation.py` |
| Comment | The automatic comment uses each upload's own question (e.g. "💬 What's keeping you up tonight? You're not the only one awake.") instead of the generic thank-you, which remains the fallback. | `pinned_comments` in `data/description_copy.json` |
| Audio | Publishing skips mixes that contain the city traffic-and-siren recording (788146) or whose listening notes mention traffic, sirens, voices, music or thunder. This removes 3 of the 27 active mixes (04 rooftop cat, 12 bakery cat, 27 city cat), whose own notes say "traffic". Previews still include them. | `clean_rain` in `scripts/channel_profile.py` |
| Upload presets | Added AI disclosure (`containsSyntheticMedia: true`, the scenes are AI-generated) and paid promotion: no. | `data/upload_settings.json` |
| Thumbnail timing | The cover is set straight after upload, before the processing wait, so a processing timeout no longer leaves YouTube's auto-picked frame (Oct 20). Processing wait raised from 15 to 60 minutes. | `PROCESSING_TIMEOUT_SECONDS` |

Black Screen and No Ads are left out of titles: the videos show animated scenes and
ad placement is not controlled by the channel. "Beat insomnia" is avoided because the
description states the sounds are not a treatment.

## Still manual in YouTube Studio

The YouTube Data API has no fields for these. Each publish run lists them in the job summary:
pin the posted comment, add to the matching playlist, end screen, caption certification
("This content has never aired on television in the U.S."), Shorts remixing, and an optional
title A/B test using the three recorded `title_options`.

## Validation

- 139 unit tests pass after merging current main (simulated YouTube and GitHub services).
- Thumbnails were reviewed as mockups on a drawn stand-in scene; the real mug-window frame
  was not available locally, so check the first preview's cover.
- Not yet done: a hosted preview of this branch and one live private upload.
