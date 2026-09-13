#!/usr/bin/env python3
"""One-time LOCAL helper to obtain a YouTube OAuth refresh token.

Run this on your own machine (NOT in GitHub Actions) after creating an
OAuth client in Google Cloud Console. It opens a browser for you to sign in
and grant access, then prints the refresh token to paste into GitHub
Secrets as YT_REFRESH_TOKEN. See README.md for the full Google Cloud
Console setup steps.

Usage:
    python scripts/get_youtube_refresh_token.py --client-secrets client_secret.json
"""
import argparse
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # Needed so the daily job can verify it's uploading to the right channel
    # before publishing (channels().list(mine=True)).
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-secrets",
        default="client_secret.json",
        help="Path to the OAuth client JSON downloaded from Google Cloud Console "
             "(Desktop app type). Never commit this file.",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    credentials = flow.run_local_server(port=0)

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
