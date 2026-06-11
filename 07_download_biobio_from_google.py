#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
buscador_google_biobio_historico_v3.py

Versión mejorada con:
- User-Agents rotativos por petición
- Retardos aleatorios más realistas
- Soporte para proxies residenciales
- Manejo de sesiones con cookies realistas
- Fingerprinting aleatorio del navegador
- Backoff exponencial ante errores
- Guardado de estado para reanudar ejecuciones largas
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ============================================================================
# Configuración de User-Agents realistas
# ============================================================================

USER_AGENTS = [
    # Chrome en Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome en macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Firefox en Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox en macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari en macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Edge en Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Chrome en Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# Cabeceras Accept-Language regionalizadas
ACCEPT_LANGUAGES = [
    "es-CL,es;q=0.9,en;q=0.7",
    "es-ES,es;q=0.9,en;q=0.8,pt;q=0.5",
    "es-419,es;q=0.9,en;q=0.7,fr;q=0.3",
    "es-CL,es;q=0.8,en;q=0.6",
]

# Cabeceras Accept variadas
ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]

# Cabeceras Sec-Fetch realistas
SEC_FETCH_SITE = ["same-origin", "none", "cross-site"]
SEC_FETCH_MODE = ["navigate", "cors"]
SEC_FETCH_DEST = ["document", "empty"]

BASE_URL = "https://www.biobiochile.cl"
GOOGLE_SEARCH_URL = "https://www.google.com/search"

DEFAULT_PARSER_FILE = "01_biobio_download.py"
DEFAULT_MAX_GOOGLE_PAGES = 10
DEFAULT_RESULTS_PER_PAGE = 10

# Retardos más realistas
DEFAULT_SLEEP_GOOGLE_MIN = 4.0
DEFAULT_SLEEP_GOOGLE_MAX = 8.0
DEFAULT_SLEEP_ARTICLE_MIN = 1.5
DEFAULT_SLEEP_ARTICLE_MAX = 3.5
DEFAULT_SLEEP_BETWEEN_DAYS_MIN = 30.0
DEFAULT_SLEEP_BETWEEN_DAYS_MAX = 60.0

# Configuración de proxy (opcional)
DEFAULT_PROXY_LIST = None  # Puede ser archivo con proxies o lista


@dataclass
class GoogleSearchResult:
    url: str
    title: str = ""
    source_method: str = ""
    google_page: int = 0
    google_rank: int = 0


@dataclass
class DaySummary:
    target_date: str
    query: str
    google_urls_found_raw: int
    valid_biobio_urls_for_date: int
    existing_articles_before: int
    existing_unique_urls_before: int
    new_urls_to_download: int
    new_articles_downloaded: int
    total_articles_after_merge: int
    output_path: str
    status: str
    errors: list[str] = field(default_factory=list)
    proxies_used: int = 0


@dataclass
class SessionStats:
    """Estadísticas de la sesión para fingerprinting"""
    user_agent: str = ""
    accept_language: str = ""
    accept: str = ""
    proxy: Optional[str] = None
    requests_made: int = 0
    last_request_time: float = 0.0


