from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def get_meta(
    soup: BeautifulSoup,
    key: str,
    *,
    text_cleaner: Callable[[str], str],
) -> str:
    tag = soup.find("meta", attrs={"property": key})
    if not tag:
        tag = soup.find("meta", attrs={"name": key})

    if tag and tag.get("content"):
        return text_cleaner(tag["content"])

    return ""


def get_canonical_url(
    soup: BeautifulSoup,
    fallback_url: str,
    *,
    base_url: str,
    normalize_url: Callable[[str], str],
) -> str:
    tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if tag and tag.get("href"):
        return normalize_url(urljoin(base_url, tag["href"]))
    return fallback_url


def get_title(
    soup: BeautifulSoup,
    article_ld: dict[str, Any],
    *,
    get_meta_value: Callable[[BeautifulSoup, str], str],
    text_cleaner: Callable[[str], str],
    text_or_empty: Callable[[Any], str],
    remove_template_noise: Callable[[str], str],
) -> str:
    if article_ld.get("headline"):
        return text_cleaner(str(article_ld["headline"]))

    h1 = soup.find("h1")
    if h1:
        return remove_template_noise(text_or_empty(h1))

    og_title = get_meta_value(soup, "og:title")
    if og_title:
        return text_cleaner(og_title)

    if soup.title:
        return text_cleaner(soup.title.get_text(" ", strip=True))

    return ""


def get_slug(url: str, *, suffix_to_remove: str = "") -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.split("/")[-1] if path else ""
    if suffix_to_remove and name.endswith(suffix_to_remove):
        return name[: -len(suffix_to_remove)]
    return name


def get_article_id(
    soup: BeautifulSoup,
    *,
    get_meta_value: Callable[[BeautifulSoup, str], str],
    text_cleaner: Callable[[str], str],
    extra_patterns: list[str] | None = None,
) -> str:
    candidates = [
        get_meta_value(soup, "article:id"),
        get_meta_value(soup, "post_id"),
        get_meta_value(soup, "id"),
    ]

    html = str(soup)
    patterns = [
        r"post[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
        *(extra_patterns or []),
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            candidates.append(match.group(1))

    for candidate in candidates:
        candidate = text_cleaner(candidate)
        if candidate:
            return candidate

    return ""


def find_article_container(soup: BeautifulSoup, extra_selectors: list[str] | None = None):
    selectors = [
        "article",
        "main article",
        "main",
        "[class*='article']",
        "[class*='post']",
        "[class*='nota']",
        *(extra_selectors or []),
    ]

    for selector in selectors:
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


def get_image_data(
    soup: BeautifulSoup,
    article_ld: dict[str, Any],
    container,
    *,
    base_url: str,
    get_meta_value: Callable[[BeautifulSoup, str], str],
    text_cleaner: Callable[[str], str],
    src_attrs: tuple[str, ...] = ("src",),
    credit_markers: tuple[str, ...] = ("imagen:", "foto:", "agencia", "cedida", "contexto"),
) -> dict[str, Any]:
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
        main_image_url = get_meta_value(soup, "og:image")

    imgs = container.find_all("img") if container else soup.find_all("img")
    image_count = len(imgs)

    if imgs and not main_image_url:
        for attr in src_attrs:
            src = imgs[0].get(attr) or ""
            if src:
                main_image_url = urljoin(base_url, src)
                break

    if imgs:
        main_image_alt = text_cleaner(imgs[0].get("alt", ""))

    figure = container.find("figure") if container else soup.find("figure")
    if figure:
        figcaption = figure.find("figcaption")
        if figcaption:
            image_caption = text_cleaner(figcaption.get_text(" ", strip=True))

    visible_text = container.get_text("\n", strip=True) if container else soup.get_text("\n", strip=True)
    for line in visible_text.splitlines():
        line_clean = text_cleaner(line)
        lower = line_clean.lower()

        if any(token in lower for token in credit_markers):
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


def save_raw_html(
    raw_html_dir: Path,
    url: str,
    html: str,
    *,
    get_slug_value: Callable[[str], str],
) -> str:
    slug = get_slug_value(url) or "article"
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:120]
    path = raw_html_dir / f"{safe_slug}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
