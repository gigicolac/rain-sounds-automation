#!/usr/bin/env python3
"""Standalone check: confirm the YT_* credentials resolve to the expected
YouTube channel, run early in the daily workflow (before the 30-90 minute
video build) so a wrong-channel setup fails in seconds, not after wasting
a full build cycle. Reuses the exact same check upload_youtube.py runs
before actually publishing, just without needing a video/thumbnail ready.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from googleapiclient.discovery import build  # noqa: E402

from upload_youtube import get_credentials, verify_target_channel  # noqa: E402


def main():
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    verify_target_channel(youtube)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"verify_youtube_channel.py failed: {exc}", file=sys.stderr)
        sys.exit(1)
