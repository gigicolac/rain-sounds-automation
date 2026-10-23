"""Read-only report of an owned video's settings, used to copy a reference
video's Studio choices into the upload presets. Prints no credentials."""
import json


def playlists_containing(youtube, video_id):
    found, token = [], None
    while True:
        page = youtube.playlists().list(part="snippet,status", mine=True, maxResults=50, pageToken=token).execute()
        for playlist in page.get("items", []):
            hits = youtube.playlistItems().list(part="id", playlistId=playlist["id"], videoId=video_id).execute()
            if hits.get("items"):
                found.append({"id": playlist["id"], "title": playlist["snippet"]["title"],
                              "privacy": playlist.get("status", {}).get("privacyStatus")})
        token = page.get("nextPageToken")
        if not token:
            return found


def video_settings(youtube, video_id):
    parts = "snippet,status,contentDetails,recordingDetails,localizations,topicDetails,paidProductPlacementDetails"
    items = youtube.videos().list(part=parts, id=video_id).execute().get("items", [])
    if not items:
        raise RuntimeError(f"Video {video_id} was not found for the authenticated channel")
    video = items[0]
    snippet = video.get("snippet", {})
    return {
        "id": video_id,
        "title": snippet.get("title"),
        "categoryId": snippet.get("categoryId"),
        "defaultLanguage": snippet.get("defaultLanguage"),
        "defaultAudioLanguage": snippet.get("defaultAudioLanguage"),
        "tags": snippet.get("tags", []),
        "status": video.get("status", {}),
        "contentDetails": video.get("contentDetails", {}),
        "recordingDetails": video.get("recordingDetails", {}),
        "localizations": sorted(video.get("localizations", {})),
        "topicDetails": video.get("topicDetails", {}),
        "paidProductPlacementDetails": video.get("paidProductPlacementDetails", {}),
        "playlists": playlists_containing(youtube, video_id),
    }


def report(youtube, video_id):
    print("Video settings report:")
    print(json.dumps(video_settings(youtube, video_id), indent=2, sort_keys=True))
