#!/usr/bin/env python3
"""Upload run/output.mp4 to YouTube via the YouTube Data API, using a
refresh-token OAuth credential (no interactive login needed at run time â€”
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
CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 5
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}

# Defaults to "public" for full automation. Override with the repo variable
# UPLOAD_PRIVACY_STATUS=unlisted while reviewing the first few videos, then
# unset it (or set it back to "public") once you're happy with the output.
VALID_PRIVACY_STATUSES = {"public", "unlisted", "private"}
# `or "public"` (not just .get(..., "public")) because GitHub Actions sets
# an unset repo variable to an empty string rather than omitting the env
# var entirely â€” an empty string must still fall back to the default.
PRIVACY_STATUS = (os.environ.get("UPLOAD_PRIVACY_STATUS") or "public").strip().lower()
if PRIVACY_STATUS not in VALID_PRIVACY_STATUSES:
    raise ValueError(
        f"Invalid UPLOAD_PRIVACY_STATUS={PRIVACY_STATUS!r}; "
        f"must be one of {sorted(VALID_PRIVACY_STATUSES)}"
    )


def get_credentials():
    client_id = os.environ["YT_CLIENT_ID"]
    client_secret = os.environ["YT_CLIENT_SECRET"]
    refresh_token = os.environ["YT_REFRESH_TOKEN"]
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def verify_target_channel(youtube):
    """Guard against uploading to the wrong YouTube channel â€” a real
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
        response = youtube.channels().list(part="id,snippet", mine=True).execute()
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
            "wrong Google account/channel â€” redo the get_youtube_refresh_token.py "
            "step signed into the correct channel."
        )
    print(f"Verified target channel: {actual_channel_title!r} ({actual_channel_id})")


def upload_video(youtube, assets):
    body = {
        "snippet": {
            "title": assets["title"][:100],  # YouTube title limit
            "description": assets["description"][:5000],
            "tags": assets["tags"],
            "categoryId": assets.get("category_id", "10"),
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(VIDEO_PATH), chunksize=CHUNK_SIZE, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

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


def wait_for_processing(youtube, video_id, timeout=900, interval=15):
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
    ledger = Ledger()
    youtube = build("youtube", "v3", credentials=get_credentials())
    verify_target_channel(youtube)
    resume = os.environ.get("RESUME_VIDEO_ID", "").strip()
    if resume:
        key, entry = ledger.find_video(resume)
        if entry["assets"] != assets:
            raise RuntimeError("Resume assets differ from the original upload")
        video_id = resume
    else:
        if not VIDEO_PATH.exists():
            raise RuntimeError("Build the video before uploading")
        if not assets.get("review_approved"):
            if os.environ.get("ALLOW_UNREVIEWED", "false").lower() != "true" or PRIVACY_STATUS == "public":
                raise RuntimeError("Unreviewed assets require explicit allow_unreviewed and private/unlisted visibility")
        key = ledger.reserve(assets)
        entry = ledger.entries[key]
        response = upload_video(youtube, assets)
        video_id = response["id"]
        entry.update(video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}", state="uploaded")
        # Local recovery evidence first; remote persistence before any optional work.
        save_result(entry)
        ledger.save()
    try:
        status = wait_for_processing(youtube, video_id)
        entry.update(state="processed", actual_privacy=status.get("privacyStatus"))
        save_result(entry)
        ledger.save()
        set_thumbnail(youtube, video_id)
        entry.update(state="complete", thumbnail="set")
        save_result(entry)
        ledger.save()
        print(f"Processed successfully: {entry['url']} (visibility: {entry.get('actual_privacy')})")
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
