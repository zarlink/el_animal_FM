from __future__ import annotations

from el_animal_fm.news.sources.mostrador.article_parser import (
    build_empty_error_article,
    extract_article,
    normalize_payload_texts,
)
from el_animal_fm.news.sources.mostrador.config import (
    DEFAULT_MAX_CATEGORY_PAGES,
    DEFAULT_SLEEP_SECONDS,
    PARSER_VERSION,
)
from el_animal_fm.news.sources.mostrador.discovery import (
    discover_article_urls,
    discover_from_categoria_dia_range,
    is_elmostrador_article_url,
    normalize_url,
)


__all__ = [
    "DEFAULT_MAX_CATEGORY_PAGES",
    "DEFAULT_SLEEP_SECONDS",
    "PARSER_VERSION",
    "build_empty_error_article",
    "discover_article_urls",
    "discover_from_categoria_dia_range",
    "extract_article",
    "is_elmostrador_article_url",
    "normalize_payload_texts",
    "normalize_url",
]


def main() -> None:
    from el_animal_fm.news.application.downloader import run_cli
    from el_animal_fm.news.sources.mostrador.adapter import create_adapter

    run_cli(create_adapter())


if __name__ == "__main__":
    main()
