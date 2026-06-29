from __future__ import annotations

from collections import Counter

import numpy as np

def sample_records(records_source: list[dict], limit: int = 20) -> list[dict]:
    samples = []

    for r in records_source[:limit]:
        a = r["article"]
        info = r["family_info"]

        samples.append({
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "published_date": a.get("published_date", ""),
            "main_section": a.get("main_section", ""),
            "url": a.get("url", ""),

            "strict_score": info["strict_score"],
            "political_score": info["political_score"],
            "geopolitical_score": info["geopolitical_score"],
            "social_noise_score": info["social_noise_score"],

            "market_hits": info["market_hits"],
            "fiscal_hits": info["fiscal_hits"],
            "company_hits": info["company_hits"],
            "commodity_hits": info["commodity_hits"],
            "political_hits": info["political_hits"],
            "geopolitical_hits": info["geopolitical_hits"],
            "social_noise_hits": info["social_noise_hits"],

            "ambiguous_market_hits": info.get("ambiguous_market_hits", []),
            "amount_hits": info.get("amount_hits", []),
            "energy_context_hits": info.get("energy_context_hits", []),
            "has_market_context": info.get("has_market_context", False),
            "has_amount_context": info.get("has_amount_context", False),
            "has_energy_market_context": info.get("has_energy_market_context", False),
            "has_geopolitical_market_context": info.get("has_geopolitical_market_context", False),
            "has_geopolitical_gas_context": info.get("has_geopolitical_gas_context", False),
            "geopolitical_gas_strong_context_hits": info.get("geopolitical_gas_strong_context_hits", []),
            "geopolitical_gas_weak_context_hits": info.get("geopolitical_gas_weak_context_hits", []),
            "geopolitical_hard_event_hits": info.get("geopolitical_hard_event_hits", []),
            "geopolitical_direct_context_hits": info.get("geopolitical_direct_context_hits", []),
            "geopolitical_support_context_hits": info.get("geopolitical_support_context_hits", []),
        })

    return samples


def make_json_serializable(obj):
    """
    Convierte tipos de numpy/pandas/sklearn a tipos nativos de Python
    para que puedan guardarse con json.dump().
    """
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, tuple):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, set):
        return [make_json_serializable(v) for v in sorted(obj)]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if obj is None:
        return None

    return obj


def build_dictionary_report(
    *,
    articles: list[dict],
    texts: list[str],
    record_stats: Counter,
    record_workers: int,
    record_chunksize: int,
    stopwords_count: int,
    financial_strict_records: list[dict],
    political_risk_records: list[dict],
    geopolitical_market_records: list[dict],
    ngrams_top: list[dict],
    tfidf_top: list[dict],
    yake_top: list[tuple[str, float]],
    financial_ngrams_top: list[dict],
    political_risk_ngrams_top: list[dict],
    geopolitical_market_ngrams_top: list[dict],
    financial_tfidf_top: list[dict],
    political_risk_tfidf_top: list[dict],
    geopolitical_market_tfidf_top: list[dict],
    entities: Counter,
    labels: np.ndarray,
    cluster_examples: dict[str, list[dict]],
) -> dict:
    financial_texts = [record["text"] for record in financial_strict_records]
    political_risk_texts = [record["text"] for record in political_risk_records]
    geopolitical_market_texts = [record["text"] for record in geopolitical_market_records]

    return {
        "metadata": {
            "articles_total": len(articles),
            "texts_general_count": len(texts),
            "financial_strict_count": len(financial_texts),
            "political_risk_count": len(political_risk_texts),
            "geopolitical_market_count": len(geopolitical_market_texts),
            "stopwords_count": stopwords_count,
            "record_processing_stats": dict(record_stats),
            "record_workers": record_workers,
            "record_chunksize": record_chunksize,
        },
        "general": {
            "ngrams_top": ngrams_top[:300],
            "tfidf_top": tfidf_top[:300],
            "yake_top": yake_top[:300],
        },
        "financial_strict": {
            "count": len(financial_texts),
            "ngrams_top": financial_ngrams_top[:300],
            "tfidf_top": financial_tfidf_top[:300],
            "samples": sample_records(financial_strict_records, limit=20),
        },
        "political_risk": {
            "count": len(political_risk_texts),
            "ngrams_top": political_risk_ngrams_top[:300],
            "tfidf_top": political_risk_tfidf_top[:300],
            "samples": sample_records(political_risk_records, limit=20),
        },
        "geopolitical_market": {
            "count": len(geopolitical_market_texts),
            "ngrams_top": geopolitical_market_ngrams_top[:300],
            "tfidf_top": geopolitical_market_tfidf_top[:300],
            "samples": sample_records(geopolitical_market_records, limit=20),
        },
        "entities_top": [
            {"text": key[0], "label": key[1], "count": value}
            for key, value in entities.most_common(300)
        ],
        "clusters": Counter(labels.tolist()) if len(labels) else {},
        "cluster_examples": cluster_examples,
    }
