#!/usr/bin/env python3
"""Post the channel's standard comment on each scheduled upload once it is public.

The YouTube Data API has no pin method, so pinning stays a manual tap; the run
summary links straight to each new comment. Comments are recorded in upload
history so a video is never commented on twice.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from googleapiclient.discovery import build  # noqa: E402

from upload_history import Ledger  # noqa: E402
from upload_youtube import COMMENT_SCOPES, ROOT, get_credentials, verify_target_channel  # noqa: E402

COMMENT_PATH = ROOT / "data" / "pinned_comment.txt"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def due(entries, now):
    """Completed scheduled uploads whose release time has passed and have no comment yet."""
    return [(key, e) for key, e in entries.items()
            if e.get("state") == "complete" and e.get("video_id") and e.get("publish_at")
            and not e.get("comment_id") and parse_time(e["publish_at"]) <= now]


def existing_comment(youtube, video_id, channel_id, text):
    """Recover a comment posted by an earlier run that stopped before recording it."""
    page = youtube.commentThreads().list(part="snippet", videoId=video_id, maxResults=100).execute()
    for thread in page.get("items", []):
        top = thread["snippet"]["topLevelComment"]
        snippet = top["snippet"]
        if snippet.get("authorChannelId", {}).get("value") == channel_id and snippet.get("textOriginal", "").strip() == text:
            return top["id"]
    return None


def comment_text(entry, default):
    # Each upload's own question gets more replies than a generic thank-you.
    return (entry.get("assets", {}).get("pinned_comment") or "").strip() or default


def post_due_comments(youtube, ledger, default_text, channel_id, now):
    links, errors = [], []
    for _, entry in due(ledger.entries, now):
        if (entry.get('channel_id') or entry.get('assets', {}).get('channel_id')) != channel_id:
            continue  # Preserve old history without posting from the new channel on old videos.
        video_id = entry["video_id"]
        text = comment_text(entry, default_text)
        try:
            items = youtube.videos().list(part="status", id=video_id).execute().get("items", [])
            if not items or items[0]["status"].get("privacyStatus") != "public":
                print(f"{video_id} is not public yet; the next run will retry.")
                continue
            entry["actual_privacy"] = "public"
            comment_id = None
            if entry.get("comment_state") == "posting":
                comment_id = existing_comment(youtube, video_id, channel_id, text)
            if not comment_id:
                entry["comment_state"] = "posting"
                ledger.save()  # Recorded before posting so a crash cannot cause a duplicate.
                response = youtube.commentThreads().insert(part="snippet", body={"snippet": {
                    "videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
                comment_id = response["snippet"]["topLevelComment"]["id"]
            entry.update(comment_id=comment_id, comment_state="posted")
            ledger.save()
            links.append(f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}")
        except Exception as exc:  # noqa: BLE001 - one video must not block the others
            errors.append(f"{video_id}: {exc}")
    return links, errors


def main():
    text = COMMENT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("data/pinned_comment.txt is empty")
    ledger = Ledger()
    youtube = build("youtube", "v3", credentials=get_credentials(COMMENT_SCOPES))
    try:
        verify_target_channel(youtube)
    except RuntimeError as exc:
        if "could not be refreshed" in str(exc):
            raise RuntimeError(
                "The YouTube login does not include comment permission yet. Run "
                "scripts/get_youtube_refresh_token.py locally, grant all permissions, and "
                "replace the YT_REFRESH_TOKEN secret. Uploads are unaffected meanwhile.") from exc
        raise
    links, errors = post_due_comments(youtube, ledger, text, os.environ["EXPECTED_YOUTUBE_CHANNEL_ID"],
                                      datetime.now(timezone.utc))
    lines = ["## Comments to pin", ""] + [f"- [Open and pin]({link})" for link in links]
    if not links:
        lines.append("No new comments this run.")
    print("\n".join(lines))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("\n".join(lines) + "\n")
    if errors:
        raise RuntimeError("Some comments failed: " + "; ".join(errors))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"post_pinned_comment.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
