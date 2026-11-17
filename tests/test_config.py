"""Тесты путей, кэша и безопасной записи файлов."""

from __future__ import annotations

import pathlib

import pytest

from spoticube import config


def test_thumb_cache_path_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    first = config.thumb_cache_path("https://i.ytimg.com/vi/abc/hq.jpg")
    second = config.thumb_cache_path("https://i.ytimg.com/vi/abc/hq.jpg")

    assert first == second
    assert first.suffix == ".img"
    assert first.parent == tmp_path / "spoticube" / "thumbs"
    assert first.is_absolute()


def test_thumb_cache_path_differs_per_url(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert config.thumb_cache_path("a") != config.thumb_cache_path("b")


def test_default_download_dir_prefers_localized_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Загрузки").mkdir()

    assert config.default_download_dir() == tmp_path / "Загрузки" / "Spoticube"


def test_default_download_dir_falls_back_to_english(tmp_path, monkeypatch):
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Downloads").mkdir()

    assert config.default_download_dir() == tmp_path / "Downloads" / "Spoticube"


def test_default_download_dir_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    assert config.default_download_dir() == tmp_path / "Spoticube"


def test_save_bytes_atomic_writes_file(tmp_path):
    target = tmp_path / "nested" / "thumb.img"

    config.save_bytes_atomic(target, b"data")

    assert target.read_bytes() == b"data"
    assert list(target.parent.iterdir()) == [target]


def test_save_bytes_atomic_overwrites_existing(tmp_path):
    target = tmp_path / "thumb.img"
    target.write_bytes(b"old")

    config.save_bytes_atomic(target, b"new")

    assert target.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [target]


def test_save_bytes_atomic_keeps_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "thumb.img"
    target.write_bytes(b"old")

    def broken_replace(src, dst):
        raise OSError("диск отвалился")

    monkeypatch.setattr(config.os, "replace", broken_replace)

    with pytest.raises(OSError):
        config.save_bytes_atomic(target, b"new")

    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]
