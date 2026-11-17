"""Обёртка над yt-dlp: поиск, метаданные и опции скачивания."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import yt_dlp

from .models import SearchResult, VideoItem

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

AUDIO_BITRATES: list[tuple[str, int]] = [
    ("128 kbps", 128),
    ("192 kbps", 192),
    ("320 kbps", 320),
]

VIDEO_HEIGHTS: list[tuple[str, int | None]] = [
    ("Лучшее доступное", None),
    ("1080p", 1080),
    ("720p", 720),
    ("480p", 480),
    ("360p", 360),
]

OUTTEMPLATE = "%(title).150B [%(id)s].%(ext)s"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match(text.strip()))


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": False,
        "concurrent_fragment_downloads": 4,
        "windowsfilenames": False,
    }


def _search_opts() -> dict:
    opts = _base_opts()
    opts.update(
        {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "cachedir": False,
        }
    )
    return opts


def _best_thumbnail(entry: dict) -> str | None:
    thumbs = [t for t in (entry.get("thumbnails") or []) if t.get("url")]
    if thumbs:
        thumbs.sort(
            key=lambda t: (t.get("width") or 0) * (t.get("height") or 0),
            reverse=True,
        )
        return thumbs[0]["url"]
    return entry.get("thumbnail")


def _entry_to_item(entry: dict) -> VideoItem | None:
    if not entry:
        return None
    video_id = entry.get("id") or ""
    url = entry.get("webpage_url") or entry.get("url") or ""
    if video_id and not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={video_id}"
    if not url.startswith("http"):
        return None
    title = entry.get("title") or video_id or "Без названия"
    duration = entry.get("duration")
    return VideoItem(
        video_id=video_id,
        title=title,
        url=url,
        channel=entry.get("channel") or entry.get("uploader") or "",
        duration=int(duration) if isinstance(duration, (int, float)) else None,
        thumbnail=_best_thumbnail(entry),
        view_count=entry.get("view_count"),
    )


def search(query: str, limit: int = 20, playlist_limit: int = 100) -> SearchResult:
    """Ищет видео на YouTube или разбирает переданную ссылку."""
    query = query.strip()
    if not query:
        return SearchResult(items=[])

    from_url = looks_like_url(query)
    target = query if from_url else f"ytsearch{limit}:{query}"
    with yt_dlp.YoutubeDL(_search_opts()) as ydl:
        info = ydl.extract_info(target, download=False)

    if not info:
        return SearchResult(items=[])

    entries = info.get("entries") if info.get("_type") == "playlist" else None
    is_playlist = from_url and entries is not None
    if entries is None:
        items = [_entry_to_item(info)]
        playlist_title = ""
    else:
        items = [_entry_to_item(entry) for entry in entries if entry]
        playlist_title = str(info.get("title") or "") if is_playlist else ""

    result: list[VideoItem] = []
    seen: set[str] = set()
    for item in items:
        if item is None or item.key in seen:
            continue
        seen.add(item.key)
        result.append(item)

    cap = playlist_limit if is_playlist else limit
    return SearchResult(
        items=result[:cap],
        is_playlist=is_playlist,
        playlist_title=playlist_title,
    )


def video_opts(outdir: str | Path, height: int | None) -> dict:
    opts = _base_opts()
    if ffmpeg_available():
        selector = f"bv*[height<={height}]+ba/b[height<={height}]/b" if height else "bv*+ba/b"
        opts.update({"format": selector, "merge_output_format": "mp4"})
    else:
        selector = f"b[height<={height}]/b" if height else "b"
        opts.update({"format": selector})
    opts.update(
        {
            "outtmpl": {"default": OUTTEMPLATE},
            "paths": {"home": str(outdir)},
            "nopart": False,
        }
    )
    return opts


def audio_opts(outdir: str | Path, bitrate: int = 192) -> dict:
    opts = _base_opts()
    if ffmpeg_available():
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(bitrate),
                    }
                ],
                "final_ext": "mp3",
                "postprocessor_args": {"extractaudio": ["-b:a", f"{bitrate}k"]},
            }
        )
    else:
        opts.update({"format": "bestaudio[ext=m4a]/bestaudio/best"})
    opts.update(
        {
            "outtmpl": {"default": OUTTEMPLATE},
            "paths": {"home": str(outdir)},
            "nopart": False,
        }
    )
    return opts
