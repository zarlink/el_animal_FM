from __future__ import annotations

from collections import Counter

import spacy

from el_animal_fm.news.application.dictionary_config import ENTITY_ALIASES, ENTITY_STOP
from el_animal_fm.news.application.dictionary_text import clean


def normalize_entity_text(value: str) -> str:
    value = clean(value)
    return ENTITY_ALIASES.get(value, value)


def extract_entities(texts_source: list[str]) -> Counter:
    nlp = spacy.load("es_core_news_lg")
    ents = Counter()

    for doc in nlp.pipe(texts_source, batch_size=32):
        for entity in doc.ents:
            ent_text = normalize_entity_text(entity.text)

            if not ent_text or ent_text in ENTITY_STOP:
                continue

            if len(ent_text) < 3:
                continue

            if entity.label_ in {"ORG", "PER", "LOC", "MISC"}:
                ents[(ent_text, entity.label_)] += 1

    return ents
