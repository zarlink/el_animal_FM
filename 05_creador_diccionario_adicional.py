import html
import json
import re
import unicodedata
from collections import Counter

import hdbscan
import numpy as np
import spacy
import yake
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from spacy.lang.es.stop_words import STOP_WORDS as SPACY_STOPWORDS

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

    # Adicionales
    "personas", "país", "chile", "región", "nacional",
    "información", "comunidad", "vida", "proceso", "clave",
    "zona", "mundo", "sistema", "centro", "especialmente",
    "antecedentes", "pese", "personal", "finalmente",
    "asimismo", "objetivo", "principal", "actualmente",
    "distintos", "distintas", "sentido", "presencia",
    "importantes", "base", "ejemplo", "fecha", "sitio",
    "com", "twitter", "pic", "the", "may","súmate", "sumate",
    "informado", "precisas", "seguimiento", "detallado",
    "entrevistas", "personajes", "influyen",
    "comunidad", "súmate", "sumate",
    "informado", "precisas", "seguimiento", "detallado",
    "entrevistas", "personajes", "influyen",
    "comunidad","súmate", "sumate","política políticas",
}


STOP = set(SPACY_STOPWORDS) | CUSTOM_STOPWORDS

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
    "acciones",
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
    "energía",
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
    "cmf",
    "mercado financiero",
    "renta fija",
    "renta variable",
    "bolsa",
    "acciones",
    "bonos",
    "wall street",
    "dólar",
    "dolares",
    "dólares",
    "tipo de cambio",
    "tasa de interés",
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
    "energía",
    "energia",
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

def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)

    text = unicodedata.normalize("NFKC", text).lower()

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
        r"súmate\s+(?:a\s+)?(?:nuestra\s+)?(?:comunidad\s+)?informado\s+precisas\s+seguimiento\s+detallado\s+políticas\s+públicas\s+entrevistas\s+personajes\s+influyen",
        r"súmate\s+informado\s+precisas",
        r"política\s+súmate\s+informado",
        r"informado\s+precisas\s+seguimiento",
        r"seguimiento\s+detallado\s+políticas",
        r"políticas\s+públicas\s+entrevistas",
        r"entrevistas\s+personajes\s+influyen",

    ]

    for pattern in boilerplate_patterns:
        text = re.sub(pattern, " ", text, flags=re.I)

    # Esto elimina frases parciales que quedan aunque el regex anterior no capture el bloque completo.
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
    text = re.sub(rf"\b\d{{1,2}}\s+({meses})\s+\d{{4}}\b", " ", text)
    text = re.sub(rf"\b({meses})\s+\d{{4}}\b", " ", text)

    # Mantiene letras, números, %, $, guiones y puntos.
    text = re.sub(r"[^a-záéíóúñü0-9%$/\-\.\s]", " ", text)

    # Elimina números sueltos, pero deja porcentajes o montos si vienen unidos.
    text = re.sub(r"\b\d+\b", " ", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text

data = json.load(open("noticias_unificadas.txt", encoding="utf-8"))
articles = data["articles"] if isinstance(data, dict) else data

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

WORD_CHARS = "a-záéíóúñü0-9"


def contains_seed(text: str, seed: str) -> bool:
    """
    Busca una semilla como término o frase completa.
    Evita matches demasiado accidentales.
    """
    seed = clean(seed)

    if not seed:
        return False

    pattern = rf"(?<![{WORD_CHARS}]){re.escape(seed)}(?![{WORD_CHARS}])"
    return re.search(pattern, text) is not None


def seed_hits(text: str, seeds: set[str]) -> set[str]:
    """
    Devuelve las semillas encontradas en el texto.
    """
    text = clean(text)
    return {seed for seed in seeds if contains_seed(text, seed)}

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

    strict_score = (
        len(market_hits) * 3
        + len(fiscal_hits) * 3
        + len(company_hits) * 3
        + len(commodity_hits) * 3
    )

    political_score = len(political_hits)
    geopolitical_score = len(geopolitical_hits)
    social_noise_score = len(social_noise_hits)

    is_financial_strict = strict_score >= 3

    is_political_risk = (
        political_score >= 2
        and (
            len(fiscal_hits) > 0
            or len(market_hits) > 0
            or len(company_hits) > 0
            or len(commodity_hits) > 0
        )
    )

    is_geopolitical_market = (
        geopolitical_score >= 1
        and (
            len(market_hits) > 0
            or len(commodity_hits) > 0
            or "aranceles" in text
            or "petróleo" in text
            or "petroleo" in text
            or "dólar" in text
            or "dolar" in text
        )
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
    }


def has_financial_seed(text: str) -> bool:
    """
    Mantengo esta función por compatibilidad,
    pero ahora significa financiero estricto.
    """
    info = classify_text_families(text)
    return info["is_financial_strict"]


records = []

for a in articles:
    if not should_use_for_financial_dictionary(a):
        continue

    txt = build_dictionary_text(a)

    if not txt:
        continue

    family_info = classify_text_families(txt)

    records.append({
        "article": a,
        "text": txt,
        "family_info": family_info,
    })

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

def extract_ngrams(texts_source: list[str], min_df: int = 5) -> list[dict]:
    if not texts_source:
        return []

    cv = CountVectorizer(
        ngram_range=(1, 3),
        min_df=min_df,
        max_df=0.6,
        stop_words=list(STOP),
        token_pattern=r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9\-]{2,}\b"
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
        token_pattern=r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9\-]{2,}\b",
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


