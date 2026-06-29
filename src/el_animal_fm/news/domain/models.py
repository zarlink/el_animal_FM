from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiscoveredUrl:
    url: str
    discovered_from_sitemap: bool = False
    discovered_from_feed: bool = False
    discovered_from_dia_page: bool = False
    discovered_from_categoria_dia: bool = False
    discovered_from_home: bool = False
    discovered_from_section: str = ""
    listing_position: int | None = None
    listing_page_number: int | None = None
    listing_title: str = ""
    listing_excerpt: str = ""
    listing_author: str = ""
    listing_date_raw: str = ""
    listing_category: str = ""
    discovery_sources: list[str] = field(default_factory=list)
