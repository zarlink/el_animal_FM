from __future__ import annotations

import json
from pathlib import Path

from el_animal_fm.news.application.dictionary_candidate_extractor import (
    extract_ngrams,
    extract_tfidf,
    extract_yake_keywords,
)
from el_animal_fm.news.application.dictionary_clustering import build_embedding_clusters
from el_animal_fm.news.application.dictionary_config import (
    DEFAULT_RECORD_WORKERS,
    RECORD_CHUNKSIZE,
    RECORD_LOG_EVERY,
    get_stopwords,
)
from el_animal_fm.news.application.dictionary_entities import extract_entities
from el_animal_fm.news.application.dictionary_records import build_records_parallel
from el_animal_fm.news.application.dictionary_report import (
    build_dictionary_report,
    make_json_serializable,
)


def load_articles(input_path: Path) -> list[dict]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return data["articles"] if isinstance(data, dict) else data


def create_dictionary_candidates(
    input_path: Path,
    output_path: Path,
    *,
    record_workers: int = DEFAULT_RECORD_WORKERS,
    record_log_every: int = RECORD_LOG_EVERY,
    record_chunksize: int = RECORD_CHUNKSIZE,
) -> dict:
    articles = load_articles(input_path)

    records, record_stats = build_records_parallel(
        articles,
        max_workers=record_workers,
        log_every=record_log_every,
        chunksize=record_chunksize,
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

    financial_ngrams_top = extract_ngrams(financial_texts, min_df=3)
    political_risk_ngrams_top = extract_ngrams(political_risk_texts, min_df=3)
    geopolitical_market_ngrams_top = extract_ngrams(geopolitical_market_texts, min_df=3)

    financial_tfidf_top = extract_tfidf(financial_texts, min_df=3)
    political_risk_tfidf_top = extract_tfidf(political_risk_texts, min_df=3)
    geopolitical_market_tfidf_top = extract_tfidf(geopolitical_market_texts, min_df=3)

    ngrams_top = extract_ngrams(texts, min_df=5)
    tfidf_top = extract_tfidf(texts, min_df=3)
    yake_top = extract_yake_keywords(texts)
    entities = extract_entities(texts)
    labels, cluster_examples = build_embedding_clusters(articles)

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
