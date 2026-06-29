from __future__ import annotations


CMF_URL = "https://www.cmfchile.cl/institucional/estadisticas/fondos_cartola_diaria.php"
DOWNLOAD_URL = "https://www.cmfchile.cl/institucional/estadisticas/cfm_download.php"
CAPTCHA_VALIDATE_URL = "https://www.cmfchile.cl/sitio/biblioteca/captcha2/captcha.php"

MAX_DAYS_PER_REQUEST = 31

DEFAULT_DOWNLOAD_DIR = "downloads"
DEFAULT_CAPTCHA_NAME = "captcha.png"
DEFAULT_DEBUG_DIR = "debug_cmf"


FUND_CATALOG: dict[str, dict[str, object]] = {
    "balanceado": {
        "label": "CARTERA BALANCEADO",
        "code": "10063",
        "search_terms": ["cartera", "balanceado"],
    },
    "national_equity": {
        "label": "NATIONAL EQUITY",
        "code": "8305",
        "search_terms": ["national", "equity"],
    },
    "toesca_equity": {
        "label": "TOESCA EQUITY",
        "code": "9936",
        "search_terms": ["toesca", "equity"],
    },
    "itau_ahorro_uf": {
        "label": "AHORRO UF ITAÚ",
        "code": "10243",
        "search_terms": ["itau", "itaú", "ahorro", "uf"],
    },
}
