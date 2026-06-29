from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from el_animal_fm.news.application.news_normalizer import normalize_payload


DEFAULT_MEDIA_DIRS = ["biobio", "mostrador"]


def find_news_file(day_dir: Path) -> Path | None:
    candidates = [
        day_dir / "noticias_dia.txt",
        day_dir / "noticias_dia",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


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
        if not day_dir.is_dir():
            continue

        if not re.fullmatch(r"\d{2}_\d{2}_\d{4}", day_dir.name):
            continue

        news_file = find_news_file(day_dir)

        if not news_file:
            print(f"[WARN] No encontré noticias_dia en: {day_dir}")
            continue

        total += 1

        if process_file(news_file, overwrite=overwrite):
            ok += 1

    return total, ok
