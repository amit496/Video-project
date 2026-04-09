"""
Upload video to YouTube with title, description, tags, category, custom thumbnail.
First run opens browser for OAuth (Desktop app client_secret.json).
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
# Category 25 = News & Politics (verify in YouTube API docs)
DEFAULT_CATEGORY_ID = "25"


def _get_credentials() -> Credentials:
    creds = None
    token_path = config.YOUTUBE_TOKEN_PICKLE
    if token_path.is_file():
        creds = pickle.loads(token_path.read_bytes())
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.YOUTUBE_CLIENT_SECRETS.is_file():
                raise FileNotFoundError(
                    f"Missing {config.YOUTUBE_CLIENT_SECRETS}. Add OAuth Desktop client JSON from Google Cloud."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(config.YOUTUBE_CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_bytes(pickle.dumps(creds))
    return creds


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: Path | None = None,
    category_id: str = DEFAULT_CATEGORY_ID,
    privacy_status: str = "private",
) -> str:
    video_path = Path(video_path)
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload %d%%", int(status.progress() * 100))

    video_id = response["id"]
    logger.info("Uploaded video id=%s", video_id)

    if thumbnail_path and Path(thumbnail_path).is_file():
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
        logger.info("Thumbnail set.")

    return video_id


def build_metadata_from_script(script: str, news_keywords: list[str]) -> tuple[str, str, list[str]]:
    """Lightweight metadata; replace with LLM call for 'high quality' SEO copy."""
    first_line = script.strip().split("\n")[0][:90]
    title = f"World News Today | {first_line}"[:100]
    desc_lines = [
        "Daily world news roundup in clear English for Indian viewers.",
        "",
        "Topics covered:",
        *[f"• {k}" for k in news_keywords[:12]],
        "",
        "#WorldNews #NewsToday #India",
    ]
    description = "\n".join(desc_lines)[:5000]
    tags = list(
        dict.fromkeys(
            ["world news", "news today", "breaking news", "international news", "India"]
            + [k[:30] for k in news_keywords[:15]]
        )
    )
    return title, description, tags
