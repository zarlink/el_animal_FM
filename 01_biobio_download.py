from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from zoneinfo import ZoneInfo


BASE_URL = "https://www.biobiochile.cl"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap.xml"
LO_ULTIMO_URL = f"{BASE_URL}/lo-ultimo.shtml"
CATEGORY_ARCHIVE_SEED_URL = f"{BASE_URL}/lista/categorias/nacional"

PARSER_VERSION = "biobio_raw_v3_category_archives"
TIMEZONE = "America/Santiago"

REQUEST_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_MAX_CATEGORY_PAGES = 30

PRIMARY_RE = re.compile(r"primary:\s+([a-z0-9-]+)\s+([a-z0-9-]+)", re.I)

BIOBIO_AI_BOILERPLATE_PATTERNS = [
    r"\bver resumen\b",
    r"\bresumen generado con una herramienta de inteligencia artificial desarrollada por biobiochile y revisado por el autor de este artículo\.?",
    r"\bresumen generado con una herramienta de inteligencia artificial\.?",
    r"\bherramienta de inteligencia artificial desarrollada por biobiochile\.?",
    r"\bdesarrollada por biobiochile y revisado por el autor de este artículo\.?",
    r"\bdesarrollada por biobiochile\.?",
    r"\brevisado por el autor de este artículo\.?",
]

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


