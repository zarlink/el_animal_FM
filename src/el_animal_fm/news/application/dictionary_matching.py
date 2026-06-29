from __future__ import annotations

import html
import math
import re
import unicodedata
from typing import Any

from el_animal_fm.news.application.enrichment_config import PHRASE_NORMALIZATIONS


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def normalize_for_match(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKC", text).lower()
    for phrase, replacement in PHRASE_NORMALIZATIONS.items():
        text = text.replace(phrase, replacement)
    text = re.sub(r"\btrump\b", "donald_trump", text)
    text = re.sub(r"\bkast\b", "jose_antonio_kast", text)
    text = re.sub(r"\bdonald\s+donald_trump\b", "donald_trump", text)
    text = re.sub(r"\bjos[eé]\s+antonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    text = re.sub(r"\bantonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    text = strip_accents(text)
    text = re.sub(r"[^a-z0-9_%$/\-\.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def term_to_pattern(term: str) -> re.Pattern:
    normalized = re.escape(normalize_for_match(term))
    normalized = normalized.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9_]){normalized}(?![a-z0-9_])", flags=re.I)


def safe_float(value: Any, default: float = 1.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default
