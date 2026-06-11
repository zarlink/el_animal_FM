from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from zoneinfo import ZoneInfo
import html as html_lib


BASE_URL = "https://www.elmostrador.cl"
DIA_URL = f"{BASE_URL}/dia/"
CATEGORIA_DIA_URL = f"{BASE_URL}/categoria/dia/"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap_news.xml"

PARSER_VERSION = "elmostrador_raw_v2_range_sections"
TIMEZONE = "America/Santiago"

REQUEST_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_MAX_CATEGORY_PAGES = 350

ELMOSTRADOR_BOILERPLATE_PATTERNS = [
    r"\bsíntesis generada con openai\b",
    r"\bsintesis generada con openai\b",
    r"\bdesarrollado por el mostrador\b",
    r"\btambién te puede interesar\b",
    r"\btambien te puede interesar\b",
    r"\bnoticias del día\b",
    r"\bnoticias del dia\b",
    r"\bdestacados\b",
    r"\bver más\b",
    r"\bver mas\b",
    r"\bpublicidad\b",
    r"\bsíguenos en\b",
    r"\bsiguenos en\b",
    r"\bsúmate a nuestro canal\b",
    r"\bsumate a nuestro canal\b",
    r"\breciba los newsletter\b",
    r"\binscríbete en el newsletter\b",
    r"\binscribete en el newsletter\b",
    r"\balgunos derechos reservados\b",
    r"\binfo@elmostrador\.cl\b",
]

DEFAULT_SECTION_ARCHIVE_URLS = [
    f"{BASE_URL}/",
    f"{BASE_URL}/noticias/pais/",
    f"{BASE_URL}/noticias/mundo/",
    f"{BASE_URL}/noticias/sin-editar/",
    f"{BASE_URL}/mercados/",
    f"{BASE_URL}/mercados/actualidad-economica/",
    f"{BASE_URL}/noticias/opinion/",
    f"{BASE_URL}/categoria/columnas/",
    f"{BASE_URL}/categoria/cartas/",
    f"{BASE_URL}/categoria/editorial/",
    f"{BASE_URL}/categoria/tv/",
    f"{BASE_URL}/noticias/multimedia/",
    f"{BASE_URL}/cultura/",
    f"{BASE_URL}/agenda-pais/",
    f"{BASE_URL}/categoria/agenda/",
    f"{BASE_URL}/braga/",
    f"{BASE_URL}/noticias/deportes/",
]


SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


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


def today_chile() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def parse_target_date(value: str | None) -> date:
    """
    Acepta:
    - None: fecha actual en Chile.
    - DD_MM_YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD
    """
    if not value:
        return today_chile()

    value = value.strip()

    for fmt in ("%d_%m_%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    raise ValueError(
        "Formato de fecha no reconocido. Usa DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD."
    )


def date_dir_name(target: date) -> str:
    return target.strftime("%d_%m_%Y")


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
        }
    )
    return session


def decode_response_text(response: requests.Response) -> str:
    """
    Decodifica HTML/XML de forma estable.
    Evita problemas de caracteres cuando response.text no detecta bien encoding.
    """
    try:
        return response.content.decode("utf-8", errors="replace")
    except Exception:
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        return response.text

def repair_mojibake(value: str) -> str:
    """
    Corrige casos típicos:
    'dÃ©ficit' -> 'déficit'
    'caÃ­da' -> 'caída'
    """
    if not isinstance(value, str) or not value:
        return value or ""

    markers = ("Ã", "Â", "â€", "â€œ", "â€", "â€™", "ðŸ")

    if not any(marker in value for marker in markers):
        return value

    candidates = [value]

    for source_encoding in ("latin1", "cp1252"):
        try:
            candidates.append(
                value.encode(source_encoding, errors="ignore").decode("utf-8", errors="ignore")
            )
        except Exception:
            pass

    def badness(text: str) -> int:
        return sum(text.count(marker) for marker in markers) + text.count("�") * 3

    return min(candidates, key=badness)


def remove_elmostrador_boilerplate(value: str) -> str:
    """
    Elimina ruido repetido propio de El Mostrador, sin eliminar el contenido útil.
    """
    if not isinstance(value, str) or not value:
        return value or ""

    text = value

    for pattern in ELMOSTRADOR_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text(value: Any) -> str:
    """
    Normaliza HTML entities, espacios, mojibake y boilerplate editorial.
    """
    if value is None:
        return ""

    text = str(value)
    text = html_lib.unescape(text)
    text = repair_mojibake(text)
    text = remove_elmostrador_boilerplate(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_payload_texts(value: Any) -> Any:
    """
    Aplica normalización recursiva antes de guardar el JSON final.
    """
    if isinstance(value, dict):
        return {k: normalize_payload_texts(v) for k, v in value.items()}

    if isinstance(value, list):
        return [normalize_payload_texts(v) for v in value]

    if isinstance(value, str):
        return normalize_text(value)

    return value

def fetch_text(session: requests.Session, url: str) -> tuple[str, int, str]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    content_type = response.headers.get("Content-Type", "")
    response.raise_for_status()
    return decode_response_text(response), response.status_code, content_type

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


def clean_text(value: str) -> str:
    return normalize_text(value)


def remove_template_noise(value: str) -> str:
    value = re.sub(r"\{\{.*?\}\}", "", value or "")
    return normalize_text(value)


def text_or_empty(tag) -> str:
    if not tag:
        return ""
    return clean_text(tag.get_text(" ", strip=True))


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


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


def url_matches_date(url: str, target: date) -> bool:
    return target.strftime("/%Y/%m/%d/") in url


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


def merge_discoveries(*groups: dict[str, DiscoveredUrl]) -> dict[str, DiscoveredUrl]:
    merged: dict[str, DiscoveredUrl] = {}

    for group in groups:
        for url, item in group.items():
            if url not in merged:
                merged[url] = item
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

            for source in item.discovery_sources:
                if source not in current.discovery_sources:
                    current.discovery_sources.append(source)

    return merged


def infer_listing_category(anchor) -> str:
    """
    Heurística: en las páginas de listado, la categoría suele aparecer cerca
    del link como texto en mayúsculas.
    """
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

        # Si la primera página ya no trae nada, las siguientes suelen ser más antiguas.
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
    """
    Respaldo no invasivo. Algunos sitios WordPress usan sitemap_index.xml,
    post-sitemap.xml o sitemap.xml. Si existen, filtramos por URLs con fecha.
    """
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

        # Si es índice, tomamos sub-sitemaps.
        locs = [loc.get_text(strip=True) for loc in soup.find_all("loc")]

        if any("sitemap" in loc.lower() for loc in locs):
            for loc in locs:
                if "sitemap" in loc.lower():
                    sitemap_urls.append(loc)
        else:
            sitemap_urls.append(candidate)

    # Limitamos para no hacer una descarga excesiva.
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


def get_meta(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key})
    if not tag:
        tag = soup.find("meta", attrs={"name": key})
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return ""


def get_canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if tag and tag.get("href"):
        return normalize_url(urljoin(BASE_URL, tag["href"]))
    return fallback_url


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


