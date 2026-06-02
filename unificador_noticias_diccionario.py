from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


DEFAULT_MEDIA_DIRS = ["biobio", "mostrador"]


def clean_text(value: Any) -> str:
    """
    Limpia texto básico para que el archivo unificado sirva después
    para extracción de palabras clave y construcción de diccionarios.
    """
    if value is None:
        return ""

    text = str(value)
    text = html.unescape(text)

    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "lxml")
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_news_files(base_dir: Path, media_dirs: list[str]) -> list[Path]:
    files: list[Path] = []

    for media in media_dirs:
        media_dir = base_dir / media

        if not media_dir.exists():
            print(f"[WARN] No existe carpeta: {media_dir}")
            continue

        for day_dir in sorted(media_dir.iterdir()):
            if not day_dir.is_dir():
                continue

            if not re.fullmatch(r"\d{2}_\d{2}_\d{4}", day_dir.name):
                continue

            news_file = day_dir / "noticias_dia.txt"

            if news_file.exists():
                files.append(news_file)
            else:
                print(f"[WARN] No encontré noticias_dia.txt en: {day_dir}")

    return files


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] No pude leer {path}: {exc}")
        return None


def build_classification_text(raw: dict[str, Any]) -> str:
    """
    Texto combinado que después servirá para extraer palabras frecuentes,
    entidades, términos financieros y reglas heurísticas.
    """
    parts = [
        raw.get("title", ""),
        raw.get("subtitle", ""),
        raw.get("lead", ""),
        raw.get("summary", ""),
        raw.get("ai_summary", ""),
        raw.get("body_text_clean", ""),
    ]

    return clean_text(" ".join(clean_text(part) for part in parts if part))


def reduce_article(article: dict[str, Any], source_file: Path) -> dict[str, Any]:
    raw = article.get("raw", {})
    technical = article.get("technical", {})

    if not isinstance(raw, dict):
        raw = {}

    if not isinstance(technical, dict):
        technical = {}

    classification_text = build_classification_text(raw)

    return {
        "source": clean_text(raw.get("source", "")),
        "source_file": str(source_file),
        "published_date": clean_text(raw.get("published_date", "")),
        "published_time": clean_text(raw.get("published_time", "")),
        "published_at": clean_text(raw.get("published_at", "")),
        "url": clean_text(raw.get("url", "")),
        "canonical_url": clean_text(raw.get("canonical_url", "")),
        "slug": clean_text(raw.get("slug", "")),

        "main_section": clean_text(raw.get("main_section", "")),
        "subsection": clean_text(raw.get("subsection", "")),
        "article_type_editorial": clean_text(raw.get("article_type_editorial", "")),
        "region_section": clean_text(raw.get("region_section", "")),

        "is_opinion": raw.get("is_opinion"),
        "is_investigation": raw.get("is_investigation"),
        "is_economy_section": raw.get("is_economy_section"),
        "is_national_section": raw.get("is_national_section"),
        "is_international_section": raw.get("is_international_section"),

        # Campos adicionales que existen especialmente en El Mostrador.
        "is_market_section": raw.get("is_market_section"),
        "is_country_section": raw.get("is_country_section"),
        "is_world_section": raw.get("is_world_section"),
        "is_multimedia": raw.get("is_multimedia"),
        "is_culture": raw.get("is_culture"),
        "is_deportes": raw.get("is_deportes"),

        "title": clean_text(raw.get("title", "")),
        "subtitle": clean_text(raw.get("subtitle", "")),
        "lead": clean_text(raw.get("lead", "")),
        "summary": clean_text(raw.get("summary", "")),
        "ai_summary": clean_text(raw.get("ai_summary", "")),
        "has_ai_summary": raw.get("has_ai_summary"),

        "author_name": clean_text(raw.get("author_name", "")),
        "author_role": clean_text(raw.get("author_role", "")),
        "source_attribution": clean_text(raw.get("source_attribution", "")),

        "body_text_clean": clean_text(raw.get("body_text_clean", "")),
        "body_length_words": raw.get("body_length_words"),
        "paragraph_count": raw.get("paragraph_count"),

        "internal_subheadings": [
            clean_text(x)
            for x in raw.get("internal_subheadings", [])
            if clean_text(x)
        ],

        "related_titles": [
            clean_text(x)
            for x in raw.get("related_titles", [])
            if clean_text(x)
        ],

        "classification_text": classification_text,
        "classification_text_length": len(classification_text),
        "parser_version": clean_text(technical.get("parser_version", "")),
        "parse_success": technical.get("parse_success"),
        "parse_errors": technical.get("parse_errors", []),
    }


def unify_news(base_dir: Path, media_dirs: list[str]) -> dict[str, Any]:
    news_files = find_news_files(base_dir, media_dirs)

    unified_articles: list[dict[str, Any]] = []
    files_summary: list[dict[str, Any]] = []

    for path in news_files:
        payload = load_json_file(path)

        if not payload:
            continue

        metadata = payload.get("metadata", {})
        articles = payload.get("articles", [])

        if not isinstance(articles, list):
            print(f"[WARN] Archivo sin lista articles válida: {path}")
            continue

        source = metadata.get("source", "")
        target_date = metadata.get("target_date", "")
        found = metadata.get("articles_found", None)
        downloaded = metadata.get("articles_downloaded", None)

        print(f"[OK] {path} | artículos: {len(articles)}")

        files_summary.append(
            {
                "file": str(path),
                "source": source,
                "target_date": target_date,
                "articles_found": found,
                "articles_downloaded": downloaded,
                "articles_unified": len(articles),
            }
        )

        for article in articles:
            if isinstance(article, dict):
                unified_articles.append(reduce_article(article, path))

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "base_dir": str(base_dir),
            "media_dirs": media_dirs,
            "files_processed": len(files_summary),
            "articles_unified": len(unified_articles),
            "description": (
                "Archivo unificado para análisis preliminar de noticias, "
                "extracción de palabras clave y construcción de diccionarios heurísticos."
            ),
        },
        "files_summary": files_summary,
        "articles": unified_articles,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unifica todos los archivos noticias_dia.txt de biobio y mostrador."
    )

    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directorio base del proyecto. Por defecto, carpeta actual.",
    )

    parser.add_argument(
        "--media",
        nargs="*",
        default=DEFAULT_MEDIA_DIRS,
        help="Carpetas de medios a procesar. Default: biobio mostrador.",
    )

    parser.add_argument(
        "--output",
        default="noticias_unificadas.txt",
        help="Nombre del archivo de salida. Default: noticias_unificadas.txt.",
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_path = base_dir / args.output

    print("=== Unificador de noticias ===")
    print(f"Directorio base: {base_dir}")
    print(f"Medios: {', '.join(args.media)}")
    print(f"Salida: {output_path}")
    print()

    unified = unify_news(base_dir, args.media)

    output_path.write_text(
        json.dumps(unified, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== Proceso terminado ===")
    print(f"Archivos procesados: {unified['metadata']['files_processed']}")
    print(f"Noticias unificadas: {unified['metadata']['articles_unified']}")
    print(f"Archivo generado: {output_path}")


if __name__ == "__main__":
    main()