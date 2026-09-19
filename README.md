# Rain Sounds YouTube Automation

A fully automated daily pipeline that publishes a short (5–8 minute)
rain-sounds ambient video to YouTube, at **$0/month**, for the **Calming
Rain Sounds** channel (`@calmingrainsoundssss`).

Videos currently run for 5, 6, 7, or 8 minutes to speed up testing. This applies
to full manual and scheduled runs using this version of the code. Titles and
descriptions use minutes.

## Review branch controls

See [PIPELINE_ROADMAP.md](PIPELINE_ROADMAP.md) for the six-step roadmap, current
controls, asset review format, and recovery instructions. This branch replaces
`verify_only` with a `mode` choice: `verify`, `preview` (default), `publish`, or
`resume`. The older setup instructions below describe the earlier workflow.

## How it works

Every day, a GitHub Actions cron job runs the pipeline end-to-end:

1. **`scripts/select_assets.py`** — day-seeded rotation picks a scene search
   term, a Pexels video, a cached audio track, a title template and a target
   duration (5–8 min). Date-seeded selection varies the choices, while persistent history blocks
   duplicate source pairs. Rotation alone does not guarantee monetization eligibility.
2. **`scripts/build_video.py`** — downloads the Pexels clip, loops it (and
   the audio) to the target duration with FFmpeg, overlays the title for the
   first 12 seconds, and exports the final `mp4`.
3. **`scripts/make_thumbnail.py`** — grabs a frame from the finished video
   and overlays a styled title using Pillow, for a proper custom thumbnail
   instead of a random auto-picked frame.
4. **`scripts/upload_youtube.py`** — uploads the video (Public, category
   Music) and sets the custom thumbnail via the YouTube Data API.

A **separate, slower workflow** (`audio-cache.yml`, monthly) keeps the local
`audio/` pool topped up from Freesound. The daily job never calls Freesound
directly — see "Why audio is cached" below.

## Repo structure

```
scripts/
  select_assets.py           # daily: pick today's scene/audio/title/duration
  fetch_audio_pool.py        # periodic: refresh audio/ from Freesound
  build_video.py             # daily: assemble the video with FFmpeg
  make_thumbnail.py          # daily: generate a custom thumbnail
  upload_youtube.py          # daily: publish to YouTube
  get_youtube_refresh_token.py  # one-time, run locally — see setup below
data/
  scene_terms.json           # Pexels search term rotation
  title_templates.json       # title template rotation
  description_template.txt   # video description template
audio/
  metadata.json              # cached track pool metadata (populated by fetch_audio_pool.py)
  *.mp3                      # cached CC0 audio previews
.github/workflows/
  daily-video.yml            # daily cron: select -> build -> thumbnail -> upload
  audio-cache.yml            # monthly cron: refresh the audio pool
```

## Why audio is cached, not fetched live

Freesound has shown occasional downtime (a "server at capacity" 503 during
testing). If the daily job called Freesound directly, an outage on any given
day would mean no video that day. Instead, `fetch_audio_pool.py` runs on its
own slow cadence and builds a pool of ~20–30 CC0 tracks in `audio/`. The
daily job only ever reads from that local pool, so a Freesound outage never
affects whether today's video gets made.

It downloads Freesound's HQ preview files (not the raw originals) because
previews are reachable with a simple API key, while raw downloads require a
full interactive OAuth2 login — previews are still good quality (up to
128kbps) and are the practical choice for an unattended job.

## One-time setup

### 1. Make the repository public

Public repos get **unlimited free GitHub Actions minutes** — needed to
comfortably encode a 1–2 hour 1080p video daily. Private repos only get
2,000 free minutes/month, which a daily long encode could burn through
quickly.

`Settings → General → Danger Zone → Change visibility → Public`

### 2. Add repo secrets

`Settings → Secrets and variables → Actions → New repository secret`

| Secret | Value |
|---|---|
| `PEXELS_API_KEY` | your Pexels API key |
| `FREESOUND_API_KEY` | your Freesound API key |
| `YT_CLIENT_ID` | from the YouTube OAuth setup below |
| `YT_CLIENT_SECRET` | from the YouTube OAuth setup below |
| `YT_REFRESH_TOKEN` | from the YouTube OAuth setup below |

Also add the required repository **variable** `EXPECTED_YOUTUBE_CHANNEL_ID`
with the intended channel identifier (starts with `UC`). The workflow reads
this from Variables, not Secrets, and refuses to upload to any other channel.

### 3. Set up YouTube OAuth (one-time, needs a browser)

