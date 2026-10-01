# Fixed anime rain channel workflow

The channel uses eleven user-selected anime study/cat/window-rain scenes and
three rain recordings (695619, 651189, 788146). No per-asset tagging or approval
form is required in `channel` mode. Existing reviewed `curated` mode and exploratory
`search` previews remain available. New discoveries are not silently added to the
channel pool: membership is recorded once in `data/channel_profile.json`.

## Current status

Implemented on `codex/asset-quality`; not merged or deployed. The user explicitly
authorized fixed-pool publishing, both shorter clips, and enlargement of the 720p
clip. Scheduled runs use channel mode after this branch is merged; the daily
schedule and upload visibility setting are unchanged. No upload was performed.

Source records are required for publication. Three scenes have source links; the
other eight remain previewable and excluded from publishing until links are
recovered. Source filenames and user selection do not prove third-party rights.
Publication uses only recorded source/licence references, without per-asset forms.

Selection favors scenes absent from the last seven uploads, then less-used scenes.
Reserved or uploaded source pairs are never reused, and the one-new-upload-per-date
rule remains. Eleven scenes and three recordings allow at most 33 distinct pairs;
only nine are currently eligible for publishing due to missing source links.
After those pairs are exhausted, add new source-backed scenes/recordings; do not
delete upload history. The current three recordings are accepted by the user,
including traffic in 788146. Titles avoid event-absence or intensity claims.

## Automatic checks

Channel sources must be at least 1280x720 and five seconds, compared with the
1920x1080/ten-second requirement retained for curated mode. Source and rendered
video decoding is checked; the finished output must be 1080p, have the requested
duration and have normalized audio below full scale. Reports retain dark-interval
warnings (night scenes can be intentionally dark). Publishing validates membership,
source records and the checksum of the successfully checked output. A stale
report or changed output cannot pass. These checks do not recognise visual/audio
content; the pool is based on the user's selections.

## Private video storage

The public code repository must not contain the source-video bundle. An ignored
`run/channel-assets.zip` is prepared locally: 11 scenes, approximately 720 MiB.
`data/channel_asset_manifest.json` records sizes and SHA-256 checksums.
`scripts/channel_storage.py <bundle.zip>` validates the whole archive before
restoring media and refuses to replace different existing files.

The user explicitly confirmed `shmop/rain-sounds-assets`; it has been created
privately. The pipeline repository `gigicolac/rain-sounds-automation` is public.

The bundle is uploaded to a private release and its asset URL recorded in
`data/channel_storage.json` when upload verification completes. The authenticated
download step verifies repository privacy, the bundle checksum and every member.
It accepts credentials only for the confirmed repository.

The user must create a fine-grained token with resource owner `shmop`, selected
repository `rain-sounds-assets`, and repository permission `Contents: Read-only`.
Add that token as the `CHANNEL_ASSET_TOKEN` Actions secret in the pipeline repository.
Never paste a token into chat or commit it. Hosted preview needs this secret.

## Validation

- All 50 tests passed after merging origin/main at 3a80247 into this task branch.
  Main's audio-cache addition 532211 is preserved, outside the channel pool.
- All four workflow files parsed.
- Integrated channel selection and build created a local 60-second 1080p preview;
  its automatic output checks passed. No YouTube upload or history reservation.
- A six-second 720p source rendered a 20-second local preview with repeat transitions.
- Three earlier 75-second audio comparisons were accepted by the user.
- Hosted preview remains pending the Actions read-only storage token and branch push.

When hosted storage is connected, run Daily Rain Video on `codex/asset-quality`
with `mode=preview`, `asset_selection=channel`, and `duration_minutes=1`. The
preview artifact contains the combined video; preview requires no YouTube login.
Use source `local:study-room` and audio `695619` to reproduce the local test.
