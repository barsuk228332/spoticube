#!/usr/bin/env python3
"""Генерирует PNG всех размеров и .ico из assets/spoticube.svg.

Запуск:
    python3 tools/make_icon.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(renderer: QSvgRenderer, size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def main() -> int:
    QGuiApplication(sys.argv[:1])

    svg = ROOT / "assets" / "spoticube.svg"
    icons_dir = ROOT / "assets" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        print(f"Не удалось прочитать SVG: {svg}", file=sys.stderr)
        return 1

    written: list[Path] = []
    for size in PNG_SIZES:
        path = icons_dir / f"spoticube-{size}.png"
        if not render(renderer, size).save(str(path), "PNG"):
            print(f"Не удалось сохранить {path}", file=sys.stderr)
            return 1
        written.append(path)

    main_png = ROOT / "assets" / "spoticube.png"
    render(renderer, 512).save(str(main_png), "PNG")
    written.append(main_png)

    ico_path = ROOT / "assets" / "spoticube.ico"
    try:
        from PIL import Image
    except ImportError:
        print("Pillow не установлен — .ico пропущен")
    else:
        source = Image.open(icons_dir / "spoticube-256.png").convert("RGBA")
        source.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
        written.append(ico_path)

    for path in written:
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size} байт")
    print(f"OK: {len(written)} файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
