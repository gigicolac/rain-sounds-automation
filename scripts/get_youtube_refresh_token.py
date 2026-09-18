#!/usr/bin/env python3
"""One-time LOCAL helper to obtain a YouTube OAuth refresh token.

Run this on your own machine (NOT in GitHub Actions) after creating an
OAuth client in Google Cloud Console. It opens a browser for you to sign in
and grant access, then prints the refresh token to paste into GitHub
Secrets as YT_REFRESH_TOKEN. See README.md for the full Google Cloud
Console setup steps.

Usage:
    python scripts/get_youtube_refresh_token.py --client-secrets client_secret.json --expected-channel-id YOUR_CHANNEL_ID
"""
import argparse
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from upload_youtube import SCOPES, verify_target_channel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-secrets",
        default="client_secret.json",
        help="Path to the OAuth client JSON downloaded from Google Cloud Console "
             "(Desktop app type). Never commit this file.",
    )
    parser.add_argument(
        "--expected-channel-id", required=True,
        help="Intended YouTube channel identifier (starts with UC).",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    credentials = flow.run_local_server(
        port=0, access_type="offline", prompt="consent select_account",
    )
    if not credentials.refresh_token:
        raise RuntimeError("Google did not return a refresh token. Repeat sign-in and grant both requested permissions.")
    granted = credentials.granted_scopes
    if granted is not None and not set(SCOPES).issubset(granted):
        raise RuntimeError("Both youtube.upload and youtube.readonly permissions must be granted. Repeat sign-in.")
    os.environ["EXPECTED_YOUTUBE_CHANNEL_ID"] = args.expected_channel_id
    verify_target_channel(build("youtube", "v3", credentials=credentials))

    with open(args.client_secrets, "r", encoding="utf-8") as f:
        client_config = json.load(f)
    client_key = "installed" if "installed" in client_config else "web"
    client_id = client_config[client_key]["client_id"]
    client_secret = client_config[client_key]["client_secret"]

    print("\nSuccess! Add these three values as GitHub Actions repo secrets:\n")
    print(f"YT_CLIENT_ID={client_id}")
    print(f"YT_CLIENT_SECRET={client_secret}")
    print(f"YT_REFRESH_TOKEN={credentials.refresh_token}")
    print(
        "\n(Settings -> Secrets and variables -> Actions -> New repository secret, "
        "one secret per line above.)"
    )


if __name__ == "__main__":
    main()