def load_proxies(proxy_source: Optional[str] = None) -> list[str]:
    """
    Carga lista de proxies desde archivo o variable de entorno.
    Formato esperado: http://user:pass@host:port o http://host:port
    """
    proxies = []

    if proxy_source and Path(proxy_source).exists():
        with open(proxy_source, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxies.append(line)

    # También puede venir de variable de entorno
    env_proxy = __import__('os').environ.get('PROXY_LIST')
    if env_proxy:
        for p in env_proxy.split(','):
            p = p.strip()
            if p and p not in proxies:
                proxies.append(p)

    if proxies:
        print(f"[INFO] Cargados {len(proxies)} proxies")

    return proxies


def get_random_user_agent() -> str:
    """Selecciona un User-Agent aleatorio"""
    return random.choice(USER_AGENTS)


def get_random_accept_language() -> str:
    """Selecciona una cabecera Accept-Language aleatoria"""
    return random.choice(ACCEPT_LANGUAGES)


def get_random_accept() -> str:
    """Selecciona una cabecera Accept aleatoria"""
    return random.choice(ACCEPT_HEADERS)


def get_random_sec_fetch() -> dict:
    """Genera cabeceras Sec-Fetch aleatorias"""
    return {
        "Sec-Fetch-Site": random.choice(SEC_FETCH_SITE),
        "Sec-Fetch-Mode": random.choice(SEC_FETCH_MODE),
        "Sec-Fetch-Dest": random.choice(SEC_FETCH_DEST),
        "Sec-Fetch-User": "?1",
    }


def create_google_session(
        proxy: Optional[str] = None,
        use_random_fingerprint: bool = True,
) -> tuple[requests.Session, SessionStats]:
    """
    Crea una sesión de requests con fingerprint aleatorio.

    Args:
        proxy: URL del proxy a usar (opcional)
        use_random_fingerprint: Si True, rota User-Agent y otras cabeceras

    Returns:
        Tupla (session, stats)
    """
    session = requests.Session()

    # Seleccionar fingerprint
    user_agent = get_random_user_agent() if use_random_fingerprint else USER_AGENTS[0]
    accept_language = get_random_accept_language() if use_random_fingerprint else ACCEPT_LANGUAGES[0]
    accept = get_random_accept() if use_random_fingerprint else ACCEPT_HEADERS[0]

    # Cabeceras base
    base_headers = {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    session.headers.update(base_headers)

    # Añadir cookies iniciales realistas
    session.cookies.set("CONSENT", f"YES+cb.{datetime.now().strftime('%Y%m%d')}-14-p0.es+FX+{random.randint(100, 999)}")
    session.cookies.set("SOCS", f"CAESHAgBEhJnd3NfMjAyNTAyMTAtMF9SQzEaAmVzIAEaBgiA_Lu4wQY")

    # Configurar proxy si se especifica
    proxy_dict = None
    if proxy:
        proxy_dict = {
            "http": proxy,
            "https": proxy,
        }
        session.proxies.update(proxy_dict)

    stats = SessionStats(
        user_agent=user_agent,
        accept_language=accept_language,
        accept=accept,
        proxy=proxy,
        requests_made=0,
        last_request_time=0.0,
    )

    return session, stats


def update_session_fingerprint(session: requests.Session, stats: SessionStats) -> None:
    """
    Actualiza el fingerprint de la sesión para la siguiente ronda de peticiones.
    Debe llamarse periódicamente (cada N peticiones o cada día).
    """
    user_agent = get_random_user_agent()
    accept_language = get_random_accept_language()
    accept = get_random_accept()

    session.headers.update({
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": accept_language,
    })

    # Añadir cabeceras Sec-Fetch aleatorias
    sec_fetch = get_random_sec_fetch()
    session.headers.update(sec_fetch)

    stats.user_agent = user_agent
    stats.accept_language = accept_language
    stats.accept = accept


def rotate_proxy(
        proxy_list: list[str],
        current_proxy: Optional[str] = None,
) -> Optional[str]:
    """
    Rota al siguiente proxy de la lista.
    Si solo hay uno o ninguno, devuelve el disponible.
    """
    if not proxy_list:
        return None

    if len(proxy_list) == 1:
        return proxy_list[0]

    # Seleccionar uno diferente al actual si es posible
    available = [p for p in proxy_list if p != current_proxy]
    if not available:
        available = proxy_list

    return random.choice(available)


def random_sleep(min_seconds: float, max_seconds: float, add_jitter: bool = True) -> float:
    """
    Pausa aleatoria con posible jitter adicional.

    Args:
        min_seconds: Tiempo mínimo de espera
        max_seconds: Tiempo máximo de espera
        add_jitter: Si True, añade variabilidad extra (distribución más natural)

    Returns:
        Segundos que durmió
    """
    base_sleep = random.uniform(min_seconds, max_seconds)

    if add_jitter:
        # Añadir variabilidad con distribución normal truncada
        jitter = max(0, random.gauss(0.2, 0.5))
        base_sleep += jitter

    time.sleep(base_sleep)
    return base_sleep


def exponential_backoff(
        attempt: int,
        base_sleep: float = 10.0,
        max_sleep: float = 300.0,
        factor: float = 2.0,
) -> float:
    """
    Calcula tiempo de espera con backoff exponencial.

    Args:
        attempt: Número de intento (0-indexed)
        base_sleep: Tiempo base en segundos
        max_sleep: Tiempo máximo en segundos
        factor: Factor multiplicativo

    Returns:
        Segundos a esperar
    """
    sleep_time = min(base_sleep * (factor ** attempt), max_sleep)
    # Añadir jitter del 10%
    sleep_time *= random.uniform(0.9, 1.1)
    return sleep_time


def google_request_with_retry(
        session: requests.Session,
        url: str,
        max_retries: int = 3,
        stats: Optional[SessionStats] = None,
) -> requests.Response:
    """
    Realiza una petición a Google con reintentos y backoff exponencial.

    Args:
        session: Sesión de requests
        url: URL a consultar
        max_retries: Número máximo de reintentos
        stats: Estadísticas de sesión (para tracking)

    Returns:
        Objeto Response

    Raises:
        requests.RequestException si todos los reintentos fallan
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=30)

            if stats:
                stats.requests_made += 1
                stats.last_request_time = time.time()

            # Si es 429 (Too Many Requests), esperar más
            if response.status_code == 429:
                wait = exponential_backoff(attempt, base_sleep=30.0)
                print(f"  [429] Demasiadas peticiones. Esperando {wait:.0f}s...")
                time.sleep(wait)
                continue

            # Si es bloqueo, esperar mucho más
            if looks_like_google_block(response.text, response.status_code):
                wait = exponential_backoff(attempt, base_sleep=60.0)
                print(f"  [BLOQUEO] Detectado. Esperando {wait:.0f}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                wait = exponential_backoff(attempt)
                print(f"  [ERROR] Intento {attempt + 1} fallido: {exc}. Reintentando en {wait:.0f}s...")
                time.sleep(wait)
            else:
                raise

    raise last_exception  # type: ignore


# ============================================================================
# Funciones de utilidad (mantenidas del original)
# ============================================================================

def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d_%m_%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato no reconocido. Usa YYYY-MM-DD, DD-MM-YYYY o DD_MM_YYYY.")


def ask_date() -> date:
    while True:
        raw = input(
            "¿Desde qué día quieres comenzar hacia atrás? "
            "Ejemplo 2026-04-30 o 30-04-2026: "
        ).strip()
        try:
            return parse_date(raw)
        except ValueError as exc:
            print(exc)


def ask_days_back() -> int:
    while True:
        raw = input(
            "¿Cuántos días quieres iterar hacia atrás, incluyendo el día inicial? "
            "Ejemplo 10, 100 o 1000: "
        ).strip()
        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass
        print("Ingresa un número entero mayor o igual a 1.")


def build_date_range(start_date: date, days_back: int) -> list[date]:
    return [start_date - timedelta(days=i) for i in range(days_back)]


def date_dir_name(target: date) -> str:
    return target.strftime("%d_%m_%Y")


def target_url_fragment(target: date) -> str:
    return target.strftime("/%Y/%m/%d/")


def google_query_for_day(target: date) -> str:
    after_date = (target - timedelta(days=1)).isoformat()
    before_date = (target + timedelta(days=1)).isoformat()
    return f"site:biobiochile.cl after:{after_date} before:{before_date}"


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    url = html.unescape(url)
    url = unquote(url)
    url = url.split("#")[0]
    url = re.sub(r"\?.*$", "", url)
    url = url.replace("http://www.biobiochile.cl", "https://www.biobiochile.cl")
    url = url.replace("http://biobiochile.cl", "https://www.biobiochile.cl")
    url = url.replace("https://biobiochile.cl", "https://www.biobiochile.cl")
    return url.strip()


def is_biobio_article_url(url: str) -> bool:
    url = normalize_url(url)
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host not in {"www.biobiochile.cl", "biobiochile.cl"}:
        return False
    if "/noticias/" not in path:
        return False
    if not path.endswith(".shtml"):
        return False
    excluded = [
        "/biobiotv/", "/podcasts/", "/programas/",
        "/especial/", "/especiales/", "/legales/",
    ]
    return not any(x in path for x in excluded)


def is_valid_url_for_target_day(url: str, target: date) -> bool:
    url = normalize_url(url)
    return is_biobio_article_url(url) and target_url_fragment(target) in url


def unwrap_google_href(href: str) -> str:
    href = html.unescape(href or "").strip()
    if not href:
        return ""
    if href.startswith("/url?"):
        parsed = urlparse(urljoin("https://www.google.com", href))
        q = parse_qs(parsed.query).get("q", [""])[0]
        return unquote(q)
    if "google.com/url?" in href:
        parsed = urlparse(href)
        q = parse_qs(parsed.query).get("q", [""])[0]
        return unquote(q)
    return href


def looks_like_google_block(page_html: str, status_code: int) -> bool:
    lower = (page_html or "").lower()
    markers = [
        "our systems have detected unusual traffic",
        "unusual traffic",
        "captcha",
        "sorry/index",
        "to continue, please type the characters",
        "detected unusual traffic",
        "too many requests",
        "rate limit",
    ]
    return status_code in {403, 429, 503} or any(marker in lower for marker in markers)


def extract_biobio_urls_from_raw_html(page_html: str) -> list[str]:
    candidates: set[str] = set()
    variants = set()
    variants.add(page_html or "")
    variants.add(html.unescape(page_html or ""))
    variants.add(unquote(page_html or ""))
    more_variants = set()
    for variant in variants:
        more_variants.add(variant.replace("\\u003d", "=").replace("\\u0026", "&"))
        more_variants.add(variant.replace("\\/", "/"))
    variants |= more_variants
    raw_pattern = re.compile(
        r"https?://(?:www\.)?biobiochile\.cl/noticias/[^\"'<>\\\s&]+?\.shtml",
        flags=re.IGNORECASE,
    )
    for variant in variants:
        for match in raw_pattern.findall(variant):
            candidates.add(normalize_url(match))
    return sorted(candidates)


def extract_biobio_urls_from_anchors(page_html: str, google_page: int) -> list[GoogleSearchResult]:
    soup = BeautifulSoup(page_html, "lxml")
    results: list[GoogleSearchResult] = []
    seen: set[str] = set()
    rank = 0
    for anchor in soup.find_all("a", href=True):
        href = unwrap_google_href(anchor.get("href", ""))
        url = normalize_url(href)
        if not is_biobio_article_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        rank += 1
        title = anchor.get_text(" ", strip=True)
        results.append(
            GoogleSearchResult(
                url=url, title=title,
                source_method="anchor_href",
                google_page=google_page, google_rank=rank,
            )
        )
    return results


def extract_biobio_urls_from_all_attrs(page_html: str, google_page: int) -> list[GoogleSearchResult]:
    soup = BeautifulSoup(page_html, "lxml")
    results: list[GoogleSearchResult] = []
    seen: set[str] = set()
    rank = 0
    for tag in soup.find_all(True):
        for attr_value in tag.attrs.values():
            values: list[str] = []
            if isinstance(attr_value, list):
                values = [str(x) for x in attr_value]
            else:
                values = [str(attr_value)]
            for value in values:
                value = html.unescape(value)
                value = unquote(value)
                if "biobiochile.cl" not in value:
                    continue
                for url in extract_biobio_urls_from_raw_html(value):
                    url = normalize_url(url)
                    if not is_biobio_article_url(url):
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    rank += 1
                    results.append(
                        GoogleSearchResult(
                            url=url, title="",
                            source_method="tag_attribute",
                            google_page=google_page, google_rank=rank,
                        )
                    )
    return results


def extract_google_results(page_html: str, google_page: int) -> list[GoogleSearchResult]:
    combined: dict[str, GoogleSearchResult] = {}
    for result in extract_biobio_urls_from_anchors(page_html, google_page):
        combined.setdefault(result.url, result)
    for result in extract_biobio_urls_from_all_attrs(page_html, google_page):
        combined.setdefault(result.url, result)
    raw_urls = extract_biobio_urls_from_raw_html(page_html)
    for idx, url in enumerate(raw_urls, start=1):
        url = normalize_url(url)
        if not is_biobio_article_url(url):
            continue
        combined.setdefault(
            url,
            GoogleSearchResult(
                url=url, title="",
                source_method="raw_html_regex",
                google_page=google_page, google_rank=idx,
            ),
        )
    return list(combined.values())


def build_google_url(query: str, start: int, results_per_page: int) -> str:
    q = quote_plus(query)
    return (
        f"{GOOGLE_SEARCH_URL}"
        f"?q={q}"
        f"&num={results_per_page}"
        f"&start={start}"
        f"&hl=es-419"
        f"&filter=0"
    )


def load_biobio_parser(parser_path: Path):
    if not parser_path.exists():
        raise FileNotFoundError(
            f"No se encontró {parser_path}. "
            "Coloca este script junto a scraper_biobio_merge_incremental.py "
            "o usa --parser-file."
        )
    spec = importlib.util.spec_from_file_location("biobio_parser_module", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No pude cargar el módulo desde {parser_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["biobio_parser_module"] = module
    spec.loader.exec_module(module)
    return module


def get_article_url_from_payload(article: dict[str, Any], parser_module) -> str:
    if hasattr(parser_module, "get_article_url_from_payload"):
        return parser_module.get_article_url_from_payload(article)
    raw = article.get("raw") if isinstance(article, dict) else {}
    if isinstance(raw, dict):
        return normalize_url(str(raw.get("canonical_url") or raw.get("url") or ""))
    return ""


def load_existing_day_payload(output_path: Path, parser_module) -> tuple[list[dict[str, Any]], set[str]]:
    if not output_path.exists():
        return [], set()
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] No se pudo leer archivo existente {output_path}: {exc}")
        return [], set()
    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        print(f"[WARN] Archivo existente sin lista válida de articles: {output_path}")
        return [], set()
    urls: set[str] = set()
    for article in articles:
        url = get_article_url_from_payload(article, parser_module)
        if url:
            urls.add(url)
    return articles, urls


def deduplicate_articles_by_url(articles: list[dict[str, Any]], parser_module) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for article in articles:
        url = get_article_url_from_payload(article, parser_module)
        if not url:
            deduped.append(article)
            continue
        if url in seen:
            continue
        seen.add(url)
        deduped.append(article)
    return deduped


def build_google_discovered(url: str, parser_module, google_result: GoogleSearchResult):
    return parser_module.DiscoveredUrl(
        url=url,
        discovered_from_sitemap=False,
        discovered_from_feed=False,
        discovery_sources=[
            "google-search",
            f"method={google_result.source_method}",
            f"google-page={google_result.google_page}",
            f"google-rank={google_result.google_rank}",
        ],
    )


def google_search_day(
        session: requests.Session,
        target: date,
        max_google_pages: int,
        results_per_page: int,
        sleep_google_min: float,
        sleep_google_max: float,
        stats: Optional[SessionStats] = None,
        debug_html_dir: Optional[Path] = None,
) -> tuple[str, list[GoogleSearchResult], list[str]]:
    """
    Busca en Google noticias de BioBio para un día específico.

    Usa delays aleatorios entre páginas para simular comportamiento humano.
    """
    query = google_query_for_day(target)
    all_results_by_url: dict[str, GoogleSearchResult] = {}
    errors: list[str] = []

    print()
    print("=" * 70)
    print(f"Google día objetivo: {target.isoformat()}")
    print(f"Consulta: {query}")
    if stats and stats.proxy:
        print(f"Proxy: {stats.proxy}")
    print(f"User-Agent: {session.headers.get('User-Agent', 'N/A')[:80]}...")
    print("=" * 70)

    empty_pages_in_a_row = 0

    for page_index in range(max_google_pages):
        start = page_index * results_per_page
        google_url = build_google_url(query, start=start, results_per_page=results_per_page)

        try:
            response = google_request_with_retry(
                session=session,
                url=google_url,
                max_retries=3,
                stats=stats,
            )
            page_html = response.text or ""

            if debug_html_dir:
                debug_html_dir.mkdir(parents=True, exist_ok=True)
                debug_path = debug_html_dir / f"google_{target.isoformat()}_page_{page_index + 1}.html"
                debug_path.write_text(page_html, encoding="utf-8", errors="replace")

            if looks_like_google_block(page_html, response.status_code):
                msg = (
                    f"Google parece haber bloqueado o solicitado verificación. "
                    f"HTTP {response.status_code}. Se detiene el día {target.isoformat()}."
                )
                print(f"[STOP] {msg}")
                errors.append(msg)
                break

        except Exception as exc:
            msg = f"Error consultando Google página {page_index + 1}: {exc}"
            print(f"[WARN] {msg}")
            errors.append(msg)
            break

        page_results = extract_google_results(page_html, google_page=page_index + 1)
        new_count = 0

        for result in page_results:
            if result.url not in all_results_by_url:
                all_results_by_url[result.url] = result
                new_count += 1

        print(
            f"  Página Google {page_index + 1}/{max_google_pages}: "
            f"{len(page_results)} URLs BioBio extraídas, nuevas: {new_count}"
        )

        if new_count == 0:
            empty_pages_in_a_row += 1
        else:
            empty_pages_in_a_row = 0

        # Dos páginas seguidas sin nada nuevo = no hay más resultados
        if page_index >= 1 and empty_pages_in_a_row >= 2:
            print("  Dos páginas seguidas sin URLs nuevas. Se corta la búsqueda del día.")
            break

        # Delay aleatorio entre páginas de Google
        if page_index < max_google_pages - 1:
            sleep_time = random_sleep(sleep_google_min, sleep_google_max, add_jitter=True)
            print(f"  Esperando {sleep_time:.1f}s antes de siguiente página...")

    return query, list(all_results_by_url.values()), errors


def process_day(
        target: date,
        parser_module,
        google_session: requests.Session,
        base_dir: Path,
        max_google_pages: int,
        results_per_page: int,
        sleep_google_min: float,
        sleep_google_max: float,
        sleep_article_min: float,
        sleep_article_max: float,
        max_articles_per_day: int,
        overwrite_existing: bool,
        debug_google_html: bool,
        proxy_list: Optional[list[str]] = None,
        stats: Optional[SessionStats] = None,
        fingerprint_rotate_frequency: int = 5,
        proxy_rotate_frequency: int = 10,
) -> DaySummary:
    """
    Procesa un día completo: busca en Google, descarga artículos nuevos.

    Incluye:
    - Rotación de fingerprint cada N peticiones
    - Rotación de proxy cada M peticiones
    - Delays aleatorios entre artículos
    """
    debug_html_dir = None
    if debug_google_html:
        debug_html_dir = base_dir / "biobio" / "_debug_google_html"

    query, google_results, errors = google_search_day(
        session=google_session,
        target=target,
        max_google_pages=max_google_pages,
        results_per_page=results_per_page,
        sleep_google_min=sleep_google_min,
        sleep_google_max=sleep_google_max,
        stats=stats,
        debug_html_dir=debug_html_dir,
    )

    valid_results_by_url: dict[str, GoogleSearchResult] = {}
    for result in google_results:
        url = normalize_url(result.url)
        if is_valid_url_for_target_day(url, target):
            valid_results_by_url[url] = result

    day_dir = base_dir / "biobio" / date_dir_name(target)
    raw_html_dir = day_dir / "html"
    output_path = day_dir / "noticias_dia.txt"

    day_dir.mkdir(parents=True, exist_ok=True)
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    existing_articles, existing_urls = load_existing_day_payload(output_path, parser_module)

    if overwrite_existing:
        print("[INFO] overwrite_existing=True: se ignora archivo previo para este día.")
        existing_articles = []
        existing_urls = set()

    urls_to_download = [
        url for url in sorted(valid_results_by_url)
        if url not in existing_urls
    ]

    if max_articles_per_day > 0:
        urls_to_download = urls_to_download[:max_articles_per_day]

    print()
    print(f"Fecha {target.isoformat()}:")
    print(f"  URLs BioBio extraídas desde Google: {len(google_results)}")
    print(f"  URLs válidas con fecha exacta {target_url_fragment(target)}: {len(valid_results_by_url)}")
    print(f"  Artículos existentes antes: {len(existing_articles)}")
    print(f"  URLs existentes únicas: {len(existing_urls)}")
    print(f"  URLs nuevas por descargar: {len(urls_to_download)}")

    new_articles: list[dict[str, Any]] = []
    article_session = parser_module.create_session()

    # Contador para rotación de fingerprint y proxy
    request_counter = 0

    for idx, url in enumerate(urls_to_download, start=1):
        print(f"[{idx}/{len(urls_to_download)}] Descargando: {url}")

        try:
            # Rotar fingerprint cada N peticiones
            if request_counter > 0 and request_counter % fingerprint_rotate_frequency == 0:
                if stats:
                    update_session_fingerprint(google_session, stats)
                    print(f"  [FINGERPRINT] Rotado. Nuevo UA: {stats.user_agent[:80]}...")

            # Rotar proxy cada M peticiones
            if proxy_list and request_counter > 0 and request_counter % proxy_rotate_frequency == 0:
                new_proxy = rotate_proxy(proxy_list, stats.proxy if stats else None)
                if new_proxy:
                    google_session.proxies.update({"http": new_proxy, "https": new_proxy})
                    if stats:
                        stats.proxy = new_proxy
                    print(f"  [PROXY] Rotado a: {new_proxy}")

            discovered = build_google_discovered(
                url=url,
                parser_module=parser_module,
                google_result=valid_results_by_url[url],
            )

            article = parser_module.extract_article(
                session=article_session,
                discovered=discovered,
                raw_html_dir=raw_html_dir,
            )

            new_articles.append(article)
            request_counter += 1

        except Exception as exc:
            msg = f"Error descargando {url}: {exc}"
            print(f"[WARN] {msg}")
            errors.append(msg)

        # Delay aleatorio entre artículos
        if idx < len(urls_to_download):
            sleep_time = random_sleep(sleep_article_min, sleep_article_max)
            print(f"  Esperando {sleep_time:.1f}s...")

    combined_articles = deduplicate_articles_by_url(existing_articles + new_articles, parser_module)

    if new_articles or overwrite_existing or not output_path.exists():
        parser_module.write_output(
            output_path=output_path,
            target=target,
            discovered_count=len(valid_results_by_url),
            articles=combined_articles,
        )
        status = "updated_with_new_articles" if new_articles else "written_without_new_articles"
    else:
        status = "no_new_articles"

    print(f"  Total final sin duplicados: {len(combined_articles)}")
    print(f"  Estado: {status}")
    print(f"  Archivo: {output_path}")

    return DaySummary(
        target_date=target.isoformat(),
        query=query,
        google_urls_found_raw=len(google_results),
        valid_biobio_urls_for_date=len(valid_results_by_url),
        existing_articles_before=len(existing_articles),
        existing_unique_urls_before=len(existing_urls),
        new_urls_to_download=len(urls_to_download),
        new_articles_downloaded=len(new_articles),
        total_articles_after_merge=len(combined_articles),
        output_path=str(output_path),
        status=status,
        errors=errors,
        proxies_used=1 if (stats and stats.proxy) else 0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Busca en Google noticias antiguas de BioBio con fingerprint rotativo y proxies."
    )

    parser.add_argument("--start-date", default=None, help="Día inicial. Ejemplo: 2026-04-30.")
    parser.add_argument("--days-back", type=int, default=None, help="Días hacia atrás, incluyendo día inicial.")
    parser.add_argument("--base-dir", default=".", help="Directorio base del proyecto.")
    parser.add_argument("--parser-file", default=DEFAULT_PARSER_FILE, help="Ruta al scraper BioBio.")
    parser.add_argument("--max-google-pages", type=int, default=DEFAULT_MAX_GOOGLE_PAGES)
    parser.add_argument("--results-per-page", type=int, default=DEFAULT_RESULTS_PER_PAGE)
    parser.add_argument("--sleep-google-min", type=float, default=DEFAULT_SLEEP_GOOGLE_MIN)
    parser.add_argument("--sleep-google-max", type=float, default=DEFAULT_SLEEP_GOOGLE_MAX)
    parser.add_argument("--sleep-article-min", type=float, default=DEFAULT_SLEEP_ARTICLE_MIN)
    parser.add_argument("--sleep-article-max", type=float, default=DEFAULT_SLEEP_ARTICLE_MAX)
    parser.add_argument("--sleep-between-days-min", type=float, default=DEFAULT_SLEEP_BETWEEN_DAYS_MIN)
    parser.add_argument("--sleep-between-days-max", type=float, default=DEFAULT_SLEEP_BETWEEN_DAYS_MAX)
    parser.add_argument("--max-articles-per-day", type=int, default=0)
    parser.add_argument("--overwrite-existing", action="store_true")
    parser.add_argument("--debug-google-html", action="store_true")
    parser.add_argument(
        "--proxy-list",
        default=None,
        help="Archivo con lista de proxies (uno por línea) o lista separada por comas.",
    )
    parser.add_argument(
        "--fingerprint-rotate",
        type=int,
        default=5,
        help="Rotar fingerprint cada N peticiones.",
    )
    parser.add_argument(
        "--proxy-rotate",
        type=int,
        default=10,
        help="Rotar proxy cada N peticiones.",
    )

    args = parser.parse_args()

    start_date = parse_date(args.start_date) if args.start_date else ask_date()
    days_back = args.days_back if args.days_back is not None else ask_days_back()

    if days_back < 1:
        raise ValueError("--days-back debe ser mayor o igual a 1.")

    base_dir = Path(args.base_dir).resolve()
    parser_path = Path(args.parser_file)
    if not parser_path.is_absolute():
        parser_path = Path.cwd() / parser_path

    parser_module = load_biobio_parser(parser_path)

    # Cargar proxies
    proxy_list = load_proxies(args.proxy_list) if args.proxy_list else []

    # Crear sesión inicial con fingerprint aleatorio
    initial_proxy = proxy_list[0] if proxy_list else None
    google_session, stats = create_google_session(
        proxy=initial_proxy,
        use_random_fingerprint=True,
    )

    targets = build_date_range(start_date, days_back)

    print("=" * 70)
    print("BUSCADOR GOOGLE BIOBIO HISTÓRICO V3")
    print(f"Día inicial: {start_date.isoformat()}")
    print(f"Días hacia atrás: {days_back}")
    print(f"Último día: {targets[-1].isoformat()}")
    print(f"Base dir: {base_dir}")
    print(f"Parser BioBio: {parser_path}")
    print(f"Proxies cargados: {len(proxy_list)}")
    print(f"User-Agent inicial: {stats.user_agent[:80]}...")
    print("=" * 70)

    summaries: list[dict[str, Any]] = []

    for idx, target in enumerate(targets, start=1):
        print()
        print("#" * 70)
        print(f"DÍA {idx}/{len(targets)} | {target.isoformat()}")
        print("#" * 70)

        try:
            summary = process_day(
                target=target,
                parser_module=parser_module,
                google_session=google_session,
                base_dir=base_dir,
                max_google_pages=args.max_google_pages,
                results_per_page=args.results_per_page,
                sleep_google_min=args.sleep_google_min,
                sleep_google_max=args.sleep_google_max,
                sleep_article_min=args.sleep_article_min,
                sleep_article_max=args.sleep_article_max,
                max_articles_per_day=args.max_articles_per_day,
                overwrite_existing=args.overwrite_existing,
                debug_google_html=args.debug_google_html,
                proxy_list=proxy_list,
                stats=stats,
                fingerprint_rotate_frequency=args.fingerprint_rotate,
                proxy_rotate_frequency=args.proxy_rotate,
            )
            summaries.append(summary.__dict__)

        except KeyboardInterrupt:
            print("Interrumpido por el usuario.")
            break

        except Exception as exc:
            print(f"[ERROR] Falló el día {target.isoformat()}: {exc}")
            summaries.append({
                "target_date": target.isoformat(),
                "status": "error",
                "error": str(exc),
            })

        # Delay largo entre días para simular comportamiento humano
        if idx < len(targets):
            sleep_time = random_sleep(args.sleep_between_days_min, args.sleep_between_days_max)
            print(f"\n[ENTRE DÍAS] Esperando {sleep_time:.1f}s antes del siguiente día...")

    # Guardar resumen
    summary_dir = base_dir / "biobio"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"resumen_google_biobio_v3_{date_dir_name(start_date)}_{days_back}_dias.txt"
    summary_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    updated_days = sum(1 for x in summaries if x.get("status") == "updated_with_new_articles")
    no_new_days = sum(1 for x in summaries if x.get("status") == "no_new_articles")
    error_days = sum(1 for x in summaries if x.get("status") == "error")
    total_new_articles = sum(int(x.get("new_articles_downloaded", 0)) for x in summaries)

    print()
    print("=" * 70)
    print("PROCESO TERMINADO")
    print(f"Días procesados: {len(summaries)}")
    print(f"Días actualizados con nuevas noticias: {updated_days}")
    print(f"Días sin nuevas noticias: {no_new_days}")
    print(f"Días con error: {error_days}")
    print(f"Noticias nuevas descargadas: {total_new_articles}")
    print(f"Resumen guardado en: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()