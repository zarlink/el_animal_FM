from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from el_animal_fm.news.infrastructure.dates import date_from_dir_name


DEFAULT_MEDIA_DIRS = ["biobio", "mostrador"]
DEFAULT_NEWS_FILE_NAMES = ("noticias_dia.txt", "noticias_dia")
DATE_DIR_PATTERN = re.compile(r"\d{2}_\d{2}_\d{4}")


def is_date_dir(path: Path) -> bool:
    return path.is_dir() and bool(DATE_DIR_PATTERN.fullmatch(path.name))


def find_news_file(
    day_dir: Path,
    *,
    file_names: tuple[str, ...] = DEFAULT_NEWS_FILE_NAMES,
) -> Path | None:
    for file_name in file_names:
        candidate = day_dir / file_name

        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def iter_media_day_dirs(base_dir: Path, media_dirs: list[str]) -> list[tuple[str, Path]]:
    day_dirs: list[tuple[str, Path]] = []

    for media in media_dirs:
        media_dir = base_dir / media

        if not media_dir.exists():
            print(f"[WARN] No existe carpeta: {media_dir}")
            continue

        for day_dir in sorted(media_dir.iterdir()):
            if is_date_dir(day_dir):
                day_dirs.append((media, day_dir))

    return day_dirs


def find_news_files(
    base_dir: Path,
    media_dirs: list[str],
    *,
    file_names: tuple[str, ...] = DEFAULT_NEWS_FILE_NAMES,
    allowed_dates: set[date] | None = None,
) -> list[Path]:
    files: list[Path] = []

    for _, day_dir in iter_media_day_dirs(base_dir, media_dirs):
        if allowed_dates is not None and date_from_dir_name(day_dir.name) not in allowed_dates:
            continue

        news_file = find_news_file(day_dir, file_names=file_names)

        if news_file:
            files.append(news_file)
        else:
            print(f"[WARN] No encontré noticias_dia en: {day_dir}")

    return files
