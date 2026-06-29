from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from el_animal_fm.news.application.shared.dictionary_matching import normalize_for_match, strip_accents
from el_animal_fm.news.application.enrichment.enrichment_config import FAMILIES
from el_animal_fm.news.application.enrichment.enrichment_dictionaries import TermEntry
from el_animal_fm.news.application.enrichment.enrichment_text import build_classification_text, get_article_raw


def parse_published_date(raw: dict[str, Any]) -> str:
    return str(raw.get("published_date") or raw.get("date") or "")


def parse_published_time(raw: dict[str, Any]) -> str:
    return str(raw.get("published_time") or "")


def temporal_features(raw: dict[str, Any]) -> dict[str, Any]:
    published_date = parse_published_date(raw)
    published_time = parse_published_time(raw)
    out = {
        "published_date": published_date,
        "published_time": published_time,
        "published_hour": None,
        "published_weekday": None,
        "is_weekend": None,
    }
    try:
        if published_date:
            dt_date = datetime.strptime(published_date, "%Y-%m-%d").date()
            out["published_weekday"] = dt_date.weekday()
            out["is_weekend"] = dt_date.weekday() >= 5
        if published_time:
            out["published_hour"] = int(str(published_time).split(":")[0])
    except Exception:
        pass
    return out


def match_family(text: str, family: str, compiled: dict[str, list[tuple[TermEntry, re.Pattern]]]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    score = 0.0
    for entry, pattern in compiled.get(family, []):
        matches = pattern.findall(text)
        if not matches:
            continue
        occurrences = len(matches)
        contribution = float(entry.weight) * math.log1p(occurrences)
        score += contribution
        hits.append({
            "term": normalize_for_match(entry.term),
            "raw_term": entry.term,
            "weight": entry.weight,
            "occurrences": occurrences,
            "score": round(contribution, 4),
            "source": entry.source,
        })
    hits = sorted(hits, key=lambda x: x["score"], reverse=True)
    return {
        "active": score >= 1.0,
        "score": round(score, 4),
        "hit_count": len(hits),
        "hits": [h["term"] for h in hits],
        "hit_details": hits[:50],
    }


def source_section_flags(raw: dict[str, Any]) -> dict[str, bool]:
    section_text = normalize_for_match(" ".join(str(raw.get(k, "")) for k in [
        "source", "main_section", "subsection", "site_vertical", "article_type_editorial", "breadcrumb_raw",
    ]))
    return {
        "section_economy": any(x in section_text for x in ["economia", "mercados", "market"]),
        "section_politics": any(x in section_text for x in ["pais", "nacional", "politica", "opinion"]),
        "section_world": any(x in section_text for x in ["mundo", "internacional"]),
        "section_sports": any(x in section_text for x in ["deportes", "futbol"]),
        "section_entertainment": any(x in section_text for x in ["espectaculos", "tv", "cultura", "braga"]),
        "section_police": any(x in section_text for x in ["policial", "tribunales"]),
    }


def general_classification(families: dict[str, dict[str, Any]], raw: dict[str, Any]) -> dict[str, bool]:
    flags = source_section_flags(raw)
    is_economic_news = (
        families["macro_fiscal"]["active"]
        or families["mercado_financiero"]["active"]
        or families["energia_commodities"]["active"]
        or families["empresas_instituciones"]["active"]
        or flags["section_economy"]
    )
    is_political_news = families["politico_regulatorio"]["active"] or flags["section_politics"]
    is_geopolitical_news = families["geopolitico_mercado"]["active"] or flags["section_world"]
    is_company_news = families["empresas_instituciones"]["active"]
    is_market_news = families["mercado_financiero"]["active"]
    is_energy_news = families["energia_commodities"]["active"]
    is_sports_or_entertainment_news = flags["section_sports"] or flags["section_entertainment"]
    is_crime_or_police_news = flags["section_police"] or families["ruido_social"]["active"]
    is_social_noise = (
        (is_sports_or_entertainment_news or is_crime_or_police_news)
        and not is_economic_news
        and not families["geopolitico_mercado"]["active"]
    )
    return {
        "is_economic_news": bool(is_economic_news),
        "is_political_news": bool(is_political_news),
        "is_geopolitical_news": bool(is_geopolitical_news),
        "is_company_news": bool(is_company_news),
        "is_market_news": bool(is_market_news),
        "is_energy_news": bool(is_energy_news),
        "is_social_noise": bool(is_social_noise),
        "is_crime_or_police_news": bool(is_crime_or_police_news),
        "is_sports_or_entertainment_news": bool(is_sports_or_entertainment_news),
    }


def score_to_unit(value: float, denominator: float = 18.0) -> float:
    return round(min(1.0, max(0.0, value / denominator)), 4)


def impact_features(families: dict[str, dict[str, Any]], classification: dict[str, bool]) -> dict[str, Any]:
    weighted_raw = (
        families["macro_fiscal"]["score"] * 0.20
        + families["mercado_financiero"]["score"] * 0.30
        + families["energia_commodities"]["score"] * 0.25
        + families["empresas_instituciones"]["score"] * 0.20
        + families["politico_regulatorio"]["score"] * 0.15
        + families["geopolitico_mercado"]["score"] * 0.30
        + families["riesgo_alerta"]["score"] * 0.20
    )
    market_impact_score = score_to_unit(weighted_raw, denominator=18.0)
    positive = families["sentimiento_positivo"]["score"]
    negative = families["sentimiento_negativo"]["score"]
    risk = families["riesgo_alerta"]["score"]
    geopolitical = families["geopolitico_mercado"]["score"]
    if positive == 0 and negative == 0:
        direction = "unknown"
    elif abs(positive - negative) < 0.75:
        direction = "mixed"
    elif positive > negative:
        direction = "positive"
    else:
        direction = "negative"
    volatility_signal = negative + risk + geopolitical + families["energia_commodities"]["score"] * 0.5
    if volatility_signal >= 4:
        volatility_effect = "increase"
    elif market_impact_score < 0.15:
        volatility_effect = "neutral"
    else:
        volatility_effect = "unknown"
    if families["geopolitico_mercado"]["active"] or families["mercado_financiero"]["active"]:
        horizon = "short_term"
    elif families["macro_fiscal"]["active"] or families["politico_regulatorio"]["active"]:
        horizon = "medium_term"
    elif market_impact_score >= 0.25:
        horizon = "short_term"
    else:
        horizon = "unknown"
    market_impact_candidate = (
        market_impact_score >= 0.20
        or classification["is_economic_news"]
        or families["geopolitico_mercado"]["active"]
    )
    confidence = market_impact_score
    if classification["is_social_noise"]:
        confidence = min(confidence, 0.25)
    return {
        "market_impact_candidate": bool(market_impact_candidate),
        "market_impact_score": market_impact_score,
        "expected_impact_direction": direction,
        "expected_impact_horizon": horizon,
        "expected_volatility_effect": volatility_effect,
        "risk_score": score_to_unit(risk, denominator=10.0),
        "uncertainty_score": score_to_unit(risk + geopolitical, denominator=14.0),
        "confidence": round(confidence, 4),
    }


def collect_entities_from_hits(families: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entity_terms = set()
    for family in ["empresas_instituciones", "geopolitico_mercado", "mercado_financiero"]:
        for term in families.get(family, {}).get("hits", []):
            entity_terms.add(term)
    entity_terms = sorted(entity_terms)
    joined = " ".join(entity_terms)
    return {
        "entities_relevant_terms": entity_terms,
        "has_banco_central": "banco_central" in entity_terms,
        "has_hacienda": "hacienda" in entity_terms or "ministerio_de_hacienda" in entity_terms,
        "has_cmf": "cmf" in entity_terms,
        "has_codelco": "codelco" in entity_terms,
        "has_enap": "enap" in entity_terms,
        "has_sqm": "sqm" in entity_terms,
        "has_china": "china" in entity_terms,
        "has_estados_unidos": "estados_unidos" in entity_terms,
        "has_donald_trump": "donald_trump" in entity_terms,
        "has_iran": "iran" in entity_terms or "iran" in strip_accents(joined),
        "has_rusia": "rusia" in entity_terms,
        "has_ucrania": "ucrania" in entity_terms,
    }


def build_classification_reason(active_families: list[str], families: dict[str, dict[str, Any]], impact: dict[str, Any]) -> str:
    if not active_families:
        return "No se detectaron familias relevantes con el diccionario actual."
    fragments = []
    for family in active_families:
        hits = families[family].get("hits", [])[:5]
        fragments.append(f"{family}: {', '.join(hits)}" if hits else family)
    return "Familias activas: " + " | ".join(fragments) + f" | market_impact_score={impact.get('market_impact_score')}"


def enrich_article(article: dict[str, Any], compiled: dict[str, list[tuple[TermEntry, re.Pattern]]], dictionary_version: str) -> dict[str, Any]:
    raw = get_article_raw(article)
    text = build_classification_text(article)
    family_features = {family: match_family(text, family, compiled) for family in FAMILIES}
    classification = general_classification(family_features, raw)
    impact = impact_features(family_features, classification)
    entities = collect_entities_from_hits(family_features)
    temporal = temporal_features(raw)
    matched_terms_all = sorted({term for family_data in family_features.values() for term in family_data.get("hits", [])})
    active_families = [family for family, data in family_features.items() if data.get("active")]
    enriched = dict(article)
    enriched["features"] = {
        "dictionary_version": dictionary_version,
        "families": family_features,
        "general_classification": classification,
        "impact": impact,
        "entities": entities,
        "temporal": temporal,
        "audit": {
            "active_families": active_families,
            "matched_terms_all": matched_terms_all,
            "matched_terms_count": len(matched_terms_all),
            "classification_text_length": len(text),
            "classification_reason": build_classification_reason(active_families, family_features, impact),
        },
    }
    return enriched
