import html
import json
import logging
import os
import re
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import time

import hdbscan
import numpy as np
import spacy
import yake
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from spacy.lang.es.stop_words import STOP_WORDS as SPACY_STOPWORDS


# ============================================================
# 0. LOGGING Y CONFIGURACIÓN DE PARALELISMO
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("creador_diccionario")

DEFAULT_RECORD_WORKERS = max(1, min(os.cpu_count() or 1, 12))
RECORD_LOG_EVERY = 250
RECORD_CHUNKSIZE = 25

# ============================================================
# 1. STOPWORDS
# ============================================================

CUSTOM_STOPWORDS = {
    # Conectores y palabras funcionales adicionales
    "que", "qué", "es", "fue", "ha", "han", "ser", "son", "está", "están",
    "era", "había", "habría", "sido", "siendo", "tiene", "tienen", "tener",
    "puede", "pueden", "podría", "debe", "será", "hay", "hace",
    "tras", "durante", "según", "además", "también", "aunque", "mientras",
    "luego", "ante", "frente", "respecto", "mediante", "través",
    "sin", "sobre", "entre", "desde", "hasta", "bajo",

    # Pronombres / demostrativos / genéricos
    "ese", "esa", "eso", "esto", "estos", "estas", "ellos", "ellas",
    "otro", "otra", "otros", "otras", "todo", "todos", "todas",
    "cada", "uno", "dos", "tres", "cuatro", "mismo", "misma",
    "algo", "algunos", "algunas", "quienes", "cual", "cuales",

    # Tiempo, fechas y calendario
    "hoy", "ayer", "mañana", "lunes", "martes", "miércoles", "miercoles",
    "jueves", "viernes", "sábado", "sabado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "setiembre", "octubre",
    "noviembre", "diciembre",
    "día", "dias", "días", "semana", "semanas", "mes", "meses",
    "año", "años", "horas", "hora",

    # Años y números frecuentes del corpus
    "2026", "2025", "2024", "2023",
    "00", "000", "10", "11", "12", "13", "14", "15", "16", "17",
    "18", "19", "20", "21", "30",

    # Verbos periodísticos frecuentes
    "dijo", "afirmó", "afirmo", "señaló", "senalo", "sostuvo",
    "explicó", "explico", "informó", "informo", "aseguró", "aseguro",
    "confirmó", "confirmo", "indicó", "indico", "agregó", "agrego",
    "manifestó", "manifesto", "declaró", "declaro", "anunció", "anuncio",
    "destacó", "destaco", "detalló", "detallo", "advirtió", "advirtio",
    "concluyó", "concluyo", "señala", "reveló", "revelo",

    # Palabras editoriales o de navegación
    "ver", "resumen", "publicidad", "newsletter", "suscríbete", "suscribete",
    "lee", "también", "tambien", "destacados", "noticias", "publicación",
    "publicacion", "artículo", "articulo", "autor", "autora",

    # Nombres del medio / ruido de fuente
    "bío", "bio", "biobío", "biobio", "bío bío", "radio", "mostrador",
    "elmostrador",

    # Genéricos demasiado amplios
    "parte", "caso", "forma", "manera", "situación", "situacion",
    "momento", "lugar", "tiempo", "contexto", "nivel", "tipo",
    "total", "general", "importante", "posible", "cerca", "nuevo",
    "nueva", "mayor", "primer", "primera", "pasado", "actual",
    "bien", "fin", "marco", "línea", "linea",

    # Adicionales detectados en el corpus
    "personas", "país", "chile", "región", "nacional",
    "información", "comunidad", "vida", "proceso", "clave",
    "zona", "mundo", "sistema", "centro", "especialmente",
    "antecedentes", "pese", "personal", "finalmente",
    "asimismo", "objetivo", "principal", "actualmente",
    "distintos", "distintas", "sentido", "presencia",
    "importantes", "base", "ejemplo", "fecha", "sitio",
    "com", "twitter", "pic", "the", "may",
    "súmate", "sumate", "informado", "precisas", "seguimiento", "detallado",
    "entrevistas", "personajes", "influyen", "política políticas",
    "busca", "medida", "condiciones", "apoyo", "persona",
    "comunicado", "plazo", "espera", "principales", "punto",
    "mantiene", "respuesta", "paso", "directamente", "posteriormente",
    "necesidad", "oficial", "llamado", "explica", "permite",
    "problema", "llegar", "futuro", "seguir", "incluyendo",
    "mantener", "comenzó", "actividad", "avanzar", "importancia",
    "participación", "medios", "ocurrido", "valor", "destaca",
    "política políticas públicas","cabe","obstante","allá","deja",
    "cosas","realidad","tomar","entrega","conjunto","cumplir","conocido",
    "representa","recibió","incluye","apunta","revisar","principalmente",
    "posibles","ambas","dejar","recibir","máximo","diversas",
    "donald","josé","jose","antonio",
}

STOP = set(SPACY_STOPWORDS) | CUSTOM_STOPWORDS

# ============================================================
# 2. NORMALIZACIONES DE FRASES IMPORTANTES
# ============================================================
# Estas normalizaciones evitan que el vectorizador separe conceptos relevantes
# como "Estados Unidos", "Banco Central" o "Wall Street" en tokens sueltos.

PHRASE_NORMALIZATIONS = {
    "estados unidos": "estados_unidos",
    "ee.uu.": "estados_unidos",
    "eeuu": "estados_unidos",
    "donald trump": "donald_trump",
    "josé antonio kast": "jose_antonio_kast",
    "jose antonio kast": "jose_antonio_kast",
    "banco central": "banco_central",
    "mercado financiero": "mercado_financiero",
    "wall street": "wall_street",
    "estrecho de ormuz": "estrecho_de_ormuz",
    "ministerio de hacienda": "ministerio_de_hacienda",
    "ministro de hacienda": "ministro_de_hacienda",
    "subsidio eléctrico": "subsidio_electrico",
    "subsidio electrico": "subsidio_electrico",
    "tasa de interés": "tasa_de_interes",
    "tasa de interes": "tasa_de_interes",
    "tipo de cambio": "tipo_de_cambio",
    "renta fija": "renta_fija",
    "renta variable": "renta_variable",
    "política fiscal": "politica_fiscal",
    "politica fiscal": "politica_fiscal",
    "déficit fiscal": "deficit_fiscal",
    "deficit fiscal": "deficit_fiscal",
    "gasto fiscal": "gasto_fiscal",
    "obras públicas": "obras_publicas",
    "obras publicas": "obras_publicas",
}

