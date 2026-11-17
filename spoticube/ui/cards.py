"""Виджеты: карточка результата, панель предпросмотра, строка загрузки."""

from __future__ import annotations

import os
import weakref
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import VideoItem
from ..util import format_bytes, format_duration, format_eta, format_speed, format_views, wrap_lines


def cover_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
    """Масштабирует изображение с обрезкой по центру (как object-fit: cover)."""
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    return scaled.copy(x, y, width, height)


class SkeletonThumb(QLabel):
    """Плейсхолдер превью: мягкая световая волна, пока грузится картинка."""

    _timer: QTimer | None = None
    _phase = 0.0
    _live: "weakref.WeakSet" = weakref.WeakSet()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Thumb")
        self._skeleton = True
        SkeletonThumb._live.add(self)
        SkeletonThumb._ensure_timer()

    @classmethod
    def _ensure_timer(cls) -> None:
        if cls._timer is None:
            cls._timer = QTimer()
            cls._timer.setInterval(33)
            cls._timer.timeout.connect(cls._tick)
        if not cls._timer.isActive():
            cls._timer.start()

    @classmethod
    def _tick(cls) -> None:
        cls._phase = (cls._phase + 0.05) % 1.0
        alive = False
        for widget in list(cls._live):
            if widget._skeleton and widget.isVisible():
                widget.update()
                alive = True
        if not alive and cls._timer is not None:
            cls._timer.stop()

    def start_skeleton(self) -> None:
        if self._skeleton:
            return
        self._skeleton = True
        SkeletonThumb._ensure_timer()
        self.update()

    def stop_skeleton(self) -> None:
        if not self._skeleton:
            return
        self._skeleton = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        if not self._skeleton:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8.0, 8.0)
        painter.setClipPath(path)

        band = max(70.0, self.width() * 0.6)
        offset = -band + (self.width() + band * 2.0) * SkeletonThumb._phase
        gradient = QLinearGradient(offset, 0.0, offset + band, 0.0)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 22))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), gradient)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 18))
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = min(self.width(), self.height()) * 0.11
        painter.drawEllipse(center, radius, radius)
        painter.end()


