"""Фоновые задачи (QRunnable) для поиска, превью и скачивания."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal

from . import config, yt
from .models import VideoItem


class DownloadCancelled(Exception):
    """Пользователь отменил загрузку."""


_NO_PAYLOAD = object()


def _safe_emit(signal, payload=_NO_PAYLOAD) -> None:
    """Отправляет сигнал, не падая, если объект уже уничтожен при выходе."""
    try:
        if payload is _NO_PAYLOAD:
            signal.emit()
        else:
            signal.emit(payload)
    except (RuntimeError, TypeError):
        pass


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)
    status = Signal(str)
    cancelled = Signal()


class SearchWorker(QRunnable):
    def __init__(self, query: str, limit: int = 20) -> None:
        super().__init__()
        self.query = query
        self.limit = limit
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = yt.search(self.query, self.limit)
        except Exception as exc:  # noqa: BLE001 - текст показываем пользователю
            _safe_emit(self.signals.failed, f"Поиск не удался: {exc}")
            return
        _safe_emit(self.signals.finished, result)


class ThumbnailWorker(QRunnable):
    """Скачивает превью и кэширует его на диске."""

    MAX_BYTES = 4 * 1024 * 1024

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = WorkerSignals()

    def _load(self, path: Path) -> bytes | None:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path.read_bytes()
        except OSError:
            return None
        return None

    def run(self) -> None:
        cache_path = config.thumb_cache_path(self.url)
        cached = self._load(cache_path)
        if cached:
            _safe_emit(self.signals.finished, cached)
            return

        request = urllib.request.Request(
            self.url, headers={"User-Agent": config.USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(self.MAX_BYTES)
        except (urllib.error.URLError, OSError, ValueError):
            _safe_emit(self.signals.finished, None)
            return

        try:
            cache_path.write_bytes(data)
        except OSError:
            pass
        _safe_emit(self.signals.finished, data)


class DownloadWorker(QRunnable):
    """Скачивает один элемент через yt-dlp с прогрессом и отменой."""

    def __init__(self, item: VideoItem, opts: dict) -> None:
        super().__init__()
        self.item = item
        self.opts = dict(opts)
        self.signals = WorkerSignals()
        self._cancel = threading.Event()
        self._last_emit = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    def _hook(self, data: dict) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled()

        status = data.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - self._last_emit < 0.15:
                return
            self._last_emit = now
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            percent = (done / total * 100.0) if total else -1.0
            _safe_emit(
                self.signals.progress,
                {
                    "percent": percent,
                    "downloaded": done,
                    "total": total,
                    "speed": data.get("speed"),
                    "eta": data.get("eta"),
                },
            )
        elif status == "finished":
            total = data.get("total_bytes") or data.get("downloaded_bytes") or 0
            _safe_emit(
                self.signals.progress,
                {
                    "percent": 100.0,
                    "downloaded": total,
                    "total": total,
                    "speed": None,
                    "eta": 0,
                },
            )
            _safe_emit(self.signals.status, "Обработка (ffmpeg)…")

    @staticmethod
    def _result_path(info: dict | None) -> str | None:
        if not info:
            return None
        downloads = info.get("requested_downloads") or []
        if downloads:
            candidate = downloads[0].get("filepath") or downloads[0].get("_filename")
            if candidate:
                return str(candidate)
        return info.get("filepath") or info.get("_filename")

    def run(self) -> None:
        opts = dict(self.opts)
        opts["progress_hooks"] = [self._hook]
        try:
            with yt_dlp.YoutubeDL(opts) as downloader:
                info = downloader.extract_info(self.item.url, download=True)
                path = self._result_path(info)
        except BaseException as exc:  # noqa: BLE001 - в т.ч. DownloadCancelled и системные
            self._cleanup_partials()
            if self._cancel.is_set() or isinstance(exc, DownloadCancelled):
                _safe_emit(self.signals.cancelled)
            else:
                _safe_emit(self.signals.failed, str(exc) or exc.__class__.__name__)
            return

        if self._cancel.is_set():
            self._cleanup_partials()
            _safe_emit(self.signals.cancelled)
            return
        _safe_emit(self.signals.finished, path)

    def _cleanup_partials(self) -> None:
        """Удаляет недокачанные фрагменты, чтобы не мусорить в папке."""
        home = (self.opts.get("paths") or {}).get("home")
        if not home or not self.item.video_id:
            return
        directory = Path(str(home))
        if not directory.is_dir():
            return
        marker = f"[{self.item.video_id}]"
        for pattern in ("*.part", "*.ytdl", "*.temp"):
            for path in directory.glob(pattern):
                if marker not in path.name:
                    continue
                try:
                    path.unlink()
                except OSError:
                    pass
