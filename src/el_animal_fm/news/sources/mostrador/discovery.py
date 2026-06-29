from __future__ import annotations

import re
from datetime import date
from functools import partial
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from el_animal_fm.news.domain.discovery import merge_discoveries
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.infrastructure.dates import url_matches_date
from el_animal_fm.news.infrastructure.http_client import fetch_text
from el_animal_fm.news.infrastructure.text import (
    clean_text as common_clean_text,
    normalize_text as common_normalize_text,
    remove_template_noise as common_remove_template_noise,
    soup_from_html,
    text_or_empty as common_text_or_empty,
)
from el_animal_fm.news.sources.mostrador.config import (
    BASE_URL,
    CATEGORIA_DIA_URL,
    DEFAULT_SECTION_ARCHIVE_URLS,
    DIA_URL,
    ELMOSTRADOR_BOILERPLATE_PATTERNS,
    NEWS_SITEMAP_URL,
    SITEMAP_URL,
)


def remove_elmostrador_boilerplate(value: str) -> str:
    if not isinstance(value, str) or not value:
        return value or ""

    text = value

    for pattern in ELMOSTRADOR_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


normalize_text = partial(
    common_normalize_text,
    boilerplate_remover=remove_elmostrador_boilerplate,
)
clean_text = partial(common_clean_text, text_normalizer=normalize_text)
remove_template_noise = partial(
    common_remove_template_noise,
    text_normalizer=normalize_text,
)
text_or_empty = partial(common_text_or_empty, text_normalizer=normalize_text)


def normalize_url(url: str) -> str:
    url = url.strip()
    url = url.split("#")[0]

    parsed = urlparse(url)
    query_items = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]

    cleaned = parsed._replace(query=urlencode(query_items, doseq=True))
    return urlunparse(cleaned)


def is_elmostrador_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc not in {"www.elmostrador.cl", "elmostrador.cl"}:
        return False

    path = parsed.path

    excluded_fragments = [
        "/autor/",
        "/tag/",
        "/tags/",
        "/wp-content/",
        "/wp-json/",
        "/newsletter",
        "/categoria/",
        "/dia/",
        "/page/",
        "/quienes-somos",
        "/carta-etica",
        "/principios-editoriales",
        "/politicas-de-privacidad",
        "/contactenos",
    ]

    if any(fragment in path for fragment in excluded_fragments):
        return False

    return bool(re.search(r"/20\d{2}/\d{2}/\d{2}/", path))


def date_from_article_url(url: str) -> date | None:
    match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
    if not match:
        return None

    year, month, day = [int(x) for x in match.groups()]
    return date(year, month, day)


