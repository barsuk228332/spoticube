"""Тесты обёртки над yt-dlp: ссылки, разбор записей и выбор форматов."""

from __future__ import annotations

import pytest

from spoticube import yt


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc", True),
        ("http://youtu.be/abc", True),
        ("  https://example.com/video  ", True),
        ("HTTP://EXAMPLE.COM", True),
        ("youtube.com/watch?v=abc", False),
        ("просто поисковый запрос", False),
        ("", False),
        ("www.youtube.com/watch?v=abc", False),
    ],
)
def test_looks_like_url(text, expected):
    assert yt.looks_like_url(text) is expected


def test_best_thumbnail_picks_largest():
    entry = {
        "thumbnails": [
            {"url": "small.jpg", "width": 120, "height": 90},
            {"url": "big.jpg", "width": 1280, "height": 720},
            {"url": "mid.jpg", "width": 480, "height": 360},
        ]
    }
    assert yt._best_thumbnail(entry) == "big.jpg"


def test_best_thumbnail_ignores_entries_without_url():
    entry = {"thumbnails": [{"width": 1280}, {"url": "only.jpg", "width": 10, "height": 10}]}
    assert yt._best_thumbnail(entry) == "only.jpg"


def test_best_thumbnail_falls_back_to_thumbnail_field():
    assert yt._best_thumbnail({"thumbnail": "fallback.jpg"}) == "fallback.jpg"


def test_best_thumbnail_returns_none_when_absent():
    assert yt._best_thumbnail({}) is None


def test_entry_to_item_builds_watch_url_from_id():
    item = yt._entry_to_item({"id": "abc123"})
    assert item is not None
    assert item.url == "https://www.youtube.com/watch?v=abc123"
    assert item.title == "abc123"
    assert item.key == "abc123"


def test_entry_to_item_keeps_full_metadata():
    item = yt._entry_to_item(
        {
            "id": "xyz",
            "title": "Название",
            "webpage_url": "https://www.youtube.com/watch?v=xyz",
            "channel": "Канал",
            "duration": 61.7,
            "thumbnail": "thumb.jpg",
            "view_count": 42,
        }
    )
    assert item is not None
    assert (item.title, item.channel, item.duration, item.view_count) == (
        "Название",
        "Канал",
        61,
        42,
    )


def test_entry_to_item_falls_back_to_uploader():
    item = yt._entry_to_item({"id": "abc", "uploader": "Автор"})
    assert item is not None
    assert item.channel == "Автор"


def test_entry_to_item_rejects_empty_or_urlless():
    assert yt._entry_to_item({}) is None
    assert yt._entry_to_item({"title": "без id и ссылки"}) is None


def test_search_on_empty_query_does_not_touch_network():
    result = yt.search("   ")
    assert result.items == []
    assert result.is_playlist is False


def test_video_opts_with_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "ffmpeg_available", lambda: True)

    opts = yt.video_opts(tmp_path, 1080)

    assert opts["format"] == "bv*[height<=1080]+ba/b[height<=1080]/b"
    assert opts["merge_output_format"] == "mp4"
    assert opts["paths"]["home"] == str(tmp_path)


def test_video_opts_best_quality(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "ffmpeg_available", lambda: True)

    assert yt.video_opts(tmp_path, None)["format"] == "bv*+ba/b"


def test_video_opts_without_ffmpeg_uses_single_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "ffmpeg_available", lambda: False)

    opts = yt.video_opts(tmp_path, 720)

    assert opts["format"] == "b[height<=720]/b"
    assert "merge_output_format" not in opts


def test_audio_opts_with_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "ffmpeg_available", lambda: True)

    opts = yt.audio_opts(tmp_path, 320)

    assert opts["format"] == "bestaudio/best"
    assert opts["final_ext"] == "mp3"
    postprocessor = opts["postprocessors"][0]
    assert postprocessor["preferredcodec"] == "mp3"
    assert postprocessor["preferredquality"] == "320"


def test_audio_opts_without_ffmpeg_keeps_native_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "ffmpeg_available", lambda: False)

    opts = yt.audio_opts(tmp_path, 192)

    assert opts["format"] == "bestaudio[ext=m4a]/bestaudio/best"
    assert "postprocessors" not in opts