def pick_article_jsonld(items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in items:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            types = {str(x).lower() for x in item_type}
        else:
            types = {str(item_type).lower()}

        if {"newsarticle", "article", "blogposting", "reportagearticle"} & types:
            return item

    return {}


def parse_spanish_date(value: str) -> tuple[str, str, str, str]:
    raw = clean_text(value)

    if not raw:
        return "", "", "", ""

    # Primero intentamos ISO/dateutil.
    try:
        parsed = date_parser.parse(raw, fuzzy=True)
        if not parsed.tzinfo:
            parsed = parsed.replace(tzinfo=ZoneInfo(TIMEZONE))
        return (
            parsed.isoformat(),
            parsed.date().isoformat(),
            parsed.time().replace(microsecond=0).isoformat(),
            raw,
        )
    except Exception:
        pass

    # Formato típico El Mostrador: 25 mayo, 2026
    match = re.search(
        r"(\d{1,2})\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
        r",?\s+"
        r"(\d{4})"
        r"(?:\s*[|,-]\s*(\d{1,2}:\d{2}))?",
        raw,
        flags=re.IGNORECASE,
    )

    if match:
        day = int(match.group(1))
        month = SPANISH_MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        time_part = match.group(4) or "00:00"

        hour, minute = [int(x) for x in time_part.split(":")]
        parsed = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(TIMEZONE))

        return (
            parsed.isoformat(),
            parsed.date().isoformat(),
            parsed.time().replace(microsecond=0).isoformat(),
            raw,
        )

    return "", "", "", raw


def get_published_data(soup: BeautifulSoup, article_ld: dict[str, Any]) -> tuple[str, str, str, str]:
    candidates = [
        str(article_ld.get("datePublished", "")),
        str(article_ld.get("dateCreated", "")),
        get_meta(soup, "article:published_time"),
        get_meta(soup, "date"),
        get_meta(soup, "pubdate"),
        get_meta(soup, "og:updated_time"),
    ]

    visible_text = soup.get_text("\n", strip=True)

    for line in visible_text.splitlines():
        line = clean_text(line)

        if re.fullmatch(
            r"\d{1,2}\s+"
            r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
            r",?\s+\d{4}",
            line,
            flags=re.IGNORECASE,
        ):
            candidates.append(line)
            break

    for candidate in candidates:
        candidate = clean_text(candidate)
        if candidate:
            published_at, published_date, published_time, raw = parse_spanish_date(candidate)
            if raw:
                return published_at, published_date, published_time, raw

    return "", "", "", ""


def get_title(soup: BeautifulSoup, article_ld: dict[str, Any]) -> str:
    if article_ld.get("headline"):
        return clean_text(str(article_ld["headline"]))

    h1 = soup.find("h1")
    if h1:
        return remove_template_noise(text_or_empty(h1))

    og_title = get_meta(soup, "og:title")
    if og_title:
        return clean_text(og_title)

    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))

    return ""


