#!/usr/bin/env python3
"""Рендерит промо-превью Spoticube в PNG средствами Qt (без внешних картинок).

Запуск:
    QT_QPA_PLATFORM=offscreen python3 tools/render_preview.py [выходной_файл]
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QListWidgetItem,
)

from spoticube import config, yt
from spoticube.ui.cards import DownloadRow
from spoticube.ui.main_window import MainWindow
from spoticube.ui.theme import apply_theme

WINDOW_W, WINDOW_H = 1240, 820
CANVAS_W, CANVAS_H = 1600, 1080
WINDOW_POS = ((CANVAS_W - WINDOW_W) // 2, 168)
RADIUS = 16.0

ACCENT = QColor("#3ddc84")
TEXT = QColor("#e6edf3")
MUTED = QColor("#8b98a9")


def load_thumbnail(url: str) -> QPixmap:
    """Берёт превью из кэша Spoticube или скачивает и кэширует."""
    path = config.thumb_cache_path(url)
    if path.is_file() and path.stat().st_size:
        data = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(4 * 1024 * 1024)
            path.write_bytes(data)
        except OSError:
            return QPixmap()

    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return QPixmap()
    return pixmap


def build_window(app: QApplication) -> MainWindow:
    window = MainWindow()
    window.resize(WINDOW_W, WINDOW_H)
    window.show()
    app.processEvents()

    result = yt.search("lofi hip hop", 6)
    if not result.items:
        raise SystemExit("Поиск ничего не вернул — проверь сеть")

    window._on_search_finished(result)
    app.processEvents()

    first_pixmap = QPixmap()
    for index, item in enumerate(result.items[:6]):
        if not item.thumbnail:
            continue
        pixmap = load_thumbnail(item.thumbnail)
        if pixmap.isNull():
            continue
        window._thumb_memory[item.thumbnail] = pixmap
        card = window.cards.get(item.key)
        if card is not None:
            card.set_thumbnail(pixmap)
        if index == 0:
            first_pixmap = pixmap

    if not first_pixmap.isNull():
        window.preview.set_thumbnail(first_pixmap)

    window.quality_combo.setCurrentIndex(window.quality_combo.findData(1080))

    done_item, active_item, queued_item = (
        result.items[0],
        result.items[1],
        result.items[2],
    )

    finished_row = DownloadRow(done_item)
    finished_row.set_done("/home/barsuk/Загрузки/Spoticube/lofi hip hop radio [abc123].mp3")

    active_row = DownloadRow(active_item)
    active_row.set_progress(
        {
            "percent": 63.0,
            "downloaded": 41_500_000,
            "total": 65_800_000,
            "speed": 3_400_000,
            "eta": 7,
        }
    )

    queued_row = DownloadRow(queued_item)
    queued_row.set_status("В очереди…")

    for row in (finished_row, active_row, queued_row):
        entry = QListWidgetItem()
        entry.setSizeHint(row.sizeHint())
        window.downloads.addItem(entry)
        window.downloads.setItemWidget(entry, row)

    window._active_downloads = {"active": 63.0, "queued": 0.0}
    window._update_title()
    window.statusBar().showMessage("Загрузка: 63% · 3,4 МБ/с", 0)

    app.processEvents()
    QTest.qWait(250)
    return window


def rounded(pixmap: QPixmap, radius: float = RADIUS) -> QPixmap:
    out = QPixmap(pixmap.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(pixmap.rect()), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return out


def draw_captions(painter: QPainter) -> None:
    title_font = QFont()
    title_font.setPixelSize(42)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(TEXT)
    painter.drawText(QPointF(WINDOW_POS[0], 88), "Spoticube")

    subtitle_font = QFont()
    subtitle_font.setPixelSize(17)
    painter.setFont(subtitle_font)
    painter.setPen(MUTED)
    painter.drawText(
        QPointF(WINDOW_POS[0], 122),
        "Поиск · превью · MP4 и MP3 · очередь загрузок",
    )

    badge_font = QFont()
    badge_font.setPixelSize(15)
    badge_font.setBold(True)
    painter.setFont(badge_font)
    text = "PySide6 + yt-dlp"
    width = painter.fontMetrics().horizontalAdvance(text)
    badge = QRectF(CANVAS_W - WINDOW_POS[0] - width - 30, 66, width + 30, 34)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(61, 220, 132, 30))
    painter.drawRoundedRect(badge, 17, 17)
    painter.setPen(ACCENT)
    painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "spoticube-preview.png"

    app = QApplication(sys.argv[:1])
    apply_theme(app)
    window = build_window(app)
    window_pixmap = rounded(window.grab())

    canvas = QPixmap(CANVAS_W, CANVAS_H)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    background = QLinearGradient(0, 0, 0, CANVAS_H)
    background.setColorAt(0.0, QColor("#0c1118"))
    background.setColorAt(1.0, QColor("#080a0e"))
    painter.fillRect(canvas.rect(), background)

    glow = QRadialGradient(QPointF(CANVAS_W * 0.5, 120), CANVAS_W * 0.62)
    glow.setColorAt(0.0, QColor(61, 220, 132, 54))
    glow.setColorAt(0.45, QColor(61, 220, 132, 16))
    glow.setColorAt(1.0, QColor(61, 220, 132, 0))
    painter.fillRect(canvas.rect(), glow)

    draw_captions(painter)
    painter.end()

    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, CANVAS_W, CANVAS_H)
    item = QGraphicsPixmapItem(window_pixmap)
    item.setPos(*WINDOW_POS)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(72)
    shadow.setOffset(0, 28)
    shadow.setColor(QColor(0, 0, 0, 205))
    item.setGraphicsEffect(shadow)
    scene.addItem(item)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scene.render(
        painter,
        QRectF(0, 0, CANVAS_W, CANVAS_H),
        QRectF(0, 0, CANVAS_W, CANVAS_H),
    )
    painter.end()

    output.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(output)):
        print("Не удалось сохранить PNG", file=sys.stderr)
        return 1

    print(f"OK {output} {canvas.width()}x{canvas.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
