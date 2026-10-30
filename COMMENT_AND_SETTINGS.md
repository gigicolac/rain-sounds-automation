# Pinned comment and preset video settings

## Preset video settings

`data/upload_settings.json` is applied to every new upload. It was copied from
reference video `EXjpeDzwuAs` (2 Oct 2026). Its Studio settings were read with
the read-only `inspect_video_id` option of **verify** mode on 23 Oct 2026:

- Title and audio language: English (Australia), `en-AU`
- Licence: standard YouTube; embedding allowed; like and view counts public
- Recording location: Melbourne. The recording date is set to each upload's
  date; the reference video used a fixed 9 Oct 2026.
- Category Music and "not made for kids" were already set by the pipeline.
- For future uploads of the current illustrated animation and recording-based
  rain mixes, **AI use: No** (`status.containsSyntheticMedia=false`), as requested
  on 30 October 2026. YouTube does not require disclosure for non-realistic
  animation or effects enhancing recorded audio. This is not a statement that
  no AI tools were used. Reassess if the content changes to realistic synthetic
  scenes, people, events or AI-generated music. Existing videos are unchanged.
  Guidance: https://support.google.com/youtube/answer/14328491
- Paid promotion: No.

Not copied, because the reference video has none or the API cannot set them:

- no playlist and no captions; the original reference had no altered-content
  flag, and the current explicit disclosure choice is documented above
- the `en-AU` localisation entry, which is YouTube's copy of the default
  language and needs no separate upload field
- comment settings, end screens, cards and monetisation, which the YouTube
  Data API does not expose

The file cannot change visibility, scheduling or audience. Those stay under
pipeline control. To check another video's settings, run **Daily Rain Video**
with mode `verify` and `inspect_video_id` set to the video's identifier. The
run reads only and changes nothing.

## Pinned comment

The YouTube Data API has no pin method, so the pipeline posts the comment and
pinning remains one tap:

1. **Post Pinned Comment** runs 15 minutes after each weekday release time in
   `data/publish_schedule.json` (US Eastern), plus a daily catch-up at
   5:45pm ET.
2. For each new-channel scheduled upload that is now public and has no recorded
   comment, it posts that upload's selected question, falling back to
   `data/pinned_comment.txt`, as the channel. It records
   `comment_id` in upload history, so a video is never commented on twice, and
   recovers a comment if a run stops mid-post.
3. The run's **Summary** page lists an "Open and pin" link for each new
   comment. Open it, then use the comment's ⋮ menu → **Pin**.

The live workflow targets only **UCaMtUdYVy9bIW1xYsWJHjXg**. Authentication must
resolve to that exact channel, and old-channel or unidentified ledger entries
are skipped before any video lookup or comment request. No separate old-channel
comment job should be enabled. Keeping this shared workflow active enables the
new channel only; disabling it would also stop the new channel's comments.

Only uploads with a scheduled `publish_at` get the comment; private/unlisted or
unscheduled tests are skipped. The private launch test f8FiHzHNxjU has no release
timestamp and is not automatically commented on. The user is handling its
comment manually. Edit `data/description_copy.json` for the rotating questions
or `data/pinned_comment.txt` for fallback wording.

Automatic posting does not automatically pin. The primary owner must enable
advanced features before manual pinning is available. Manager access cannot
complete the owner's identity verification. Pinning can take up to 24 hours to
become available after advanced features are enabled:
https://support.google.com/youtube/answer/9891124
https://support.google.com/youtube/answer/6000964

### Comment authorization and recovery

Posting comments needs the `youtube.force-ssl` permission. The new-channel
authorization installed on 30 October 2026 includes that grant. The earlier
old-channel scope failure is historical. If permission is revoked or expires,
refresh authorization for the new channel; never restore old-channel credentials.
Uploads request only upload and read-only permissions.

1. On your computer, in this repository, with the same `client_secret.json`
   used originally:
   `python scripts/get_youtube_refresh_token.py --client-secrets client_secret.json --expected-channel-id UCaMtUdYVy9bIW1xYsWJHjXg`
2. Sign in, choose the **Calming Rain Sounds** channel, and allow every
   permission requested.
3. Copy the printed `YT_REFRESH_TOKEN` value into **GitHub → Settings →
   Secrets and variables → Actions → YT_REFRESH_TOKEN → Update**. Never paste
   it into chat or commit it.
4. Optionally run **Post Pinned Comment** manually to confirm it succeeds.
