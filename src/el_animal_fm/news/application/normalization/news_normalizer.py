from __future__ import annotations

import re
from typing import Any

from el_animal_fm.news.infrastructure.text import normalize_spaces, strip_html


TEXT_FIELDS_SIMPLE = [
    "title",
    "subtitle",
    "lead",
    "ai_summary",
    "summary",
    "author_name",
    "author_role",
    "source_attribution",
    "image_caption",
    "image_credit",
    "main_image_alt",
]

LIST_FIELDS = [
    "read_also_titles",
    "read_also_dates",
    "related_titles",
    "internal_subheadings",
    "also_interesting_titles",
    "featured_titles",
    "same_day_titles",
    "mentioned_documents_raw",
]

BOILERPLATE_PATTERNS = [
    r"^lee también\.?:?$",
    r"^lee tambien\.?:?$",
    r"^ver resumen$",
    r"^suscríbete en nuestro canal",
    r"^suscribete en nuestro canal",
    r"^síguenos",
    r"^siguenos",
    r"^publicidad$",
    r"^ética y transparencia",
    r"^etica y transparencia",
    r"^visto ahora$",
    r"^noticias relacionadas$",
    r"^también te puede interesar",
    r"^tambien te puede interesar",
]

TEXT_NORMALIZER_VERSION = "normalize_news_texts_v1"


def is_boilerplate(text: str) -> bool:
    if not text:
        return True

    clean = strip_html(text).lower().strip()

    if len(clean) <= 2:
        return True

    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, clean, flags=re.IGNORECASE):
            return True

    return False


def split_into_paragraphs(text: str) -> list[str]:
    """Intenta reconstruir párrafos limpios desde texto ya normalizado."""
    if not text:
        return []

    chunks = re.split(r"\n+", text)

    if len(chunks) <= 1:
        chunks = [text]

    paragraphs: list[str] = []

    for chunk in chunks:
        chunk = strip_html(chunk)

        if not chunk:
            continue

        if is_boilerplate(chunk):
            continue

        if chunk not in paragraphs:
            paragraphs.append(chunk)

    return paragraphs


def clean_paragraphs(value: Any) -> list[str]:
    """Limpia una lista de párrafos o un string con HTML."""
    paragraphs: list[str] = []

    if isinstance(value, list):
        iterable = value
    elif isinstance(value, str):
        iterable = [value]
    else:
        iterable = []

    for item in iterable:
        cleaned = strip_html(item)

        if not cleaned:
            continue

        if is_boilerplate(cleaned):
            continue

        if cleaned not in paragraphs:
            paragraphs.append(cleaned)

    return paragraphs


def clean_body_text_from_raw(raw: dict[str, Any]) -> tuple[str, str, list[str]]:
    """
    Repara body_text_raw, body_text_clean y paragraphs.

    Prioridad:
    1. paragraphs existentes, si son útiles.
    2. body_text_raw.
    3. body_text_clean.
    4. ai_summary / subtitle como respaldo mínimo.
    """
    paragraphs = clean_paragraphs(raw.get("paragraphs", []))

    if len(paragraphs) < 2:
        candidate = (
            raw.get("body_text_raw")
            or raw.get("body_text_clean")
            or raw.get("ai_summary")
            or raw.get("subtitle")
            or ""
        )

        candidate_clean = strip_html(candidate)
        extracted = split_into_paragraphs(candidate_clean)

        if len(extracted) > len(paragraphs):
            paragraphs = extracted

    body_text_raw = "\n".join(paragraphs)
    body_text_clean = normalize_spaces(" ".join(paragraphs))

    return body_text_raw, body_text_clean, paragraphs


def clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned_items: list[str] = []

    for item in value:
        cleaned = strip_html(item)

        if not cleaned:
            continue

        if is_boilerplate(cleaned):
            continue

        if cleaned not in cleaned_items:
            cleaned_items.append(cleaned)

    return cleaned_items


def normalize_article(article: dict[str, Any]) -> dict[str, Any]:
    raw = article.get("raw", {})

    if not isinstance(raw, dict):
        return article

    for field in TEXT_FIELDS_SIMPLE:
        if field in raw:
            raw[field] = strip_html(raw.get(field, ""))

    for field in LIST_FIELDS:
        if field in raw:
            raw[field] = clean_string_list(raw.get(field, []))

    body_text_raw, body_text_clean, paragraphs = clean_body_text_from_raw(raw)

    raw["body_text_raw"] = body_text_raw
    raw["body_text_clean"] = body_text_clean
    raw["paragraphs"] = paragraphs
    raw["paragraph_count"] = len(paragraphs)
    raw["body_length_chars"] = len(body_text_clean)
    raw["body_length_words"] = len(body_text_clean.split())
    raw["quote_count"] = body_text_clean.count("“") + body_text_clean.count("”")

    article["raw"] = raw
    return article


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    articles = payload.get("articles", [])

    if not isinstance(articles, list):
        return payload

    payload["articles"] = [
        normalize_article(article)
        for article in articles
        if isinstance(article, dict)
    ]

    metadata = payload.setdefault("metadata", {})
    metadata["text_normalized"] = True
    metadata["text_normalizer_version"] = TEXT_NORMALIZER_VERSION

    return payload
