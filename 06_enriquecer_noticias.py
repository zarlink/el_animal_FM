#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
enriquecer_noticias.py

Recorre carpetas diarias de noticias descargadas desde BioBioChile y El Mostrador,
lee `noticias_dia.txt`, aplica diccionarios temáticos y genera un archivo enriquecido
por día, sin destruir el archivo original.

Entrada esperada:
    biobio/DD_MM_YYYY/noticias_dia.txt
    mostrador/DD_MM_YYYY/noticias_dia.txt
    diccionarios/*.json | *.txt
    candidatos_diccionario.json

Salida por día:
    biobio/DD_MM_YYYY/noticias_dia_enriquecidas.txt
    mostrador/DD_MM_YYYY/noticias_dia_enriquecidas.txt
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_SOURCES = ("biobio", "mostrador")
DEFAULT_INPUT_NAME = "noticias_dia.txt"
DEFAULT_OUTPUT_NAME = "noticias_dia_enriquecidas.txt"
DEFAULT_DICTIONARY_DIR = "diccionarios"
DEFAULT_CANDIDATES_FILE = "candidatos_diccionario.json"
DEFAULT_DICTIONARY_VERSION = "heuristic_v1"

DATE_FOLDER_RE = re.compile(r"^\d{2}_\d{2}_\d{4}$")

FAMILIES = [
    "macro_fiscal",
    "mercado_financiero",
    "energia_commodities",
    "empresas_instituciones",
    "politico_regulatorio",
    "geopolitico_mercado",
    "riesgo_alerta",
    "sentimiento_positivo",
    "sentimiento_negativo",
    "ruido_social",
]

FAMILY_ALIASES = {
    "macro_fiscal": "macro_fiscal",
    "fiscal": "macro_fiscal",
    "hacienda": "macro_fiscal",
    "presupuesto": "macro_fiscal",

    "mercado_financiero": "mercado_financiero",
    "mercado": "mercado_financiero",
    "financial": "mercado_financiero",
    "financial_strict": "mercado_financiero",
    "bolsa": "mercado_financiero",

    "energia_commodities": "energia_commodities",
    "energia": "energia_commodities",
    "commodities": "energia_commodities",
    "commodity": "energia_commodities",
    "petroleo": "energia_commodities",
    "petróleo": "energia_commodities",

    "empresas_instituciones": "empresas_instituciones",
    "empresas": "empresas_instituciones",
    "instituciones": "empresas_instituciones",
    "companies": "empresas_instituciones",
    "company": "empresas_instituciones",

    "politico_regulatorio": "politico_regulatorio",
    "political": "politico_regulatorio",
    "political_risk": "politico_regulatorio",
    "regulatorio": "politico_regulatorio",
    "regulacion": "politico_regulatorio",
    "regulación": "politico_regulatorio",

    "geopolitico_mercado": "geopolitico_mercado",
    "geopolitico": "geopolitico_mercado",
    "geopolítico": "geopolitico_mercado",
    "geopolitical": "geopolitico_mercado",
    "geopolitical_market": "geopolitico_mercado",

    "riesgo_alerta": "riesgo_alerta",
    "riesgo": "riesgo_alerta",
    "alerta": "riesgo_alerta",
    "risk": "riesgo_alerta",

    "sentimiento_positivo": "sentimiento_positivo",
    "positivo": "sentimiento_positivo",
    "positive": "sentimiento_positivo",

    "sentimiento_negativo": "sentimiento_negativo",
    "negativo": "sentimiento_negativo",
    "negative": "sentimiento_negativo",

    "ruido_social": "ruido_social",
    "noise": "ruido_social",
    "social_noise": "ruido_social",
}

GENERIC_CANDIDATE_STOPWORDS = {
    "gobierno", "presidente", "ministro", "autoridades", "sector", "público", "pública",
    "millones", "mil", "trabajo", "seguridad", "investigación", "salud", "ministerio",
    "desarrollo", "social", "sociales", "casos", "casa", "grupo", "relación", "datos",
    "alto", "alta", "falta", "jefe", "local", "regional", "comuna", "servicio",
    "servicios", "personas", "persona", "hechos", "inicio", "causa", "cargo", "plan",
    "resultados", "problemas", "jornada", "equipo", "ciudad", "tribunal", "informe",
    "gestión", "organización", "defensa", "justicia", "declaraciones", "partido",
}

PHRASE_NORMALIZATIONS = {
    "ee.uu.": "estados_unidos",
    "eeuu": "estados_unidos",
    "estados unidos": "estados_unidos",
    "donald trump": "donald_trump",
    "josé antonio kast": "jose_antonio_kast",
    "jose antonio kast": "jose_antonio_kast",
    "banco central": "banco_central",
    "ministerio de hacienda": "ministerio_de_hacienda",
    "ministro de hacienda": "ministro_de_hacienda",
    "tipo de cambio": "tipo_de_cambio",
    "tasa de interés": "tasa_de_interes",
    "tasa de interes": "tasa_de_interes",
    "renta fija": "renta_fija",
    "renta variable": "renta_variable",
    "wall street": "wall_street",
    "estrecho de ormuz": "estrecho_de_ormuz",
    "política fiscal": "politica_fiscal",
    "politica fiscal": "politica_fiscal",
    "déficit fiscal": "deficit_fiscal",
    "deficit fiscal": "deficit_fiscal",
    "gasto fiscal": "gasto_fiscal",
    "subsidio eléctrico": "subsidio_electrico",
    "subsidio electrico": "subsidio_electrico",
}

DEFAULT_SEED_TERMS = {
    "macro_fiscal": {
        "hacienda": 2.0,
        "ministerio_de_hacienda": 2.5,
        "presupuesto": 2.0,
        "deficit_fiscal": 2.5,
        "gasto_fiscal": 2.0,
        "politica_fiscal": 2.0,
        "subsidio": 1.3,
        "subsidio_electrico": 2.0,
        "impuestos": 2.0,
        "reforma tributaria": 2.5,
        "deuda pública": 2.0,
        "deuda publica": 2.0,
        "sueldo mínimo": 1.7,
        "sueldo minimo": 1.7,
    },
    "mercado_financiero": {
        "banco_central": 3.0,
        "cmf": 2.5,
        "dólar": 2.5,
        "dolar": 2.5,
        "tipo_de_cambio": 3.0,
        "tasa_de_interes": 2.5,
        "ipc": 2.0,
        "inflación": 2.5,
        "inflacion": 2.5,
        "imacec": 2.5,
        "bolsa": 2.0,
        "wall_street": 2.5,
        "renta_fija": 2.5,
        "renta_variable": 2.5,
        "bonos": 2.0,
        "acciones": 1.5,
        "mercado_financiero": 2.5,
    },
    "energia_commodities": {
        "petróleo": 3.0,
        "petroleo": 3.0,
        "cobre": 2.8,
        "litio": 2.5,
        "gas": 1.5,
        "combustibles": 2.0,
        "bencina": 1.7,
        "diésel": 1.7,
        "diesel": 1.7,
        "electricidad": 1.8,
        "tarifas eléctricas": 2.0,
        "tarifas electricas": 2.0,
        "enap": 2.5,
        "codelco": 2.5,
        "sqm": 2.2,
        "opep": 2.5,
    },
    "empresas_instituciones": {
        "codelco": 2.5,
        "enap": 2.3,
        "sqm": 2.3,
        "cap": 1.8,
        "copec": 2.0,
        "falabella": 2.0,
        "cencosud": 2.0,
        "banco de chile": 2.0,
        "bci": 2.0,
        "itau": 2.0,
        "itaú": 2.0,
        "cmf": 2.0,
        "banco_central": 2.0,
    },
    "politico_regulatorio": {
        "proyecto de ley": 2.0,
        "proyecto_de_ley": 2.0,
        "congreso": 2.0,
        "senado": 1.8,
        "cámara": 1.8,
        "camara": 1.8,
        "regulación": 2.0,
        "regulacion": 2.0,
        "reforma": 1.7,
        "ley": 1.2,
        "gobierno": 1.0,
        "ejecutivo": 1.0,
        "hacienda": 1.5,
        "presupuesto": 1.5,
    },
    "geopolitico_mercado": {
        "irán": 2.8,
        "iran": 2.8,
        "israel": 2.0,
        "rusia": 2.5,
        "ucrania": 2.5,
        "china": 2.0,
        "estados_unidos": 1.8,
        "donald_trump": 1.8,
        "guerra": 1.2,
        "conflicto": 1.0,
        "estrecho_de_ormuz": 3.0,
        "aranceles": 2.5,
        "sanciones económicas": 2.3,
        "sanciones economicas": 2.3,
        "sanciones financieras": 2.3,
        "exportaciones": 1.5,
        "importaciones": 1.5,
        "cadena de suministro": 2.0,
    },
    "riesgo_alerta": {
        "riesgo": 1.5,
        "crisis": 2.0,
        "alerta": 1.7,
        "incertidumbre": 2.0,
        "caída": 1.8,
        "caida": 1.8,
        "desplome": 2.5,
        "recesión": 2.5,
        "recesion": 2.5,
        "conflicto": 1.5,
        "ataque": 1.5,
        "emergencia": 1.5,
        "quiebra": 2.5,
    },
    "sentimiento_positivo": {
        "crecimiento": 1.5,
        "alza": 1.2,
        "sube": 1.2,
        "recuperación": 1.5,
        "recuperacion": 1.5,
        "mejora": 1.5,
        "acuerdo": 1.2,
        "inversión": 1.4,
        "inversion": 1.4,
        "expansión": 1.5,
        "expansion": 1.5,
    },
    "sentimiento_negativo": {
        "caída": 1.5,
        "caida": 1.5,
        "baja": 1.2,
        "crisis": 1.8,
        "riesgo": 1.4,
        "incertidumbre": 1.8,
        "desaceleración": 1.8,
        "desaceleracion": 1.8,
        "pérdidas": 1.6,
        "perdidas": 1.6,
        "quiebra": 2.2,
        "déficit": 1.5,
        "deficit": 1.5,
    },
    "ruido_social": {
        "farándula": 1.5,
        "farandula": 1.5,
        "espectáculos": 1.5,
        "espectaculos": 1.5,
        "deportes": 1.5,
        "fútbol": 1.5,
        "futbol": 1.5,
        "policial": 1.0,
        "delito": 1.0,
        "detenido": 1.0,
        "música": 1.2,
        "musica": 1.2,
        "cine": 1.2,
    },
}


def parse_target_date(value: str | None) -> date:
    if not value:
        return datetime.now().date()
    value = value.strip()
    for fmt in ("%d_%m_%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato de fecha no reconocido. Usa DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD.")


def date_from_dir_name(value: str) -> date:
    return datetime.strptime(value, "%d_%m_%Y").date()


def build_date_range(end_date: date, days_count: int) -> set[date]:
    return {end_date - timedelta(days=i) for i in range(days_count)}


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def normalize_for_match(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKC", text).lower()
    for phrase, replacement in PHRASE_NORMALIZATIONS.items():
        text = text.replace(phrase, replacement)
    text = re.sub(r"\btrump\b", "donald_trump", text)
    text = re.sub(r"\bkast\b", "jose_antonio_kast", text)
    text = re.sub(r"\bdonald\s+donald_trump\b", "donald_trump", text)
    text = re.sub(r"\bjos[eé]\s+antonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    text = re.sub(r"\bantonio\s+jose_antonio_kast\b", "jose_antonio_kast", text)
    text = strip_accents(text)
    text = re.sub(r"[^a-z0-9_%$/\-\.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def term_to_pattern(term: str) -> re.Pattern:
    normalized = re.escape(normalize_for_match(term))
    normalized = normalized.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9_]){normalized}(?![a-z0-9_])", flags=re.I)


def safe_float(value: Any, default: float = 1.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


@dataclass
class TermEntry:
    term: str
    weight: float = 1.0
    source: str = ""


def canonical_family(value: str | None, fallback: str = "mercado_financiero") -> str:
    if not value:
        return fallback
    cleaned = normalize_for_match(value).replace("-", "_").replace(" ", "_")
    if cleaned in FAMILY_ALIASES:
        return FAMILY_ALIASES[cleaned]
    for key, family in FAMILY_ALIASES.items():
        if key in cleaned:
            return family
    if cleaned in FAMILIES:
        return cleaned
    return fallback


def add_term(dictionaries: dict[str, list[TermEntry]], family: str, term: Any, weight: Any = 1.0, source: str = "") -> None:
    if term is None:
        return
    term_str = str(term).strip()
    if not term_str:
        return
    normalized = normalize_for_match(term_str)
    if len(normalized) < 3:
        return
    dictionaries[canonical_family(family)].append(TermEntry(term=term_str, weight=safe_float(weight, 1.0), source=source))


def load_terms_from_text_file(path: Path, family: str, dictionaries: dict[str, list[TermEntry]]) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s*[,;]\s*", line)
        if len(parts) >= 2:
            add_term(dictionaries, family, parts[0], parts[1], str(path))
        else:
            add_term(dictionaries, family, line, 1.0, str(path))


def extract_terms_from_json_value(value: Any, family: str, dictionaries: dict[str, list[TermEntry]], source: str) -> None:
    if value is None:
        return
    if isinstance(value, str):
        add_term(dictionaries, family, value, 1.0, source)
        return
    if isinstance(value, (int, float)):
        return
    if isinstance(value, list):
        for item in value:
            extract_terms_from_json_value(item, family, dictionaries, source)
        return
    if isinstance(value, dict):
        term_value = value.get("term") or value.get("text") or value.get("keyword") or value.get("name") or value.get("entity")
        if term_value:
            weight = value.get("weight") or value.get("peso") or value.get("score") or value.get("count") or value.get("df") or 1.0
            add_term(dictionaries, family, term_value, weight, source)
            return
        for key in ("terms", "keywords", "items", "palabras", "diccionario"):
            if key in value:
                extract_terms_from_json_value(value[key], family, dictionaries, source)
                return
        family_keys_found = False
        for key, subvalue in value.items():
            possible_family = canonical_family(key, fallback="")
            if possible_family in FAMILIES:
                family_keys_found = True
                extract_terms_from_json_value(subvalue, possible_family, dictionaries, source)
        if family_keys_found:
            return
        for key, subvalue in value.items():
            if isinstance(subvalue, (int, float, str)):
                maybe_weight = subvalue if isinstance(subvalue, (int, float)) else 1.0
                add_term(dictionaries, family, key, maybe_weight, source)


def infer_family_from_file_name(path: Path) -> str:
    return canonical_family(path.stem, fallback="mercado_financiero")


def load_dictionary_files(dictionary_dir: Path) -> dict[str, list[TermEntry]]:
    dictionaries: dict[str, list[TermEntry]] = defaultdict(list)
    for family, terms in DEFAULT_SEED_TERMS.items():
        for term, weight in terms.items():
            add_term(dictionaries, family, term, weight, "DEFAULT_SEED_TERMS")
    if not dictionary_dir.exists():
        print(f"[WARN] Carpeta de diccionarios no encontrada: {dictionary_dir}")
        return dictionaries
    for path in sorted(dictionary_dir.iterdir()):
        if path.is_dir():
            continue
        family = infer_family_from_file_name(path)
        try:
            if path.suffix.lower() in {".txt", ".csv"}:
                load_terms_from_text_file(path, family, dictionaries)
            elif path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                extract_terms_from_json_value(data, family, dictionaries, str(path))
        except Exception as exc:
            print(f"[WARN] No se pudo cargar diccionario {path}: {exc}")
    return dictionaries


def candidate_weight_from_item(item: dict[str, Any]) -> float:
    if "df_pct" in item:
        df_pct = safe_float(item.get("df_pct"), 0.0)
        return max(0.2, min(1.0, 1.0 - df_pct))
    if "score" in item:
        return max(0.2, min(1.0, safe_float(item.get("score"), 1.0)))
    if "count" in item:
        return max(0.2, min(1.0, math.log1p(safe_float(item.get("count"), 1.0)) / 10))
    return 0.5


def load_candidates_file(candidates_path: Path, dictionaries: dict[str, list[TermEntry]], candidate_top_limit: int = 150, candidate_max_df_pct: float = 0.12) -> None:
    if not candidates_path.exists():
        print(f"[WARN] Archivo candidatos no encontrado: {candidates_path}")
        return
    try:
        data = json.loads(candidates_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] No se pudo cargar candidatos {candidates_path}: {exc}")
        return
    section_to_family = {
        "financial_strict": "mercado_financiero",
        "political_risk": "politico_regulatorio",
        "geopolitical_market": "geopolitico_mercado",
    }
    for section, family in section_to_family.items():
        section_data = data.get(section, {})
        if not isinstance(section_data, dict):
            continue
        collected: list[dict[str, Any]] = []
        for key in ("ngrams_top", "tfidf_top"):
            values = section_data.get(key, [])
            if isinstance(values, list):
                collected.extend([x for x in values if isinstance(x, dict)])
        count = 0
        for item in collected:
            term = str(item.get("term", "")).strip()
            normalized = normalize_for_match(term)
            if not normalized or normalized in GENERIC_CANDIDATE_STOPWORDS:
                continue
            df_pct = safe_float(item.get("df_pct"), 0.0)
            if df_pct and df_pct > candidate_max_df_pct:
                continue
            add_term(dictionaries, family, term, candidate_weight_from_item(item), str(candidates_path))
            count += 1
            if count >= candidate_top_limit:
                break


def deduplicate_dictionaries(dictionaries: dict[str, list[TermEntry]]) -> dict[str, list[TermEntry]]:
    result: dict[str, list[TermEntry]] = {}
    for family, entries in dictionaries.items():
        by_normalized: dict[str, TermEntry] = {}
        for entry in entries:
            normalized = normalize_for_match(entry.term)
            if not normalized:
                continue
            current = by_normalized.get(normalized)
            if current is None or entry.weight > current.weight:
                by_normalized[normalized] = entry
        result[family] = sorted(
            by_normalized.values(),
            key=lambda x: (len(normalize_for_match(x.term).split()), x.weight, x.term),
            reverse=True,
        )
    return result


def compile_dictionaries(dictionaries: dict[str, list[TermEntry]]) -> dict[str, list[tuple[TermEntry, re.Pattern]]]:
    compiled: dict[str, list[tuple[TermEntry, re.Pattern]]] = {}
    for family, entries in dictionaries.items():
        compiled[family] = []
        for entry in entries:
            try:
                compiled[family].append((entry, term_to_pattern(entry.term)))
            except Exception as exc:
                print(f"[WARN] No se pudo compilar patrón para {entry.term}: {exc}")
    return compiled


def get_article_raw(article: dict[str, Any]) -> dict[str, Any]:
    raw = article.get("raw")
    return raw if isinstance(raw, dict) else article


def build_classification_text(article: dict[str, Any]) -> str:
    raw = get_article_raw(article)
    parts = [
        raw.get("title", ""),
        raw.get("subtitle", ""),
        raw.get("lead", ""),
        raw.get("summary", ""),
        raw.get("ai_summary", ""),
        raw.get("body_text_clean", ""),
        raw.get("main_section", ""),
        raw.get("subsection", ""),
        raw.get("breadcrumb_raw", ""),
    ]
    paragraphs = raw.get("paragraphs")
    if isinstance(paragraphs, list) and not raw.get("body_text_clean"):
        parts.extend([str(p) for p in paragraphs])
    return normalize_for_match(" ".join(str(x) for x in parts if x))


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


def discover_news_files(base_dir: Path, sources: list[str], allowed_dates: set[date] | None = None, input_name: str = DEFAULT_INPUT_NAME) -> list[Path]:
    files: list[Path] = []
    for source in sources:
        source_dir = base_dir / source
        if not source_dir.exists():
            print(f"[WARN] No existe carpeta fuente: {source_dir}")
            continue
        for day_dir in sorted(source_dir.iterdir()):
            if not day_dir.is_dir() or not DATE_FOLDER_RE.match(day_dir.name):
                continue
            day_date = date_from_dir_name(day_dir.name)
            if allowed_dates is not None and day_date not in allowed_dates:
                continue
            input_path = day_dir / input_name
            if input_path.exists():
                files.append(input_path)
    return sorted(files)


def enrich_news_file(input_path: Path, compiled: dict[str, list[tuple[TermEntry, re.Pattern]]], dictionary_version: str, output_name: str, overwrite: bool = False) -> dict[str, Any]:
    output_path = input_path.parent / output_name
    if output_path.exists() and not overwrite:
        return {"input_path": str(input_path), "output_path": str(output_path), "status": "skipped_existing_output"}
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"input_path": str(input_path), "output_path": str(output_path), "status": "error", "error": f"json_load_error: {exc}"}
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return {"input_path": str(input_path), "output_path": str(output_path), "status": "error", "error": "missing_articles_list"}
    enriched_articles = [enrich_article(article, compiled, dictionary_version) for article in articles]
    metadata = dict(payload.get("metadata", {}))
    metadata["features_enriched"] = True
    metadata["features_dictionary_version"] = dictionary_version
    metadata["features_generated_at"] = datetime.now().isoformat()
    metadata["features_articles_count"] = len(enriched_articles)
    output_payload = dict(payload)
    output_payload["metadata"] = metadata
    output_payload["articles"] = enriched_articles
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    active_counter = Counter()
    impact_candidates = 0
    for article in enriched_articles:
        features = article.get("features", {})
        audit = features.get("audit", {})
        for family in audit.get("active_families", []):
            active_counter[family] += 1
        if features.get("impact", {}).get("market_impact_candidate"):
            impact_candidates += 1
    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "enriched",
        "articles": len(enriched_articles),
        "market_impact_candidates": impact_candidates,
        "active_families_counter": dict(active_counter),
    }


def enrich_files_parallel(files: list[Path], compiled: dict[str, list[tuple[TermEntry, re.Pattern]]], dictionary_version: str, output_name: str, overwrite: bool, workers: int) -> list[dict[str, Any]]:
    if workers <= 1:
        return [enrich_news_file(path, compiled, dictionary_version, output_name, overwrite) for path in files]
    summaries: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(enrich_news_file, path, compiled, dictionary_version, output_name, overwrite): path for path in files}
        for idx, future in enumerate(as_completed(future_map), start=1):
            path = future_map[future]
            try:
                summary = future.result()
            except Exception as exc:
                summary = {"input_path": str(path), "status": "error", "error": f"worker_error: {exc}"}
            print(f"[{idx}/{len(files)}] {summary.get('status')}: {path}")
            summaries.append(summary)
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Enriquece noticias descargadas con features derivados de diccionarios.")
    parser.add_argument("--base-dir", default=".", help="Directorio base del proyecto.")
    parser.add_argument("--dictionary-dir", default=DEFAULT_DICTIONARY_DIR, help="Carpeta con diccionarios.")
    parser.add_argument("--candidates-file", default=DEFAULT_CANDIDATES_FILE, help="Archivo candidatos_diccionario.json.")
    parser.add_argument("--dictionary-version", default=DEFAULT_DICTIONARY_VERSION, help="Versión del diccionario.")
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME, help="Nombre del archivo diario de entrada.")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME, help="Nombre del archivo diario enriquecido.")
    parser.add_argument("--sources", nargs="+", default=list(DEFAULT_SOURCES), help="Fuentes a procesar: biobio mostrador.")
    parser.add_argument("--workers", type=int, default=4, help="Cantidad de archivos diarios a enriquecer en paralelo.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe archivos enriquecidos existentes.")
    parser.add_argument("--no-candidates", action="store_true", help="No usar candidatos_diccionario.json como apoyo.")
    parser.add_argument("--candidate-top-limit", type=int, default=150, help="Máximo de candidatos a importar por familia.")
    parser.add_argument("--candidate-max-df-pct", type=float, default=0.12, help="DF máximo permitido para candidatos.")
    parser.add_argument("--date", default=None, help="Fecha final. Formatos: DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD.")
    parser.add_argument("--days-back", type=int, default=None, help="Cantidad de días hacia atrás incluyendo fecha final.")
    parser.add_argument("--date-from", default=None, help="Fecha inicial opcional.")
    parser.add_argument("--date-to", default=None, help="Fecha final opcional.")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    dictionary_dir = (base_dir / args.dictionary_dir).resolve()
    candidates_path = (base_dir / args.candidates_file).resolve()

    dictionaries = load_dictionary_files(dictionary_dir)
    if not args.no_candidates:
        load_candidates_file(candidates_path, dictionaries, args.candidate_top_limit, args.candidate_max_df_pct)
    dictionaries = deduplicate_dictionaries(dictionaries)
    compiled = compile_dictionaries(dictionaries)

    print("=== Diccionarios cargados ===")
    for family in FAMILIES:
        print(f"  {family}: {len(compiled.get(family, []))} términos")

    allowed_dates: set[date] | None = None
    if args.date_from or args.date_to:
        if not args.date_from or not args.date_to:
            raise ValueError("Debes usar --date-from y --date-to juntos.")
        start = parse_target_date(args.date_from)
        end = parse_target_date(args.date_to)
        if start > end:
            raise ValueError("--date-from no puede ser posterior a --date-to.")
        allowed_dates = {start + timedelta(days=i) for i in range((end - start).days + 1)}
    elif args.days_back is not None:
        end = parse_target_date(args.date)
        allowed_dates = build_date_range(end, args.days_back)

    files = discover_news_files(base_dir, args.sources, allowed_dates, args.input_name)

    print()
    print("=== Archivos encontrados ===")
    print(f"Total: {len(files)}")
    for path in files[:10]:
        print(f"  {path}")
    if len(files) > 10:
        print(f"  ... y {len(files) - 10} más")

    summaries = enrich_files_parallel(files, compiled, args.dictionary_version, args.output_name, args.overwrite, args.workers)

    summary_dir = base_dir / "features_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = summary_dir / f"resumen_enriquecimiento_{timestamp}.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    enriched = sum(1 for item in summaries if item.get("status") == "enriched")
    skipped = sum(1 for item in summaries if item.get("status") == "skipped_existing_output")
    errors = sum(1 for item in summaries if item.get("status") == "error")

    print()
    print("=" * 70)
    print("PROCESO DE ENRIQUECIMIENTO TERMINADO")
    print(f"Archivos enriquecidos: {enriched}")
    print(f"Archivos omitidos: {skipped}")
    print(f"Errores: {errors}")
    print(f"Resumen guardado en: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
