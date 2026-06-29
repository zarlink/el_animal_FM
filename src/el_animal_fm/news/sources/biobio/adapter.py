from __future__ import annotations

from typing import Any

from el_animal_fm.news.application.source_adapter import NewsSourceAdapter
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.sources.biobio import discovery
from el_animal_fm.news.sources.biobio import scraper


def build_error_article(discovered: DiscoveredUrl, exc: Exception) -> dict[str, Any]:
    return {
        "raw": {
            "source": "biobiochile",
            "source_type": "news_site",
            "url": discovered.url,
        },
        "technical": {
            "http_status": None,
            "content_type": "",
            "downloaded_from_sitemap": discovered.discovered_from_sitemap,
            "downloaded_from_feed": discovered.discovered_from_feed,
            "html_raw_path": "",
            "parser_version": scraper.PARSER_VERSION,
            "parse_success": False,
            "parse_errors": [f"parallel_worker_error: {exc}"],
            "template_noise_detected": False,
            "robots_allowed_checked": "not_checked",
            "discovery_sources": discovered.discovery_sources or [],
        },
    }


def create_adapter() -> NewsSourceAdapter:
    return NewsSourceAdapter(
        display_name="BioBioChile",
        source_name="biobiochile",
        source_folder="biobio",
        parser_version=scraper.PARSER_VERSION,
        default_sleep_seconds=scraper.DEFAULT_SLEEP_SECONDS,
        default_max_category_pages=scraper.DEFAULT_MAX_CATEGORY_PAGES,
        days_back_example=14,
        payload_normalizer=scraper.normalize_payload_texts,
        normalize_url=discovery.normalize_url,
        discover_article_urls=discovery.discover_article_urls,
        extract_article=scraper.extract_article,
        build_error_article=build_error_article,
    )


__all__ = ["create_adapter"]
