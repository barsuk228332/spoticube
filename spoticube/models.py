"""Модель данных о видео."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VideoItem:
    video_id: str
    title: str
    url: str
    channel: str = ""
    duration: int | None = None
    thumbnail: str | None = None
    view_count: int | None = None

    @property
    def key(self) -> str:
        return self.video_id or self.url


@dataclass(slots=True)
class SearchResult:
    """Результат поиска: найденные видео и признак плейлиста."""

    items: list[VideoItem]
    is_playlist: bool = False
    playlist_title: str = ""