# ============================================================
# 3. SEMILLAS TEMÁTICAS
# ============================================================

# Se mantienen estas semillas por compatibilidad conceptual, pero el filtrado
# principal usa las familias estrictas y contextuales definidas más abajo.

FINANCIAL_SEEDS_STRONG = {
    "hacienda",
    "banco central",
    "cmf",
    "codelco",
    "enap",
    "wall street",
    "opep",
    "inflación",
    "ipc",
    "tasa de interés",
    "mercado financiero",
    "renta fija",
    "renta variable",
    "bolsa",
    "bonos",
    "dólar",
    "tipo de cambio",
    "presupuesto",
    "déficit fiscal",
    "gasto fiscal",
    "subsidio eléctrico",
}

FINANCIAL_SEEDS_MEDIUM = {
    "mercado",
    "inversión",
    "economía",
    "económico",
    "capital",
    "empresa",
    "empresas",
    "pesos",
    "dólares",
    "millones",
    "petróleo",
    "gas",
    "cobre",
    "litio",
    "minería",
    "obras públicas",
}

FINANCIAL_SEEDS_CONTEXT = {
    "gobierno",
    "presidente",
    "ministerio",
    "ley",
    "proyecto",
    "congreso",
    "eeuu",
    "estados unidos",
    "china",
    "trump",
    "irán",
    "israel",
    "rusia",
    "ucrania",
    "guerra",
}

MARKET_STRICT_SEEDS = {
    "banco central",
    "banco_central",
    "cmf",
    "mercado financiero",
    "mercado_financiero",
    "renta fija",
    "renta_fija",
    "renta variable",
    "renta_variable",
    "bolsa",
    "bonos",
    "wall street",
    "wall_street",
    "dólar",
    "dolar",
    "tipo de cambio",
    "tipo_de_cambio",
    "tasa de interés",
    "tasa_de_interes",
    "tasa de interes",
    "ipc",
    "inflación",
    "inflacion",
}

FISCAL_STRICT_SEEDS = {
    "hacienda",
    "ministerio de hacienda",
    "ministro de hacienda",
    "presupuesto",
    "déficit fiscal",
    "deficit fiscal",
    "gasto fiscal",
    "política fiscal",
    "politica fiscal",
    "subsidio eléctrico",
    "subsidio electrico",
    "recursos públicos",
    "recursos publicos",
}

COMPANY_STRICT_SEEDS = {
    "codelco",
    "enap",
    "sqm",
    "cap",
    "copec",
    "falabella",
    "cencosud",
    "banco de chile",
    "bci",
    "santander",
    "itaú",
    "itau",
}

COMMODITY_STRICT_SEEDS = {
    "cobre",
    "litio",
    "petróleo",
    "petroleo",
    "gas",
    "minería",
    "mineria",
    "opep",
}

POLITICAL_RISK_SEEDS = {
    "gobierno",
    "presidente",
    "ministerio",
    "ministro",
    "ley",
    "proyecto",
    "congreso",
    "ejecutivo",
    "regulación",
    "regulacion",
    "reforma",
    "impuestos",
    "tributaria",
    "fiscalización",
    "fiscalizacion",
    "sanción",
    "sancion",
}

GEOPOLITICAL_RISK_SEEDS = {
    "estados unidos",
    "eeuu",
    "ee.uu.",
    "trump",
    "donald trump",
    "china",
    "irán",
    "iran",
    "israel",
    "rusia",
    "ucrania",
    "guerra",
    "conflicto",
    "estrecho de ormuz",
    "otan",
    "onu",
    "casa blanca",
}

SOCIAL_SECURITY_NOISE_SEEDS = {
    "carabineros",
    "pdi",
    "fiscalía",
    "fiscalia",
    "ministerio público",
    "ministerio publico",
    "prisión preventiva",
    "prision preventiva",
    "detención",
    "detencion",
    "delito",
    "homicidio",
    "víctima",
    "victima",
    "policía",
    "policia",
}

# Términos ambiguos: no deben gatillar una clasificación financiera por sí solos.
# Se usan solo si aparecen junto con contexto bursátil/financiero.
AMBIGUOUS_MARKET_SEEDS = {
    "acciones",
    "capital",
    "mercado",
    "empresa",
    "empresas",
}

AMOUNT_SEEDS = {
    "millones",
    "miles",
    "pesos",
    "dólares",
    "dolares",
    "usd",
    "uf",
    "$",
}

AMOUNT_CONTEXT_SEEDS = {
    "hacienda",
    "ministerio_de_hacienda",
    "ministro_de_hacienda",
    "presupuesto",
    "deficit_fiscal",
    "gasto_fiscal",
    "politica_fiscal",
    "subsidio_electrico",
    "recursos_publicos",

    "banco_central",
    "mercado_financiero",
    "wall_street",
    "bolsa",
    "bonos",
    "renta_fija",
    "renta_variable",
    "ipc",
    "inflación",
    "inflacion",
    "tasa_de_interes",
    "tipo_de_cambio",

    "codelco",
    "enap",
    "sqm",
    "cap",
    "copec",
    "falabella",
    "cencosud",

    "ingresos",
    "utilidades",
    "ganancias",
    "pérdidas",
    "perdidas",
    "deuda",
    "financiamiento",
    "inversión",
    "inversion",

    "cobre",
    "litio",
    "petróleo",
    "petroleo",
    "gas",
}

MARKET_CONTEXT_SEEDS = {
    "bolsa",
    "wall street",
    "wall_street",
    "renta variable",
    "renta_variable",
    "mercado financiero",
    "mercado_financiero",
    "inversionistas",
    "bursátil",
    "bursatil",
    "índice",
    "indice",
    "acciones chilenas",
    "acciones_chilenas",
    "acciones bursátiles",
    "acciones_bursatiles",
}

