from __future__ import annotations


BASE_URL = "https://www.elmostrador.cl"
DIA_URL = f"{BASE_URL}/dia/"
CATEGORIA_DIA_URL = f"{BASE_URL}/categoria/dia/"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap_news.xml"

DISPLAY_NAME = "El Mostrador"
SOURCE_NAME = "elmostrador"
SOURCE_FOLDER = "mostrador"
PARSER_VERSION = "elmostrador_raw_v2_range_sections"
TIMEZONE = "America/Santiago"
DAYS_BACK_EXAMPLE = 30

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

