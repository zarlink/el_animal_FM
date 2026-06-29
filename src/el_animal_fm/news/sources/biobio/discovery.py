from __future__ import annotations

import re
from datetime import date
from functools import partial
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from el_animal_fm.news.domain.discovery import merge_discoveries
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.infrastructure.dates import url_matches_date
from el_animal_fm.news.infrastructure.http_client import (
    REQUEST_TIMEOUT,
    fetch_text,
)
from el_animal_fm.news.infrastructure.text import (
    clean_text as common_clean_text,
    normalize_text as common_normalize_text,
    soup_from_html,
)


BASE_URL = "https://www.biobiochile.cl"
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap.xml"
LO_ULTIMO_URL = f"{BASE_URL}/lo-ultimo.shtml"
CATEGORY_ARCHIVE_SEED_URL = f"{BASE_URL}/lista/categorias/nacional"

PRIMARY_RE = re.compile(r"primary:\s+([a-z0-9-]+)\s+([a-z0-9-]+)", re.I)

DEFAULT_CATEGORY_ARCHIVE_URLS = [
    f"{BASE_URL}/lista/categorias/nacional",
    f"{BASE_URL}/lista/categorias/internacional",
    f"{BASE_URL}/lista/categorias/economia",
    f"{BASE_URL}/lista/categorias/deportes",
    f"{BASE_URL}/lista/categorias/sociedad",
    f"{BASE_URL}/lista/categorias/espectaculos-y-tv",
    f"{BASE_URL}/lista/categorias/opinion",
    f"{BASE_URL}/lista/categorias/bbcl-investiga",
]

clean_text = partial(common_clean_text, text_normalizer=common_normalize_text)


def is_biobio_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc not in {"www.biobiochile.cl", "biobiochile.cl"}:
        return False

    path = parsed.path.lower()

    if not path.endswith(".shtml"):
        return False

    excluded_paths = [
        "/biobiotv/",
        "/podcasts/",
        "/programas/",
        "/especial/",
        "/especiales/",
        "/legales/",
    ]

    if any(excluded in path for excluded in excluded_paths):
        return False

    if "legales.biobiochile.cl" in url:
        return False

    if "/noticias/" not in path:
        return False

    return True


def normalize_url(url: str) -> str:
    url = url.strip()
    url = url.split("#")[0]
    url = re.sub(r"\?utm_source=.*$", "", url)
    return url