def page_url_for_number(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url

    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    path = re.sub(r"/page/\d+$", "", path)

    cleaned = parsed._replace(path=f"{path}/page/{page_number}/", query="")
    return urlunparse(cleaned)


def infer_listing_category(anchor) -> str:
    candidates: list[str] = []

    parent = anchor.parent
    for _ in range(3):
        if not parent:
            break

        text = clean_text(parent.get_text(" ", strip=True))
        if text:
            parts = re.split(r"\s{2,}|\|", text)
            for part in parts:
                part_clean = clean_text(part)
                if (
                    2 <= len(part_clean) <= 40
                    and part_clean.upper() == part_clean
                    and any(ch.isalpha() for ch in part_clean)
                ):
                    candidates.append(part_clean)

        parent = parent.parent

    return candidates[0] if candidates else ""


def infer_listing_excerpt(anchor) -> str:
    parent = anchor.parent
    if not parent:
        return ""

    container = parent.parent or parent
    text = clean_text(container.get_text(" ", strip=True))
    title = clean_text(anchor.get_text(" ", strip=True))

    if title and title in text:
        text = text.replace(title, " ")

    text = clean_text(text)

    if len(text) > 300:
        text = text[:300].strip()

    return text


def discover_from_page(
    session: requests.Session,
    page_url: str,
    target: date,
    source_name: str,
    page_number: int | None = None,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    try:
        html, _, _ = fetch_text(session, page_url)
    except Exception as exc:
        print(f"[WARN] No se pudo leer {page_url}: {exc}")
        return discovered

    soup = soup_from_html(html)

    position = 0

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(BASE_URL, anchor["href"]))

        if not is_elmostrador_article_url(url):
            continue

        if not url_matches_date(url, target):
            continue

        position += 1

        title = remove_template_noise(text_or_empty(anchor))
        category = infer_listing_category(anchor)
        excerpt = infer_listing_excerpt(anchor)

        item = DiscoveredUrl(
            url=url,
            discovered_from_sitemap=False,
            discovered_from_feed=source_name in {"feed"},
            discovered_from_dia_page=source_name == "dia",
            discovered_from_categoria_dia=source_name == "categoria-dia",
            discovered_from_home=source_name == "home",
            discovered_from_section=source_name,
            listing_position=position,
            listing_page_number=page_number,
            listing_title=title,
            listing_excerpt=excerpt,
            listing_category=category,
            discovery_sources=[source_name],
        )

        discovered[url] = item

    return discovered


def discover_dates_from_page(
    session: requests.Session,
    page_url: str,
    allowed_dates: set[date],
    source_name: str,
    page_number: int | None = None,
) -> tuple[dict[date, dict[str, DiscoveredUrl]], list[date]]:
    discovered_by_date: dict[date, dict[str, DiscoveredUrl]] = {
        target: {} for target in allowed_dates
    }
    page_dates: list[date] = []

    try:
        html, _, _ = fetch_text(session, page_url)
    except Exception as exc:
        print(f"[WARN] No se pudo leer {page_url}: {exc}")
        return discovered_by_date, page_dates

    soup = soup_from_html(html)
    positions_by_date: dict[date, int] = {}

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(BASE_URL, anchor["href"]))

        if not is_elmostrador_article_url(url):
            continue

        article_date = date_from_article_url(url)
        if not article_date:
            continue

        page_dates.append(article_date)

        if article_date not in allowed_dates:
            continue

        positions_by_date[article_date] = positions_by_date.get(article_date, 0) + 1

        title = remove_template_noise(text_or_empty(anchor))
        category = infer_listing_category(anchor)
        excerpt = infer_listing_excerpt(anchor)

        discovered_by_date[article_date][url] = DiscoveredUrl(
            url=url,
            discovered_from_sitemap=False,
            discovered_from_feed=source_name in {"feed"},
            discovered_from_dia_page=source_name == "dia",
            discovered_from_categoria_dia=source_name == "categoria-dia",
            discovered_from_home=source_name == "home",
            discovered_from_section=source_name,
            listing_position=positions_by_date[article_date],
            listing_page_number=page_number,
            listing_title=title,
            listing_excerpt=excerpt,
            listing_category=category,
            discovery_sources=[source_name, page_url],
        )

    return discovered_by_date, page_dates


def discover_from_categoria_dia_paginated(
    session: requests.Session,
    target: date,
    max_pages: int,
) -> dict[str, DiscoveredUrl]:
    all_items: dict[str, DiscoveredUrl] = {}

    for page_number in range(1, max_pages + 1):
        if page_number == 1:
            page_url = CATEGORIA_DIA_URL
        else:
            page_url = f"{CATEGORIA_DIA_URL}page/{page_number}/"

        print(f"Buscando en categoria/dia página {page_number}: {page_url}")

        discovered = discover_from_page(
            session=session,
            page_url=page_url,
            target=target,
            source_name="categoria-dia",
            page_number=page_number,
        )

        print(f"  Encontradas: {len(discovered)}")

        all_items = merge_discoveries(all_items, discovered)

        if page_number > 1 and len(discovered) == 0:
            break

    return all_items


def discover_from_categoria_dia_range(
    session: requests.Session,
    targets: list[date],
    max_pages: int,
) -> dict[date, dict[str, DiscoveredUrl]]:
    allowed_dates = set(targets)
    all_items: dict[date, dict[str, DiscoveredUrl]] = {target: {} for target in targets}

    if not targets:
        return all_items

    oldest_target = min(targets)

    for page_number in range(1, max_pages + 1):
        page_url = page_url_for_number(CATEGORIA_DIA_URL, page_number)
        print(f"Buscando en categoria/dia página {page_number}: {page_url}")

        discovered_by_date, page_dates = discover_dates_from_page(
            session=session,
            page_url=page_url,
            allowed_dates=allowed_dates,
            source_name="categoria-dia",
            page_number=page_number,
        )

        page_total = sum(len(items) for items in discovered_by_date.values())
        print(f"  Encontradas para rango: {page_total}")

        for target, items in discovered_by_date.items():
            all_items[target] = merge_discoveries(all_items[target], items)

        if page_number > 1 and page_total == 0 and page_dates and max(page_dates) < oldest_target:
            break

    return all_items


