from __future__ import annotations

import re
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from zoneinfo import ZoneInfo

from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.infrastructure import article_html
from el_animal_fm.news.infrastructure.http_client import (
    REQUEST_TIMEOUT,
    decode_response_text,
)
from el_animal_fm.news.infrastructure.structured_data import (
    parse_json_ld,
    pick_article_jsonld,
)
from el_animal_fm.news.infrastructure.text import (
    clean_text as common_clean_text,
    detect_template_noise,
    normalize_payload_texts as common_normalize_payload_texts,
    normalize_text as common_normalize_text,
    remove_template_noise as common_remove_template_noise,
    soup_from_html,
    text_or_empty as common_text_or_empty,
)
from el_animal_fm.news.sources.biobio.config import (
    BASE_URL,
    BIOBIO_AI_BOILERPLATE_PATTERNS,
    PARSER_VERSION,
    TIMEZONE,
)
from el_animal_fm.news.sources.biobio.discovery import (
    is_biobio_article_url,
    normalize_url,
)


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


normalize_text = partial(
    common_normalize_text,
    boilerplate_remover=remove_biobio_ai_boilerplate,
)
normalize_payload_texts = partial(
    common_normalize_payload_texts,
    text_normalizer=normalize_text,
)
clean_text = partial(common_clean_text, text_normalizer=normalize_text)
remove_template_noise = partial(
    common_remove_template_noise,
    text_normalizer=normalize_text,
)
text_or_empty = partial(common_text_or_empty, text_normalizer=normalize_text)


def get_meta(soup: BeautifulSoup, key: str) -> str:
    return article_html.get_meta(soup, key, text_cleaner=clean_text)


def get_canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    return article_html.get_canonical_url(
        soup,
        fallback_url,
        base_url=BASE_URL,
        normalize_url=normalize_url,
    )


def get_title(soup: BeautifulSoup, article_ld: dict[str, Any]) -> str:
    return article_html.get_title(
        soup,
        article_ld,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
        text_or_empty=text_or_empty,
        remove_template_noise=remove_template_noise,
    )


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
    return article_html.get_slug(url, suffix_to_remove=".shtml")


def get_article_id(soup: BeautifulSoup, url: str) -> str:
    return article_html.get_article_id(
        soup,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
    )


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
    return article_html.find_article_container(soup)


def remove_unwanted_tags(container) -> None:
    article_html.remove_unwanted_tags(container)


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
    return article_html.get_image_data(
        soup,
        article_ld,
        container,
        base_url=BASE_URL,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
    )


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


def save_raw_html(raw_html_dir: Path, url: str, html: str) -> str:
    return article_html.save_raw_html(
        raw_html_dir,
        url,
        html,
        get_slug_value=get_slug,
    )


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
