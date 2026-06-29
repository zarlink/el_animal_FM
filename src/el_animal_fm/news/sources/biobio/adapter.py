from __future__ import annotations

from typing import Any

from el_animal_fm.news.application.download.source_adapter import NewsSourceAdapter
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.sources.biobio.config import (
    DAYS_BACK_EXAMPLE,
    DEFAULT_MAX_CATEGORY_PAGES,
    DEFAULT_SLEEP_SECONDS,
    DISPLAY_NAME,
    PARSER_VERSION,
    SOURCE_FOLDER,
    SOURCE_NAME,
)
from el_animal_fm.news.sources.biobio import article_parser
from el_animal_fm.news.sources.biobio import discovery


def build_error_article(discovered: DiscoveredUrl, exc: Exception) -> dict[str, Any]:
    return {
        "raw": {
            "source": SOURCE_NAME,
            "source_type": "news_site",
            "url": discovered.url,
        },
        "technical": {
            "http_status": None,
            "content_type": "",
            "downloaded_from_sitemap": discovered.discovered_from_sitemap,
            "downloaded_from_feed": discovered.discovered_from_feed,
            "html_raw_path": "",
            "parser_version": PARSER_VERSION,
            "parse_success": False,
            "parse_errors": [f"parallel_worker_error: {exc}"],
            "template_noise_detected": False,
            "robots_allowed_checked": "not_checked",
            "discovery_sources": discovered.discovery_sources or [],
        },
    }


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
    )


__all__ = ["create_adapter"]