def get_slug(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.split("/")[-1] if path else ""
    return name


def get_article_id(soup: BeautifulSoup, url: str) -> str:
    candidates = [
        get_meta(soup, "article:id"),
        get_meta(soup, "post_id"),
        get_meta(soup, "id"),
    ]

    html = str(soup)
    patterns = [
        r"post[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
        r"article[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
        r"wp-post-(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            candidates.append(match.group(1))

    for candidate in candidates:
        candidate = clean_text(candidate)
        if candidate:
            return candidate

    return ""


def humanize_section(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").title()


def infer_sections_from_url(url: str) -> dict[str, str]:
    path_parts = [p for p in urlparse(url).path.split("/") if p]

    date_index = None

    for i, part in enumerate(path_parts):
        if re.fullmatch(r"20\d{2}", part):
            date_index = i
            break

    category_parts = path_parts[:date_index] if date_index is not None else []

    if category_parts and category_parts[0] == "noticias":
        category_parts = category_parts[1:]

    main_section = humanize_section(category_parts[0]) if category_parts else ""
    subsection = humanize_section(category_parts[1]) if len(category_parts) >= 2 else ""
    program_or_series = ""

    if main_section.lower() == "multimedia" and subsection:
        program_or_series = subsection

    site_vertical = main_section

    region_section = ""

    for part in category_parts:
        lower = part.lower()
        if (
            lower.startswith("aqui-")
            or lower.startswith("aquí-")
            or lower in {"aqui-regiones", "aquí-regiones"}
            or lower in {"arica", "coquimbo", "los-rios", "magallanes", "nuble", "valparaiso", "biobio"}
        ):
            region_section = humanize_section(part)
            break

    return {
        "main_section": main_section,
        "subsection": subsection,
        "site_vertical": site_vertical,
        "program_or_series": program_or_series,
        "region_section": region_section,
    }


def get_breadcrumb_raw(soup: BeautifulSoup) -> str:
    candidates = []

    for selector in [
        ".breadcrumb",
        ".breadcrumbs",
        "nav[aria-label='breadcrumb']",
        "[class*='breadcrumb']",
        "[class*='miga']",
    ]:
        for tag in soup.select(selector):
            text = remove_template_noise(text_or_empty(tag))
            if text:
                candidates.append(text)

    return candidates[0] if candidates else ""


def infer_article_type(url: str, breadcrumb_raw: str, main_section: str, subsection: str, body_text: str) -> str:
    value = f"{url} {breadcrumb_raw} {main_section} {subsection} {body_text[:500]}".lower()

    if "cartas-al-director" in value or "cartas al director" in value:
        return "letter_to_editor"

    if "editorial" in value or "editoriales" in value:
        return "editorial"

    if "opinion" in value or "opinión" in value or "columna" in value:
        return "column"

    if "multimedia" in value or "vodcast" in value or "punto-por-punto" in value:
        return "multimedia"

    if "mercados" in value:
        return "markets_news"

    return "news"


def bool_sections(main_section: str, subsection: str, article_type: str, url: str) -> dict[str, bool]:
    value = f"{main_section} {subsection} {article_type} {url}".lower()

    return {
        "is_opinion": "opinion" in value or "opinión" in value or article_type in {"column", "letter_to_editor", "editorial"},
        "is_column": article_type == "column",
        "is_letter_to_editor": article_type == "letter_to_editor",
        "is_editorial": article_type == "editorial",
        "is_market_section": "mercados" in value,
        "is_economy_section": "econom" in value or "mercados" in value,
        "is_country_section": "pais" in value or "país" in value,
        "is_world_section": "mundo" in value,
        "is_multimedia": "multimedia" in value or article_type == "multimedia",
        "is_regional": "aqui" in value or "aquí" in value or "regiones" in value,
        "is_agenda_pais": "agenda pais" in value or "agenda país" in value or "agenda-pais" in value,
        "is_culture": "cultura" in value,
        "is_deportes": "deportes" in value,
    }


def get_author_info(soup: BeautifulSoup, article_ld: dict[str, Any]) -> dict[str, str | bool]:
    author_name = ""
    author_url = ""
    author_role = ""
    author_bio = ""
    author_type = ""

    author = article_ld.get("author")

    if isinstance(author, dict):
        author_name = clean_text(str(author.get("name", "")))
        author_url = clean_text(str(author.get("url", "")))
        author_bio = clean_text(str(author.get("description", "")))
    elif isinstance(author, list) and author:
        first_author = author[0]
        if isinstance(first_author, dict):
            author_name = clean_text(str(first_author.get("name", "")))
            author_url = clean_text(str(first_author.get("url", "")))
            author_bio = clean_text(str(first_author.get("description", "")))
        else:
            author_name = clean_text(str(first_author))
    elif isinstance(author, str):
        author_name = clean_text(author)

    if not author_name:
        meta_author = get_meta(soup, "author")
        if meta_author:
            author_name = meta_author

    possible_author_selectors = [
        "[class*='author']",
        "[class*='autor']",
        "a[href*='/autor/']",
    ]

    for selector in possible_author_selectors:
        tag = soup.select_one(selector)
        if not tag:
            continue

        text = remove_template_noise(text_or_empty(tag))

        if text and not author_name:
            # Evita tomar bloques muy largos.
            if len(text) <= 160:
                author_name = re.sub(r"^Por\s*:\s*", "", text, flags=re.IGNORECASE).strip()

        if tag.name == "a" and tag.get("href") and not author_url:
            author_url = urljoin(BASE_URL, tag["href"])

        break

    visible_lines = [
        clean_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if clean_text(line)
    ]

    for idx, line in enumerate(visible_lines):
        lower = line.lower()

        if lower.startswith("por:") or lower == "por":
            if idx + 1 < len(visible_lines) and not author_name:
                author_name = clean_text(visible_lines[idx + 1])

        if author_name and author_name in line and "|" in line:
            parts = [clean_text(x) for x in line.split("|")]
            if parts:
                author_name = parts[0].replace("Por:", "").strip()
            if len(parts) > 1:
                author_role = parts[1]

    lower_author = author_name.lower()

    is_newsroom = "mesa de noticias" in lower_author or "el mostrador" == lower_author
    is_agency_content = any(token in lower_author for token in ["efe", "reuters", "afp"])
    is_external_columnist = False

    if author_role:
        role_lower = author_role.lower()
        is_external_columnist = any(
            token in role_lower
            for token in ["académico", "academico", "consultor", "investigador", "abogado", "sociólogo", "psicólogo"]
        )

    is_staff_writer = not is_newsroom and not is_agency_content and not is_external_columnist

    if is_newsroom:
        author_type = "newsroom"
    elif is_agency_content:
        author_type = "agency"
    elif is_external_columnist:
        author_type = "external_columnist"
    elif is_staff_writer:
        author_type = "staff_or_named_author"
    else:
        author_type = "unknown"

    return {
        "author_name": author_name,
        "author_url": author_url,
        "author_role": author_role,
        "author_bio": author_bio,
        "author_type": author_type,
        "is_staff_writer": is_staff_writer,
        "is_newsroom": is_newsroom,
        "is_external_columnist": is_external_columnist,
        "is_agency_content": is_agency_content,
    }


def find_article_container(soup: BeautifulSoup):
    for selector in [
        "article",
        "main article",
        "main",
        "[class*='article']",
        "[class*='post']",
        "[class*='nota']",
        "[class*='single']",
    ]:
        tag = soup.select_one(selector)
        if tag:
            return tag

    return soup.body or soup


def remove_unwanted_tags(container) -> None:
    for tag in container.find_all(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
            "button",
            "iframe",
        ]
    ):
        tag.decompose()


def is_boilerplate_paragraph(text: str) -> bool:
    lower = normalize_text(text).lower()

    bad_fragments = [
        "publicidad",
        "síguenos en",
        "siguenos en",
        "súmate a nuestro canal",
        "sumate a nuestro canal",
        "reciba los newsletter",
        "inscríbete en el newsletter",
        "inscribete en el newsletter",
        "inscríbase",
        "volver arriba",
        "también te puede interesar",
        "tambien te puede interesar",
        "destacados",
        "noticias del día",
        "noticias del dia",
        "ver más",
        "ver mas",
        "algunos derechos reservados",
        "santa lucía",
        "info@elmostrador.cl",
        "desarrollado por el mostrador",
        "síntesis generada con openai",
        "sintesis generada con openai",
        "{{",
        "}}",
    ]

    if any(fragment in lower for fragment in bad_fragments):
        return True

    # Evita líneas de menú.
    if text.upper() == text and len(text) <= 60:
        return True

    return False


def extract_ai_summary(soup: BeautifulSoup) -> tuple[str, bool, str]:
    lines = [
        clean_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if clean_text(line)
    ]

    for idx, line in enumerate(lines):
        if "síntesis generada con openai" in line.lower():
            collected = []

            for next_line in lines[idx + 1 : idx + 8]:
                lower = next_line.lower()

                if "desarrollado por el mostrador" in lower:
                    break

                if is_boilerplate_paragraph(next_line):
                    continue

                if len(next_line) > 40:
                    collected.append(next_line)

            summary = clean_text(" ".join(collected))
            summary = remove_elmostrador_boilerplate(summary)

            if summary:
                return summary, True, "openai_elmostrador"

    return "", False, ""


def extract_body(container, ai_summary: str = "") -> dict[str, Any]:
    container_copy = BeautifulSoup(str(container), "lxml")
    remove_unwanted_tags(container_copy)

    paragraphs: list[str] = []

    for p in container_copy.find_all("p"):
        text = remove_template_noise(text_or_empty(p))

        if not text:
            continue

        if len(text) < 25:
            continue

        if ai_summary and text in ai_summary:
            continue

        if is_boilerplate_paragraph(text):
            continue

        if text not in paragraphs:
            paragraphs.append(text)

    if not paragraphs:
        fallback_text = remove_template_noise(container_copy.get_text("\n", strip=True))
        fallback_lines = [
            clean_text(line)
            for line in fallback_text.splitlines()
            if len(clean_text(line)) >= 25
            and not is_boilerplate_paragraph(clean_text(line))
            and (not ai_summary or clean_text(line) not in ai_summary)
        ]
        paragraphs = list(dict.fromkeys(fallback_lines))

    body_text_raw = "\n".join(paragraphs)
    body_text_clean = clean_text(" ".join(paragraphs))

    internal_subheadings: list[str] = []

    for heading in container_copy.find_all(["h2", "h3", "h4"]):
        text = remove_template_noise(text_or_empty(heading))

        if not text:
            continue

        if is_boilerplate_paragraph(text):
            continue

        if len(text) < 180 and text not in internal_subheadings:
            internal_subheadings.append(text)

    quote_count = body_text_clean.count("“") + body_text_clean.count('"') // 2

    return {
        "body_text_raw": body_text_raw,
        "body_text_clean": body_text_clean,
        "paragraphs": paragraphs,
        "paragraph_count": len(paragraphs),
        "body_length_chars": len(body_text_clean),
        "body_length_words": len(body_text_clean.split()),
        "internal_subheadings": internal_subheadings,
        "quote_count": quote_count,
        "has_quotes": quote_count > 0,
    }


def get_subtitle_lead_and_summary(
    soup: BeautifulSoup,
    article_ld: dict[str, Any],
    paragraphs: list[str],
    ai_summary: str,
) -> dict[str, str | int]:
    description = ""

    if article_ld.get("description"):
        description = clean_text(str(article_ld["description"]))

    if not description:
        description = get_meta(soup, "description") or get_meta(soup, "og:description")

    subtitle = description
    lead = paragraphs[0] if paragraphs else ""
    summary = ai_summary or description

    return {
        "subtitle": subtitle,
        "lead": lead,
        "summary": summary,
        "title_length_chars": 0,
        "subtitle_length_chars": len(subtitle),
        "summary_length_chars": len(summary),
    }


def get_image_data(soup: BeautifulSoup, article_ld: dict[str, Any], container) -> dict[str, Any]:
    main_image_url = ""
    main_image_alt = ""
    image_caption = ""
    image_credit = ""

    image_value = article_ld.get("image")

    if isinstance(image_value, str):
        main_image_url = image_value
    elif isinstance(image_value, dict):
        main_image_url = str(image_value.get("url", ""))
    elif isinstance(image_value, list) and image_value:
        first_image = image_value[0]
        if isinstance(first_image, str):
            main_image_url = first_image
        elif isinstance(first_image, dict):
            main_image_url = str(first_image.get("url", ""))

    if not main_image_url:
        main_image_url = get_meta(soup, "og:image")

    imgs = container.find_all("img") if container else soup.find_all("img")
    image_count = len(imgs)

    if imgs and not main_image_url:
        src = imgs[0].get("src") or imgs[0].get("data-src") or ""
        if src:
            main_image_url = urljoin(BASE_URL, src)

    if imgs:
        main_image_alt = clean_text(imgs[0].get("alt", ""))

    figure = container.find("figure") if container else soup.find("figure")
    if figure:
        figcaption = figure.find("figcaption")
        if figcaption:
            image_caption = clean_text(figcaption.get_text(" ", strip=True))

    visible_text = container.get_text("\n", strip=True) if container else soup.get_text("\n", strip=True)

    for line in visible_text.splitlines():
        line_clean = clean_text(line)
        lower = line_clean.lower()

        if any(token in lower for token in ["foto:", "fotos:", "agenciauno", "agencia uno", "imagen:", "crédito"]):
            if len(line_clean) <= 160:
                image_credit = line_clean
                break

    return {
        "main_image_url": main_image_url,
        "main_image_alt": main_image_alt,
        "image_caption": image_caption,
        "image_credit": image_credit,
        "has_image": bool(main_image_url or imgs),
        "image_count": image_count,
    }


def extract_video_audio_data(soup: BeautifulSoup, container) -> dict[str, Any]:
    scope = container or soup

    iframe_urls = []

    for iframe in scope.find_all("iframe"):
        if iframe.get("src"):
            iframe_urls.append(urljoin(BASE_URL, iframe["src"]))

    video = scope.find("video")
    audio = scope.find("audio")

    video_url = ""

    if iframe_urls:
        video_url = iframe_urls[0]
    elif video and video.get("src"):
        video_url = urljoin(BASE_URL, video["src"])

    audio_url = ""
    if audio and audio.get("src"):
        audio_url = urljoin(BASE_URL, audio["src"])

    has_embedded_youtube = any("youtube.com" in url or "youtu.be" in url for url in iframe_urls)
    has_embedded_spotify = any("spotify.com" in url for url in iframe_urls) or (
        "spotify.com" in audio_url
    )

    has_video = bool(video_url or video or has_embedded_youtube)
    has_audio = bool(audio_url or audio or has_embedded_spotify)

    if has_video and has_audio:
        media_type = "mixed"
    elif has_video:
        media_type = "video"
    elif has_audio:
        media_type = "audio"
    else:
        media_type = "text"

    return {
        "has_video": has_video,
        "video_url": video_url,
        "has_audio": has_audio,
        "audio_url": audio_url,
        "has_embedded_youtube": has_embedded_youtube,
        "has_embedded_spotify": has_embedded_spotify,
        "media_type": media_type,
    }


def extract_links_in_body(container, current_url: str) -> dict[str, Any]:
    internal_links: list[str] = []
    external_links: list[str] = []
    document_links: list[str] = []
    mentioned_documents_raw: list[str] = []

    if not container:
        return {
            "external_links_in_body": [],
            "internal_links_in_body": [],
            "document_links": [],
            "has_document_link": False,
            "mentioned_documents_raw": [],
        }

    for anchor in container.find_all("a", href=True):
        href = normalize_url(urljoin(BASE_URL, anchor["href"]))
        text = clean_text(anchor.get_text(" ", strip=True))

        if href == current_url:
            continue

        parsed = urlparse(href)

        if parsed.netloc in {"www.elmostrador.cl", "elmostrador.cl"}:
            if href not in internal_links:
                internal_links.append(href)
        else:
            if href not in external_links:
                external_links.append(href)

        if href.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            if href not in document_links:
                document_links.append(href)
            if text and text not in mentioned_documents_raw:
                mentioned_documents_raw.append(text)

    return {
        "external_links_in_body": external_links,
        "internal_links_in_body": internal_links,
        "document_links": document_links,
        "has_document_link": bool(document_links),
        "mentioned_documents_raw": mentioned_documents_raw,
    }


def previous_heading_text(anchor) -> str:
    heading = anchor.find_previous(["h2", "h3", "h4"])
    if heading:
        return clean_text(heading.get_text(" ", strip=True)).lower()
    return ""


def extract_related_links(soup: BeautifulSoup, container, current_url: str) -> dict[str, Any]:
    scope = soup

    also_links: list[str] = []
    also_titles: list[str] = []

    featured_links: list[str] = []
    featured_titles: list[str] = []

    same_day_links: list[str] = []
    same_day_titles: list[str] = []

    related_links: list[str] = []
    related_titles: list[str] = []

    for anchor in scope.find_all("a", href=True):
        href = normalize_url(urljoin(BASE_URL, anchor["href"]))
        title = remove_template_noise(text_or_empty(anchor))

        if not is_elmostrador_article_url(href):
            continue

        if href == current_url:
            continue

        heading_text = previous_heading_text(anchor)
        parent_text = clean_text(anchor.parent.get_text(" ", strip=True)).lower() if anchor.parent else ""
        context = f"{heading_text} {parent_text}"

        if "también te puede interesar" in context or "tambien te puede interesar" in context:
            if href not in also_links:
                also_links.append(href)
                also_titles.append(title)
        elif "destacados" in context:
            if href not in featured_links:
                featured_links.append(href)
                featured_titles.append(title)
        elif "noticias del día" in context or "noticias del dia" in context:
            if href not in same_day_links:
                same_day_links.append(href)
                same_day_titles.append(title)
        else:
            if href not in related_links:
                related_links.append(href)
                related_titles.append(title)

    return {
        "also_interesting_links": also_links,
        "also_interesting_titles": also_titles,
        "also_interesting_count": len(also_links),
        "featured_links": featured_links,
        "featured_titles": featured_titles,
        "featured_count": len(featured_links),
        "same_day_links": same_day_links,
        "same_day_titles": same_day_titles,
        "same_day_count": len(same_day_links),
        "related_links": related_links,
        "related_titles": related_titles,
        "related_count": len(related_links),
    }


def extract_share_and_channel_links(soup: BeautifulSoup) -> dict[str, str]:
    facebook = ""
    x_url = ""
    whatsapp = ""
    google_news = ""
    whatsapp_channel = ""
    youtube = ""
    spotify = ""

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]

        if not facebook and ("facebook.com/sharer" in href or "facebook.com/share" in href):
            facebook = href

        if not x_url and ("twitter.com/intent" in href or "x.com/intent" in href or "twitter.com/share" in href):
            x_url = href

        if not whatsapp and ("whatsapp://" in href or "wa.me" in href or "api.whatsapp.com" in href):
            whatsapp = href

        if not google_news and "news.google.com" in href:
            google_news = href

        if not whatsapp_channel and "whatsapp.com" in href:
            whatsapp_channel = href

        if not youtube and ("youtube.com" in href or "youtu.be" in href):
            youtube = href

        if not spotify and "spotify.com" in href:
            spotify = href

    return {
        "share_facebook_url": facebook,
        "share_x_url": x_url,
        "share_whatsapp_url": whatsapp,
        "google_news_url": google_news,
        "whatsapp_channel_url": whatsapp_channel,
        "youtube_url": youtube,
        "spotify_url": spotify,
    }


def infer_source_attribution_and_agency(body_text: str, image_credit: str, author_name: str) -> dict[str, str | bool]:
    value = f"{body_text[:1000]} {image_credit} {author_name}".lower()

    agency_markers = {
        "agenciauno": "AgenciaUNO",
        "agencia uno": "AgenciaUNO",
        "efe": "EFE",
        "reuters": "Reuters",
        "afp": "AFP",
        "ap": "AP",
    }

    agency_name = ""
    source_attribution = ""

    for marker, normalized in agency_markers.items():
        if marker in value:
            agency_name = normalized
            source_attribution = normalized
            break

    return {
        "source_attribution": source_attribution,
        "agency_name": agency_name,
        "is_agency_content": bool(agency_name and agency_name != "AgenciaUNO"),
    }


def detect_template_noise(html: str) -> bool:
    return "{{" in html or "}}" in html


def save_raw_html(raw_html_dir: Path, url: str, html: str) -> str:
    slug = get_slug(url) or "article"
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:120]
    path = raw_html_dir / f"{safe_slug}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