This step needs to happen on your own machine, not in Actions, because it
requires an interactive Google sign-in.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and
   create a new project (or use an existing one).
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen** → External → fill in the
   basics → add your own Google account as a test user → add the scope
   `https://www.googleapis.com/auth/youtube.upload` and
   `https://www.googleapis.com/auth/youtube.readonly`.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → Application type: **Desktop app** → Create.
5. Download the resulting JSON file, save it as `client_secret.json` in the
   repo root **on your local machine only** (it's gitignored — never commit
   it).
6. Locally: `pip install -r requirements.txt`, then run:
   ```
   python scripts/get_youtube_refresh_token.py --client-secrets client_secret.json --expected-channel-id YOUR_CHANNEL_ID
   ```
7. A browser window opens — sign in with the Google account that owns the
   `@calmingrainsoundssss` channel and grant access.
8. The script verifies the selected channel before printing three values — copy them into the GitHub secrets from
   step 2: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

The helper explicitly requests renewed consent and offline access. Grant both
permissions. Existing upload-only refresh tokens cannot gain read-only access
just by changing the scopes in Python; repeat authorization and replace the
three secrets together. Do not paste these values into chat or commit them.

For unattended use, check the consent screen publishing status: External apps
left in Testing issue refresh tokens that expire after seven days for these
permissions. See [Google's token expiration guidance](https://developers.google.com/identity/protocols/oauth2#expiration).
Separately, YouTube may restrict uploads from unverified projects to private
viewing; requesting public visibility does not override that restriction.

### 4. Populate the audio cache (must run before the first daily video)

`Actions → Refresh Audio Cache → Run workflow`

The daily job will fail with a clear error if `audio/metadata.json` is
empty or missing, so this has to run (and succeed) at least once first.

### 5. Test the daily pipeline manually

`Actions → Daily Rain Video → Run workflow`

Manual runs default to **verify_only**: leave it checked to validate credentials
and the target channel without creating or uploading a video. After this passes,
set `UPLOAD_PRIVACY_STATUS=unlisted`, then run again with **verify_only** unchecked
to test the full pipeline. Scheduled runs continue to execute the full pipeline.

If verification reports `invalid_scope`, regenerate the token with the helper
above and grant both permissions. For `invalid_grant`, also check for token
expiry or revoked access. Never remove the channel check to bypass either error.

Check the Actions log and confirm the video actually appears correctly on
the channel — scene, audio, title, thumbnail — before trusting the
unattended daily cron.

**Reviewing the first few videos before going fully public:** by default,
uploads publish as Public immediately (needed for the daily-upload pattern
to build watch time). If you'd rather sanity-check the first couple of
videos before anyone can find them, set a repo variable:

`Settings → Secrets and variables → Actions → Variables → New repository
variable → name: UPLOAD_PRIVACY_STATUS, value: unlisted`

While that's set, every upload publishes as Unlisted (viewable only via
direct link — check it from YouTube Studio, no need to flip it per video).
Once you're happy with the output, delete that variable (or set it back to
`public`) and every upload after that goes straight to Public with no
further manual step.

### 6. Let it run

Once you're happy with a manual test run, the cron schedules take over:
daily video at 01:00 UTC, audio cache refresh monthly on the 1st. Both can
still be triggered manually any time from the Actions tab.

## Cost breakdown — $0/month

| Component | Cost |
|---|---|
| Pexels API | Free |
| Freesound API | Free |
| GitHub Actions (public repo) | Free, unlimited minutes |
| YouTube Data API | Free — one upload/day uses ~1,600 of the 10,000 daily quota units |
| FFmpeg, Pillow | Free, open source |

## Known limitations

- **Loop seams**: both the video and audio are looped with a simple repeat
  (not crossfaded at each loop boundary), with only a global fade-in/out
  applied. Fine for most ambient footage/tracks, but an audible or visible
  seam is possible depending on the source clip/track.
- **Quota headroom**: one upload/day leaves plenty of YouTube API quota
  spare if you ever want to add more automation (e.g. auto-replying to
  comments) later.
- **Video source**: currently Pexels stock footage only. An illustrated/
  anime-style visual identity was considered to match the channel's
  existing branding, but was intentionally left out of this build —
  Pinterest doesn't offer a reliable way to verify image licensing (its API
  doesn't expose search data at all, and its "free to use" filters are
  widely reported as unreliable), which is a real risk for a monetised
  channel. If you want to revisit this, the cleanest free/licensed path is
  a manually curated pool of CC0 illustrations (e.g. from itch.io) dropped
  into a `scenes/` folder, rotated the same way `audio/` is, with FFmpeg's
  `zoompan` filter for a Ken-Burns pan/zoom instead of Pexels video. Ask for
  this as a follow-up build.