class ResultCard(QFrame):
    clicked = Signal(str)
    activated = Signal(str)

    CARD_W = 300
    CARD_H = 236
    THUMB_W = 286
    THUMB_H = 161

    def __init__(self, item: VideoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self._selected = False
        self._shadow: QGraphicsDropShadowEffect | None = None
        self._blur_anim: QPropertyAnimation | None = None
        self._offset_anim: QPropertyAnimation | None = None
        self.setObjectName("ResultCard")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(item.title)

        root = QVBoxLayout(self)
        root.setContentsMargins(7, 7, 7, 7)
        root.setSpacing(5)

        self.thumb_label = SkeletonThumb()
        self.thumb_label.setFixedSize(self.THUMB_W, self.THUMB_H)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.thumb_label)

        badge_text = format_duration(item.duration) if item.duration else ""
        if badge_text:
            self.badge = QLabel(badge_text, self.thumb_label)
            self.badge.setStyleSheet(
                "background: rgba(6, 10, 14, 200); color: #e6edf3;"
                "border-radius: 5px; padding: 1px 6px; font-size: 11px; font-weight: 600;"
            )
            self.badge.adjustSize()
            self.badge.move(
                self.THUMB_W - self.badge.width() - 6,
                self.THUMB_H - self.badge.height() - 6,
            )

        self.title_label = QLabel()
        self.title_label.setObjectName("CardTitle")
        self.title_label.setFixedHeight(34)
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        root.addWidget(self.title_label)

        meta_parts = [part for part in (item.channel, format_views(item.view_count)) if part]
        self.meta_label = QLabel(" · ".join(meta_parts))
        self.meta_label.setObjectName("CardMeta")
        root.addWidget(self.meta_label)

        self._apply_texts()

    def _apply_texts(self) -> None:
        metrics = QFontMetrics(self.title_label.font())
        self.title_label.setText(
            wrap_lines(self.item.title, metrics, self.THUMB_W - 6, 2)
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply_texts()

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.thumb_label.stop_skeleton()
        self.thumb_label.setPixmap(
            cover_pixmap(pixmap, self.THUMB_W, self.THUMB_H)
        )

    def set_selected(self, value: bool) -> None:
        if self._selected == value:
            return
        self._selected = value
        self.setProperty("selected", value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item.key)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.item.key)
        super().mouseDoubleClickEvent(event)

    # --- анимация наведения ---------------------------------------------------

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().enterEvent(event)
        self._animate_shadow(True)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().leaveEvent(event)
        self._animate_shadow(False)

    def _ensure_shadow(self) -> QGraphicsDropShadowEffect:
        if self._shadow is None:
            effect = QGraphicsDropShadowEffect(self)
            effect.setOffset(0.0, 0.0)
            effect.setBlurRadius(0.0)
            effect.setColor(QColor(0, 0, 0, 155))
            self.setGraphicsEffect(effect)
            self._shadow = effect
        return self._shadow

    def _animate_shadow(self, hovered: bool) -> None:
        effect = self._ensure_shadow()
        if self._blur_anim is None:
            self._blur_anim = QPropertyAnimation(effect, b"blurRadius", self)
            self._blur_anim.setDuration(150)
            self._blur_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._offset_anim = QPropertyAnimation(effect, b"offset", self)
            self._offset_anim.setDuration(150)
            self._offset_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._blur_anim.stop()
        self._blur_anim.setStartValue(effect.blurRadius())
        self._blur_anim.setEndValue(22.0 if hovered else 0.0)
        self._blur_anim.start()

        self._offset_anim.stop()
        self._offset_anim.setStartValue(effect.offset())
        self._offset_anim.setEndValue(
            QPointF(0.0, 7.0) if hovered else QPointF(0.0, 0.0)
        )
        self._offset_anim.start()

        self.setProperty("hovered", hovered)


class PreviewPane(QFrame):
    download_video = Signal()
    download_audio = Signal()
    open_external = Signal(str)

    PREVIEW_W = 360
    THUMB_W = 336
    THUMB_H = 189

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFixedWidth(self.PREVIEW_W + 36)
        self.item: VideoItem | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(17, 17, 17, 17)
        root.setSpacing(12)

        heading = QLabel("ПРЕДПРОСМОТР")
        heading.setObjectName("SectionTitle")
        root.addWidget(heading)

        self.thumb = SkeletonThumb()
        self.thumb.setFixedSize(self.THUMB_W, self.THUMB_H)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setWordWrap(True)
        self.thumb.setText("Здесь появится\nпревью видео")
        self.thumb.stop_skeleton()
        root.addWidget(self.thumb)

        self.title_label = QLabel("Ничего не выбрано")
        self.title_label.setObjectName("PreviewTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumHeight(40)
        root.addWidget(self.title_label)

        self.meta_label = QLabel("Найдите видео или вставьте ссылку")
        self.meta_label.setObjectName("PreviewMeta")
        self.meta_label.setWordWrap(True)
        root.addWidget(self.meta_label)

        root.addSpacing(4)

        self.video_btn = QPushButton("Скачать видео")
        self.video_btn.setObjectName("Primary")
        self.video_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.video_btn.clicked.connect(self.download_video.emit)
        root.addWidget(self.video_btn)

        self.audio_btn = QPushButton("Скачать аудио (MP3)")
        self.audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_btn.clicked.connect(self.download_audio.emit)
        root.addWidget(self.audio_btn)

        self.open_btn = QPushButton("Открыть на YouTube")
        self.open_btn.setObjectName("Ghost")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_clicked)
        root.addWidget(self.open_btn)

        root.addStretch(1)

        self._set_actions_enabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for widget in (self.video_btn, self.audio_btn, self.open_btn):
            widget.setEnabled(enabled)

    def _open_clicked(self) -> None:
        if self.item:
            self.open_external.emit(self.item.url)

    def show_item(self, item: VideoItem) -> None:
        self.item = item
        self.title_label.setText(item.title)
        meta = [part for part in (item.channel, format_views(item.view_count)) if part]
        if item.duration:
            meta.append(format_duration(item.duration))
        self.meta_label.setText(" · ".join(meta) or "—")
        self.thumb.clear()
        if item.thumbnail:
            self.thumb.setText("")
            self.thumb.start_skeleton()
        else:
            self.thumb.stop_skeleton()
            self.thumb.setText("Нет превью")
        self._set_actions_enabled(True)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.thumb.stop_skeleton()
        self.thumb.setText("")
        self.thumb.setPixmap(cover_pixmap(pixmap, self.THUMB_W, self.THUMB_H))

    def clear(self) -> None:
        self.item = None
        self.title_label.setText("Ничего не выбрано")
        self.meta_label.setText("Найдите видео или вставьте ссылку")
        self.thumb.clear()
        self.thumb.stop_skeleton()
        self.thumb.setText("Здесь появится\nпревью видео")
        self._set_actions_enabled(False)


