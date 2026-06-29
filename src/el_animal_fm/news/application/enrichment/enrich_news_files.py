from __future__ import annotations

import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any

from el_animal_fm.news.application.enrichment.enrichment_config import DEFAULT_INPUT_NAME
from el_animal_fm.news.application.enrichment.enrichment_dictionaries import TermEntry
from el_animal_fm.news.application.shared.news_file_collection import find_news_files
from el_animal_fm.news.application.enrichment.news_enrichment import enrich_article


def discover_news_files(
    base_dir: Path,
    sources: list[str],
    allowed_dates: set[date] | None = None,
    input_name: str = DEFAULT_INPUT_NAME,
) -> list[Path]:
    return find_news_files(
        base_dir,
        sources,
        file_names=(input_name,),
        allowed_dates=allowed_dates,
    )


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
