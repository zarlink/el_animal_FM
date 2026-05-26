from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
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

PARSER_VERSION = "biobio_raw_v1"
TIMEZONE = "America/Santiago"

REQUEST_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.5


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


def fetch_text(session: requests.Session, url: str) -> tuple[str, int, str]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    content_type = response.headers.get("Content-Type", "")
    response.raise_for_status()
    return response.text, response.status_code, content_type


def is_biobio_article_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc not in {"www.biobiochile.cl", "biobiochile.cl"}:
        return False

    if not parsed.path.endswith(".shtml"):
        return False

    # Evita enlaces a apps, legales u otros subdominios no noticiosos.
    if "legales.biobiochile.cl" in url:
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
    """
    Google News sitemap suele tener noticias recientes.
    Si falla, no detenemos el proceso.
    """
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
    """
    BioBio ha usado sitemaps mensuales del tipo:
    /static/sitemap-YYYY-MM.xml
    """
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
    """
    Respaldo. Lo Último puede venir mezclado con placeholders, menús y enlaces repetidos.
    Solo aceptamos URLs con la fecha objetivo.
    """
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
) -> dict[str, DiscoveredUrl]:
    print("Buscando URLs en news-sitemap.xml...")
    news = discover_from_news_sitemap(session, target)
    print(f"  Encontradas en news-sitemap: {len(news)}")

    print("Buscando URLs en sitemap mensual...")
    monthly = discover_from_monthly_sitemap(session, target)
    print(f"  Encontradas en sitemap mensual: {len(monthly)}")

    print("Buscando URLs en Lo Último como respaldo...")
    latest = discover_from_lo_ultimo(session, target)
    print(f"  Encontradas en Lo Último: {len(latest)}")

    merged = merge_discoveries(news, monthly, latest)

    return dict(sorted(merged.items(), key=lambda kv: kv[0]))


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def get_meta(soup: BeautifulSoup, key: str) -> str:
    """
    Busca meta property='key' o name='key'.
    """
    tag = soup.find("meta", attrs={"property": key})
    if not tag:
        tag = soup.find("meta", attrs={"name": key})

    if tag and tag.get("content"):
        return tag["content"].strip()

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
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def remove_template_noise(value: str) -> str:
    value = re.sub(r"\{\{.*?\}\}", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


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
    """
    Retorna:
    - published_at ISO
    - published_date YYYY-MM-DD
    - published_time HH:MM:SS
    - published_at_raw
    """
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

    # Respaldo buscando patrones visibles.
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
    """
    Intenta inferir main_section, subsection y region_section desde la URL.
    Ejemplo:
    /noticias/nacional/chile/2026/05/21/titulo.shtml
    """
    path_parts = [p for p in urlparse(url).path.split("/") if p]

    main_section = ""
    subsection = ""
    region_section = ""

    if "noticias" in path_parts:
        idx = path_parts.index("noticias")
        after = path_parts[idx + 1 :]

        # Cortar antes del año.
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

    # Respaldo heurístico.
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

    # Cargo/rol: heurística conservadora.
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
    lower = text.lower()

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
        "{{",
        "}}",
    ]

    return any(fragment in lower for fragment in bad_fragments)


def extract_body(container) -> tuple[str, str, list[str], int, int, list[str], int]:
    """
    Retorna:
    body_text_raw, body_text_clean, paragraphs, paragraph_count,
    body_length_chars, internal_subheadings, quote_count.
    """
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

    if not paragraphs:
        fallback_text = remove_template_noise(container_copy.get_text("\n", strip=True))
        fallback_lines = [
            clean_text(line)
            for line in fallback_text.splitlines()
            if len(clean_text(line)) >= 25 and not is_boilerplate_paragraph(line)
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
    """
    Intenta encontrar resumen IA.
    Puede no estar disponible en HTML inicial.
    """
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

    # Buscar bloque cercano a la declaración del resumen IA.
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
        return possible_texts[0], True, "bio_bio_ai_reviewed_by_author"

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

    # Heurística para crédito.
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
        html = response.text
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
    ) = extract_body(container)

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

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga noticias diarias de BioBioChile y guarda datos raw + technical."
    )

    parser.add_argument(
        "--date",
        default=None,
        help="Fecha objetivo. Formatos aceptados: DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD. Si se omite, usa hoy en Chile.",
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
        help="Límite de noticias para prueba. 0 = sin límite.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Pausa en segundos entre descargas.",
    )

    args = parser.parse_args()

    target = parse_target_date(args.date)

    base_dir = Path(args.base_dir).resolve()
    day_dir = base_dir / "biobio" / date_dir_name(target)
    raw_html_dir = day_dir / "html"
    output_path = day_dir / "noticias_dia.txt"

    day_dir.mkdir(parents=True, exist_ok=True)
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    session = create_session()

    print("=== Scraper diario BioBioChile ===")
    print(f"Fecha objetivo: {target.isoformat()}")
    print(f"Carpeta destino: {day_dir}")
    print(f"Archivo salida: {output_path}")
    print()

    discoveries = discover_article_urls(session, target)
    urls = list(discoveries.keys())

    if args.max_articles and args.max_articles > 0:
        urls = urls[: args.max_articles]

    print()
    print(f"Total de noticias detectadas para el día: {len(discoveries)}")
    if args.max_articles and args.max_articles > 0:
        print(f"Modo prueba: se descargarán solo {len(urls)} noticias.")
    else:
        print(f"Se descargarán {len(urls)} noticias.")
    print()

    articles: list[dict[str, Any]] = []

    for index, url in enumerate(urls, start=1):
        print(f"[{index}/{len(urls)}] Descargando: {url}")

        article = extract_article(
            session=session,
            discovered=discoveries[url],
            raw_html_dir=raw_html_dir,
        )

        articles.append(article)

        if args.sleep > 0:
            time.sleep(args.sleep)

    write_output(
        output_path=output_path,
        target=target,
        discovered_count=len(discoveries),
        articles=articles,
    )

    successful = sum(1 for a in articles if a.get("technical", {}).get("parse_success"))
    failed = len(articles) - successful

    print()
    print("=== Proceso terminado ===")
    print(f"Noticias detectadas: {len(discoveries)}")
    print(f"Noticias descargadas: {len(articles)}")
    print(f"Parseadas sin observaciones: {successful}")
    print(f"Con observaciones o errores: {failed}")
    print(f"Archivo guardado en: {output_path}")


if __name__ == "__main__":
    main()