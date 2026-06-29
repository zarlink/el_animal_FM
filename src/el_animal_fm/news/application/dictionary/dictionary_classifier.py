from __future__ import annotations

import re

from el_animal_fm.news.application.dictionary.dictionary_config import (
    AMBIGUOUS_MARKET_SEEDS,
    AMOUNT_CONTEXT_SEEDS,
    AMOUNT_SEEDS,
    COMMODITY_STRICT_SEEDS,
    ENERGY_CONTEXT_SEEDS,
    FISCAL_STRICT_SEEDS,
    GAS_GEOPOLITICAL_STRONG_CONTEXT_SEEDS,
    GAS_GEOPOLITICAL_WEAK_CONTEXT_SEEDS,
    GEOPOLITICAL_HARD_EVENT_SEEDS,
    GEOPOLITICAL_MARKET_DIRECT_CONTEXT_SEEDS,
    GEOPOLITICAL_MARKET_SUPPORT_CONTEXT_SEEDS,
    GEOPOLITICAL_RISK_SEEDS,
    MARKET_CONTEXT_SEEDS,
    MARKET_STRICT_SEEDS,
    COMPANY_STRICT_SEEDS,
    POLITICAL_RISK_SEEDS,
    SOCIAL_SECURITY_NOISE_SEEDS,
)
from el_animal_fm.news.application.dictionary.dictionary_text import clean


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

    strong_context_hits = seed_hits(text, AMOUNT_CONTEXT_SEEDS)

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
