from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import requests

from el_animal_fm.news.domain.models import DiscoveredUrl


PreloadByDate = dict[date, dict[str, DiscoveredUrl]]


@dataclass(frozen=True)
class NewsSourceAdapter:
    """Contrato que el motor de descarga necesita de cada fuente."""

    display_name: str
    source_name: str
    source_folder: str
    parser_version: str
    default_sleep_seconds: float
    default_max_category_pages: int
    days_back_example: int
    payload_normalizer: Callable[[Any], Any]
    normalize_url: Callable[[str], str]
    discover_article_urls: Callable[..., dict[str, DiscoveredUrl]]
    extract_article: Callable[[requests.Session, DiscoveredUrl, Path], dict[str, Any]]
    build_error_article: Callable[[DiscoveredUrl, Exception], dict[str, Any]]
    preload_range: Callable[[requests.Session, list[date], int], PreloadByDate] | None = None

