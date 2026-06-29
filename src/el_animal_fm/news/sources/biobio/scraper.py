from __future__ import annotations

from el_animal_fm.news.sources.biobio.article_parser import (
    extract_article,
    normalize_payload_texts,
)
from el_animal_fm.news.sources.biobio.config import (
    DEFAULT_MAX_CATEGORY_PAGES,
    DEFAULT_SLEEP_SECONDS,
    PARSER_VERSION,
)
from el_animal_fm.news.sources.biobio.discovery import (
    discover_article_urls,
    is_biobio_article_url,
    normalize_url,
)


__all__ = [
    "DEFAULT_MAX_CATEGORY_PAGES",
    "DEFAULT_SLEEP_SECONDS",
    "PARSER_VERSION",
    "discover_article_urls",
    "extract_article",
    "is_biobio_article_url",
    "normalize_payload_texts",
    "normalize_url",
]


def main() -> None:
    from el_animal_fm.news.application.download.downloader import run_cli
    from el_animal_fm.news.sources.biobio.adapter import create_adapter

    run_cli(create_adapter())


if __name__ == "__main__":
    main()
