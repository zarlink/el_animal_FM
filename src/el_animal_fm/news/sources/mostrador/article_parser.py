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
from el_animal_fm.news.sources.mostrador.config import (
    BASE_URL,
    ELMOSTRADOR_BOILERPLATE_PATTERNS,
    PARSER_VERSION,
    SPANISH_MONTHS,
    TIMEZONE,
)
from el_animal_fm.news.sources.mostrador.discovery import (
    is_elmostrador_article_url,
    normalize_url,
)


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


normalize_text = partial(
    common_normalize_text,
    boilerplate_remover=remove_elmostrador_boilerplate,
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
    return article_html.get_title(
        soup,
        article_ld,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
        text_or_empty=text_or_empty,
        remove_template_noise=remove_template_noise,
    )


def get_slug(url: str) -> str:
    return article_html.get_slug(url)


def get_article_id(soup: BeautifulSoup, url: str) -> str:
    return article_html.get_article_id(
        soup,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
        extra_patterns=[
            r"article[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
            r"wp-post-(\d+)",
        ],
    )


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
    return article_html.find_article_container(
        soup,
        extra_selectors=["[class*='single']"],
    )


def remove_unwanted_tags(container) -> None:
    article_html.remove_unwanted_tags(container)


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
    return article_html.get_image_data(
        soup,
        article_ld,
        container,
        base_url=BASE_URL,
        get_meta_value=get_meta,
        text_cleaner=clean_text,
        src_attrs=("src", "data-src"),
        credit_markers=("foto:", "fotos:", "agenciauno", "agencia uno", "imagen:", "crédito"),
    )


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


def save_raw_html(raw_html_dir: Path, url: str, html: str) -> str:
    return article_html.save_raw_html(
        raw_html_dir,
        url,
        html,
        get_slug_value=get_slug,
    )


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
    article_ld = pick_article_jsonld(
        json_ld_items,
        allowed_types={"newsarticle", "article", "blogposting", "reportagearticle"},
    )

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
