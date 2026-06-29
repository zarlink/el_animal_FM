from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from el_animal_fm.news.application.shared.dictionary_matching import (
    normalize_for_match,
    safe_float,
    term_to_pattern,
)
from el_animal_fm.news.application.enrichment.enrichment_config import (
    DEFAULT_SEED_TERMS,
    FAMILIES,
    FAMILY_ALIASES,
    GENERIC_CANDIDATE_STOPWORDS,
)


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
