from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from el_animal_fm.news.application.shared.news_file_collection import (
    DEFAULT_MEDIA_DIRS,
    find_news_file,
    is_date_dir,
)
from el_animal_fm.news.application.normalization.news_normalizer import normalize_payload


def read_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".bak")

    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def build_output_path(path: Path, *, overwrite: bool) -> Path:
    if overwrite:
        return path

    return path.with_name(path.stem + "_normalizado" + path.suffix)


def process_file(path: Path, overwrite: bool = True) -> bool:
    try:
        payload = read_payload(path)
    except Exception as exc:
        print(f"[ERROR] No pude leer JSON: {path} | {exc}")
        return False

    ensure_backup(path)

    normalized = normalize_payload(payload)
    output_path = build_output_path(path, overwrite=overwrite)
    write_payload(output_path, normalized)

    print(f"[OK] Reparado: {output_path}")
    return True


def process_media_dir(media_dir: Path, overwrite: bool = True) -> tuple[int, int]:
    if not media_dir.exists():
        print(f"[WARN] No existe carpeta: {media_dir}")
        return 0, 0

    total = 0
    ok = 0

    for day_dir in sorted(media_dir.iterdir()):
        if not is_date_dir(day_dir):
            continue

        news_file = find_news_file(day_dir)

        if not news_file:
            print(f"[WARN] No encontré noticias_dia en: {day_dir}")
            continue

        total += 1

        if process_file(news_file, overwrite=overwrite):
            ok += 1

    return total, ok
