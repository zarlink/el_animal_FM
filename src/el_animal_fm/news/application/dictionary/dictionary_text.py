from __future__ import annotations

import html
import re
import unicodedata

from el_animal_fm.news.application.dictionary.dictionary_config import PHRASE_NORMALIZATIONS


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