class DownloadRow(QWidget):
    cancel_requested = Signal()
    open_requested = Signal(str)

    def __init__(self, item: VideoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.path: str | None = None
        self._finished = False

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setObjectName("CardTitle")
        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info.addWidget(self.title_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        info.addWidget(self.progress)

        self.status_label = QLabel("В очереди…")
        self.status_label.setObjectName("CardMeta")
        info.addWidget(self.status_label)

        root.addLayout(info, 1)

        self.open_btn = QPushButton("Открыть")
        self.open_btn.setObjectName("Ghost")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_clicked)
        self.open_btn.hide()
        root.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_clicked)
        root.addWidget(self.cancel_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_title(item.title)
        self.setMinimumHeight(74)

    def set_title(self, text: str) -> None:
        metrics = QFontMetrics(self.title_label.font())
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, 520)
        self.title_label.setText(elided)
        self.title_label.setToolTip(text)

    def _cancel_clicked(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Отмена…")
        self.cancel_requested.emit()

    def _open_clicked(self) -> None:
        if self.path:
            target = Path(self.path)
            directory = target if target.is_dir() else target.parent
            self.open_requested.emit(str(directory))

    def set_progress(self, data: dict) -> None:
        percent = data.get("percent", -1)
        if percent is None or percent < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(percent * 10))

        parts: list[str] = []
        total = data.get("total") or 0
        done = data.get("downloaded") or 0
        if total:
            parts.append(f"{format_bytes(done)} / {format_bytes(total)}")
        elif done:
            parts.append(format_bytes(done))
        speed = format_speed(data.get("speed"))
        if speed:
            parts.append(speed)
        eta = format_eta(data.get("eta"))
        if eta:
            parts.append(f"осталось {eta}")
        if parts:
            self.status_label.setText(" · ".join(parts))

    def set_status(self, text: str) -> None:
        if not self._finished:
            self.status_label.setText(text)

    def set_done(self, path: str | None) -> None:
        self._finished = True
        self.path = path
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000)
        self.cancel_btn.hide()
        self.open_btn.show()
        name = os.path.basename(path) if path else ""
        self.status_label.setText(f"Готово · {name}" if name else "Готово")
        self.status_label.setStyleSheet("color: #3ddc84;")

    def set_error(self, message: str) -> None:
        self._finished = True
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.cancel_btn.hide()
        short = message.strip().splitlines()[0] if message.strip() else "неизвестная ошибка"
        self.status_label.setText(f"Ошибка: {short}"[:220])
        self.status_label.setStyleSheet("color: #f08a94;")
        self.status_label.setToolTip(message)

    def set_cancelled(self) -> None:
        self._finished = True
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.cancel_btn.hide()
        self.status_label.setText("Отменено")
        self.status_label.setStyleSheet(f"color: #8b98a9;")


def card_grid_size() -> QSize:
    return QSize(ResultCard.CARD_W + 14, ResultCard.CARD_H + 14)
