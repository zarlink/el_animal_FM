from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from el_animal_fm.news.infrastructure.dates import date_dir_name


TIMEZONE = "America/Santiago"


def get_day_dir(base_dir: Path, source_folder: str, target: date) -> Path:
    return base_dir / source_folder / date_dir_name(target)


def get_day_output_path(base_dir: Path, source_folder: str, target: date) -> Path:
    return get_day_dir(base_dir, source_folder, target) / "noticias_dia.txt"


def should_skip_existing_day(
    base_dir: Path,
    source_folder: str,
    target: date,
    overwrite_existing: bool = False,
) -> bool:
    if overwrite_existing:
        return False

    return get_day_dir(base_dir, source_folder, target).exists()


def build_skipped_day_summary(base_dir: Path, source_folder: str, target: date) -> dict[str, Any]:
    day_dir = get_day_dir(base_dir, source_folder, target)
    output_path = get_day_output_path(base_dir, source_folder, target)
    raw_html_dir = day_dir / "html"

    return {
        "target_date": target.isoformat(),
        "status": "skipped_existing_day",
        "reason": "La carpeta diaria ya existe y overwrite_existing=False.",
        "day_dir": str(day_dir),
        "output_path": str(output_path),
        "output_exists": output_path.exists(),
        "html_dir_exists": raw_html_dir.exists(),
    }


def get_article_url_from_payload(
    article: dict[str, Any],
    *,
    normalize_url: Callable[[str], str],
) -> str:
    if not isinstance(article, dict):
        return ""

    raw = article.get("raw")
    if isinstance(raw, dict):
        return normalize_url(str(raw.get("canonical_url") or raw.get("url") or ""))

    return normalize_url(str(article.get("canonical_url") or article.get("url") or ""))


def load_existing_day_payload(
    output_path: Path,
    *,
    normalize_url: Callable[[str], str],
) -> tuple[dict[str, Any], list[dict[str, Any]], set[str]]:
    if not output_path.exists():
        return {}, [], set()

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] No se pudo leer archivo existente {output_path}: {exc}")
        return {}, [], set()

    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        print(f"[WARN] Archivo existente sin lista válida de articles: {output_path}")
        return payload, [], set()

    existing_urls: set[str] = set()
    for article in articles:
        url = get_article_url_from_payload(article, normalize_url=normalize_url)
        if url:
            existing_urls.add(url)

    return payload, articles, existing_urls


def deduplicate_articles_by_url(
    articles: list[dict[str, Any]],
    *,
    normalize_url: Callable[[str], str],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for article in articles:
        url = get_article_url_from_payload(article, normalize_url=normalize_url)

        if not url:
            deduped.append(article)
            continue

        if url in seen:
            continue

        seen.add(url)
        deduped.append(article)

    return deduped


def write_output(
    output_path: Path,
    target: date,
    discovered_count: int,
    articles: list[dict[str, Any]],
    *,
    source: str,
    parser_version: str,
    payload_normalizer: Callable[[Any], Any],
) -> None:
    payload = {
        "metadata": {
            "source": source,
            "target_date": target.isoformat(),
            "target_date_folder": date_dir_name(target),
            "articles_found": discovered_count,
            "articles_downloaded": len(articles),
            "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
            "parser_version": parser_version,
        },
        "articles": articles,
    }

    payload = payload_normalizer(payload)

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
