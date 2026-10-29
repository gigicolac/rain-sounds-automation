# New rain channel: ready-for-authorization setup

Prepared 29 October 2026 for Calming Rain Sounds, @calming_rain_soundss,
channel UCaMtUdYVy9bIW1xYsWJHjXg. This guide supersedes the earlier generated-only
proposal in NEW_CHANNEL_MIGRATION.md; that file retains the investigation history.

## Completed

- Old Daily Rain Video workflow disabled on GitHub and verified disabled_manually.
- Old-channel scheduled video lOundwDDmAE changed from Scheduled to Private in
  YouTube Studio and saved. Existing published videos remain untouched.
- Claimed source 695619 and all 18 known derived mixes excluded. Prior records,
  files and upload history preserved. The new pool contains none of those mixes.
- Ten new 90-second recording-based mixes: five using the Ranger cabin shelter
  recipe, five using Woodland night shelter. Both recipes use recording 651189,
  checksum 035c23de195d1bfd5a44d6b6dac92501fd132c55b68dd26c5d1d78c3fec71d66.
- The user explicitly allowed that shared source and automatic approval. Records
  state user_authorized_automatic plus technical_checked; full_playback and
  loop_checked remain false because no new listening review was asserted.
- Finished mix identities/hashes/seeds and visual identities/master hashes are
  single-use. Sharing approved recording 651189 is an explicit exception.
- Eighteen generated illustrated scenes restored by checksum and checked against
  recorded used visual identities, render hashes and master hashes. New-channel
  Studio Videos inventory was checked through manager access: No content available.
- Private storage release new-channel-forest-2026-10-29 contains asset 688356401:
  18 scenes plus 10 mixes, 230953801 bytes. Manifest and bundle hash configured.
- Expected-channel repository variable changed to the exact new channel ID.
  Existing YouTube secrets have NOT been replaced or reused for the new channel.
- Publishing configuration: three-hour videos; builds Monday/Wednesday/Friday
  11am Australia/Sydney; public releases Monday/Wednesday noon and Friday 11am
  America/New_York. Delayed scheduled runs skip disabled weekdays. Manual
  immediate/private/unlisted overrides remain explicit choices.
- Active local app automation generate-three-forest-rain-mixes: Monday 09:00
  Australia/Sydney, creates three fresh mixes and records user-authorized automatic
  approval only on successful checks. Keep the local host available for execution.
  It does not publish videos or enable the paused workflow.

## Verification

153 tests passed, including source eligibility, auto-approval truthfulness,
selection, scheduling and recovery. A one-minute 1920x1080 preview was rendered,
fully decoded, checked for black frames/audio duration/peaks, and its frame and
thumbnail visually inspected. All automatic checks passed. This was local-only,
not a YouTube upload and not a listening approval. Windows preview used a local
Arial font override; production retains its existing Linux font configuration.

Preview: run/output.mp4. Report: run/channel-quality.json.
Batch: run/new-channel-forest-ten-20261029.
Library: run/window-rain-library-20261029, vibe new-channel-batch.
Bundle: run/reviewed-channel-assets.zip.

## Weekly replenishment procedure

Run create_approved_forest_batch.py with --count 3, a new date-based seed and
output directory, using the verified source in the primary checkout audio/.
The script rejects changed source bytes and never reads source 695619. Add the
approved output via stage_custom_audio.py, upload the new private bundle under a
new immutable asset name, update the storage configuration and preserve old files.
Update the deployed catalogue/storage through the normal reviewed branch process.
The local generation automation prepares these updates; it does not silently
merge or publish them. Repeat visual provisioning before the unused scene pool
runs out: 18 scenes currently support six weeks at three releases per week.

## Owner authorization and final activation

Manager access through YouTube Studio cannot authorize the YouTube APIs. The
attempt signed in as Shoma resolved to personal channel UCI5XKmwUVQS_qGO4zfpYaMg;
the guard rejected it, saved no credentials and uploaded nothing.
The account that owns the new channel must complete the existing local OAuth
(Open Authorization) flow for the uploader and verify the returned channel ID.
No password or tokens should be pasted into chat. Then update all three YT_*
secrets together, retaining the existing comment/read/upload permissions.

After owner authorization and explicit merge approval:
1. Merge the reviewed launch change while keeping the workflow disabled.
2. Run verify against the new credentials and confirm the exact new channel ID.
3. Run a hosted preview; inspect its media and source report.
4. Re-enable Daily Rain Video for the configured new channel and schedule.
Do not re-enable with old credentials. Check long-upload/custom-thumbnail feature
eligibility during activation. No new-channel video has been uploaded yet.

YouTube manager limitation:
https://support.google.com/youtube/answer/9481328?hl=en
