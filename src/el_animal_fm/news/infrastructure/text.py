from __future__ import annotations

import html as html_lib
import re
from collections.abc import Callable
from typing import Any

from bs4 import BeautifulSoup


def repair_mojibake(value: str) -> str:
    """Corrige textos ya dañados tipo 'dÃ©ficit' -> 'déficit' cuando sea posible."""
    if not isinstance(value, str) or not value:
        return value or ""

    markers = ("Ã", "Â", "â€", "â€œ", "â€", "â€™", "ðŸ")

    if not any(marker in value for marker in markers):
        return value

    candidates = [value]

    for source_encoding in ("latin1", "cp1252"):
        try:
            candidates.append(
                value.encode(source_encoding, errors="ignore").decode("utf-8", errors="ignore")
            )
        except Exception:
            pass

    def badness(text: str) -> int:
        return sum(text.count(marker) for marker in markers) + text.count("�") * 3

    return min(candidates, key=badness)


def normalize_text(
    value: Any,
    *,
    boilerplate_remover: Callable[[str], str] | None = None,
) -> str:
    if value is None:
        return ""

    text = str(value)
    text = html_lib.unescape(text)
    text = repair_mojibake(text)

    if boilerplate_remover:
        text = boilerplate_remover(text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_payload_texts(
    value: Any,
    *,
    text_normalizer: Callable[[Any], str],
) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_payload_texts(child, text_normalizer=text_normalizer)
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_payload_texts(child, text_normalizer=text_normalizer)
            for child in value
        ]

    if isinstance(value, str):
        return text_normalizer(value)

    return value


def clean_text(value: str, *, text_normalizer: Callable[[Any], str]) -> str:
    return text_normalizer(value)


def remove_template_noise(value: str, *, text_normalizer: Callable[[Any], str]) -> str:
    value = re.sub(r"\{\{.*?\}\}", "", value or "")
    return text_normalizer(value)


def text_or_empty(tag, *, text_normalizer: Callable[[Any], str]) -> str:
    if not tag:
        return ""
    return text_normalizer(tag.get_text(" ", strip=True))


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def detect_template_noise(html: str) -> bool:
    return "{{" in html or "}}" in html
