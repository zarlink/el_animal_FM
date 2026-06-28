from __future__ import annotations

from el_animal_fm.news.domain.models import DiscoveredUrl


def merge_discoveries(*groups: dict[str, DiscoveredUrl]) -> dict[str, DiscoveredUrl]:
    """Combina descubrimientos por URL preservando señales de todas las fuentes."""
    merged: dict[str, DiscoveredUrl] = {}

    for group in groups:
        for url, item in group.items():
            if url not in merged:
                merged[url] = item
                if merged[url].discovery_sources is None:
                    merged[url].discovery_sources = []
                continue

            current = merged[url]

            current.discovered_from_sitemap = (
                current.discovered_from_sitemap or item.discovered_from_sitemap
            )
            current.discovered_from_feed = (
                current.discovered_from_feed or item.discovered_from_feed
            )
            current.discovered_from_dia_page = (
                current.discovered_from_dia_page or item.discovered_from_dia_page
            )
            current.discovered_from_categoria_dia = (
                current.discovered_from_categoria_dia or item.discovered_from_categoria_dia
            )
            current.discovered_from_home = (
                current.discovered_from_home or item.discovered_from_home
            )

            if not current.discovered_from_section and item.discovered_from_section:
                current.discovered_from_section = item.discovered_from_section

            if current.listing_position is None and item.listing_position is not None:
                current.listing_position = item.listing_position

            if current.listing_page_number is None and item.listing_page_number is not None:
                current.listing_page_number = item.listing_page_number

            for attr in [
                "listing_title",
                "listing_excerpt",
                "listing_author",
                "listing_date_raw",
                "listing_category",
            ]:
                if not getattr(current, attr) and getattr(item, attr):
                    setattr(current, attr, getattr(item, attr))

            for source in item.discovery_sources or []:
                if source not in current.discovery_sources:
                    current.discovery_sources.append(source)

    return merged
