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

Not copied, because the reference video has none or the API cannot set them:

- no playlist, no "altered or synthetic content" flag and no captions
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
2. For each scheduled upload that is now public and has no recorded comment,
   it posts the text in `data/pinned_comment.txt` as the channel. It records
   `comment_id` in upload history, so a video is never commented on twice, and
   recovers a comment if a run stops mid-post.
3. The run's **Summary** page lists an "Open and pin" link for each new
   comment. Open it, then use the comment's ⋮ menu → **Pin**.

Only uploads with a scheduled `publish_at` get the comment; older videos are
left alone. Edit `data/pinned_comment.txt` to change the wording.

### One-time login update (required before comments work)

Posting comments needs the `youtube.force-ssl` permission, which the current
`YT_REFRESH_TOKEN` lacks. Until it is replaced, the comment workflow fails
with an explanatory message. Uploads keep working, because they request only
the upload and read-only permissions.

1. On your computer, in this repository, with the same `client_secret.json`
   used originally:
   `python scripts/get_youtube_refresh_token.py --client-secrets client_secret.json --expected-channel-id UCnA4UvAlDyqAs7G0RVv-ETg`
2. Sign in, choose the **Calming Rain Sounds** channel, and allow every
   permission requested.
3. Copy the printed `YT_REFRESH_TOKEN` value into **GitHub → Settings →
   Secrets and variables → Actions → YT_REFRESH_TOKEN → Update**. Never paste
   it into chat or commit it.
4. Optionally run **Post Pinned Comment** manually to confirm it succeeds.
