from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


def parse_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)

        if not raw:
            continue

        try:
            parsed = json.loads(raw)
        except Exception:
            continue

        if isinstance(parsed, list):
            items.extend([x for x in parsed if isinstance(x, dict)])
        elif isinstance(parsed, dict):
            if "@graph" in parsed and isinstance(parsed["@graph"], list):
                items.extend([x for x in parsed["@graph"] if isinstance(x, dict)])
            else:
                items.append(parsed)

    return items


def pick_article_jsonld(
    items: list[dict[str, Any]],
    allowed_types: set[str] | None = None,
) -> dict[str, Any]:
    allowed_types = allowed_types or {"newsarticle", "article", "reportagearticle"}

    for item in items:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            types = {str(x).lower() for x in item_type}
        else:
            types = {str(item_type).lower()}

        if allowed_types & types:
            return item

    return {}
