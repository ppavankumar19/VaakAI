import os
from urllib.parse import urlparse

import yt_dlp

# yt-dlp renamed MatchFilterReject → RejectedVideoReached in 2025+
_MatchFilterReject = getattr(yt_dlp.utils, 'RejectedVideoReached',
                             getattr(yt_dlp.utils, 'MatchFilterReject', Exception))

YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
MAX_DURATION_SECONDS = 3600   # 60 minutes
MAX_FILE_BYTES = 500 * 1024 * 1024  # 500 MB


class URLDownloadError(Exception):
    pass


def validate_youtube_url(url: str) -> None:
    """Raise URLDownloadError if url is not a safe public YouTube URL."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise URLDownloadError("Invalid URL format.")

    if parsed.scheme not in ("http", "https"):
        raise URLDownloadError("Only http/https URLs are supported.")

    if parsed.netloc.lower() not in YOUTUBE_DOMAINS:
        raise URLDownloadError(
            "Only YouTube URLs are supported (youtube.com or youtu.be)."
        )


def _check_duration(info, *, incomplete):
    duration = info.get("duration")
    if duration and duration > MAX_DURATION_SECONDS:
        return f"Video exceeds {MAX_DURATION_SECONDS // 60}-minute limit."
    return None


def download_youtube_video(url: str, session_id: str, download_dir: str) -> tuple[str, str]:
    """
    Download a public YouTube video to download_dir/{session_id}.ext.
    Returns (video_path, title).
    Raises URLDownloadError on failure.
    """
    validate_youtube_url(url)
    os.makedirs(download_dir, exist_ok=True)

    output_template = os.path.join(download_dir, f"{session_id}.%(ext)s")

    ydl_opts = {
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "max_filesize": MAX_FILE_BYTES,
        "match_filter": _check_duration,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except _MatchFilterReject as e:
            raise URLDownloadError(str(e))
        except yt_dlp.utils.DownloadError as e:
            raise URLDownloadError(str(e))

    title = info.get("title", "YouTube Video")
    ext = info.get("ext", "mp4")
    video_path = os.path.join(download_dir, f"{session_id}.{ext}")

    if not os.path.exists(video_path):
        # yt-dlp may have merged to a different extension; scan for the file
        for fname in os.listdir(download_dir):
            if fname.startswith(session_id + "."):
                video_path = os.path.join(download_dir, fname)
                break
        else:
            raise URLDownloadError("Downloaded file not found after yt-dlp run.")

    if os.path.getsize(video_path) > MAX_FILE_BYTES:
        os.remove(video_path)
        raise URLDownloadError("Downloaded file exceeds 500 MB limit.")

    return video_path, title
