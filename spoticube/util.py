"""Форматирование значений и вспомогательные функции для UI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "прямой эфир" if seconds == 0 else "—"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _plural(number: int, one: str, few: str, many: str) -> str:
    mod100 = number % 100
    mod10 = number % 10
    if 11 <= mod100 <= 14:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


def format_views(count: int | None) -> str:
    if not count:
        return ""
    if count >= 1_000_000_000:
        value, word = count / 1_000_000_000, "млрд"
    elif count >= 1_000_000:
        value, word = count / 1_000_000, "млн"
    elif count >= 1_000:
        value, word = count / 1_000, "тыс."
    else:
        return f"{count} {_plural(count, 'просмотр', 'просмотра', 'просмотров')}"
    text = f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} {word} просмотров"


def format_bytes(size: float | int | None) -> str:
    if not size:
        return "0 Б"
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def format_speed(bytes_per_second: float | None) -> str:
    if not bytes_per_second:
        return ""
    return f"{format_bytes(bytes_per_second)}/с"


def format_eta(seconds: int | float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    if total >= 3600:
        return f"{total // 3600} ч {total % 3600 // 60} мин"
    if total >= 60:
        return f"{total // 60} мин {total % 60} с"
    return f"{total} с"


def wrap_lines(text: str, metrics: QFontMetrics, width: int, max_lines: int = 2) -> str:
    """Разбивает текст на строки по ширине и обрезает лишнее многоточием."""
    words = " ".join(text.split()).split()
    if not words:
        return ""
    lines: list[str] = []
    current = ""
    index = 0
    while index < len(words) and len(lines) < max_lines:
        candidate = f"{current} {words[index]}".strip()
        if current and metrics.horizontalAdvance(candidate) > width:
            lines.append(current)
            current = ""
            continue
        current = candidate
        index += 1
    if current:
        lines.append(current)
    if index < len(words) and lines:
        tail = " ".join(words[index:])
        last = f"{lines[-1]} {tail}"
        lines[-1] = metrics.elidedText(last, Qt.TextElideMode.ElideRight, width)
    return "\n".join(lines)
