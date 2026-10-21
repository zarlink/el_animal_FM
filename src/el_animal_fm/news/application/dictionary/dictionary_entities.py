from __future__ import annotations

from collections import Counter
from time import perf_counter
import logging

from el_animal_fm.news.application.dictionary.dictionary_cache import DictionaryCache, dependencies, fingerprint

from el_animal_fm.news.application.dictionary.dictionary_progress import log_text_progress

import spacy

from el_animal_fm.news.application.dictionary.dictionary_config import ENTITY_ALIASES, ENTITY_STOP
from el_animal_fm.news.application.dictionary.dictionary_text import clean


def normalize_entity_text(value: str) -> str:
    value = clean(value)
    return ENTITY_ALIASES.get(value, value)


def extract_entities(texts_source: list[str], *, cache: DictionaryCache | None = None) -> Counter:
    signature = dependencies("dictionary_entities", packages=("spacy", "es-core-news-lg", "thinc", "numpy", "blis"))
    raw_results = [None] * len(texts_source)
    missing = {}
    for index, text in enumerate(texts_source):
        key = fingerprint([signature, text])
        cached = cache.get("entities_raw", key) if cache is not None else None
        if cached is not None:
            raw_results[index] = cached
        else:
            if key not in missing:
                missing[key] = (text, [])
            missing[key][1].append(index)
    logging.getLogger("creador_diccionario").info(
        "CACHÉ | entidades | documentos_por_calcular=%d", len(missing)
    )
    started = perf_counter()
    if missing:
        nlp = spacy.load("es_core_news_lg")
        documents = nlp.pipe((entry[0] for entry in missing.values()), batch_size=32)
        for index, ((key, (_, indices)), doc) in enumerate(zip(missing.items(), documents), start=1):
            raw = [(entity.text, entity.label_) for entity in doc.ents]
            if cache is not None:
                cache.put("entities_raw", key, raw)
            for position in indices:
                raw_results[position] = raw
            log_text_progress("Entidades extracción", index, len(missing), started)

    ents = Counter()
    for index, raw in enumerate(raw_results, start=1):
        for text, label in raw:
            ent_text = normalize_entity_text(text)
            if not ent_text or ent_text in ENTITY_STOP or len(ent_text) < 3:
                continue
            if label in {"ORG", "PER", "LOC", "MISC"}:
                ents[(ent_text, label)] += 1
        log_text_progress("Entidades agregación", index, len(texts_source), started)
    return ents