def build_empty_error_article(
    discovered: DiscoveredUrl,
    http_status: int | None,
    content_type: str,
    error: str,
) -> dict[str, Any]:
    return {
        "raw": {
            "source": "elmostrador",
            "source_type": "news_site",
            "url": discovered.url,
            "canonical_url": "",
            "article_id": "",
            "slug": get_slug(discovered.url),
        },
        "technical": {
            "http_status": http_status,
            "content_type": content_type,
            "downloaded_from_sitemap": discovered.discovered_from_sitemap,
            "downloaded_from_feed": discovered.discovered_from_feed,
            "downloaded_from_dia_page": discovered.discovered_from_dia_page,
            "downloaded_from_categoria_dia": discovered.discovered_from_categoria_dia,
            "html_raw_path": "",
            "parser_version": PARSER_VERSION,
            "parse_success": False,
            "parse_errors": [error],
            "template_noise_detected": False,
            "robots_allowed_checked": "not_checked",
            "discovery_sources": discovered.discovery_sources,
        },
    }


def extract_article(
    session: requests.Session,
    discovered: DiscoveredUrl,
    raw_html_dir: Path,
) -> dict[str, Any]:
    url = discovered.url
    parse_errors: list[str] = []

    http_status = None
    content_type = ""

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        http_status = response.status_code
        content_type = response.headers.get("Content-Type", "")
        response.raise_for_status()
        html = decode_response_text(response)
    except Exception as exc:
        return build_empty_error_article(
            discovered=discovered,
            http_status=http_status,
            content_type=content_type,
            error=f"download_error: {exc}",
        )

    html_raw_path = save_raw_html(raw_html_dir, url, html)

    soup = soup_from_html(html)
    json_ld_items = parse_json_ld(soup)
    article_ld = pick_article_jsonld(json_ld_items)

    canonical_url = get_canonical_url(soup, url)
    article_id = get_article_id(soup, url)
    slug = get_slug(url)

    published_at, published_date, published_time, published_at_raw = get_published_data(
        soup,
        article_ld,
    )

    section_data = infer_sections_from_url(url)
    main_section = clean_text(str(article_ld.get("articleSection", ""))) or section_data["main_section"]
    subsection = section_data["subsection"]
    site_vertical = section_data["site_vertical"] or main_section
    program_or_series = section_data["program_or_series"]
    region_section = section_data["region_section"]

    breadcrumb_raw = get_breadcrumb_raw(soup)

    container = find_article_container(soup)

    ai_summary, has_ai_summary, summary_source = extract_ai_summary(soup)

    body_data = extract_body(container, ai_summary=ai_summary)

    title = get_title(soup, article_ld)

    subtitle_data = get_subtitle_lead_and_summary(
        soup=soup,
        article_ld=article_ld,
        paragraphs=body_data["paragraphs"],
        ai_summary=ai_summary,
    )

    article_type = infer_article_type(
        url=url,
        breadcrumb_raw=breadcrumb_raw,
        main_section=main_section,
        subsection=subsection,
        body_text=body_data["body_text_clean"],
    )

    section_flags = bool_sections(
        main_section=main_section,
        subsection=subsection,
        article_type=article_type,
        url=url,
    )

    author_data = get_author_info(soup, article_ld)

    image_data = get_image_data(soup, article_ld, container)
    media_data = extract_video_audio_data(soup, container)
    body_links_data = extract_links_in_body(container, canonical_url)
    related_data = extract_related_links(soup, container, canonical_url)
    share_data = extract_share_and_channel_links(soup)

    attribution_data = infer_source_attribution_and_agency(
        body_text=body_data["body_text_clean"],
        image_credit=image_data["image_credit"],
        author_name=str(author_data["author_name"]),
    )

    # Si el autor ya fue identificado como agencia, respetamos esa señal.
    is_agency_content = bool(author_data["is_agency_content"]) or bool(attribution_data["is_agency_content"])

    source_attribution = str(attribution_data["source_attribution"])
    agency_name = str(attribution_data["agency_name"])

    if is_agency_content and not agency_name:
        agency_name = str(author_data["author_name"])

    visible_views_raw = ""
    views_count = None

    raw = {
        "source": "elmostrador",
        "source_type": "news_site",

        "url": url,
        "canonical_url": canonical_url,
        "article_id": article_id,
        "slug": slug,

        "scraped_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        "published_at_raw": published_at_raw,
        "published_at": published_at,
        "published_date": published_date,
        "published_time": published_time,
        "timezone": TIMEZONE,

        "main_section": main_section,
        "subsection": subsection,
        "breadcrumb_raw": breadcrumb_raw,
        "article_type_editorial": article_type,
        "site_vertical": site_vertical,
        "program_or_series": program_or_series,

        "is_opinion": section_flags["is_opinion"],
        "is_column": section_flags["is_column"],
        "is_letter_to_editor": section_flags["is_letter_to_editor"],
        "is_editorial": section_flags["is_editorial"],
        "is_market_section": section_flags["is_market_section"],
        "is_economy_section": section_flags["is_economy_section"],
        "is_country_section": section_flags["is_country_section"],
        "is_world_section": section_flags["is_world_section"],
        "is_multimedia": section_flags["is_multimedia"],
        "is_regional": section_flags["is_regional"],
        "is_agenda_pais": section_flags["is_agenda_pais"],
        "is_culture": section_flags["is_culture"],
        "is_deportes": section_flags["is_deportes"],
        "region_section": region_section,

        "title": title,
        "subtitle": subtitle_data["subtitle"],
        "lead": subtitle_data["lead"],
        "summary": subtitle_data["summary"],
        "ai_summary": ai_summary,
        "has_ai_summary": has_ai_summary,
        "summary_source": summary_source,

        "title_length_chars": len(title),
        "subtitle_length_chars": subtitle_data["subtitle_length_chars"],
        "summary_length_chars": subtitle_data["summary_length_chars"],

        "author_name": author_data["author_name"],
        "author_url": author_data["author_url"],
        "author_role": author_data["author_role"],
        "author_bio": author_data["author_bio"],
        "author_type": author_data["author_type"],

        "source_attribution": source_attribution,
        "is_staff_writer": author_data["is_staff_writer"],
        "is_newsroom": author_data["is_newsroom"],
        "is_external_columnist": author_data["is_external_columnist"],
        "is_agency_content": is_agency_content,
        "agency_name": agency_name,
        "desk_or_team": "Mesa de noticias" if "mesa de noticias" in str(author_data["author_name"]).lower() else "",

        "body_text_raw": body_data["body_text_raw"],
        "body_text_clean": body_data["body_text_clean"],
        "paragraphs": body_data["paragraphs"],
        "paragraph_count": body_data["paragraph_count"],
        "body_length_chars": body_data["body_length_chars"],
        "body_length_words": body_data["body_length_words"],
        "internal_subheadings": body_data["internal_subheadings"],
        "quote_count": body_data["quote_count"],
        "has_quotes": body_data["has_quotes"],

        "external_links_in_body": body_links_data["external_links_in_body"],
        "internal_links_in_body": body_links_data["internal_links_in_body"],
        "document_links": body_links_data["document_links"],
        "has_document_link": body_links_data["has_document_link"],
        "mentioned_documents_raw": body_links_data["mentioned_documents_raw"],

        "main_image_url": image_data["main_image_url"],
        "main_image_alt": image_data["main_image_alt"],
        "image_caption": image_data["image_caption"],
        "image_credit": image_data["image_credit"],
        "has_image": image_data["has_image"],
        "image_count": image_data["image_count"],

        "has_video": media_data["has_video"],
        "video_url": media_data["video_url"],
        "has_audio": media_data["has_audio"],
        "audio_url": media_data["audio_url"],
        "has_embedded_youtube": media_data["has_embedded_youtube"],
        "has_embedded_spotify": media_data["has_embedded_spotify"],
        "media_type": media_data["media_type"],

        "also_interesting_links": related_data["also_interesting_links"],
        "also_interesting_titles": related_data["also_interesting_titles"],
        "also_interesting_count": related_data["also_interesting_count"],

        "featured_links": related_data["featured_links"],
        "featured_titles": related_data["featured_titles"],
        "featured_count": related_data["featured_count"],

        "same_day_links": related_data["same_day_links"],
        "same_day_titles": related_data["same_day_titles"],
        "same_day_count": related_data["same_day_count"],

        "related_links": related_data["related_links"],
        "related_titles": related_data["related_titles"],
        "related_count": related_data["related_count"],

        "share_facebook_url": share_data["share_facebook_url"],
        "share_x_url": share_data["share_x_url"],
        "share_whatsapp_url": share_data["share_whatsapp_url"],
        "google_news_url": share_data["google_news_url"],
        "whatsapp_channel_url": share_data["whatsapp_channel_url"],
        "youtube_url": share_data["youtube_url"],
        "spotify_url": share_data["spotify_url"],
        "visible_views_raw": visible_views_raw,
        "views_count": views_count,

        "discovery": {
            "discovered_from_dia_page": discovered.discovered_from_dia_page,
            "discovered_from_categoria_dia": discovered.discovered_from_categoria_dia,
            "discovered_from_home": discovered.discovered_from_home,
            "discovered_from_section": discovered.discovered_from_section,
            "listing_position": discovered.listing_position,
            "listing_page_number": discovered.listing_page_number,
            "listing_title": discovered.listing_title,
            "listing_excerpt": discovered.listing_excerpt,
            "listing_author": discovered.listing_author,
            "listing_date_raw": discovered.listing_date_raw,
            "listing_category": discovered.listing_category,
        },
    }

    if not title:
        parse_errors.append("missing_title")

    if not body_data["body_text_clean"]:
        parse_errors.append("missing_body_text")

    if not published_at and not published_at_raw:
        parse_errors.append("missing_published_at")

    if not main_section:
        parse_errors.append("missing_main_section")

    technical = {
        "http_status": http_status,
        "content_type": content_type,
        "downloaded_from_sitemap": discovered.discovered_from_sitemap,
        "downloaded_from_feed": discovered.discovered_from_feed,
        "downloaded_from_dia_page": discovered.discovered_from_dia_page,
        "downloaded_from_categoria_dia": discovered.discovered_from_categoria_dia,
        "html_raw_path": html_raw_path,
        "parser_version": PARSER_VERSION,
        "parse_success": len(parse_errors) == 0,
        "parse_errors": parse_errors,
        "template_noise_detected": detect_template_noise(html),
        "robots_allowed_checked": "not_checked",
        "discovery_sources": discovered.discovery_sources,
    }

    return {
        "raw": raw,
        "technical": technical,
    }


