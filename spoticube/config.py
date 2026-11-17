"""Пути, кэш и настройки приложения."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

APP_NAME = "Spoticube"
ORG_NAME = "spoticube"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = Path(base) / "spoticube"
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumb_cache_dir() -> Path:
    path = cache_root() / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumb_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return thumb_cache_dir() / f"{digest}.img"


def save_bytes_atomic(path: Path, data: bytes) -> None:
    """Пишет файл через временный и подменяет его целиком.

    Так в кэше не остаётся «половинчатый» файл, если процесс прервётся
    посреди записи: до ``os.replace`` старое содержимое остаётся нетронутым.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def default_download_dir() -> Path:
    downloads = Path.home() / "Загрузки"
    if not downloads.is_dir():
        downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        downloads = Path.home()
    return downloads / "Spoticube"


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def icon_file() -> Path:
    """Основной PNG-значок приложения (или SVG, если PNG ещё не сгенерирован)."""
    png = ASSETS_DIR / "spoticube.png"
    if png.is_file():
        return png
    return ASSETS_DIR / "spoticube.svg"


def icon_files() -> list[Path]:
    """Все готовые размеры значка — чтобы панель задач брала резкий вариант."""
    icons_dir = ASSETS_DIR / "icons"
    if icons_dir.is_dir():
        sizes = sorted(
            icons_dir.glob("spoticube-*.png"),
            key=lambda p: int(p.stem.rsplit("-", 1)[-1] or 0),
        )
        if sizes:
            return sizes
    single = icon_file()
    return [single] if single.is_file() else []
