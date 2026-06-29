from __future__ import annotations


BASE_URL = "https://www.biobiochile.cl"
NEWS_SITEMAP_URL = f"{BASE_URL}/news-sitemap.xml"
LO_ULTIMO_URL = f"{BASE_URL}/lo-ultimo.shtml"
CATEGORY_ARCHIVE_SEED_URL = f"{BASE_URL}/lista/categorias/nacional"

DISPLAY_NAME = "BioBioChile"
SOURCE_NAME = "biobiochile"
SOURCE_FOLDER = "biobio"
PARSER_VERSION = "biobio_raw_v3_category_archives"
TIMEZONE = "America/Santiago"
DAYS_BACK_EXAMPLE = 14

DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_MAX_CATEGORY_PAGES = 30

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

