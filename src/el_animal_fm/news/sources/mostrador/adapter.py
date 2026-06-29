from __future__ import annotations

from datetime import date

import requests

from el_animal_fm.news.application.source_adapter import NewsSourceAdapter, PreloadByDate
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.sources.mostrador.config import (
    DAYS_BACK_EXAMPLE,
    DEFAULT_MAX_CATEGORY_PAGES,
    DEFAULT_SLEEP_SECONDS,
    DISPLAY_NAME,
    PARSER_VERSION,
    SOURCE_FOLDER,
    SOURCE_NAME,
)
from el_animal_fm.news.sources.mostrador import article_parser
from el_animal_fm.news.sources.mostrador import discovery


def build_error_article(discovered: DiscoveredUrl, exc: Exception) -> dict:
    return article_parser.build_empty_error_article(
        discovered=discovered,
        http_status=None,
        content_type="",
        error=f"parallel_worker_error: {exc}",
    )


def preload_range(
    session: requests.Session,
    targets: list[date],
    max_category_pages: int,
) -> PreloadByDate:
    return discovery.discover_from_categoria_dia_range(
        session=session,
        targets=targets,
        max_pages=max_category_pages,
    )


def create_adapter() -> NewsSourceAdapter:
    return NewsSourceAdapter(
        display_name=DISPLAY_NAME,
        source_name=SOURCE_NAME,
        source_folder=SOURCE_FOLDER,
        parser_version=PARSER_VERSION,
        default_sleep_seconds=DEFAULT_SLEEP_SECONDS,
        default_max_category_pages=DEFAULT_MAX_CATEGORY_PAGES,
        days_back_example=DAYS_BACK_EXAMPLE,
        payload_normalizer=article_parser.normalize_payload_texts,
        normalize_url=discovery.normalize_url,
        discover_article_urls=discovery.discover_article_urls,
        extract_article=article_parser.extract_article,
        build_error_article=build_error_article,
        preload_range=preload_range,
    )


__all__ = ["create_adapter"]