def write_output(
    output_path: Path,
    target: date,
    discovered_count: int,
    articles: list[dict[str, Any]],
) -> None:
    payload = {
        "metadata": {
            "source": "elmostrador",
            "target_date": target.isoformat(),
            "target_date_folder": date_dir_name(target),
            "articles_found": discovered_count,
            "articles_downloaded": len(articles),
            "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
            "parser_version": PARSER_VERSION,
        },
        "articles": articles,
    }

    payload = normalize_payload_texts(payload)

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ask_days_back() -> int:
    while True:
        raw = input(
            "¿Cuántos días quieres descargar hacia atrás, incluyendo la fecha final? "
            "Ejemplo 30 = fecha final + 29 días anteriores: "
        ).strip()

        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass

        print("Ingresa un número entero mayor o igual a 1.")


def build_date_range(end_date: date, days_count: int) -> list[date]:
    return [end_date - timedelta(days=i) for i in range(days_count)]


def get_day_dir(base_dir: Path, target: date) -> Path:
    """Devuelve la carpeta diaria donde se guarda la descarga de una fecha."""
    return base_dir / "mostrador" / date_dir_name(target)


def get_day_output_path(base_dir: Path, target: date) -> Path:
    """Devuelve el archivo principal esperado para una fecha."""
    return get_day_dir(base_dir, target) / "noticias_dia.txt"


