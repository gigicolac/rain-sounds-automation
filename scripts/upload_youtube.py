#!/usr/bin/env python3
"""Upload run/output.mp4 to YouTube via the YouTube Data API, using a
refresh-token OAuth credential (no interactive login needed at run time —
see scripts/get_youtube_refresh_token.py for the one-time setup that
produces YT_REFRESH_TOKEN).

Reads run/assets.json for title/description/tags, run/output.mp4 for the
video, and run/thumbnail.jpg (optional) for the thumbnail.
"""
import json
import os
import sys
import time
from pathlib import Path

from upload_history import Ledger
from publish_schedule import api_timestamp, next_publish_at
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "run"
ASSETS_PATH = RUN_DIR / "assets.json"
VIDEO_PATH = RUN_DIR / "output.mp4"
THUMBNAIL_PATH = RUN_DIR / "thumbnail.jpg"
RESULT_PATH = RUN_DIR / "upload_result.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # Needed for channels().list(mine=True) in verify_target_channel().
    "https://www.googleapis.com/auth/youtube.readonly",
]
# Posting the standard comment (post_pinned_comment.py) needs youtube.force-ssl.
# Uploads keep requesting only SCOPES, so a token without it still uploads.
COMMENT_SCOPES = SCOPES + ["https://www.googleapis.com/auth/youtube.force-ssl"]
SETTINGS_PATH = ROOT / "data" / "upload_settings.json"
# A three-hour upload can take well over 15 minutes to process.
PROCESSING_TIMEOUT = int(os.environ.get("PROCESSING_TIMEOUT_SECONDS") or 3600)
CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 5
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}

# Defaults to "public" for full automation. Override with the repo variable
# UPLOAD_PRIVACY_STATUS=unlisted while reviewing the first few videos, then
# unset it (or set it back to "public") once you're happy with the output.
VALID_PRIVACY_STATUSES = {"public", "unlisted", "private"}
# `or "public"` (not just .get(..., "public")) because GitHub Actions sets
# an unset repo variable to an empty string rather than omitting the env
# var entirely — an empty string must still fall back to the default.
PRIVACY_STATUS = (os.environ.get("UPLOAD_PRIVACY_STATUS") or "public").strip().lower()
if PRIVACY_STATUS not in VALID_PRIVACY_STATUSES:
    raise ValueError(
        f"Invalid UPLOAD_PRIVACY_STATUS={PRIVACY_STATUS!r}; "
        f"must be one of {sorted(VALID_PRIVACY_STATUSES)}"
    )


def get_credentials(scopes=SCOPES):
    client_id = os.environ["YT_CLIENT_ID"]
    client_secret = os.environ["YT_CLIENT_SECRET"]
    refresh_token = os.environ["YT_REFRESH_TOKEN"]
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )


def signup_required(exc):
    body = exc.content.decode("utf-8", "replace") if isinstance(exc.content, bytes) else str(exc.content)
    return "youtubeSignupRequired" in str(exc) or "youtubeSignupRequired" in body


def list_own_channel(youtube, retry_delay=60):
    """channels().list(mine=True), retried once on youtubeSignupRequired.
    That 401 failed the 21 and 22 Oct 2026 scheduled runs, then cleared
    on 23 Oct, so a single delayed retry absorbs a transient occurrence.
    """
    try:
        return youtube.channels().list(part="id,snippet", mine=True).execute()
    except HttpError as exc:
        if not signup_required(exc):
            raise
        print(f"YouTube returned youtubeSignupRequired; retrying once in {retry_delay}s")
        time.sleep(retry_delay)
        return youtube.channels().list(part="id,snippet", mine=True).execute()


