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

from google.oauth2.credentials import Credentials
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
# var entirely — an empty string must still fall back to the default.
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
            "EXPECTED_YOUTUBE_CHANNEL_ID is not set. Add it as a repo secret "
            "(the channel ID from your channel's URL, e.g. "
            "youtube.com/channel/<THIS_PART>) so uploads can be verified "
            "against the intended channel before publishing."
        )

    response = youtube.channels().list(part="id,snippet", mine=True).execute()
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
        return
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(THUMBNAIL_PATH), mimetype="image/jpeg"),
        ).execute()
        print("Thumbnail set.")
    except HttpError as exc:
        # Non-fatal: the video itself already uploaded successfully.
        print(f"Failed to set thumbnail (video still published): {exc}", file=sys.stderr)


def main():
    if not ASSETS_PATH.exists():
        raise RuntimeError(f"{ASSETS_PATH} not found — run select_assets.py first")
    if not VIDEO_PATH.exists():
        raise RuntimeError(f"{VIDEO_PATH} not found — run build_video.py first")

    assets = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    verify_target_channel(youtube)

    print(f"Uploading with privacyStatus={PRIVACY_STATUS!r}")
    response = upload_video(youtube, assets)
    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Uploaded: {video_url}")

    set_thumbnail(youtube, video_id)

    RESULT_PATH.write_text(json.dumps({"video_id": video_id, "url": video_url}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"upload_youtube.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