def should_skip_existing_day(
    base_dir: Path,
    target: date,
    overwrite_existing: bool = False,
) -> bool:
    """
    Decide si una fecha debe omitirse.

    Regla incremental:
    - Si la carpeta mostrador/DD_MM_YYYY ya existe, se considera ya trabajada.
    - Por defecto no se toca ni se sobrescribe.
    - Si overwrite_existing=True, se fuerza la redescarga.
    """
    if overwrite_existing:
        return False

    return get_day_dir(base_dir, target).exists()


def build_skipped_day_summary(base_dir: Path, target: date) -> dict[str, Any]:
    """
    Construye una entrada de resumen para días omitidos por existir previamente.
    No modifica la carpeta ni sus archivos.
    """
    day_dir = get_day_dir(base_dir, target)
    output_path = get_day_output_path(base_dir, target)
    raw_html_dir = day_dir / "html"

    return {
        "target_date": target.isoformat(),
        "status": "skipped_existing_day",
        "reason": "La carpeta diaria ya existe y overwrite_existing=False.",
        "day_dir": str(day_dir),
        "output_path": str(output_path),
        "output_exists": output_path.exists(),
        "html_dir_exists": raw_html_dir.exists(),
    }


def get_article_url_from_payload(article: dict[str, Any]) -> str:
    """
    Obtiene la URL principal de una noticia ya guardada.

    Soporta la estructura actual:
        {"raw": {"url": "...", "canonical_url": "..."}}

    y también una estructura plana, por si en algún momento el payload cambia.
    """
    if not isinstance(article, dict):
        return ""

    raw = article.get("raw")
    if isinstance(raw, dict):
        return normalize_url(str(raw.get("canonical_url") or raw.get("url") or ""))

    return normalize_url(str(article.get("canonical_url") or article.get("url") or ""))