def verify_target_channel(youtube):
    """Guard against uploading to the wrong YouTube channel — a real
    incident: the Google account used for OAuth setup manages multiple
    channels/brand accounts, and the resulting token defaulted to the
    wrong one, silently. Requires EXPECTED_YOUTUBE_CHANNEL_ID (the
    channel ID from the target channel's URL, e.g.
    youtube.com/channel/<THIS_PART>) and fails loudly before uploading
    anything if the authenticated credentials resolve to a different
    channel.
    """
    expected_channel_id = os.environ.get("EXPECTED_YOUTUBE_CHANNEL_ID", "").strip()
    if not expected_channel_id:
        raise RuntimeError(
            "EXPECTED_YOUTUBE_CHANNEL_ID is not set. Add it as a repository variable "
            "(the channel ID from your channel's URL, e.g. "
            "youtube.com/channel/<THIS_PART>) so uploads can be verified "
            "against the intended channel before publishing."
        )

    try:
        response = list_own_channel(youtube)
    except HttpError as exc:
        if not signup_required(exc):
            raise
        raise RuntimeError(
            "YouTube reported youtubeSignupRequired twice: the Google account behind "
            "YT_REFRESH_TOKEN did not resolve to a YouTube channel. Check that the channel "
            "still exists and the app's access was not removed. If it persists, run "
            "scripts/get_youtube_refresh_token.py --client-secrets client_secret.json "
            "--expected-channel-id " + expected_channel_id + " locally, pick the channel "
            "(not the personal account) when signing in, and replace the three YT_* "
            "repository secrets with its output."
        ) from exc
    except RefreshError as exc:
        raise RuntimeError(
            "YouTube authorization could not be refreshed. If the error is invalid_scope, "
            "the token may predate the required youtube.readonly permission. Run "
            "scripts/get_youtube_refresh_token.py --client-secrets client_secret.json "
            "--expected-channel-id " + expected_channel_id + " locally, grant both "
            "permissions, and replace the three YT_* repository secrets with its output. "
            "For invalid_grant, also check whether the token expired or was revoked."
        ) from exc
    items = response.get("items", [])
    if not items:
        raise RuntimeError("Could not resolve the authenticated channel via channels().list(mine=True)")

    actual_channel_id = items[0]["id"]
    actual_channel_title = items[0]["snippet"]["title"]
    if actual_channel_id != expected_channel_id:
        raise RuntimeError(
            f"Refusing to upload: authenticated as channel "
            f"{actual_channel_title!r} ({actual_channel_id}), but "
            f"EXPECTED_YOUTUBE_CHANNEL_ID is {expected_channel_id!r}. The "
            "OAuth refresh token was likely generated while signed into the "
            "wrong Google account/channel — redo the get_youtube_refresh_token.py "
            "step signed into the correct channel."
        )
    print(f"Verified target channel: {actual_channel_title!r} ({actual_channel_id})")


def scheduled_release():
    """Public uploads are released at the configured weekday time unless
    PUBLISH_TIMING=now; explicit private/unlisted uploads are never scheduled."""
    if PRIVACY_STATUS != "public" or (os.environ.get("PUBLISH_TIMING") or "schedule").strip().lower() == "now":
        return None
    return api_timestamp(next_publish_at())


def upload_body(assets, publish_at=None):
    preset = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    body = {
        "snippet": {
            **preset.get("snippet", {}),
            "title": assets["title"][:100],  # YouTube title limit
            "description": assets["description"][:5000],
            "tags": assets["tags"],
            "categoryId": assets.get("category_id", "10"),
        },
        # Presets cannot override visibility, scheduling or audience.
        "status": {
            **preset.get("status", {}),
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }
    if preset.get("recordingDetails"):
        body["recordingDetails"] = dict(preset["recordingDetails"])
        if assets.get("date"):
            body["recordingDetails"]["recordingDate"] = f"{assets['date']}T00:00:00Z"
    if preset.get("paidProductPlacementDetails"):
        body["paidProductPlacementDetails"] = dict(preset["paidProductPlacementDetails"])
    if publish_at:
        # YouTube accepts publishAt only on private videos and makes them public then.
        body["status"].update(privacyStatus="private", publishAt=publish_at)
    return body


def upload_video(youtube, assets, publish_at=None):
    body = upload_body(assets, publish_at)
    media = MediaFileUpload(str(VIDEO_PATH), chunksize=CHUNK_SIZE, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part=",".join(body), body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except HttpError as exc:
            if exc.resp.status in RETRIABLE_STATUS_CODES and retries < MAX_RETRIES:
                retries += 1
                sleep_s = 2 ** retries
                print(f"Retriable upload error ({exc.resp.status}), retry {retries}/{MAX_RETRIES} in {sleep_s}s")
                time.sleep(sleep_s)
                continue
            raise
    return response


def set_thumbnail(youtube, video_id):
    if not THUMBNAIL_PATH.exists():
        print("No thumbnail found, skipping.")
        raise RuntimeError("Thumbnail file is missing; rebuild it before resuming")
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(THUMBNAIL_PATH), mimetype="image/jpeg"),
        ).execute()
        print("Thumbnail set.")
    except HttpError as exc:
        # Non-fatal: the video itself already uploaded successfully.
        raise RuntimeError(f"Video uploaded, but thumbnail failed. Resume this video instead of re-uploading: {video_id}") from exc