# Energía también es ambigua. Solo se considera señal de mercado si aparece
# asociada a electricidad, tarifas, combustibles, petróleo, gas, ENAP, OPEP, etc.
ENERGY_CONTEXT_SEEDS = {
    "eléctrico",
    "electrico",
    "eléctrica",
    "electrica",
    "tarifa",
    "tarifas",
    "tarifario",
    "subsidio eléctrico",
    "subsidio_electrico",
    "generación eléctrica",
    "generacion electrica",
    "transmisión eléctrica",
    "transmision electrica",
    "distribución eléctrica",
    "distribucion electrica",
    "enap",
    "petróleo",
    "petroleo",
    "gas",
    "combustible",
    "combustibles",
    "bencina",
    "diésel",
    "diesel",
    "opep",
}

# Contextos geopolíticos duros: indican evento internacional con potencial de mercado.
# No incluye "estados_unidos" ni "donald_trump" porque pueden aparecer en noticias
# internacionales no financieras.
GEOPOLITICAL_HARD_EVENT_SEEDS = {
    "irán",
    "iran",
    "israel",
    "rusia",
    "ucrania",
    "china",
    "guerra",
    "conflicto",
    "estrecho_de_ormuz",
    "estrecho de ormuz",
    "aranceles",
}

# Contextos de mercado suficientemente fuertes.
# Si una noticia geopolítica contiene alguno de estos, puede entrar a geopolitical_market.
GEOPOLITICAL_MARKET_DIRECT_CONTEXT_SEEDS = {
    "petróleo",
    "petroleo",
    "opep",
    "estrecho_de_ormuz",
    "estrecho de ormuz",
    "aranceles",
    "sanciones económicas",
    "sanciones economicas",
    "sanciones comerciales",
    "sanciones financieras",
    "sanciones internacionales",
    "exportaciones",
    "importaciones",
    "cadena de suministro",
    "wall_street",
    "wall street",
    "bolsa",
    "dólar",
    "dolar",
    "tipo_de_cambio",
    "tipo de cambio",
}

# Contextos de apoyo: son útiles, pero no deben activar la familia por sí solos.
# Requieren al menos dos señales geopolíticas duras.
GEOPOLITICAL_MARKET_SUPPORT_CONTEXT_SEEDS = {
    "precios",
    "comercio",
    "mercado",
    "dólares",
    "dolares",
    "millones",
    "sanciones",
}

# Contextos fuertes para que "gas" cuente como señal geopolítica de mercado.
# No incluye "guerra" ni "conflicto", porque esas palabras pueden aparecer en sentido
# local, político o metafórico y producir falsos positivos.
GAS_GEOPOLITICAL_STRONG_CONTEXT_SEEDS = {
    "rusia",
    "ucrania",
    "irán",
    "iran",
    "israel",
    "china",
    "estados_unidos",
    "donald_trump",
    "sanciones económicas",
    "sanciones economicas",
    "sanciones comerciales",
    "sanciones financieras",
    "sanciones internacionales",
    "opep",
    "estrecho_de_ormuz",
    "estrecho de ormuz",
}

# Contextos débiles para "gas".
# Sirven solo si además existe un contexto directo fuerte de mercado/geopolítica.
GAS_GEOPOLITICAL_WEAK_CONTEXT_SEEDS = {
    "guerra",
    "conflicto",
}


# ============================================================
# 4. LIMPIEZA Y NORMALIZACIÓN
# ============================================================

