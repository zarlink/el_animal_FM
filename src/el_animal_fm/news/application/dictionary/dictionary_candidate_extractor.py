from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
import logging
import os
from time import perf_counter

from el_animal_fm.news.application.dictionary.dictionary_progress import log_text_progress
from el_animal_fm.news.application.dictionary.dictionary_cache import DictionaryCache, dependencies, fingerprint

import yake
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from el_animal_fm.news.application.dictionary.dictionary_config import TOKEN_PATTERN, get_stopwords
from el_animal_fm.news.application.dictionary.dictionary_text import clean


STOP = get_stopwords()


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


_YAKE_EXTRACTOR = None
logger = logging.getLogger("creador_diccionario")
DEFAULT_YAKE_WORKERS = max(1, min(os.cpu_count() or 1, 6))


def _initialize_yake_worker():
    global _YAKE_EXTRACTOR
    _YAKE_EXTRACTOR = yake.KeywordExtractor(lan="es", n=3, top=20)


def _extract_yake_document(text: str):
    if _YAKE_EXTRACTOR is None:
        _initialize_yake_worker()
    return _YAKE_EXTRACTOR.extract_keywords(text)


def extract_yake_keywords(
    texts_source: list[str], *, workers: int = DEFAULT_YAKE_WORKERS,
    chunksize: int = 25, cache: DictionaryCache | None = None,
) -> list[tuple[str, float]]:
    if workers < 1 or chunksize < 1:
        raise ValueError("YAKE workers y chunksize deben ser positivos")
    if not texts_source:
        return []

    signature = dependencies("dictionary_candidate_extractor", packages=("yake", "numpy", "jellyfish", "networkx", "segtok"))
    # Keep the unfiltered keywords: stopword changes must not run YAKE again.
    raw_results = [None] * len(texts_source)
    missing = {}
    reused = 0
    started = perf_counter()
    for index, text in enumerate(texts_source):
        key = fingerprint([signature, text])
        cached = cache.get("yake_raw", key) if cache is not None else None
        if cached is not None:
            raw_results[index] = cached
            reused += 1
        else:
            if key not in missing:
                missing[key] = (text, [])
            missing[key][1].append(index)

    logger.info("YAKE | reutilizados=%d | documentos_por_calcular=%d | workers=%d",
                reused, len(missing), workers)
    tasks = list(missing.items())

    def collect(results):
        completed = reused
        for (key, (_, indices)), keywords in zip(tasks, results):
            if cache is not None:
                cache.put("yake_raw", key, keywords)
            for index in indices:
                raw_results[index] = keywords
            completed += len(indices)
            # Duplicated documents may jump over an exact multiple of 500.
            if completed // 500 != (completed - len(indices)) // 500 or completed == len(texts_source):
                logger.info("PROGRESO | YAKE extracción | %d/%d | tiempo=%.2fs",
                            completed, len(texts_source), perf_counter() - started)

    if tasks:
        worker_count = min(workers, len(tasks))
        task_texts = (entry[1][0] for entry in tasks)
        if worker_count == 1:
            _initialize_yake_worker()
            collect(map(_extract_yake_document, task_texts))
        else:
            # Spawn avoids inheriting CUDA state, SQLite connections or log threads.
            with ProcessPoolExecutor(max_workers=worker_count, mp_context=get_context("spawn"),
                                     initializer=_initialize_yake_worker) as executor:
                collect(executor.map(_extract_yake_document, task_texts, chunksize=chunksize))

    yake_scores = Counter()
    for index, keywords in enumerate(raw_results, start=1):
        # Merge by original document order, including duplicates. This preserves
        # floating-point summation and the insertion order used to break ties.
        for term, score in keywords:
            term = clean(term)
            if not is_bad_candidate_term(term):
                yake_scores[term] += (1.0 / (score + 1e-9))
        log_text_progress("YAKE agregación", index, len(texts_source), started)
    return yake_scores.most_common(1000)