@dataclass
class DiscoveredUrl:
    url: str
    discovered_from_sitemap: bool = False
    discovered_from_feed: bool = False
    discovery_sources: list[str] | None = None


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

    El problema observado era mojibake del tipo "caÃ­da" en vez de "caída",
    típico de bytes UTF-8 interpretados como Latin-1/Windows-1252.
    BioBioChile publica normalmente en UTF-8, por eso preferimos UTF-8
    y dejamos fallback solo si falla.
    """
    try:
        return response.content.decode("utf-8", errors="replace")
    except Exception:
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        return response.text


def repair_mojibake(value: str) -> str:
    """Corrige textos ya dañados tipo 'dÃ©ficit' -> 'déficit' cuando sea posible."""
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


def remove_biobio_ai_boilerplate(value: str) -> str:
    """
    Elimina el disclaimer repetido del resumen IA de BioBioChile,
    sin eliminar necesariamente el contenido útil del resumen.
    """
    if not isinstance(value, str) or not value:
        return value or ""

    text = value

    for pattern in BIOBIO_AI_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_text(value: Any) -> str:
    """Normaliza HTML entities, espacios, mojibake y boilerplate IA en todos los textos extraídos."""
    if value is None:
        return ""

    text = str(value)
    text = html_lib.unescape(text)
    text = repair_mojibake(text)
    text = remove_biobio_ai_boilerplate(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_payload_texts(value: Any) -> Any:
    """Aplica normalización recursiva antes de guardar el JSON final."""
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

    # Opcional, pero recomendable:
    # privilegia noticias escritas reales.
    if "/noticias/" not in path:
        return False

    return True


def url_matches_date(url: str, target: date) -> bool:
    date_fragment = target.strftime("/%Y/%m/%d/")
    return date_fragment in url


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


def merge_discoveries(*groups: dict[str, DiscoveredUrl]) -> dict[str, DiscoveredUrl]:
    merged: dict[str, DiscoveredUrl] = {}

    for group in groups:
        for url, item in group.items():
            if url not in merged:
                merged[url] = item
                if merged[url].discovery_sources is None:
                    merged[url].discovery_sources = []
            else:
                merged[url].discovered_from_sitemap = (
                    merged[url].discovered_from_sitemap or item.discovered_from_sitemap
                )
                merged[url].discovered_from_feed = (
                    merged[url].discovered_from_feed or item.discovered_from_feed
                )

            for source in item.discovery_sources or []:
                if source not in merged[url].discovery_sources:
                    merged[url].discovery_sources.append(source)

    return merged


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


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


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

        if {"newsarticle", "article", "reportagearticle"} & types:
            return item

    return {}


def clean_text(value: str) -> str:
    return normalize_text(value)


def remove_template_noise(value: str) -> str:
    value = re.sub(r"\{\{.*?\}\}", "", value or "")
    return normalize_text(value)


def text_or_empty(tag) -> str:
    if not tag:
        return ""
    return clean_text(tag.get_text(" ", strip=True))


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


def parse_datetime_value(value: str) -> tuple[str, str, str, str]:
    raw = clean_text(value)

    if not raw:
        return "", "", "", ""

    try:
        parsed = date_parser.parse(raw, fuzzy=True)
        if not parsed.tzinfo:
            parsed = parsed.replace(tzinfo=ZoneInfo(TIMEZONE))
        iso = parsed.isoformat()
        return iso, parsed.date().isoformat(), parsed.time().replace(microsecond=0).isoformat(), raw
    except Exception:
        return "", "", "", raw


def get_published_data(soup: BeautifulSoup, article_ld: dict[str, Any]) -> tuple[str, str, str, str]:
    candidates = [
        str(article_ld.get("datePublished", "")),
        get_meta(soup, "article:published_time"),
        get_meta(soup, "date"),
        get_meta(soup, "pubdate"),
    ]

    visible_text = soup.get_text(" ", strip=True)
    match = re.search(
        r"(Lunes|Martes|Miércoles|Miercoles|Jueves|Viernes|Sábado|Sabado|Domingo)"
        r"\s+\d{1,2}\s+[a-záéíóúñ]+\s+de\s+\d{4}\s*\|\s*\d{1,2}:\d{2}",
        visible_text,
        flags=re.IGNORECASE,
    )
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        candidate = clean_text(candidate)
        if candidate:
            published_at, published_date, published_time, raw = parse_datetime_value(candidate)
            if raw:
                return published_at, published_date, published_time, raw

    return "", "", "", ""


def get_slug(url: str) -> str:
    path = urlparse(url).path
    name = path.rstrip("/").split("/")[-1]
    return name.replace(".shtml", "")


def get_article_id(soup: BeautifulSoup, url: str) -> str:
    candidates = []

    for meta_name in ["article:id", "post_id", "id"]:
        candidates.append(get_meta(soup, meta_name))

    html = str(soup)
    match = re.search(r"post[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)", html, flags=re.IGNORECASE)
    if match:
        candidates.append(match.group(1))

    for candidate in candidates:
        candidate = clean_text(candidate)
        if candidate:
            return candidate

    return ""


def infer_sections_from_url(url: str) -> tuple[str, str, str]:
    path_parts = [p for p in urlparse(url).path.split("/") if p]

    main_section = ""
    subsection = ""
    region_section = ""

    if "noticias" in path_parts:
        idx = path_parts.index("noticias")
        after = path_parts[idx + 1 :]

        category_parts = []
        for part in after:
            if re.fullmatch(r"\d{4}", part):
                break
            category_parts.append(part)

        if category_parts:
            main_section = category_parts[0].replace("-", " ").title()
        if len(category_parts) >= 2:
            subsection = category_parts[1].replace("-", " ").title()

        region_candidates = {
            "zona-norte",
            "region-de-valparaiso",
            "region-metropolitana",
            "region-del-bio-bio",
            "region-de-la-araucania",
            "region-de-los-rios",
            "region-de-los-lagos",
            "aysen-y-magallanes",
            "ohiggins-maule-nuble",
        }

        for part in category_parts:
            if part in region_candidates or part.startswith("region-"):
                region_section = part.replace("-", " ").title()

    return main_section, subsection, region_section


def get_breadcrumb_raw(soup: BeautifulSoup) -> str:
    candidates = []

    for selector in [
        ".breadcrumb",
        ".breadcrumbs",
        "nav[aria-label='breadcrumb']",
        "[class*='breadcrumb']",
    ]:
        for tag in soup.select(selector):
            text = remove_template_noise(text_or_empty(tag))
            if text:
                candidates.append(text)

    if candidates:
        return candidates[0]

    return ""


def infer_article_type(url: str, breadcrumb_raw: str, body_text: str) -> str:
    all_text = f"{url} {breadcrumb_raw} {body_text[:500]}".lower()

    if "opinion" in all_text or "columna de opinión" in all_text or "columnas-bbcl" in all_text:
        return "opinion"

    if "agencia de noticias" in all_text or "agencia efe" in all_text:
        return "agencia"

    if "reportajes" in all_text or "bbcl investiga" in all_text:
        return "reportaje"

    if "entrevistas" in all_text:
        return "entrevista"

    return "noticia"


def bool_sections(main_section: str, url: str, article_type: str) -> dict[str, bool]:
    value = f"{main_section} {url} {article_type}".lower()

    return {
        "is_opinion": "opinion" in value,
        "is_investigation": "bbcl-investiga" in value or "bbcl investiga" in value or "reportaje" in value,
        "is_economy_section": "econom" in value,
        "is_national_section": "nacional" in value,
        "is_international_section": "internacional" in value,
    }


def get_author_info(soup: BeautifulSoup, article_ld: dict[str, Any]) -> tuple[str, str, str, str]:
    author_name = ""
    author_url = ""
    author_role = ""
    author_image_url = ""

    author = article_ld.get("author")

    if isinstance(author, dict):
        author_name = clean_text(str(author.get("name", "")))
        author_url = clean_text(str(author.get("url", "")))
    elif isinstance(author, list) and author:
        first_author = author[0]
        if isinstance(first_author, dict):
            author_name = clean_text(str(first_author.get("name", "")))
            author_url = clean_text(str(first_author.get("url", "")))
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
        "a[href*='/lista/autores/']",
    ]

    for selector in possible_author_selectors:
        tag = soup.select_one(selector)
        if tag:
            text = remove_template_noise(text_or_empty(tag))
            if text and len(text) <= 120 and not author_name:
                author_name = text

            if tag.name == "a" and tag.get("href") and not author_url:
                author_url = urljoin(BASE_URL, tag["href"])

            img = tag.find("img")
            if img and img.get("src") and not author_image_url:
                author_image_url = urljoin(BASE_URL, img["src"])

            break

    visible_text = soup.get_text("\n", strip=True)
    role_candidates = []
    for line in visible_text.splitlines():
        line_clean = clean_text(line)
        lower = line_clean.lower()

        if any(token in lower for token in ["periodista", "editor", "editora", "columnista", "agencia"]):
            if len(line_clean) <= 120:
                role_candidates.append(line_clean)

    if role_candidates:
        author_role = role_candidates[0]

    return author_name, author_url, author_role, author_image_url


def find_article_container(soup: BeautifulSoup):
    for selector in [
        "article",
        "main article",
        "main",
        "[class*='article']",
        "[class*='post']",
        "[class*='nota']",
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
        "selecciona tu región",
        "descarga la app",
        "documentos perdidos",
        "whatsapp radio bío bío",
        "contenidos bajo licencia",
        "cerrar anuncio",
        "cargar más noticias",
        "síguenos",
        "newsletter",
        "lorem ipsum",

        # Boilerplate IA BioBioChile
        "ver resumen",
        "resumen generado con una herramienta de inteligencia artificial",
        "herramienta de inteligencia artificial desarrollada por biobiochile",
        "desarrollada por biobiochile",
        "revisado por el autor de este artículo",

        "{{",
        "}}",
    ]

    return any(fragment in lower for fragment in bad_fragments)


def extract_body(container, article_ld: dict[str, Any] | None = None) -> tuple[str, str, list[str], int, int, list[str], int]:
    container_copy = BeautifulSoup(str(container), "lxml")
    remove_unwanted_tags(container_copy)

    paragraphs: list[str] = []

    for p in container_copy.find_all("p"):
        text = remove_template_noise(text_or_empty(p))

        if not text:
            continue

        if len(text) < 25:
            continue

        if is_boilerplate_paragraph(text):
            continue

        if text not in paragraphs:
            paragraphs.append(text)

    if not paragraphs and article_ld:
        article_body = article_ld.get("articleBody") or article_ld.get("text")
        if isinstance(article_body, str) and len(article_body.strip()) >= 25:
            paragraphs = [
                clean_text(line)
                for line in re.split(r"\n+", article_body)
                if len(clean_text(line)) >= 25 and not is_boilerplate_paragraph(clean_text(line))
            ]

    if not paragraphs:
        fallback_text = remove_template_noise(container_copy.get_text("\n", strip=True))
        fallback_lines = [
            clean_text(line)
            for line in fallback_text.splitlines()
            if len(clean_text(line)) >= 25 and not is_boilerplate_paragraph(clean_text(line))
        ]
        paragraphs = list(dict.fromkeys(fallback_lines))

    body_text_raw = "\n".join(paragraphs)
    body_text_clean = clean_text(" ".join(paragraphs))
    paragraph_count = len(paragraphs)
    body_length_chars = len(body_text_clean)
    body_length_words = len(body_text_clean.split())

    internal_subheadings = []
    for heading in container_copy.find_all(["h2", "h3"]):
        text = remove_template_noise(text_or_empty(heading))
        if text and len(text) < 180 and text not in internal_subheadings:
            internal_subheadings.append(text)

    quote_count = body_text_clean.count("“") + body_text_clean.count('"') // 2

    return (
        body_text_raw,
        body_text_clean,
        paragraphs,
        paragraph_count,
        body_length_chars,
        internal_subheadings,
        quote_count,
    )


def get_subtitle_and_lead(soup: BeautifulSoup, article_ld: dict[str, Any], paragraphs: list[str]) -> tuple[str, str]:
    description = ""

    if article_ld.get("description"):
        description = clean_text(str(article_ld["description"]))

    if not description:
        description = get_meta(soup, "description") or get_meta(soup, "og:description")

    subtitle = description
    lead = paragraphs[0] if paragraphs else ""

    return subtitle, lead


def extract_ai_summary(soup: BeautifulSoup) -> tuple[str, bool, str]:
    possible_texts = []

    for tag in soup.find_all(True):
        class_value = " ".join(tag.get("class", [])) if tag.get("class") else ""
        id_value = tag.get("id", "")

        combined = f"{class_value} {id_value}".lower()

        if "resumen" in combined or "summary" in combined:
            text = remove_template_noise(text_or_empty(tag))
            if text and len(text) > 40 and not is_boilerplate_paragraph(text):
                possible_texts.append(text)

    visible_text = soup.get_text("\n", strip=True)

    marker = "Resumen generado con una herramienta de Inteligencia Artificial"
    if marker.lower() in visible_text.lower():
        lines = [clean_text(x) for x in visible_text.splitlines() if clean_text(x)]
        for idx, line in enumerate(lines):
            if marker.lower() in line.lower():
                nearby = " ".join(lines[max(0, idx - 4) : idx])
                nearby = remove_template_noise(nearby)
                if len(nearby) > 40 and not is_boilerplate_paragraph(nearby):
                    possible_texts.append(nearby)

    if possible_texts:
        cleaned_summary = remove_biobio_ai_boilerplate(possible_texts[0])
        cleaned_summary = normalize_text(cleaned_summary)

        if cleaned_summary:
            return cleaned_summary, True, "bio_bio_ai_reviewed_by_author"

    return "", False, ""


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
        main_image_url = urljoin(BASE_URL, imgs[0].get("src", ""))

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

        if any(token in lower for token in ["imagen:", "foto:", "agencia", "cedida", "contexto"]):
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

    iframe = scope.find("iframe")
    video = scope.find("video")
    audio = scope.find("audio")

    video_url = ""

    if iframe and iframe.get("src"):
        video_url = urljoin(BASE_URL, iframe["src"])
    elif video and video.get("src"):
        video_url = urljoin(BASE_URL, video["src"])

    has_video = bool(video_url or video)
    has_audio = bool(audio)

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
        "media_type": media_type,
    }


def extract_related_links(soup: BeautifulSoup, container, current_url: str) -> dict[str, Any]:
    scope = container or soup

    read_also_links: list[str] = []
    read_also_titles: list[str] = []
    read_also_dates: list[str] = []

    related_links: list[str] = []
    related_titles: list[str] = []

    for anchor in scope.find_all("a", href=True):
        href = normalize_url(urljoin(BASE_URL, anchor["href"]))
        title = remove_template_noise(text_or_empty(anchor))

        if not is_biobio_article_url(href):
            continue

        if href == current_url:
            continue

        parent_text = ""
        parent = anchor.parent
        if parent:
            parent_text = remove_template_noise(parent.get_text(" ", strip=True)).lower()

        if "lee también" in parent_text or "lee tambien" in parent_text:
            if href not in read_also_links:
                read_also_links.append(href)
                read_also_titles.append(title)
                read_also_dates.append("")
        else:
            if href not in related_links:
                related_links.append(href)
                related_titles.append(title)

    return {
        "read_also_links": read_also_links,
        "read_also_titles": read_also_titles,
        "read_also_dates": read_also_dates,
        "related_links": related_links,
        "related_titles": related_titles,
        "related_count": len(related_links),
    }


def extract_share_links(soup: BeautifulSoup) -> dict[str, str]:
    facebook = ""
    x_url = ""
    whatsapp = ""

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]

        if not facebook and ("facebook.com/sharer" in href or "facebook.com/share" in href):
            facebook = href

        if not x_url and ("twitter.com/intent" in href or "x.com/intent" in href):
            x_url = href

        if not whatsapp and ("whatsapp://" in href or "wa.me" in href or "api.whatsapp.com" in href):
            whatsapp = href

    return {
        "share_facebook_url": facebook,
        "share_x_url": x_url,
        "share_whatsapp_url": whatsapp,
    }


def infer_source_attribution(body_text: str, article_type: str) -> tuple[str, bool, bool, bool]:
    lower = body_text.lower()

    source_attribution = ""
    is_agency_content = False

    agency_markers = [
        "agencia efe",
        "agencia uno",
        "reuters",
        "france presse",
        "afp",
        "europa press",
        "radio france internationale",
        "rfi",
    ]

    for marker in agency_markers:
        if marker in lower:
            source_attribution = marker
            is_agency_content = True
            break

    is_external_columnist = article_type == "opinion"
    is_staff_writer = not is_agency_content and not is_external_columnist

    return source_attribution, is_agency_content, is_staff_writer, is_external_columnist


def detect_template_noise(html: str) -> bool:
    return "{{" in html or "}}" in html


def save_raw_html(raw_html_dir: Path, url: str, html: str) -> str:
    slug = get_slug(url) or "article"
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:120]
    path = raw_html_dir / f"{safe_slug}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


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
        return {
            "raw": {
                "source": "biobiochile",
                "source_type": "news_site",
                "url": url,
            },
            "technical": {
                "http_status": http_status,
                "content_type": content_type,
                "downloaded_from_sitemap": discovered.discovered_from_sitemap,
                "downloaded_from_feed": discovered.discovered_from_feed,
                "html_raw_path": "",
                "parser_version": PARSER_VERSION,
                "parse_success": False,
                "parse_errors": [f"download_error: {exc}"],
                "template_noise_detected": False,
                "robots_allowed_checked": "not_checked",
                "discovery_sources": discovered.discovery_sources or [],
            },
        }

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

    main_section_url, subsection_url, region_section = infer_sections_from_url(url)

    main_section = clean_text(
        str(article_ld.get("articleSection", ""))
    ) or main_section_url

    subsection = subsection_url
    breadcrumb_raw = get_breadcrumb_raw(soup)

    container = find_article_container(soup)

    (
        body_text_raw,
        body_text_clean,
        paragraphs,
        paragraph_count,
        body_length_chars,
        internal_subheadings,
        quote_count,
    ) = extract_body(container, article_ld=article_ld)

    body_length_words = len(body_text_clean.split())

    title = get_title(soup, article_ld)
    subtitle, lead = get_subtitle_and_lead(soup, article_ld, paragraphs)

    ai_summary, has_ai_summary, summary_source = extract_ai_summary(soup)

    article_type = infer_article_type(url, breadcrumb_raw, body_text_clean)

    section_flags = bool_sections(main_section, url, article_type)

    author_name, author_url, author_role, author_image_url = get_author_info(soup, article_ld)

    (
        source_attribution,
        is_agency_content,
        is_staff_writer,
        is_external_columnist,
    ) = infer_source_attribution(body_text_clean, article_type)

    image_data = get_image_data(soup, article_ld, container)
    media_data = extract_video_audio_data(soup, container)
    related_data = extract_related_links(soup, container, canonical_url)
    share_data = extract_share_links(soup)

    visible_views_raw = ""
    views_count = None

    raw = {
        "source": "biobiochile",
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
        "is_opinion": section_flags["is_opinion"],
        "is_investigation": section_flags["is_investigation"],
        "is_economy_section": section_flags["is_economy_section"],
        "is_national_section": section_flags["is_national_section"],
        "is_international_section": section_flags["is_international_section"],
        "region_section": region_section,

        "title": title,
        "subtitle": subtitle,
        "lead": lead,
        "ai_summary": ai_summary,
        "has_ai_summary": has_ai_summary,
        "summary_source": summary_source,

        "author_name": author_name,
        "author_url": author_url,
        "author_role": author_role,
        "author_image_url": author_image_url,
        "source_attribution": source_attribution,
        "is_agency_content": is_agency_content,
        "is_staff_writer": is_staff_writer,
        "is_external_columnist": is_external_columnist,

        "body_text_raw": body_text_raw,
        "body_text_clean": body_text_clean,
        "paragraphs": paragraphs,
        "paragraph_count": paragraph_count,
        "body_length_chars": body_length_chars,
        "body_length_words": body_length_words,
        "internal_subheadings": internal_subheadings,
        "quote_count": quote_count,

        "main_image_url": image_data["main_image_url"],
        "main_image_alt": image_data["main_image_alt"],
        "image_caption": image_data["image_caption"],
        "image_credit": image_data["image_credit"],
        "has_image": image_data["has_image"],
        "image_count": image_data["image_count"],
        "has_video": media_data["has_video"],
        "video_url": media_data["video_url"],
        "has_audio": media_data["has_audio"],
        "media_type": media_data["media_type"],

        "read_also_links": related_data["read_also_links"],
        "read_also_titles": related_data["read_also_titles"],
        "read_also_dates": related_data["read_also_dates"],
        "related_links": related_data["related_links"],
        "related_titles": related_data["related_titles"],
        "related_count": related_data["related_count"],

        "share_facebook_url": share_data["share_facebook_url"],
        "share_x_url": share_data["share_x_url"],
        "share_whatsapp_url": share_data["share_whatsapp_url"],
        "visible_views_raw": visible_views_raw,
        "views_count": views_count,
    }

    if not title:
        parse_errors.append("missing_title")

    if not body_text_clean:
        parse_errors.append("missing_body_text")

    if not published_at and not published_at_raw:
        parse_errors.append("missing_published_at")

    technical = {
        "http_status": http_status,
        "content_type": content_type,
        "downloaded_from_sitemap": discovered.discovered_from_sitemap,
        "downloaded_from_feed": discovered.discovered_from_feed,
        "html_raw_path": html_raw_path,
        "parser_version": PARSER_VERSION,
        "parse_success": len(parse_errors) == 0,
        "parse_errors": parse_errors,
        "template_noise_detected": detect_template_noise(html),
        "robots_allowed_checked": "not_checked",
        "discovery_sources": discovered.discovery_sources or [],
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
            "source": "biobiochile",
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
    """
    Pregunta por consola cuántos días descargar.
    Regla: 1 = solo hoy; 14 = hoy + 13 días anteriores.
    """
    while True:
        raw = input(
            "¿Cuántos días quieres descargar hacia atrás, incluyendo hoy? "
            "Ejemplo 14 = hoy + 13 días anteriores: "
        ).strip()
        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass
        print("Ingresa un número entero mayor o igual a 1.")


def build_date_range(end_date: date, days_count: int) -> list[date]:
    """Devuelve fechas desde end_date hacia atrás. 14 => 14 fechas totales."""
    return [end_date - timedelta(days=i) for i in range(days_count)]


def get_day_dir(base_dir: Path, target: date) -> Path:
    """Devuelve la carpeta diaria donde se guarda la descarga de una fecha."""
    return base_dir / "biobio" / date_dir_name(target)


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
    - Si la carpeta biobio/DD_MM_YYYY ya existe, se considera ya trabajada.
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


def scrape_single_day(
    session: requests.Session,
    target: date,
    base_dir: Path,
    max_articles: int = 0,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    max_category_pages: int = DEFAULT_MAX_CATEGORY_PAGES,
    article_workers: int = 8
) -> dict[str, Any]:
    day_dir = base_dir / "biobio" / date_dir_name(target)
    raw_html_dir = day_dir / "html"
    output_path = day_dir / "noticias_dia.txt"

    day_dir.mkdir(parents=True, exist_ok=True)
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(f"Scraping BioBioChile para fecha: {target.isoformat()}")
    print(f"Carpeta destino: {day_dir}")
    print(f"Archivo salida: {output_path}")
    print("=" * 70)

    discoveries = discover_article_urls(
        session=session,
        target=target,
        max_category_pages=max_category_pages,
    )
    urls = list(discoveries.keys())

    if max_articles and max_articles > 0:
        urls = urls[:max_articles]

    print()
    print(f"Total de noticias detectadas para el día: {len(discoveries)}")
    if max_articles and max_articles > 0:
        print(f"Modo prueba: se descargarán solo {len(urls)} noticias.")
    else:
        print(f"Se descargarán {len(urls)} noticias.")
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
                "source": "biobiochile",
                "source_type": "news_site",
                "url": url,
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

    articles = [article for article in articles if article is not None]

    write_output(
        output_path=output_path,
        target=target,
        discovered_count=len(discoveries),
        articles=articles,
    )

    successful = sum(1 for a in articles if a.get("technical", {}).get("parse_success"))
    failed = len(articles) - successful

    print()
    print("Resumen del día:")
    print(f"  Noticias detectadas: {len(discoveries)}")
    print(f"  Noticias descargadas: {len(articles)}")
    print(f"  Parseadas sin observaciones: {successful}")
    print(f"  Con observaciones o errores: {failed}")
    print(f"  Archivo guardado en: {output_path}")

    return {
        "target_date": target.isoformat(),
        "articles_found": len(discoveries),
        "articles_downloaded": len(articles),
        "parse_success": successful,
        "parse_failed": failed,
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga noticias de BioBioChile desde hoy hacia atrás y guarda datos raw + technical."
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
            "Ejemplo: 14 = fecha final + 13 días anteriores. Si se omite, se pregunta por consola."
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
            "Número máximo de páginas API a revisar por categoría. "
            "Sube este valor si necesitas más de 30 días o categorías con mucho volumen."
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
            "Si se indica, vuelve a descargar días cuya carpeta ya existe. "
            "Por defecto, las carpetas existentes se omiten y se dejan intactas."
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

    print("=== Scraper BioBioChile por rango de días ===")
    print(f"Fecha final: {end_date.isoformat()}")
    print(f"Días totales a descargar: {days_count}")
    print(f"Primera fecha a procesar: {targets[0].isoformat()}")
    print(f"Última fecha a procesar: {targets[-1].isoformat()}")
    print(f"Directorio base: {base_dir}")
    print(f"Sobrescribir carpetas existentes: {args.overwrite_existing}")

    existing_targets = [
        target for target in targets
        if get_day_dir(base_dir, target).exists()
    ]
    pending_targets = [
        target for target in targets
        if not get_day_dir(base_dir, target).exists() or args.overwrite_existing
    ]

    print(f"Días ya existentes: {len(existing_targets)}")
    print(f"Días pendientes de descarga: {len(pending_targets)}")

    global_summary: list[dict[str, Any]] = []

    for target in targets:
        if should_skip_existing_day(
            base_dir=base_dir,
            target=target,
            overwrite_existing=args.overwrite_existing,
        ):
            skipped_summary = build_skipped_day_summary(base_dir, target)
            print(
                f"[SKIP] {target.isoformat()} | "
                f"carpeta existente: {skipped_summary['day_dir']}"
            )
            global_summary.append(skipped_summary)
            continue

        try:
            summary = scrape_single_day(
                session=session,
                target=target,
                base_dir=base_dir,
                max_articles=args.max_articles,
                sleep_seconds=args.sleep,
                max_category_pages=args.max_category_pages,
                article_workers=args.article_workers
            )
            summary["status"] = "downloaded"
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

    summary_dir = base_dir / "biobio"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"resumen_descarga_{date_dir_name(end_date)}_{days_count}_dias.txt"
    summary_path.write_text(
        json.dumps(normalize_payload_texts(global_summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    downloaded_days = sum(1 for item in global_summary if item.get("status") == "downloaded")
    skipped_days = sum(1 for item in global_summary if item.get("status") == "skipped_existing_day")
    error_days = sum(1 for item in global_summary if item.get("status") == "error")

    print("\n" + "=" * 70)
    print("PROCESO GENERAL TERMINADO")
    print(f"Días en rango: {len(global_summary)}")
    print(f"Días descargados: {downloaded_days}")
    print(f"Días omitidos por existir: {skipped_days}")
    print(f"Días con error: {error_days}")
    print(f"Resumen general guardado en: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