def discover_from_news_sitemap(
    session: requests.Session,
    target: date,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    try:
        xml_text, _, _ = fetch_text(session, NEWS_SITEMAP_URL)
    except Exception as exc:
        print(f"[WARN] No se pudo leer news-sitemap.xml: {exc}")
        return discovered

    soup = BeautifulSoup(xml_text, "xml")

    for url_node in soup.find_all("url"):
        loc_node = url_node.find("loc")
        if not loc_node:
            continue

        url = normalize_url(loc_node.get_text(strip=True))

        if not is_biobio_article_url(url):
            continue

        publication_date_node = url_node.find("news:publication_date")
        sitemap_date_ok = False

        if publication_date_node:
            try:
                parsed_dt = date_parser.parse(publication_date_node.get_text(strip=True))
                sitemap_date_ok = parsed_dt.date() == target
            except Exception:
                sitemap_date_ok = False

        if sitemap_date_ok or url_matches_date(url, target):
            discovered[url] = DiscoveredUrl(
                url=url,
                discovered_from_sitemap=True,
                discovered_from_feed=False,
                discovery_sources=["news-sitemap"],
            )

    return discovered


def discover_from_monthly_sitemap(
    session: requests.Session,
    target: date,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    sitemap_url = f"{BASE_URL}/static/sitemap-{target.year}-{target.month:02d}.xml"

    try:
        xml_text, _, _ = fetch_text(session, sitemap_url)
    except Exception as exc:
        print(f"[WARN] No se pudo leer sitemap mensual {sitemap_url}: {exc}")
        return discovered

    soup = BeautifulSoup(xml_text, "xml")

    for url_node in soup.find_all("url"):
        loc_node = url_node.find("loc")
        if not loc_node:
            continue

        url = normalize_url(loc_node.get_text(strip=True))

        if not is_biobio_article_url(url):
            continue

        if url_matches_date(url, target):
            discovered[url] = DiscoveredUrl(
                url=url,
                discovered_from_sitemap=True,
                discovered_from_feed=False,
                discovery_sources=["monthly-sitemap"],
            )

    return discovered


def discover_from_lo_ultimo(
    session: requests.Session,
    target: date,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    try:
        html, _, _ = fetch_text(session, LO_ULTIMO_URL)
    except Exception as exc:
        print(f"[WARN] No se pudo leer Lo Último: {exc}")
        return discovered

    soup = BeautifulSoup(html, "lxml")

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(BASE_URL, anchor["href"]))

        if not is_biobio_article_url(url):
            continue

        if not url_matches_date(url, target):
            continue

        discovered[url] = DiscoveredUrl(
            url=url,
            discovered_from_sitemap=False,
            discovered_from_feed=True,
            discovery_sources=["lo-ultimo"],
        )

    return discovered


def parse_archive_primary_secondary(html: str, archive_url: str) -> tuple[str, str]:
    text = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
    match = PRIMARY_RE.search(text)

    if not match:
        raise RuntimeError(f"No pude extraer primary/secondary desde {archive_url}")

    return match.group(1), match.group(2)


def parse_quoted_vue_attr(value: str) -> str:
    value = clean_text(value)

    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]

    return value


def parse_vue_request_parameters(value: str) -> dict[str, str]:
    params: dict[str, str] = {}

    for key, single_quoted, double_quoted, bare in re.findall(
        r"([a-zA-Z0-9_-]+)\s*:\s*(?:'([^']*)'|\"([^\"]*)\"|([^,}\s]+))",
        value or "",
    ):
        params[key] = single_quoted or double_quoted or bare

    return params


def parse_fetch_btn_config(
    soup: BeautifulSoup,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    fetch_btn = soup.find("fetch-btn")

    request_url = f"{BASE_URL}/lista/api/get-todo-sin-robin"
    request_parameters = {"categorias": f"group-{primary}"}
    initial_offset = 20
    limit = 10

    if not fetch_btn:
        return {
            "request_url": request_url,
            "request_parameters": request_parameters,
            "initial_offset": initial_offset,
            "limit": limit,
        }

    request_url_raw = fetch_btn.get(":request-url") or fetch_btn.get("request-url")
    if request_url_raw:
        request_url = parse_quoted_vue_attr(request_url_raw)

    params_raw = fetch_btn.get(":request-parameters") or fetch_btn.get("request-parameters")
    parsed_params = parse_vue_request_parameters(params_raw or "")
    if parsed_params:
        request_parameters = parsed_params
    elif secondary and secondary != primary:
        request_parameters = {"categorias": f"{primary},{secondary}"}

    initial_offset_raw = fetch_btn.get("initial-offset")
    if initial_offset_raw:
        try:
            initial_offset = int(initial_offset_raw)
        except ValueError:
            initial_offset = 20

    limit_raw = fetch_btn.get("limit") or fetch_btn.get(":limit")
    if limit_raw:
        try:
            limit = int(parse_quoted_vue_attr(limit_raw))
        except ValueError:
            limit = 10

    return {
        "request_url": urljoin(BASE_URL, request_url),
        "request_parameters": request_parameters,
        "initial_offset": initial_offset,
        "limit": limit,
    }


def article_date_from_api_item(item: dict[str, Any]) -> date | None:
    candidates = [
        str(item.get("post_date_date", "")),
        str(item.get("raw_post_date", "")),
        str(item.get("post_date", "")),
        str(item.get("post_date_txt", "")),
        str(item.get("post_URL", "")),
    ]

    for candidate in candidates:
        candidate = clean_text(candidate)

        if not candidate:
            continue

        url_match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", candidate)
        if url_match:
            year, month, day = [int(x) for x in url_match.groups()]
            return date(year, month, day)

        try:
            return date_parser.parse(candidate, fuzzy=True).date()
        except Exception:
            continue

    return None


def discover_from_archive_html(
    html: str,
    archive_url: str,
    target: date,
    source_name: str,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}
    soup = soup_from_html(html)
    position = 0

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(BASE_URL, anchor["href"]))

        if not is_biobio_article_url(url):
            continue

        if not url_matches_date(url, target):
            continue

        position += 1
        discovered[url] = DiscoveredUrl(
            url=url,
            discovered_from_sitemap=False,
            discovered_from_feed=False,
            discovery_sources=[source_name, archive_url],
        )

    return discovered


def discover_from_category_api(
    session: requests.Session,
    archive_url: str,
    config: dict[str, Any],
    target: date,
    max_pages: int,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    if max_pages <= 0:
        return discovered

    request_url = str(config["request_url"])
    request_parameters = dict(config["request_parameters"])
    offset = int(config["initial_offset"])
    limit = int(config["limit"])

    for page_number in range(1, max_pages + 1):
        params = {
            "limit": limit,
            "offset": offset,
            **request_parameters,
        }

        try:
            response = session.get(request_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            items = response.json()
        except Exception as exc:
            print(f"[WARN] No se pudo leer API de categoría {archive_url}: {exc}")
            break

        if not isinstance(items, list) or not items:
            break

        page_dates: list[date] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            url = normalize_url(str(item.get("post_URL_https") or item.get("post_URL") or ""))

            if not is_biobio_article_url(url):
                continue

            item_date = article_date_from_api_item(item)
            if item_date:
                page_dates.append(item_date)

            if item_date == target or url_matches_date(url, target):
                discovered[url] = DiscoveredUrl(
                    url=url,
                    discovered_from_sitemap=False,
                    discovered_from_feed=False,
                    discovery_sources=[
                        "category-api",
                        archive_url,
                        f"offset={offset}",
                    ],
                )

        offset += len(items)

        if page_dates and max(page_dates) < target:
            break

    return discovered


def discover_category_archive_urls(session: requests.Session) -> list[str]:
    urls = list(DEFAULT_CATEGORY_ARCHIVE_URLS)

    try:
        html, _, _ = fetch_text(session, CATEGORY_ARCHIVE_SEED_URL)
    except Exception as exc:
        print(f"[WARN] No se pudo leer índice de categorías: {exc}")
        return urls

    soup = soup_from_html(html)

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(BASE_URL, anchor["href"]))
        parsed = urlparse(url)

        if parsed.netloc not in {"www.biobiochile.cl", "biobiochile.cl"}:
            continue

        if not parsed.path.startswith("/lista/categorias/"):
            continue

        if url not in urls:
            urls.append(url)

    return urls


def discover_from_category_archives(
    session: requests.Session,
    target: date,
    max_pages: int,
) -> dict[str, DiscoveredUrl]:
    all_items: dict[str, DiscoveredUrl] = {}
    archive_urls = discover_category_archive_urls(session)

    print(f"Buscando URLs en archivos de categorías ({len(archive_urls)} categorías)...")

    for archive_url in archive_urls:
        try:
            html, _, _ = fetch_text(session, archive_url)
            primary, secondary = parse_archive_primary_secondary(html, archive_url)
        except Exception as exc:
            print(f"[WARN] No se pudo inicializar categoría {archive_url}: {exc}")
            continue

        source_name = f"category-archive:{primary}/{secondary}"
        config = parse_fetch_btn_config(soup_from_html(html), primary, secondary)

        initial = discover_from_archive_html(
            html=html,
            archive_url=archive_url,
            target=target,
            source_name=source_name,
        )

        paginated = discover_from_category_api(
            session=session,
            archive_url=archive_url,
            config=config,
            target=target,
            max_pages=max_pages,
        )

        merged = merge_discoveries(initial, paginated)
        print(f"  {primary}/{secondary}: {len(merged)}")

        all_items = merge_discoveries(all_items, merged)

    return all_items


def discover_article_urls(
    session: requests.Session,
    target: date,
    max_category_pages: int,
) -> dict[str, DiscoveredUrl]:
    category_archives = discover_from_category_archives(
        session=session,
        target=target,
        max_pages=max_category_pages,
    )
    print(f"  Encontradas en archivos de categorías: {len(category_archives)}")

    print("Buscando URLs en news-sitemap.xml...")
    news = discover_from_news_sitemap(session, target)
    print(f"  Encontradas en news-sitemap: {len(news)}")

    print("Buscando URLs en sitemap mensual...")
    monthly = discover_from_monthly_sitemap(session, target)
    print(f"  Encontradas en sitemap mensual: {len(monthly)}")

    print("Buscando URLs en Lo Último como respaldo...")
    latest = discover_from_lo_ultimo(session, target)
    print(f"  Encontradas en Lo Último: {len(latest)}")

    merged = merge_discoveries(category_archives, news, monthly, latest)

    return dict(sorted(merged.items(), key=lambda kv: kv[0]))