def studio_checklist(entry, assets):
    """Settings the YouTube API cannot set; done by hand in Studio for each upload."""
    options = "\n".join(f"  - {t}" for t in assets.get("title_options", [])) or "  - (none recorded)"
    return "\n".join([
        f"## Studio checklist for {entry.get('url', 'this upload')}",
        f"Goes public: {entry.get('publish_at') or 'now'}",
        "",
        "- [ ] Pin the channel comment once it is posted (post_pinned_comment.py links it)",
        "- [ ] Add to the playlist that matches this video's theme",
        "- [ ] End screen: link the playlist or video most relevant to this theme",
        "- [ ] Caption certification: This content has never aired on television in the U.S.",
        "- [ ] Shorts remixing: allowed",
        "- [ ] Optional title A/B test (Test & Compare) with:",
        options,
    ])


def write_summary(entry, assets):
    text = studio_checklist(entry, assets)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def wait_for_processing(youtube, video_id, timeout=PROCESSING_TIMEOUT, interval=15):
    deadline = time.monotonic() + timeout
    while True:
        response = youtube.videos().list(
            part="status,processingDetails", id=video_id).execute()
        items = response.get("items", [])
        if items:
            status = items[0].get("status", {})
            processing = items[0].get("processingDetails", {})
            if status.get("uploadStatus") in {"failed", "rejected", "deleted"} or processing.get("processingStatus") in {"failed", "terminated"}:
                reason = status.get("rejectionReason") or status.get("failureReason") or processing.get("processingFailureReason", "unknown")
                raise RuntimeError(f"YouTube rejected/failed video {video_id}: {reason}")
            if status.get("uploadStatus") == "processed" or processing.get("processingStatus") == "succeeded":
                return status
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Video {video_id} is still processing. Resume it later; do not upload again.")
        time.sleep(interval)


def save_result(entry):
    RUN_DIR.mkdir(exist_ok=True)
    temp = RESULT_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    temp.replace(RESULT_PATH)


def main():
    assets = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))
    from content_policy import enabled, profile
    if enabled(ROOT) and os.environ.get('EXPECTED_YOUTUBE_CHANNEL_ID', '').strip() != profile(ROOT)['youtube_channel_id']:
        raise RuntimeError('Expected channel must match the configured new channel before uploading or resuming')
    ledger = Ledger()
    youtube = build("youtube", "v3", credentials=get_credentials())
    verify_target_channel(youtube)
    resume = os.environ.get("RESUME_VIDEO_ID", "").strip()
    if resume:
        key, entry = ledger.find_video(resume)
        from content_policy import check_resume
        check_resume(ROOT, entry)
        if entry["assets"] != assets:
            raise RuntimeError("Resume assets differ from the original upload")
        video_id = resume
    else:
        if not VIDEO_PATH.exists():
            raise RuntimeError("Build the video before uploading")
        from channel_profile import publication_ready
        if not publication_ready(assets, ROOT):
            if assets.get('selection_explanation', {}).get('policy') == 'channel_profile':
                raise RuntimeError('Channel assets require source records, pool membership and successful automatic render checks')
            if os.environ.get("ALLOW_UNREVIEWED", "false").lower() != "true" or PRIVACY_STATUS == "public":
                raise RuntimeError("Unreviewed assets require explicit allow_unreviewed and private/unlisted visibility")
        publish_at = scheduled_release()
        key = ledger.reserve(assets, publish_at)
        entry = ledger.entries[key]
        if publish_at:
            print(f"Scheduling public release for {publish_at}")
        response = upload_video(youtube, assets, publish_at)
        video_id = response["id"]
        entry.update(video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}", state="uploaded")
        # Local recovery evidence first; remote persistence before any optional work.
        save_result(entry)
        ledger.save()
    try:
        # Set the cover before waiting: a processing timeout must not leave an auto-picked frame (Oct 20).
        if entry.get("thumbnail") != "set":
            set_thumbnail(youtube, video_id)
            entry["thumbnail"] = "set"
            save_result(entry)
            ledger.save()
        status = wait_for_processing(youtube, video_id)
        entry.update(state="complete", actual_privacy=status.get("privacyStatus"))
        entry.pop("last_error", None)
        save_result(entry)
        ledger.save()
        release = f"; scheduled to go public at {entry['publish_at']}" if entry.get("publish_at") else ""
        print(f"Processed successfully: {entry['url']} (visibility: {entry.get('actual_privacy')}{release})")
        write_summary(entry, assets)
    except Exception as exc:
        entry["last_error"] = str(exc)
        save_result(entry)
        ledger.save()
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"upload_youtube.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
