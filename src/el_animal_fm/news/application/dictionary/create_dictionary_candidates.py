from __future__ import annotations

import json
from pathlib import Path

from el_animal_fm.news.application.dictionary import dictionary_config as config
from el_animal_fm.news.application.dictionary.dictionary_cache import DictionaryCache, dependencies
from el_animal_fm.news.application.dictionary.dictionary_candidate_extractor import DEFAULT_YAKE_WORKERS

from el_animal_fm.news.application.dictionary.dictionary_progress import log_stage

from el_animal_fm.news.application.dictionary.dictionary_candidate_extractor import (
    extract_ngrams,
    extract_tfidf,
    extract_yake_keywords,
)
from el_animal_fm.news.application.dictionary.dictionary_clustering import build_embedding_clusters
from el_animal_fm.news.application.dictionary.dictionary_config import (
    DEFAULT_RECORD_WORKERS,
    RECORD_CHUNKSIZE,
    RECORD_LOG_EVERY,
    get_stopwords,
)
from el_animal_fm.news.application.dictionary.dictionary_entities import extract_entities
from el_animal_fm.news.application.dictionary.dictionary_records import build_records_parallel
from el_animal_fm.news.application.dictionary.dictionary_report import (
    build_dictionary_report,
    make_json_serializable,
)


def load_articles(input_path: Path) -> list[dict]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return data["articles"] if isinstance(data, dict) else data


def create_dictionary_candidates(
    input_path: Path, output_path: Path, *,
    record_workers: int = DEFAULT_RECORD_WORKERS,
    record_log_every: int = RECORD_LOG_EVERY,
    record_chunksize: int = RECORD_CHUNKSIZE,
    yake_workers: int = DEFAULT_YAKE_WORKERS,
    yake_chunksize: int = 25,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> dict:
    directory = (cache_dir if cache_dir is not None else output_path.parent / ".dictionary_cache") if use_cache else None
    with DictionaryCache(directory) as cache:
        return _create_dictionary_candidates(
            input_path, output_path, record_workers=record_workers,
            record_log_every=record_log_every, record_chunksize=record_chunksize,
            yake_workers=yake_workers, yake_chunksize=yake_chunksize, cache=cache,
        )


def _create_dictionary_candidates(
    input_path: Path,
    output_path: Path,
    *,
    record_workers: int = DEFAULT_RECORD_WORKERS,
    record_log_every: int = RECORD_LOG_EVERY,
    record_chunksize: int = RECORD_CHUNKSIZE,
    yake_workers: int,
    yake_chunksize: int,
    cache: DictionaryCache,
) -> dict:
    articles = load_articles(input_path)

    records, record_stats = build_records_parallel(
        articles,
        max_workers=record_workers,
        log_every=record_log_every,
        chunksize=record_chunksize,
        cache=cache,
    )

    texts = [record["text"] for record in records]

    financial_strict_records = [
        record for record in records
        if record["family_info"]["is_financial_strict"]
        and not record["family_info"]["is_social_noise_dominant"]
    ]

    political_risk_records = [
        record for record in records
        if record["family_info"]["is_political_risk"]
        and not record["family_info"]["is_social_noise_dominant"]
    ]

    geopolitical_market_records = [
        record for record in records
        if record["family_info"]["is_geopolitical_market"]
        and not record["family_info"]["is_social_noise_dominant"]
    ]

    financial_texts = [record["text"] for record in financial_strict_records]
    political_risk_texts = [record["text"] for record in political_risk_records]
    geopolitical_market_texts = [record["text"] for record in geopolitical_market_records]

    print(f"Textos generales usados: {len(texts)}")
    print(f"Textos financieros estrictos: {len(financial_texts)}")
    print(f"Textos riesgo político: {len(political_risk_texts)}")
    print(f"Textos geopolíticos con mercado: {len(geopolitical_market_texts)}")

    analysis_signature = dependencies(
        "dictionary_candidate_extractor",
        values={"stopwords": get_stopwords(), "token_pattern": config.TOKEN_PATTERN},
        packages=("scikit-learn", "numpy", "scipy"),
    )

    def analyze(kind, source, min_df):
        function = extract_ngrams if kind == "ngrams" else extract_tfidf
        return cache.compute(kind, analysis_signature, [min_df, source],
                             lambda: function(source, min_df=min_df))

    with log_stage("N-gramas financieros", len(financial_texts)):
        financial_ngrams_top = analyze("ngrams", financial_texts, 3)
    with log_stage("N-gramas riesgo político", len(political_risk_texts)):
        political_risk_ngrams_top = analyze("ngrams", political_risk_texts, 3)
    with log_stage("N-gramas geopolíticos", len(geopolitical_market_texts)):
        geopolitical_market_ngrams_top = analyze("ngrams", geopolitical_market_texts, 3)

    with log_stage("TF-IDF financieros", len(financial_texts)):
        financial_tfidf_top = analyze("tfidf", financial_texts, 3)
    with log_stage("TF-IDF riesgo político", len(political_risk_texts)):
        political_risk_tfidf_top = analyze("tfidf", political_risk_texts, 3)
    with log_stage("TF-IDF geopolíticos", len(geopolitical_market_texts)):
        geopolitical_market_tfidf_top = analyze("tfidf", geopolitical_market_texts, 3)

    with log_stage("N-gramas generales", len(texts)):
        ngrams_top = analyze("ngrams", texts, 5)
    with log_stage("TF-IDF generales", len(texts)):
        tfidf_top = analyze("tfidf", texts, 3)
    with log_stage("YAKE", len(texts)):
        yake_top = extract_yake_keywords(texts, workers=yake_workers, chunksize=yake_chunksize, cache=cache)
    with log_stage("Entidades", len(texts)):
        entities = extract_entities(texts, cache=cache)
    with log_stage("Embeddings y clustering", len(articles)):
        labels, cluster_examples = build_embedding_clusters(articles, cache=cache)

    with log_stage("Construcción y guardado del reporte"):
        report = build_dictionary_report(
            articles=articles,
            texts=texts,
            record_stats=record_stats,
            record_workers=record_workers,
            record_chunksize=record_chunksize,
            stopwords_count=len(get_stopwords()),
            financial_strict_records=financial_strict_records,
            political_risk_records=political_risk_records,
            geopolitical_market_records=geopolitical_market_records,
            ngrams_top=ngrams_top,
            tfidf_top=tfidf_top,
            yake_top=yake_top,
            financial_ngrams_top=financial_ngrams_top,
            political_risk_ngrams_top=political_risk_ngrams_top,
            geopolitical_market_ngrams_top=geopolitical_market_ngrams_top,
            financial_tfidf_top=financial_tfidf_top,
            political_risk_tfidf_top=political_risk_tfidf_top,
            geopolitical_market_tfidf_top=geopolitical_market_tfidf_top,
            entities=entities,
            labels=labels,
            cluster_examples=cluster_examples,
        )

        output_path.write_text(
            json.dumps(make_json_serializable(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return report
