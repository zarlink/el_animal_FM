from __future__ import annotations

import os
from functools import cache


DEFAULT_INPUT_PATH = "noticias_unificadas.txt"
DEFAULT_OUTPUT_PATH = "candidatos_diccionario.json"

DEFAULT_RECORD_WORKERS = max(1, min(os.cpu_count() or 1, 12))
RECORD_LOG_EVERY = 250
RECORD_CHUNKSIZE = 25

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

@cache
def get_stopwords() -> set[str]:
    from spacy.lang.es.stop_words import STOP_WORDS as spacy_stopwords

    return set(spacy_stopwords) | CUSTOM_STOPWORDS

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

TOKEN_PATTERN = r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9_\-]{2,}\b"

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