def discover_section_archive_urls(session: requests.Session) -> list[str]:
    urls = list(DEFAULT_SECTION_ARCHIVE_URLS)

    for seed_url in [BASE_URL, DIA_URL, CATEGORIA_DIA_URL]:
        try:
            html, _, _ = fetch_text(session, seed_url)
        except Exception as exc:
            print(f"[WARN] No se pudo descubrir secciones desde {seed_url}: {exc}")
            continue

        soup = soup_from_html(html)

        for anchor in soup.find_all("a", href=True):
            url = normalize_url(urljoin(BASE_URL, anchor["href"]))
            parsed = urlparse(url)

            if parsed.netloc not in {"www.elmostrador.cl", "elmostrador.cl"}:
                continue

            path = parsed.path

            if re.search(r"/20\d{2}/\d{2}/\d{2}/", path):
                continue

            if path.rstrip("/") == "/categoria/dia":
                continue

            if re.search(r"/page/\d+/?$", path):
                continue

            if "/autor/" in path or "/claves/" in path or "/tag/" in path:
                continue

            if any(
                path.startswith(prefix)
                for prefix in [
                    "/noticias/",
                    "/categoria/",
                    "/mercados/",
                    "/cultura/",
                    "/agenda-pais/",
                    "/braga/",
                ]
            ):
                if url not in urls:
                    urls.append(url)

    return urls


def discover_from_section_archives(
    session: requests.Session,
    target: date,
) -> dict[str, DiscoveredUrl]:
    all_items: dict[str, DiscoveredUrl] = {}
    section_urls = discover_section_archive_urls(session)

    print(f"Buscando URLs en secciones/categorías ({len(section_urls)} secciones)...")

    for section_url in section_urls:
        discovered = discover_from_page(
            session=session,
            page_url=section_url,
            target=target,
            source_name=f"section:{urlparse(section_url).path.strip('/') or 'home'}",
            page_number=1,
        )

        if discovered:
            print(f"  {section_url}: {len(discovered)}")

        all_items = merge_discoveries(all_items, discovered)

    return all_items


def discover_from_candidate_sitemaps(
    session: requests.Session,
    target: date,
) -> dict[str, DiscoveredUrl]:
    discovered: dict[str, DiscoveredUrl] = {}

    candidates = [
        NEWS_SITEMAP_URL,
        SITEMAP_URL,
        f"{BASE_URL}/sitemap_index.xml",
        f"{BASE_URL}/post-sitemap.xml",
    ]

    sitemap_urls: list[str] = []

    for candidate in candidates:
        try:
            xml_text, _, _ = fetch_text(session, candidate)
        except Exception:
            continue

        soup = BeautifulSoup(xml_text, "xml")
        locs = [loc.get_text(strip=True) for loc in soup.find_all("loc")]

        if any("sitemap" in loc.lower() for loc in locs):
            for loc in locs:
                if "sitemap" in loc.lower():
                    sitemap_urls.append(loc)
        else:
            sitemap_urls.append(candidate)

    sitemap_urls = list(dict.fromkeys(sitemap_urls))[:20]

    for sitemap_url in sitemap_urls:
        try:
            xml_text, _, _ = fetch_text(session, sitemap_url)
        except Exception:
            continue

        soup = BeautifulSoup(xml_text, "xml")

        for loc in soup.find_all("loc"):
            url = normalize_url(loc.get_text(strip=True))

            if not is_elmostrador_article_url(url):
                continue

            if not url_matches_date(url, target):
                continue

            discovered[url] = DiscoveredUrl(
                url=url,
                discovered_from_sitemap=True,
                discovery_sources=["sitemap"],
            )

    return discovered


def discover_article_urls(
    session: requests.Session,
    target: date,
    max_category_pages: int,
    preloaded_categoria: dict[str, DiscoveredUrl] | None = None,
) -> dict[str, DiscoveredUrl]:
    print("Buscando URLs en /dia/...")
    dia = discover_from_page(
        session=session,
        page_url=DIA_URL,
        target=target,
        source_name="dia",
        page_number=1,
    )
    print(f"  Encontradas en /dia/: {len(dia)}")

    sections = discover_from_section_archives(
        session=session,
        target=target,
    )
    print(f"  Encontradas en secciones/categorías: {len(sections)}")

    if preloaded_categoria is None:
        print("Buscando URLs en /categoria/dia/...")
        categoria = discover_from_categoria_dia_paginated(
            session=session,
            target=target,
            max_pages=max_category_pages,
        )
    else:
        categoria = preloaded_categoria
        print(f"Usando URLs precargadas desde /categoria/dia/: {len(categoria)}")

    print("Buscando URLs en sitemaps candidatos como respaldo...")
    sitemaps = discover_from_candidate_sitemaps(session, target)
    print(f"  Encontradas en sitemaps: {len(sitemaps)}")

    merged = merge_discoveries(dia, sections, categoria, sitemaps)
    return dict(sorted(merged.items(), key=lambda kv: kv[0]))
