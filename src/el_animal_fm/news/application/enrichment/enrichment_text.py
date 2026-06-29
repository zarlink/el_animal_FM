from __future__ import annotations

from typing import Any

from el_animal_fm.news.application.shared.dictionary_matching import normalize_for_match


def get_article_raw(article: dict[str, Any]) -> dict[str, Any]:
    raw = article.get("raw")
    return raw if isinstance(raw, dict) else article


def build_classification_text(article: dict[str, Any]) -> str:
    raw = get_article_raw(article)
    parts = [
        raw.get("title", ""),
        raw.get("subtitle", ""),
        raw.get("lead", ""),
        raw.get("summary", ""),
        raw.get("ai_summary", ""),
        raw.get("body_text_clean", ""),
        raw.get("main_section", ""),
        raw.get("subsection", ""),
        raw.get("breadcrumb_raw", ""),
    ]
    paragraphs = raw.get("paragraphs")
    if isinstance(paragraphs, list) and not raw.get("body_text_clean"):
        parts.extend([str(p) for p in paragraphs])
    return normalize_for_match(" ".join(str(x) for x in parts if x))
