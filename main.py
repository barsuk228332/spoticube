#!/usr/bin/env python3
"""Spoticube — графический загрузчик видео и аудио с YouTube."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "Не установлен PySide6. Установите зависимости:\n"
            "  python3 -m pip install --user -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    from spoticube import config
    from spoticube.ui.main_window import MainWindow
    from spoticube.ui.theme import apply_theme

    app = QApplication(sys.argv)
    app.setApplicationName("Spoticube")
    app.setApplicationDisplayName("Spoticube")
    app.setOrganizationName("spoticube")
    # связывает окно с .desktop-файлом: от этого зависит значок в панели задач (Wayland/GNOME)
    app.setDesktopFileName("spoticube")

    app_icon = QIcon()
    for icon_path in config.icon_files():
        app_icon.addFile(str(icon_path))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
