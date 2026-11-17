"""Главное окно приложения."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import config, yt
from ..models import SearchResult, VideoItem
from ..workers import DownloadWorker, SearchWorker, ThumbnailWorker
from .cards import DownloadRow, PreviewPane, ResultCard, card_grid_size

SEARCH_LIMIT = 24


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Spoticube — YouTube Downloader")
        self.resize(1200, 840)
        self.setAcceptDrops(True)

        self.settings = QSettings(config.ORG_NAME, config.APP_NAME)
        self.outdir: Path = config.default_download_dir()
        self.items: dict[str, VideoItem] = {}
        self.cards: dict[str, ResultCard] = {}
        self.current_key: str | None = None

        self._thumb_memory: dict[str, QPixmap] = {}
        self._thumb_workers: dict[str, ThumbnailWorker] = {}
        self._download_workers: dict[str, DownloadWorker] = {}
        self._active_downloads: dict[str, float] = {}
        self._search_worker: SearchWorker | None = None

        self.search_pool = QThreadPool(self)
        self.search_pool.setMaxThreadCount(2)
        self.thumb_pool = QThreadPool(self)
        self.thumb_pool.setMaxThreadCount(8)
        self.download_pool = QThreadPool(self)
        self.download_pool.setMaxThreadCount(3)

        self._build_ui()
        self._restore_settings()
        self._check_environment()

    # --- построение интерфейса -------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 10)
        outer.setSpacing(12)

        outer.addLayout(self._build_top_bar())

        self.results = QListWidget()
        self.results.setObjectName("Results")
        self.results.setViewMode(QListWidget.ViewMode.IconMode)
        self.results.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.results.setMovement(QListWidget.Movement.Static)
        self.results.setUniformItemSizes(True)
        self.results.setGridSize(card_grid_size())
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setWordWrap(True)

        self.preview = PreviewPane()
        self.preview.download_video.connect(lambda: self._download_current("video"))
        self.preview.download_audio.connect(lambda: self._download_current("audio"))
        self.preview.open_external.connect(self._open_url)

        top = QSplitter(Qt.Orientation.Horizontal)
        top.setChildrenCollapsible(False)
        top.addWidget(self.results)
        top.addWidget(self.preview)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 0)
        top.setSizes([780, 396])

        bottom = self._build_downloads_panel()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 250])
        outer.addWidget(self._build_results_header())
        outer.addWidget(splitter, 1)

        self.statusBar().showMessage("Введите запрос или ссылку на YouTube")

    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск на YouTube или ссылка: youtube.com/watch?v=… / youtu.be/…"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.start_search)
        bar.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("Найти")
        self.search_btn.setObjectName("Primary")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setMinimumWidth(96)
        self.search_btn.clicked.connect(self.start_search)
        bar.addWidget(self.search_btn)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Видео (MP4)", "video")
        self.mode_combo.addItem("Аудио (MP3)", "audio")
        self.mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        bar.addWidget(self.mode_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        bar.addWidget(self.quality_combo)

        self.folder_btn = QPushButton("Папка…")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.clicked.connect(self._choose_folder)
        bar.addWidget(self.folder_btn)

        self.open_folder_btn = QPushButton("Открыть папку")
        self.open_folder_btn.setObjectName("Ghost")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(lambda: self._open_folder(str(self.outdir)))
        bar.addWidget(self.open_folder_btn)

        return bar

    def _build_downloads_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("ЗАГРУЗКИ")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)

        self.clear_btn = QPushButton("Очистить завершённые")
        self.clear_btn.setObjectName("Ghost")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_finished)
        header.addWidget(self.clear_btn)
        layout.addLayout(header)

        self.downloads = QListWidget()
        self.downloads.setObjectName("Downloads")
        self.downloads.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.downloads.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.downloads.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.downloads, 1)
        return panel

    # --- поиск ----------------------------------------------------------------

    def start_search(self) -> None:
        query = self.search_input.text().strip()
        if not query or self._search_worker is not None:
            return
        self._clear_results()
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Поиск…")
        self.statusBar().showMessage(f"Ищу «{query}»…")

        worker = SearchWorker(query, SEARCH_LIMIT)
        worker.setAutoDelete(False)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.failed.connect(self._on_search_failed)
        self._search_worker = worker
        self.search_pool.start(worker)

    def _finish_search(self) -> None:
        self._search_worker = None
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Найти")

    def _on_search_finished(self, result: SearchResult) -> None:
        self._finish_search()
        items = list(result.items)
        if not items:
            self.results_label.setText("РЕЗУЛЬТАТЫ")
            self.download_all_btn.hide()
            self.statusBar().showMessage("Ничего не найдено — попробуйте другой запрос")
            return
        for item in items:
            self._add_result(item)

        if result.is_playlist:
            title = (result.playlist_title or "плейлист").upper()
            self.results_label.setText(f"ПЛЕЙЛИСТ · {title[:44]}")
            self.download_all_btn.setText(f"Скачать плейлист ({len(items)})")
        else:
            self.results_label.setText(f"РЕЗУЛЬТАТЫ · {len(items)}")
            self.download_all_btn.setText(f"Скачать всё ({len(items)})")
        self.download_all_btn.show()

        self.statusBar().showMessage(f"Найдено: {len(items)}")
        self._select_key(items[0].key)

    def _on_search_failed(self, message: str) -> None:
        self._finish_search()
        self.statusBar().showMessage(message, 10000)

    def _clear_results(self) -> None:
        self.results.clear()
        self.cards.clear()
        self.items.clear()
        self.current_key = None
        self.preview.clear()
        self.results_label.setText("РЕЗУЛЬТАТЫ")
        self.download_all_btn.hide()

    def _add_result(self, item: VideoItem) -> None:
        self.items[item.key] = item

        card = ResultCard(item)
        card.clicked.connect(self._select_key)
        card.activated.connect(self._on_card_activated)
        self.cards[item.key] = card

        entry = QListWidgetItem()
        entry.setData(Qt.ItemDataRole.UserRole, item.key)
        entry.setSizeHint(QSize(ResultCard.CARD_W + 14, ResultCard.CARD_H + 14))
        entry.setToolTip(item.title)
        self.results.addItem(entry)
        self.results.setItemWidget(entry, card)

        if item.thumbnail:
            self._request_thumbnail(item.thumbnail, card)

    def _select_key(self, key: str) -> None:
        item = self.items.get(key)
        if item is None:
            return
        previous = self.cards.get(self.current_key or "")
        if previous is not None:
            previous.set_selected(False)
        self.current_key = key
        card = self.cards.get(key)
        if card is not None:
            card.set_selected(True)

        self.preview.show_item(item)
        if item.thumbnail:
            pixmap = self._thumb_memory.get(item.thumbnail)
            if pixmap is not None:
                self.preview.set_thumbnail(pixmap)
            else:
                self._request_thumbnail(item.thumbnail, None)

    # --- превью ---------------------------------------------------------------

    def _request_thumbnail(self, url: str, card: ResultCard | None) -> None:
        pixmap = self._thumb_memory.get(url)
        if pixmap is not None:
            if card is not None:
                card.set_thumbnail(pixmap)
            return
        if url in self._thumb_workers:
            return
        worker = ThumbnailWorker(url)
        worker.setAutoDelete(False)
        worker.signals.finished.connect(
            lambda data, u=url: self._on_thumbnail_loaded(u, data)
        )
        self._thumb_workers[url] = worker
        self.thumb_pool.start(worker)

    def _on_thumbnail_loaded(self, url: str, data: bytes | None) -> None:
        self._thumb_workers.pop(url, None)
        if not data:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        if len(self._thumb_memory) > 240:
            self._thumb_memory.clear()
        self._thumb_memory[url] = pixmap

        for key, item in self.items.items():
            if item.thumbnail != url:
                continue
            card = self.cards.get(key)
            if card is not None:
                card.set_thumbnail(pixmap)

        current = self.preview.item
        if current is not None and current.thumbnail == url:
            self.preview.set_thumbnail(pixmap)

    # --- загрузки -------------------------------------------------------------

    def _on_card_activated(self, key: str) -> None:
        item = self.items.get(key)
        if item is not None:
            self._enqueue(item, str(self.mode_combo.currentData()))

    def _download_current(self, mode: str) -> None:
        if self.current_key is None:
            return
        item = self.items.get(self.current_key)
        if item is not None:
            self._enqueue(item, mode)

    def _enqueue(self, item: VideoItem, mode: str | None = None) -> None:
        mode = mode or str(self.mode_combo.currentData())
        try:
            self.outdir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Папка недоступна", f"Не удалось создать папку:\n{exc}")
            return

        if mode == "audio":
            bitrate = int(self.quality_combo.currentData() or 192)
            opts = yt.audio_opts(self.outdir, bitrate)
        else:
            raw = self.quality_combo.currentData()
            height = None if raw in (None, -1) else int(raw)
            opts = yt.video_opts(self.outdir, height)

        row = DownloadRow(item)
        entry = QListWidgetItem()
        entry.setSizeHint(QSize(420, 84))
        self.downloads.addItem(entry)
        self.downloads.setItemWidget(entry, row)
        self.downloads.scrollToBottom()

        worker = DownloadWorker(item, opts)
        worker.setAutoDelete(False)
        token = f"{item.key}:{id(worker)}"
        self._download_workers[token] = worker
        self._active_downloads[token] = 0.0
        self._update_title()

        row.cancel_requested.connect(worker.cancel)
        row.open_requested.connect(self._open_folder)
        worker.signals.progress.connect(row.set_progress)
        worker.signals.progress.connect(
            lambda data, t=token: self._on_download_progress(t, data)
        )
        worker.signals.status.connect(row.set_status)
        worker.signals.finished.connect(
            lambda path, t=token: self._on_download_finished(t, row, path)
        )
        worker.signals.failed.connect(
            lambda message, t=token: self._on_download_failed(t, row, message)
        )
        worker.signals.cancelled.connect(
            lambda t=token: self._on_download_cancelled(t, row)
        )

        row.set_status("Подготовка…")
        self.download_pool.start(worker)
        self.statusBar().showMessage(f"Загрузка: {item.title}", 6000)

    def _on_download_finished(self, token: str, row: DownloadRow, path: str | None) -> None:
        self._download_workers.pop(token, None)
        self._active_downloads.pop(token, None)
        row.set_done(path)
        self._update_title()
        self.statusBar().showMessage("Загрузка завершена", 6000)

    def _on_download_failed(self, token: str, row: DownloadRow, message: str) -> None:
        self._download_workers.pop(token, None)
        self._active_downloads.pop(token, None)
        row.set_error(message)
        self._update_title()
        self.statusBar().showMessage("Загрузка не удалась — подробности в очереди", 8000)

    def _on_download_cancelled(self, token: str, row: DownloadRow) -> None:
        self._download_workers.pop(token, None)
        self._active_downloads.pop(token, None)
        row.set_cancelled()
        self._update_title()
        self.statusBar().showMessage("Загрузка отменена", 5000)

    def _clear_finished(self) -> None:
        for index in reversed(range(self.downloads.count())):
            entry = self.downloads.item(index)
            widget = self.downloads.itemWidget(entry)
            if isinstance(widget, DownloadRow) and widget._finished:
                self.downloads.takeItem(index)

    # --- папки и ссылки -------------------------------------------------------

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Папка для загрузок", str(self.outdir)
        )
        if not directory:
            return
        self.outdir = Path(directory)
        self.settings.setValue("outdir", str(self.outdir))
        self._update_folder_label()

    def _update_folder_label(self) -> None:
        self.folder_btn.setToolTip(str(self.outdir))
        name = self.outdir.name or str(self.outdir)
        self.folder_btn.setText(f"Папка: {name}")

    def _open_folder(self, path: str) -> None:
        target = Path(path)
        if not target.exists():
            target = self.outdir
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    # --- настройки ------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        mode = str(self.mode_combo.currentData())
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        if mode == "audio":
            for label, value in yt.AUDIO_BITRATES:
                self.quality_combo.addItem(label, int(value))
            self.quality_combo.setCurrentIndex(1)
        else:
            for label, height in yt.VIDEO_HEIGHTS:
                self.quality_combo.addItem(label, -1 if height is None else int(height))
            self.quality_combo.setCurrentIndex(1)
        self.quality_combo.blockSignals(False)
        self.settings.setValue("mode", mode)

    def _on_quality_changed(self) -> None:
        value = self.quality_combo.currentData()
        if value is None:
            return
        self.settings.setValue("quality", int(value))

    def _restore_settings(self) -> None:
        stored = self.settings.value("outdir", str(config.default_download_dir()))
        path = Path(str(stored)).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            self.outdir = path
        except OSError:
            self.outdir = Path.home()
        self._update_folder_label()

        mode = str(self.settings.value("mode", "video"))
        index = self.mode_combo.findData(mode)
        self.mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_mode_changed()

        saved = self.settings.value("quality")
        if saved is not None:
            try:
                value = int(saved)
            except (TypeError, ValueError):
                value = 0
            quality_index = self.quality_combo.findData(value)
            if quality_index >= 0:
                self.quality_combo.setCurrentIndex(quality_index)

    def _check_environment(self) -> None:
        if not yt.ffmpeg_available():
            self.statusBar().showMessage(
                "ffmpeg не найден: MP3 и склейка видео недоступны — будут скачиваться готовые файлы",
                15000,
            )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.settings.setValue("outdir", str(self.outdir))
        self.settings.sync()
        for worker in list(self._download_workers.values()):
            worker.cancel()
        self.thumb_pool.clear()
        self.search_pool.clear()
        self.thumb_pool.waitForDone(800)
        self.search_pool.waitForDone(800)
        super().closeEvent(event)

    # --- массовая загрузка ----------------------------------------------------

    def _build_results_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(8)

        self.results_label = QLabel("РЕЗУЛЬТАТЫ")
        self.results_label.setObjectName("SectionTitle")
        layout.addWidget(self.results_label)
        layout.addStretch(1)

        self.download_all_btn = QPushButton("Скачать всё")
        self.download_all_btn.setObjectName("Ghost")
        self.download_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_all_btn.clicked.connect(self._download_all)
        self.download_all_btn.hide()
        layout.addWidget(self.download_all_btn)
        return header

    def _download_all(self) -> None:
        items = list(self.items.values())
        if not items:
            return
        mode = str(self.mode_combo.currentData())
        for item in items:
            self._enqueue(item, mode)
        self.statusBar().showMessage(
            f"В очередь добавлено: {len(items)}. Загрузки идут по три параллельно", 8000
        )

    # --- счётчик в заголовке --------------------------------------------------

    def _on_download_progress(self, token: str, data: dict) -> None:
        if token not in self._active_downloads:
            return
        percent = data.get("percent")
        if percent is None or percent < 0:
            return
        self._active_downloads[token] = float(percent)
        self._update_title()

    def _update_title(self) -> None:
        active = self._active_downloads
        if not active:
            self.setWindowTitle("Spoticube — YouTube Downloader")
            return
        values = [value for value in active.values() if value >= 0]
        average = sum(values) / len(values) if values else 0.0
        count = len(active)
        if count % 10 == 1 and count % 100 != 11:
            word = "загрузка"
        elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
            word = "загрузки"
        else:
            word = "загрузок"
        self.setWindowTitle(f"Spoticube — {count} {word} · {average:.0f}%")

    # --- перетаскивание ссылки ------------------------------------------------

    @staticmethod
    def _dropped_url(mime) -> str | None:
        if mime.hasUrls():
            for url in mime.urls():
                text = url.toString()
                if yt.looks_like_url(text) or "youtu" in text:
                    return text
        if mime.hasText():
            text = mime.text().strip()
            if yt.looks_like_url(text):
                return text
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._dropped_url(event.mimeData()):
            self.statusBar().showMessage("Отпустите ссылку, чтобы загрузить видео")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._dropped_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.statusBar().showMessage("Введите запрос или ссылку на YouTube")
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        url = self._dropped_url(event.mimeData())
        if not url:
            event.ignore()
            return
        self.search_input.setText(url)
        self.start_search()
        event.acceptProposedAction()