financial_ngrams_top = extract_ngrams(financial_texts, min_df=3)
political_risk_ngrams_top = extract_ngrams(political_risk_texts, min_df=3)
geopolitical_market_ngrams_top = extract_ngrams(geopolitical_market_texts, min_df=3)
financial_tfidf_top = extract_tfidf(financial_texts, min_df=3)
political_risk_tfidf_top = extract_tfidf(political_risk_texts, min_df=3)
geopolitical_market_tfidf_top = extract_tfidf(geopolitical_market_texts, min_df=3)

# n-gramas
cv = CountVectorizer(ngram_range=(1,3), min_df=5,max_df=0.6,
                     stop_words=list(STOP), token_pattern=r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9\-]{2,}\b")
X = cv.fit_transform(texts)

term_counts = X.sum(axis=0).A1
doc_freq = (X > 0).sum(axis=0).A1
terms = cv.get_feature_names_out()

ngrams_top = sorted(
    [
        {
            "term": term,
            "count": int(count),
            "df": int(df),
            "df_pct": float(df / len(texts)),
        }
        for term, count, df in zip(terms, term_counts, doc_freq)
    ],
    key=lambda x: (x["df"], x["count"]),
    reverse=True
)[:2000]

# TF-IDF
tfv = TfidfVectorizer(ngram_range=(1,3),
                      min_df=3,
                      max_df=0.6,
                      stop_words=list(STOP),
                      token_pattern=r"(?u)\b[a-záéíóúñü][a-záéíóúñü0-9\-]{2,}\b",
                      sublinear_tf=True)

T = tfv.fit_transform(texts)
tfidf_mean = T.mean(axis=0).A1
tfidf_top = sorted(zip(tfv.get_feature_names_out(), tfidf_mean), key=lambda x: x[1], reverse=True)[:2000]

# YAKE
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

kw = yake.KeywordExtractor(lan="es", n=3, top=20)
yake_scores = Counter()

for txt in texts:
    for term, score in kw.extract_keywords(txt):
        term = clean(term)

        if is_bad_candidate_term(term):
            continue

        yake_scores[term] += (1.0 / (score + 1e-9))

yake_top = yake_scores.most_common(1000)

# NER
ENTITY_STOP = {
    "chile", "santiago", "valparaíso", "concepción",
    "lunes", "martes", "miércoles", "jueves", "viernes",
    "mayo", "abril", "junio",
    "bío bío", "bio bio", "el mostrador"
}

nlp = spacy.load("es_core_news_lg")
ents = Counter()
for doc in nlp.pipe(texts, batch_size=32):
    for e in doc.ents:
        ent_text = clean(e.text)

        if not ent_text or ent_text in ENTITY_STOP:
            continue

        if len(ent_text) < 3:
            continue

        if e.label_ in {"ORG", "PER", "LOC", "MISC"}:
            ents[(ent_text, e.label_)] += 1

# Embeddings + clustering
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


embedding_articles = []
embedding_texts = []

for a in articles:
    # Si ya agregaste esta función, úsala.
    # Sirve para excluir deportes, cultura, multimedia, opinión, cartas, etc.
    if "should_use_for_financial_dictionary" in globals():
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

#Test de salida
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
            "market_hits": info["market_hits"],
            "fiscal_hits": info["fiscal_hits"],
            "company_hits": info["company_hits"],
            "commodity_hits": info["commodity_hits"],
            "political_hits": info["political_hits"],
            "geopolitical_hits": info["geopolitical_hits"],
        })

    return samples

# Salida
out = {
    "metadata": {
        "articles_total": len(articles),
        "texts_general_count": len(texts),
        "financial_strict_count": len(financial_texts),
        "political_risk_count": len(political_risk_texts),
        "geopolitical_market_count": len(geopolitical_market_texts),
        "stopwords_count": len(STOP),
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
}


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

out_serializable = make_json_serializable(out)

with open("candidatos_diccionario.json", "w", encoding="utf-8") as f:
    json.dump(out_serializable, f, ensure_ascii=False, indent=2)