def load_existing_day_payload(output_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], set[str]]:
    """
    Carga noticias existentes desde noticias_dia.txt, si existe.

    Devuelve:
    - payload completo existente, o {} si no existe/no se puede leer
    - lista de artículos existentes
    - set de URLs existentes normalizadas
    """
    if not output_path.exists():
        return {}, [], set()

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] No se pudo leer archivo existente {output_path}: {exc}")
        return {}, [], set()

    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        print(f"[WARN] Archivo existente sin lista válida de articles: {output_path}")
        return payload, [], set()

    existing_urls: set[str] = set()

    for article in articles:
        url = get_article_url_from_payload(article)
        if url:
            existing_urls.add(url)

    return payload, articles, existing_urls


def deduplicate_articles_by_url(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Elimina duplicados por URL/canonical_url preservando el primer registro encontrado.
    """
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for article in articles:
        url = get_article_url_from_payload(article)

        if not url:
            deduped.append(article)
            continue

        if url in seen:
            continue

        seen.add(url)
        deduped.append(article)

    return deduped


def scrape_single_day(
    session: requests.Session,
    target: date,
    base_dir: Path,
    max_articles: int = 0,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    max_category_pages: int = DEFAULT_MAX_CATEGORY_PAGES,
    preloaded_categoria: dict[str, DiscoveredUrl] | None = None,
    article_workers: int = 8,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    day_dir = get_day_dir(base_dir, target)
    raw_html_dir = day_dir / "html"
    output_path = get_day_output_path(base_dir, target)

    day_dir.mkdir(parents=True, exist_ok=True)
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    existing_payload, existing_articles, existing_urls = load_existing_day_payload(output_path)

    if overwrite_existing:
        print("[INFO] overwrite_existing=True: se ignorará el archivo previo y se redescargarán las noticias detectadas.")
        existing_articles = []
        existing_urls = set()

    print("\n" + "=" * 70)
    print(f"Scraping El Mostrador para fecha: {target.isoformat()}")
    print(f"Carpeta destino: {day_dir}")
    print(f"Archivo salida: {output_path}")
    print("=" * 70)

    discoveries = discover_article_urls(
        session=session,
        target=target,
        max_category_pages=max_category_pages,
        preloaded_categoria=preloaded_categoria,
    )

    urls_detected = list(discoveries.keys())

    if max_articles and max_articles > 0:
        urls_detected = urls_detected[:max_articles]

    urls = [
        url for url in urls_detected
        if normalize_url(url) not in existing_urls
    ]

    print()
    print(f"Total de noticias detectadas para el día: {len(discoveries)}")
    print(f"Noticias existentes en archivo del día: {len(existing_articles)}")
    print(f"URLs existentes únicas: {len(existing_urls)}")
    print(f"Noticias nuevas por descargar: {len(urls)}")

    if max_articles and max_articles > 0:
        print(f"Modo prueba activo: universo limitado a {len(urls_detected)} URLs detectadas.")

    print()

    articles: list[dict[str, Any] | None] = [None] * len(urls)

    def worker(index: int, url: str) -> tuple[int, dict[str, Any]]:
        local_session = create_session()

        article = extract_article(
            session=local_session,
            discovered=discoveries[url],
            raw_html_dir=raw_html_dir,
        )

        return index, article

    def build_parallel_error_article(url: str, exc: Exception) -> dict[str, Any]:
        discovered = discoveries[url]

        return {
            "raw": {
                "source": "elmostrador",
                "source_type": "news_site",
                "url": url,
                "canonical_url": "",
                "article_id": "",
                "slug": get_slug(url),
            },
            "technical": {
                "http_status": None,
                "content_type": "",
                "downloaded_from_sitemap": discovered.discovered_from_sitemap,
                "downloaded_from_feed": discovered.discovered_from_feed,
                "downloaded_from_dia_page": discovered.discovered_from_dia_page,
                "downloaded_from_categoria_dia": discovered.discovered_from_categoria_dia,
                "html_raw_path": "",
                "parser_version": PARSER_VERSION,
                "parse_success": False,
                "parse_errors": [f"parallel_worker_error: {exc}"],
                "template_noise_detected": False,
                "robots_allowed_checked": "not_checked",
                "discovery_sources": discovered.discovery_sources,
            },
        }

    if article_workers <= 1:
        for index, url in enumerate(urls):
            print(f"[{index + 1}/{len(urls)}] Descargando: {url}")

            try:
                _, article = worker(index, url)
                articles[index] = article
            except Exception as exc:
                print(f"[{index + 1}/{len(urls)}] ERROR: {url} | {exc}")
                articles[index] = build_parallel_error_article(url, exc)

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    else:
        print(f"Descargando noticias en paralelo con {article_workers} workers...")

        with ThreadPoolExecutor(max_workers=article_workers) as executor:
            futures = {
                executor.submit(worker, index, url): (index, url)
                for index, url in enumerate(urls)
            }

            for completed, future in enumerate(as_completed(futures), start=1):
                index, url = futures[future]

                try:
                    result_index, article = future.result()
                    articles[result_index] = article
                    print(f"[{completed}/{len(urls)}] OK: {url}")

                except Exception as exc:
                    print(f"[{completed}/{len(urls)}] ERROR: {url} | {exc}")
                    articles[index] = build_parallel_error_article(url, exc)

    new_articles = [article for article in articles if article is not None]
    combined_articles = deduplicate_articles_by_url(existing_articles + new_articles)

    if new_articles or overwrite_existing or not output_path.exists():
        write_output(
            output_path=output_path,
            target=target,
            discovered_count=len(discoveries),
            articles=combined_articles,
        )
        output_written = True
    else:
        output_written = False

    successful_total = sum(
        1 for a in combined_articles
        if a.get("technical", {}).get("parse_success")
    )
    failed_total = len(combined_articles) - successful_total

    successful_new = sum(
        1 for a in new_articles
        if a.get("technical", {}).get("parse_success")
    )
    failed_new = len(new_articles) - successful_new

    print()
    print("Resumen del día:")
    print(f"  Noticias detectadas: {len(discoveries)}")
    print(f"  Noticias existentes antes de ejecutar: {len(existing_articles)}")
    print(f"  Noticias nuevas descargadas: {len(new_articles)}")
    print(f"  Noticias totales guardadas sin duplicados: {len(combined_articles)}")
    print(f"  Nuevas parseadas sin observaciones: {successful_new}")
    print(f"  Nuevas con observaciones o errores: {failed_new}")
    print(f"  Total parseadas sin observaciones: {successful_total}")
    print(f"  Total con observaciones o errores: {failed_total}")
    print(f"  Archivo guardado en: {output_path}")
    print(f"  Archivo actualizado: {output_written}")

    return {
        "target_date": target.isoformat(),
        "articles_found": len(discoveries),
        "articles_existing_before": len(existing_articles),
        "articles_new_downloaded": len(new_articles),
        "articles_total_after_merge": len(combined_articles),
        "parse_success_new": successful_new,
        "parse_failed_new": failed_new,
        "parse_success_total": successful_total,
        "parse_failed_total": failed_total,
        "output_path": str(output_path),
        "output_written": output_written,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga/actualiza noticias de El Mostrador por rango de días, agregando solo URLs nuevas si el archivo diario ya existe."
    )

    parser.add_argument(
        "--date",
        default=None,
        help=(
            "Fecha final del rango. Formatos aceptados: DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD. "
            "Si se omite, usa hoy en Chile."
        ),
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help=(
            "Cantidad de días totales a descargar hacia atrás, incluyendo la fecha final. "
            "Ejemplo: 30 = fecha final + 29 días anteriores. Si se omite, se pregunta por consola."
        ),
    )

    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directorio base del proyecto. Por defecto, carpeta actual.",
    )

    parser.add_argument(
        "--max-articles",
        type=int,
        default=0,
        help="Límite de noticias por día para prueba. 0 = sin límite.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Pausa en segundos entre descargas.",
    )

    parser.add_argument(
        "--max-category-pages",
        type=int,
        default=DEFAULT_MAX_CATEGORY_PAGES,
        help=(
            "Número máximo de páginas a revisar en /categoria/dia/page/N/. "
            "Para 30 días puede requerir subir este valor si el sitio publicó mucho."
        ),
    )

    parser.add_argument(
        "--article-workers",
        type=int,
        default=8,
        help="Número de noticias a descargar en paralelo por día. Usa 1 para modo secuencial.",
    )

    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help=(
            "Si se indica, ignora el noticias_dia.txt existente y redescarga todas las URLs detectadas. "
            "Por defecto, si el archivo existe, conserva sus noticias y agrega solo URLs nuevas."
        ),
    )

    args = parser.parse_args()

    end_date = parse_target_date(args.date)
    days_count = args.days_back if args.days_back is not None else ask_days_back()

    if days_count < 1:
        raise ValueError("--days-back debe ser mayor o igual a 1.")

    targets = build_date_range(end_date, days_count)
    base_dir = Path(args.base_dir).resolve()
    session = create_session()

    print("=== Scraper El Mostrador por rango de días ===")
    print(f"Fecha final: {end_date.isoformat()}")
    print(f"Días totales a descargar: {days_count}")
    print(f"Primera fecha a procesar: {targets[0].isoformat()}")
    print(f"Última fecha a procesar: {targets[-1].isoformat()}")
    print(f"Directorio base: {base_dir}")
    print(f"Sobrescribir archivo diario existente: {args.overwrite_existing}")

    existing_file_targets = [
        target for target in targets
        if get_day_output_path(base_dir, target).exists()
    ]

    print(f"Días con noticias_dia.txt existente: {len(existing_file_targets)}")
    print("Modo incremental por URL: no se omiten carpetas existentes; se agregan solo noticias nuevas.")

    global_summary: list[dict[str, Any]] = []

    if targets:
        print()
        print(
            "Precargando /categoria/dia/ para el rango completo "
            f"({len(targets)} días a revisar)..."
        )
        preloaded_categoria_by_date = discover_from_categoria_dia_range(
            session=session,
            targets=targets,
            max_pages=args.max_category_pages,
        )
    else:
        preloaded_categoria_by_date = {}

    for target in targets:
        try:
            preloaded_categoria = preloaded_categoria_by_date.get(target, {})

            summary = scrape_single_day(
                session=session,
                target=target,
                base_dir=base_dir,
                max_articles=args.max_articles,
                sleep_seconds=args.sleep,
                max_category_pages=args.max_category_pages,
                preloaded_categoria=preloaded_categoria,
                article_workers=args.article_workers,
                overwrite_existing=args.overwrite_existing,
            )

            if summary.get("articles_new_downloaded", 0) > 0:
                summary["status"] = "updated_with_new_articles"
            elif summary.get("output_written"):
                summary["status"] = "written_without_new_articles"
            else:
                summary["status"] = "no_new_articles"

            global_summary.append(summary)

        except Exception as exc:
            print(f"[ERROR] Falló la descarga del día {target.isoformat()}: {exc}")
            global_summary.append(
                {
                    "target_date": target.isoformat(),
                    "status": "error",
                    "error": str(exc),
                }
            )

    summary_dir = base_dir / "mostrador"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"resumen_descarga_{date_dir_name(end_date)}_{days_count}_dias.txt"
    summary_path.write_text(
        json.dumps(global_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    updated_days = sum(1 for item in global_summary if item.get("status") == "updated_with_new_articles")
    no_new_days = sum(1 for item in global_summary if item.get("status") == "no_new_articles")
    written_days = sum(1 for item in global_summary if item.get("status") == "written_without_new_articles")
    error_days = sum(1 for item in global_summary if item.get("status") == "error")
    total_new_articles = sum(int(item.get("articles_new_downloaded", 0)) for item in global_summary)
    total_after_merge = sum(int(item.get("articles_total_after_merge", 0)) for item in global_summary)

    print("\n" + "=" * 70)
    print("PROCESO GENERAL TERMINADO")
    print(f"Días en rango: {len(global_summary)}")
    print(f"Días actualizados con noticias nuevas: {updated_days}")
    print(f"Días sin noticias nuevas: {no_new_days}")
    print(f"Días escritos sin noticias nuevas: {written_days}")
    print(f"Días con error: {error_days}")
    print(f"Noticias nuevas descargadas en total: {total_new_articles}")
    print(f"Noticias totales acumuladas en archivos procesados: {total_after_merge}")
    print(f"Resumen general guardado en: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