def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)

    text = unicodedata.normalize("NFKC", text).lower()

    # Normaliza frases compuestas antes de tokenizar.
    # Normaliza frases compuestas antes de tokenizar.
    for phrase, replacement in PHRASE_NORMALIZATIONS.items():
        text = text.replace(phrase, replacement)

    # Normalización contextual de apellidos políticos frecuentes.
    # Esto debe ir FUERA del for anterior, para no ejecutarlo una vez por cada frase.
    text = re.sub(r"\btrump\b", "donald_trump", text)
    text = re.sub(r"\bkast\b", "jose_antonio_kast", text)

    # Corrige duplicados generados por formas como "Donald, Trump" o "José Antonio, Kast".
    text = re.sub(r"\bdonald\s+donald_trump\b", "donald_trump", text)
    text = re.sub(r"\bjos[eé]\s+antonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    text = re.sub(r"\bantonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    # Boilerplate BioBio / El Mostrador
    boilerplate_patterns = [
        r"ver resumen",
        r"lee también",
        r"lee tambien",
        r"suscríbete.*",
        r"suscribete.*",
        r"síntesis generada con openai",
        r"sintesis generada con openai",
        r"desarrollado por el mostrador",
        r"resumen generado con una herramienta de inteligencia artificial.*?",
        r"herramienta de inteligencia artificial desarrollada por biobiochile.*?",
        r"revisado por el autor de este artículo",
        r"también te puede interesar",
        r"tambien te puede interesar",
        r"noticias del día",
        r"noticias del dia",
        r"súmate a nuestro canal.*",
        r"sumate a nuestro canal.*",
        r"reciba los newsletter.*",
        r"súmate comunidad informado precisas seguimiento detallado políticas públicas entrevistas personajes influyen",
        r"súmate comunidad",
        r"comunidad informado precisas",
        r"informado precisas seguimiento",
        r"seguimiento detallado políticas",
        r"políticas públicas entrevistas",
        r"entrevistas personajes influyen",
        r"pic twitter com",
        r"twitter com",
        r"súmate\s+(?:a\s+)?(?:nuestra\s+)?(?:comunidad\s+)?informado\s+precisas\s+seguimiento\s+detallado\s+políticas\s+públicas\s+entrevistas\s+personajes\s+influyen",
        r"súmate\s+informado\s+precisas",
        r"política\s+súmate\s+informado",
        r"informado\s+precisas\s+seguimiento",
        r"seguimiento\s+detallado\s+políticas",
        r"políticas\s+públicas\s+entrevistas",
        r"entrevistas\s+personajes\s+influyen",
        r"política\W+políticas(?:\W+públicas)?",
        r"política\W+políticas(?:\W+públicas)?",
        r"politica\W+politicas(?:\W+publicas)?",
    ]

    for pattern in boilerplate_patterns:
        text = re.sub(pattern, " ", text, flags=re.I)

    # Limpieza adicional de fragmentos residuales.
    for fragment in [
        "súmate informado",
        "sumate informado",
        "informado precisas",
        "precisas seguimiento",
        "seguimiento detallado",
        "detallado políticas",
        "detallado politicas",
        "políticas públicas entrevistas",
        "politicas publicas entrevistas",
        "entrevistas personajes",
        "entrevistas personajes influyen",
        "política políticas públicas",
        "política políticas",
    ]:
        text = text.replace(fragment, " ")

    # Fechas tipo 25 mayo 2026 / mayo 2026
    meses = (
        "enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        "septiembre|setiembre|octubre|noviembre|diciembre"
    )
    text = re.sub(
        r"\bpol[íi]tica\s+pol[íi]ticas(?:\s+p[úu]blicas)?\b",
        " ",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\bpol[íi]ticas\s+p[úu]blicas\b",
        " ",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\bpol[íi]tica\s+pol[íi]tica\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(rf"\b\d{{1,2}}\s+({meses})\s+\d{{4}}\b", " ", text)
    text = re.sub(rf"\b({meses})\s+\d{{4}}\b", " ", text)

    # Mantiene letras, números, %, $, guiones, puntos y guion bajo.
    text = re.sub(r"[^a-záéíóúñü0-9_%$/\-\.\s]", " ", text)

    # Limpieza final de remanentes editoriales que sobreviven a la primera pasada.
    text = re.sub(
        r"\bpol[íi]tica\s+pol[íi]ticas(?:\s+p[úu]blicas)?\b",
        " ",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\bpol[íi]ticas\s+p[úu]blicas\s+entrevistas\b.*?(?:influyen)?",
        " ",
        text,
        flags=re.I,
    )

    # Elimina números sueltos, pero deja porcentajes o montos si vienen unidos.
    text = re.sub(r"\b\d+\b", " ", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text



def build_dictionary_text(a: dict) -> str:
    parts = [
        a.get("title", ""),
        a.get("subtitle", ""),
        a.get("lead", ""),
        a.get("ai_summary", ""),
        a.get("body_text_clean", ""),
    ]

    # Si no existen esos campos, usa classification_text como respaldo.
    if not any(parts):
        parts = [a.get("classification_text", "")]

    return clean(" ".join(str(p) for p in parts if p))


def should_use_for_financial_dictionary(a: dict) -> bool:
    excluded_flags = [
        "is_deportes",
        "is_culture",
        "is_multimedia",
        "is_opinion",
        "is_column",
        "is_letter_to_editor",
        "is_editorial",
    ]

    for flag in excluded_flags:
        if a.get(flag) is True:
            return False

    section_text = " ".join([
        str(a.get("main_section", "")),
        str(a.get("subsection", "")),
        str(a.get("article_type_editorial", "")),
    ]).lower()

    excluded_words = [
        "deportes",
        "cultura",
        "multimedia",
        "opinión",
        "opinion",
        "cartas",
        "editorial",
        "espectáculos",
        "espectaculos",
    ]

    if any(word in section_text for word in excluded_words):
        return False

    return True


# ============================================================
# 6. MATCHING DE SEMILLAS Y CLASIFICACIÓN DE FAMILIAS
# ============================================================

WORD_CHARS = "a-záéíóúñü0-9_"


def contains_seed(text: str, seed: str) -> bool:
    """
    Busca una semilla como término o frase completa.
    Evita matches accidentales dentro de otras palabras.
    """
    text = clean(text)
    seed = clean(seed)

    if not seed:
        return False

    pattern = rf"(?<![{WORD_CHARS}]){re.escape(seed)}(?![{WORD_CHARS}])"
    return re.search(pattern, text) is not None


def seed_hits(text: str, seeds: set[str]) -> set[str]:
    """
    Devuelve las semillas encontradas en el texto, normalizadas.
    Esto evita contar varias veces alias equivalentes como:
    'eeuu', 'ee.uu.' y 'estados unidos'.
    """
    text = clean(text)

    hits = set()

    for seed in seeds:
        normalized_seed = clean(seed)

        if normalized_seed and contains_seed(text, seed):
            hits.add(normalized_seed)

    return hits

def has_market_context(text: str) -> bool:
    """
    Determina si una palabra ambigua como 'acciones' o 'mercado'
    aparece en un contexto realmente financiero/bursátil.
    """
    text = clean(text)
    return bool(seed_hits(text, MARKET_CONTEXT_SEEDS))


def has_ambiguous_market_signal(text: str) -> bool:
    """
    Permite usar términos ambiguos solo cuando van acompañados
    de contexto bursátil o financiero.
    """
    text = clean(text)
    ambiguous_hits = seed_hits(text, AMBIGUOUS_MARKET_SEEDS)
    return bool(ambiguous_hits) and has_market_context(text)

def has_amount_context(text: str) -> bool:
    text = clean(text)

    amount_hits = seed_hits(text, AMOUNT_SEEDS)

    if not amount_hits:
        return False

    strong_context_hits = seed_hits(text, {
        "hacienda",
        "ministerio_de_hacienda",
        "ministro_de_hacienda",
        "presupuesto",
        "deficit_fiscal",
        "gasto_fiscal",
        "politica_fiscal",
        "subsidio_electrico",
        "banco_central",
        "mercado_financiero",
        "wall_street",
        "bolsa",
        "bonos",
        "renta_fija",
        "renta_variable",
        "tipo_de_cambio",
        "tasa_de_interes",
        "ipc",
        "inflación",
        "inflacion",
        "codelco",
        "enap",
        "sqm",
        "copec",
        "falabella",
        "cencosud",
        "ingresos",
        "utilidades",
        "ganancias",
        "pérdidas",
        "perdidas",
        "deuda",
        "financiamiento",
        "cobre",
        "litio",
        "petróleo",
        "petroleo",
        "gas",
    })

    # No basta con "empresa", "inversión" o "mercado" como contexto débil.
    return bool(strong_context_hits)


def has_energy_market_context(text: str) -> bool:
    """
    Permite usar 'energía' solo cuando aparece en contexto eléctrico,
    tarifario, petrolero, gasífero o de combustibles.
    """
    text = clean(text)

    has_energy_word = (
            contains_seed(text, "energía")
            or contains_seed(text, "energia")
    )

    has_context = bool(seed_hits(text, ENERGY_CONTEXT_SEEDS))

    return has_energy_word and has_context


def has_geopolitical_gas_context(text: str) -> bool:
    """
    Considera 'gas' como señal geopolítica de mercado solo si aparece
    con contexto internacional duro.

    'guerra' o 'conflicto' solos no bastan, porque pueden aparecer en
    noticias locales, políticas o en sentido metafórico.
    """
    text = clean(text)

    if not contains_seed(text, "gas"):
        return False

    strong_hits = seed_hits(text, GAS_GEOPOLITICAL_STRONG_CONTEXT_SEEDS)
    weak_hits = seed_hits(text, GAS_GEOPOLITICAL_WEAK_CONTEXT_SEEDS)

    # Caso fuerte: gas + Rusia/Ucrania/Irán/Ormuz/OPEP/sanciones internacionales/etc.
    if strong_hits:
        return True

    # Caso débil: gas + guerra/conflicto solo cuenta si además hay una señal directa
    # fuerte de mercado/geopolítica, como petróleo, OPEP, Ormuz, aranceles, dólar,
    # exportaciones, importaciones, bolsa, Wall Street o cadena de suministro.
    direct_hits = seed_hits(text, GEOPOLITICAL_MARKET_DIRECT_CONTEXT_SEEDS)

    if weak_hits and direct_hits:
        return True

    return False

def has_geopolitical_market_context(text: str) -> bool:
    """
    Determina si una noticia geopolítica tiene contexto económico,
    comercial, energético, financiero o de commodities.

    Regla:
    - Señales fuertes como petróleo, OPEP, Ormuz, sanciones,
      aranceles, dólar, bolsa o cadena de suministro activan contexto.
    - Señales débiles como precios, comercio, mercado, dólares o millones
      solo activan contexto si hay al menos dos señales geopolíticas duras.
    """
    text = clean(text)

    hard_geo_hits = seed_hits(text, GEOPOLITICAL_HARD_EVENT_SEEDS)
    direct_context_hits = seed_hits(text, GEOPOLITICAL_MARKET_DIRECT_CONTEXT_SEEDS)
    support_context_hits = seed_hits(text, GEOPOLITICAL_MARKET_SUPPORT_CONTEXT_SEEDS)

    market_hits = seed_hits(text, MARKET_STRICT_SEEDS)
    commodity_hits = seed_hits(text, COMMODITY_STRICT_SEEDS)
    commodity_hits_without_gas = commodity_hits - {"gas"}

    # 1. Contexto directo fuerte: petróleo, dólar, OPEP, Ormuz,
    # sanciones económicas, aranceles, exportaciones, importaciones, Wall Street, etc.
    if direct_context_hits:
        return True

    # 1.b. Gas solo cuenta si tiene contexto geopolítico duro.
    if has_geopolitical_gas_context(text):
        return True

    # 2. Commodities o energía en contexto real:
    # debe haber al menos una señal geopolítica dura.
    # "gas" se excluye de este gatillo general, porque tiene su propia regla contextual.
    if (commodity_hits_without_gas or has_energy_market_context(text)) and hard_geo_hits:
        return True

    # 3. Mercado financiero estricto:
    # también requiere señal geopolítica dura.
    if market_hits and hard_geo_hits:
        return True

    # 4. Montos con contexto:
    # para evitar falsos positivos, exige al menos dos señales geopolíticas duras.
    if has_amount_context(text) and len(hard_geo_hits) >= 2:
        return True

    # 5. Contextos débiles como precios/comercio/mercado/dólares/millones:
    # solo entran si hay al menos dos señales geopolíticas duras.
    if support_context_hits and len(hard_geo_hits) >= 2:
        return True

    return False

def classify_text_families(text: str) -> dict:
    """
    Clasifica un texto en familias temáticas útiles para diccionarios.
    No decide impacto positivo/negativo todavía.
    """
    text = clean(text)

    market_hits = seed_hits(text, MARKET_STRICT_SEEDS)
    fiscal_hits = seed_hits(text, FISCAL_STRICT_SEEDS)
    company_hits = seed_hits(text, COMPANY_STRICT_SEEDS)
    commodity_hits = seed_hits(text, COMMODITY_STRICT_SEEDS)
    political_hits = seed_hits(text, POLITICAL_RISK_SEEDS)
    geopolitical_hits = seed_hits(text, GEOPOLITICAL_RISK_SEEDS)
    social_noise_hits = seed_hits(text, SOCIAL_SECURITY_NOISE_SEEDS)

    ambiguous_market_hits = seed_hits(text, AMBIGUOUS_MARKET_SEEDS)
    amount_hits = seed_hits(text, AMOUNT_SEEDS)
    energy_context_hits = seed_hits(text, ENERGY_CONTEXT_SEEDS)

    # Agrega términos ambiguos al mercado solo si hay contexto bursátil/financiero.
    if has_ambiguous_market_signal(text):
        market_hits = market_hits | ambiguous_market_hits

    amount_context_ok = has_amount_context(text)

    # Agrega energía solo si aparece en contexto energético real.
    if has_energy_market_context(text):
        commodity_hits = commodity_hits | {"energia_contextual"}

    strict_score = (
            len(market_hits) * 3
            + len(fiscal_hits) * 3
            + len(company_hits) * 3
            + len(commodity_hits) * 3
            + (1 if amount_context_ok else 0)
    )

    political_score = len(political_hits)
    geopolitical_score = len(geopolitical_hits)
    social_noise_score = len(social_noise_hits)

    is_financial_strict = (
            strict_score >= 4
            or len(fiscal_hits) > 0
            or len(company_hits) > 0
            or len(commodity_hits) > 0
            or len(market_hits) >= 2
    )

    is_political_risk = (
            political_score >= 2
            and (
                    len(fiscal_hits) > 0
                    or len(market_hits) > 0
                    or len(company_hits) > 0
                    or len(commodity_hits) > 0
            )
    )

    geopolitical_market_context_ok = has_geopolitical_market_context(text)

    is_geopolitical_market = (
            geopolitical_score >= 1
            and geopolitical_market_context_ok
    )

    is_social_noise_dominant = (
            social_noise_score >= 2
            and strict_score == 0
            and geopolitical_score == 0
    )

    return {
        "is_financial_strict": is_financial_strict,
        "is_political_risk": is_political_risk,
        "is_geopolitical_market": is_geopolitical_market,
        "is_social_noise_dominant": is_social_noise_dominant,

        "strict_score": strict_score,
        "political_score": political_score,
        "geopolitical_score": geopolitical_score,
        "social_noise_score": social_noise_score,

        "market_hits": sorted(market_hits),
        "fiscal_hits": sorted(fiscal_hits),
        "company_hits": sorted(company_hits),
        "commodity_hits": sorted(commodity_hits),
        "political_hits": sorted(political_hits),
        "geopolitical_hits": sorted(geopolitical_hits),
        "social_noise_hits": sorted(social_noise_hits),

        "ambiguous_market_hits": sorted(ambiguous_market_hits),
        "amount_hits": sorted(amount_hits),
        "energy_context_hits": sorted(energy_context_hits),
        "has_market_context": has_market_context(text),
        "has_amount_context": amount_context_ok,
        "has_energy_market_context": has_energy_market_context(text),
        "has_geopolitical_market_context": geopolitical_market_context_ok,
        "has_geopolitical_gas_context": has_geopolitical_gas_context(text),
        "geopolitical_gas_strong_context_hits": sorted(seed_hits(text, GAS_GEOPOLITICAL_STRONG_CONTEXT_SEEDS)),
        "geopolitical_gas_weak_context_hits": sorted(seed_hits(text, GAS_GEOPOLITICAL_WEAK_CONTEXT_SEEDS)),
        "geopolitical_hard_event_hits": sorted(seed_hits(text, GEOPOLITICAL_HARD_EVENT_SEEDS)),
        "geopolitical_direct_context_hits": sorted(seed_hits(text, GEOPOLITICAL_MARKET_DIRECT_CONTEXT_SEEDS)),
        "geopolitical_support_context_hits": sorted(seed_hits(text, GEOPOLITICAL_MARKET_SUPPORT_CONTEXT_SEEDS)),

    }


def has_financial_seed(text: str) -> bool:
    """
    Mantengo esta función por compatibilidad,
    pero ahora significa financiero estricto.
    """
    info = classify_text_families(text)
    return info["is_financial_strict"]


def process_article_for_record(a: dict) -> dict:
    """
    Worker independiente para procesar una noticia.

    Retorna un dict con status:
    - ok: artículo convertido en record válido.
    - excluded: descartado por sección/tipo.
    - empty: sin texto útil.
    - error: error controlado.
    """
    try:
        if not should_use_for_financial_dictionary(a):
            return {
                "status": "excluded",
                "reason": "section_or_type_excluded",
            }

        txt = build_dictionary_text(a)

        if not txt:
            return {
                "status": "empty",
                "reason": "empty_dictionary_text",
            }

        family_info = classify_text_families(txt)

        return {
            "status": "ok",
            "record": {
                "article": a,
                "text": txt,
                "family_info": family_info,
            },
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": repr(exc),
            "url": a.get("url", ""),
            "title": a.get("title", ""),
        }

def build_records_parallel(
    articles: list[dict],
    max_workers: int = DEFAULT_RECORD_WORKERS,
    log_every: int = RECORD_LOG_EVERY,
    chunksize: int = RECORD_CHUNKSIZE,
) -> tuple[list[dict], Counter]:
    """
    Construye records en paralelo.

    Cada artículo se procesa de forma independiente:
    - filtro por sección/tipo
    - construcción de texto
    - limpieza
    - clasificación por familias
    """
    total = len(articles)
    records = []
    stats = Counter()

    logger.info(
        f"INICIO | Construcción paralela de records | "
        f"artículos={total} | workers={max_workers} | chunksize={chunksize}"
    )

    start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results_iter = executor.map(
            process_article_for_record,
            articles,
            chunksize=chunksize,
        )

        for index, result in enumerate(results_iter, start=1):
            status = result.get("status", "unknown")
            stats[status] += 1

            if status == "ok":
                records.append(result["record"])

            elif status == "error":
                logger.warning(
                    "Error procesando artículo | "
                    f"url={result.get('url', '')} | "
                    f"title={result.get('title', '')} | "
                    f"error={result.get('error', '')}"
                )

            if index % log_every == 0 or index == total:
                elapsed = time.perf_counter() - start
                logger.info(
                    f"PROGRESO | records | {index}/{total} | "
                    f"ok={stats['ok']} | "
                    f"excluidos={stats['excluded']} | "
                    f"vacíos={stats['empty']} | "
                    f"errores={stats['error']} | "
                    f"tiempo={elapsed:.2f}s"
                )

    elapsed = time.perf_counter() - start

    logger.info(
        f"FIN | Construcción paralela de records | "
        f"records={len(records)} | "
        f"excluidos={stats['excluded']} | "
        f"vacíos={stats['empty']} | "
        f"errores={stats['error']} | "
        f"tiempo_total={elapsed:.2f}s"
    )

    return records, stats



# ============================================================
# 8. EXTRACCIÓN DE N-GRAMAS Y TF-IDF
# ============================================================

TOKEN_PATTERN = r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9_\-]{2,}\b"


def extract_ngrams(texts_source: list[str], min_df: int = 5) -> list[dict]:
    if not texts_source:
        return []

    cv = CountVectorizer(
        ngram_range=(1, 3),
        min_df=min_df,
        max_df=0.6,
        stop_words=list(STOP),
        token_pattern=TOKEN_PATTERN,
    )

    X = cv.fit_transform(texts_source)

    term_counts = X.sum(axis=0).A1
    doc_freq = (X > 0).sum(axis=0).A1
    terms = cv.get_feature_names_out()

    return sorted(
        [
            {
                "term": term,
                "count": int(count),
                "df": int(df),
                "df_pct": float(df / len(texts_source)),
            }
            for term, count, df in zip(terms, term_counts, doc_freq)
        ],
        key=lambda x: (x["df"], x["count"]),
        reverse=True
    )[:2000]


def extract_tfidf(texts_source: list[str], min_df: int = 3) -> list[dict]:
    if not texts_source:
        return []

    tfv = TfidfVectorizer(
        ngram_range=(1, 3),
        min_df=min_df,
        max_df=0.6,
        stop_words=list(STOP),
        token_pattern=TOKEN_PATTERN,
        sublinear_tf=True,
    )

    T = tfv.fit_transform(texts_source)
    tfidf_mean = T.mean(axis=0).A1
    terms = tfv.get_feature_names_out()

    return sorted(
        [
            {
                "term": term,
                "score": float(score),
            }
            for term, score in zip(terms, tfidf_mean)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:2000]


# ============================================================
# 9. YAKE
# ============================================================

def is_bad_candidate_term(term: str) -> bool:
    term = clean(term)

    if not term:
        return True

    tokens = term.split()

    if len(tokens) == 1 and tokens[0] in STOP:
        return True

    if all(token in STOP for token in tokens):
        return True

    if len(term) < 4:
        return True

    bad_fragments = [
        "pan pan",
        "programa full measure",
        "tribeca",
        "san sebastián guadalajara",
        "bío bío",
        "radio bío bío",
        "señor director",
        "director señor director",
        "mundo editorial planeta",
        "súmate informado",
        "súmate informado precisas",
        "política súmate",
        "política súmate informado",
        "informado precisas",
        "informado precisas seguimiento",
        "precisas seguimiento",
        "precisas seguimiento detallado",
        "seguimiento detallado",
        "seguimiento detallado políticas",
        "detallado políticas",
        "detallado políticas públicas",
        "políticas públicas entrevistas",
        "públicas entrevistas",
        "públicas entrevistas personajes",
        "entrevistas personajes",
        "entrevistas personajes influyen",
    ]

    if any(fragment in term for fragment in bad_fragments):
        return True

    return False



# ============================================================
# 10. NER + NORMALIZACIÓN DE ENTIDADES
# ============================================================

ENTITY_STOP = {
    "chile", "santiago", "valparaíso", "concepción",
    "lunes", "martes", "miércoles", "jueves", "viernes",
    "mayo", "abril", "junio",
    "bío bío", "bio bio", "el mostrador",
}

ENTITY_ALIASES = {
    "eeuu": "estados_unidos",
    "ee.uu.": "estados_unidos",
    "estados unidos": "estados_unidos",
    "estados_unidos": "estados_unidos",

    "trump": "donald_trump",
    "donald trump": "donald_trump",
    "donald_trump": "donald_trump",

    "kast": "jose_antonio_kast",
    "josé antonio kast": "jose_antonio_kast",
    "jose antonio kast": "jose_antonio_kast",
    "jose_antonio_kast": "jose_antonio_kast",

    "banco central": "banco_central",
    "banco_central": "banco_central",

    "wall street": "wall_street",
    "wall_street": "wall_street",

    "estrecho de ormuz": "estrecho_de_ormuz",
    "estrecho_de_ormuz": "estrecho_de_ormuz",
}


def normalize_entity_text(value: str) -> str:
    value = clean(value)
    return ENTITY_ALIASES.get(value, value)




# ============================================================
# 11. EMBEDDINGS + HDBSCAN
# ============================================================

def build_embedding_text(a: dict) -> str:
    """
    Texto más corto para embeddings.
    Evita usar el cuerpo completo, porque puede diluir el tema central.
    """
    parts = [
        a.get("title", ""),
        a.get("subtitle", ""),
        a.get("lead", ""),
        a.get("ai_summary", ""),
    ]

    txt = clean(" ".join(str(p) for p in parts if p))

    # Respaldo si no hay título/subtítulo/resumen.
    if not txt:
        txt = clean(a.get("classification_text", ""))

    # Evita textos excesivamente largos para clustering.
    return txt[:1200]




# ============================================================
# 12. SALIDA AUDITABLE
# ============================================================

def sample_records(records_source: list[dict], limit: int = 20) -> list[dict]:
    samples = []

    for r in records_source[:limit]:
        a = r["article"]
        info = r["family_info"]

        samples.append({
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "published_date": a.get("published_date", ""),
            "main_section": a.get("main_section", ""),
            "url": a.get("url", ""),

            "strict_score": info["strict_score"],
            "political_score": info["political_score"],
            "geopolitical_score": info["geopolitical_score"],
            "social_noise_score": info["social_noise_score"],

            "market_hits": info["market_hits"],
            "fiscal_hits": info["fiscal_hits"],
            "company_hits": info["company_hits"],
            "commodity_hits": info["commodity_hits"],
            "political_hits": info["political_hits"],
            "geopolitical_hits": info["geopolitical_hits"],
            "social_noise_hits": info["social_noise_hits"],

            "ambiguous_market_hits": info.get("ambiguous_market_hits", []),
            "amount_hits": info.get("amount_hits", []),
            "energy_context_hits": info.get("energy_context_hits", []),
            "has_market_context": info.get("has_market_context", False),
            "has_amount_context": info.get("has_amount_context", False),
            "has_energy_market_context": info.get("has_energy_market_context", False),
            "has_geopolitical_market_context": info.get("has_geopolitical_market_context", False),
            "has_geopolitical_gas_context": info.get("has_geopolitical_gas_context", False),
            "geopolitical_gas_strong_context_hits": info.get("geopolitical_gas_strong_context_hits", []),
            "geopolitical_gas_weak_context_hits": info.get("geopolitical_gas_weak_context_hits", []),
            "geopolitical_hard_event_hits": info.get("geopolitical_hard_event_hits", []),
            "geopolitical_direct_context_hits": info.get("geopolitical_direct_context_hits", []),
            "geopolitical_support_context_hits": info.get("geopolitical_support_context_hits", []),
        })

    return samples



def make_json_serializable(obj):
    """
    Convierte tipos de numpy/pandas/sklearn a tipos nativos de Python
    para que puedan guardarse con json.dump().
    """
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, tuple):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, set):
        return [make_json_serializable(v) for v in sorted(obj)]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if obj is None:
        return None

    return obj


def main() -> None:
    # ============================================================
    # 5. CARGA Y CONSTRUCCIÓN DE TEXTOS
    # ============================================================

    data = json.load(open("noticias_unificadas.txt", encoding="utf-8"))
    articles = data["articles"] if isinstance(data, dict) else data

    # ============================================================
    # 7. REGISTROS POR FAMILIA
    # ============================================================

    records, record_stats = build_records_parallel(
        articles,
        max_workers=DEFAULT_RECORD_WORKERS,
        log_every=RECORD_LOG_EVERY,
        chunksize=RECORD_CHUNKSIZE,
    )

    texts = [r["text"] for r in records]

    financial_strict_records = [
        r for r in records
        if r["family_info"]["is_financial_strict"]
           and not r["family_info"]["is_social_noise_dominant"]
    ]

    political_risk_records = [
        r for r in records
        if r["family_info"]["is_political_risk"]
           and not r["family_info"]["is_social_noise_dominant"]
    ]

    geopolitical_market_records = [
        r for r in records
        if r["family_info"]["is_geopolitical_market"]
           and not r["family_info"]["is_social_noise_dominant"]
    ]

    financial_texts = [r["text"] for r in financial_strict_records]
    political_risk_texts = [r["text"] for r in political_risk_records]
    geopolitical_market_texts = [r["text"] for r in geopolitical_market_records]

    print(f"Textos generales usados: {len(texts)}")
    print(f"Textos financieros estrictos: {len(financial_texts)}")
    print(f"Textos riesgo político: {len(political_risk_texts)}")
    print(f"Textos geopolíticos con mercado: {len(geopolitical_market_texts)}")

    ### 8 ####
    financial_ngrams_top = extract_ngrams(financial_texts, min_df=3)
    political_risk_ngrams_top = extract_ngrams(political_risk_texts, min_df=3)
    geopolitical_market_ngrams_top = extract_ngrams(geopolitical_market_texts, min_df=3)

    financial_tfidf_top = extract_tfidf(financial_texts, min_df=3)
    political_risk_tfidf_top = extract_tfidf(political_risk_texts, min_df=3)
    geopolitical_market_tfidf_top = extract_tfidf(geopolitical_market_texts, min_df=3)

    ngrams_top = extract_ngrams(texts, min_df=5)
    tfidf_top = extract_tfidf(texts, min_df=3)

    #### 9 ####
    kw = yake.KeywordExtractor(lan="es", n=3, top=20)
    yake_scores = Counter()

    for txt in texts:
        for term, score in kw.extract_keywords(txt):
            term = clean(term)

            if is_bad_candidate_term(term):
                continue

            yake_scores[term] += (1.0 / (score + 1e-9))

    yake_top = yake_scores.most_common(1000)

    ### 10 - Normalize ###
    nlp = spacy.load("es_core_news_lg")
    ents = Counter()

    for doc in nlp.pipe(texts, batch_size=32):
        for e in doc.ents:
            ent_text = normalize_entity_text(e.text)

            if not ent_text or ent_text in ENTITY_STOP:
                continue

            if len(ent_text) < 3:
                continue

            if e.label_ in {"ORG", "PER", "LOC", "MISC"}:
                ents[(ent_text, e.label_)] += 1


    ### 11 Embeding ###
    embedding_articles = []
    embedding_texts = []

    for a in articles:
        if not should_use_for_financial_dictionary(a):
            continue

        txt = build_embedding_text(a)

        if txt and len(txt.split()) >= 5:
            embedding_articles.append(a)
            embedding_texts.append(txt)

    if embedding_texts:
        model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        emb = model.encode(
            embedding_texts,
            show_progress_bar=True,
            normalize_embeddings=True,
            batch_size=64,
        )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=15,
            min_samples=5,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=False,
        )

        labels = clusterer.fit_predict(emb)

    else:
        emb = np.array([])
        labels = np.array([])

    cluster_examples = defaultdict(list)

    if len(labels):
        for label, article, txt in zip(labels, embedding_articles, embedding_texts):
            label = str(label)

            if len(cluster_examples[label]) >= 10:
                continue

            cluster_examples[label].append({
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "published_date": article.get("published_date", ""),
                "main_section": article.get("main_section", ""),
                "url": article.get("url", ""),
                "text_preview": txt[:300],
            })

    #### 12 OUT ###
    out = {
        "metadata": {
            "articles_total": len(articles),
            "texts_general_count": len(texts),
            "financial_strict_count": len(financial_texts),
            "political_risk_count": len(political_risk_texts),
            "geopolitical_market_count": len(geopolitical_market_texts),
            "stopwords_count": len(STOP),
            "record_processing_stats": dict(record_stats),
            "record_workers": DEFAULT_RECORD_WORKERS,
            "record_chunksize": RECORD_CHUNKSIZE,
        },

        "general": {
            "ngrams_top": ngrams_top[:300],
            "tfidf_top": tfidf_top[:300],
            "yake_top": yake_top[:300],
        },

        "financial_strict": {
            "count": len(financial_texts),
            "ngrams_top": financial_ngrams_top[:300],
            "tfidf_top": financial_tfidf_top[:300],
            "samples": sample_records(financial_strict_records, limit=20),
        },

        "political_risk": {
            "count": len(political_risk_texts),
            "ngrams_top": political_risk_ngrams_top[:300],
            "tfidf_top": political_risk_tfidf_top[:300],
            "samples": sample_records(political_risk_records, limit=20),
        },

        "geopolitical_market": {
            "count": len(geopolitical_market_texts),
            "ngrams_top": geopolitical_market_ngrams_top[:300],
            "tfidf_top": geopolitical_market_tfidf_top[:300],
            "samples": sample_records(geopolitical_market_records, limit=20),
        },

        "entities_top": [
            {"text": k[0], "label": k[1], "count": v}
            for k, v in ents.most_common(300)
        ],

        "clusters": Counter(labels.tolist()) if len(labels) else {},
        "cluster_examples": dict(cluster_examples),
    }

    out_serializable = make_json_serializable(out)

    with open("candidatos_diccionario.json", "w", encoding="utf-8") as f:
        json.dump(out_serializable, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()