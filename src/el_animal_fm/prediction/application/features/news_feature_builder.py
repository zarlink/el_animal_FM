from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.shared.prediction_utils import (
    feature_safe_name,
    folder_to_date,
    safe_float,
)
from el_animal_fm.prediction.infrastructure.output_paths import NEWS_FILE_NAME, NEWS_SOURCES

def parse_article_publication_time(article: dict[str, Any]) -> time | None:
    raw = article.get("raw", {}) if isinstance(article, dict) else {}
    if not isinstance(raw, dict):
        return None

    published_time_raw = str(raw.get("published_time", "") or "").strip()
    if published_time_raw:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                part = published_time_raw[:8] if fmt == "%H:%M:%S" else published_time_raw[:5]
                return datetime.strptime(part, fmt).time()
            except ValueError:
                pass

    published_at = str(raw.get("published_at", "") or raw.get("published_at_raw", "") or "").strip()
    if "T" in published_at:
        time_part = published_at.split("T", 1)[1]
        time_part = time_part.split("-", 1)[0].split("+", 1)[0].strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                part = time_part[:8] if fmt == "%H:%M:%S" else time_part[:5]
                return datetime.strptime(part, fmt).time()
            except ValueError:
                pass

    return None

def add_numeric_feature(row: dict[str, float], prefix: str, value: Any) -> None:
    vf = safe_float(value)
    if math.isnan(vf):
        return
    row[f"{prefix}_sum"] = vf
    row[f"{prefix}_mean"] = vf

def add_feature_value(row: dict[str, float], prefix: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (bool, int, float, np.integer, np.floating)):
        add_numeric_feature(row, prefix, value)
        return
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return
        vf = safe_float(text)
        if not math.isnan(vf):
            add_numeric_feature(row, prefix, vf)
            return
        row[f"{prefix}_{feature_safe_name(text)}_count"] = 1.0
        return
    if isinstance(value, list):
        row[f"{prefix}_items_sum"] = float(len(value))
        row[f"{prefix}_items_mean"] = float(len(value))
        return
    if isinstance(value, dict):
        for k, v in value.items():
            add_feature_value(row, f"{prefix}_{feature_safe_name(k)}", v)

def discover_news_files(source_dir: Path, start: date, end: date) -> list[tuple[date, Path, str]]:
    files: list[tuple[date, Path, str]] = []
    if not source_dir.exists():
        return files

    source_name = source_dir.name
    for day_dir in source_dir.iterdir():
        if not day_dir.is_dir():
            continue
        day = folder_to_date(day_dir.name)
        if not day or day < start or day > end:
            continue
        p = day_dir / NEWS_FILE_NAME
        if p.exists():
            files.append((day, p, source_name))

    return sorted(files, key=lambda x: x[0])

def extract_article_feature_row(article: dict[str, Any], source: str) -> dict[str, float]:
    row: dict[str, float] = {"news_count": 1.0, f"news_count_{source}": 1.0}

    raw = article.get("raw", {}) if isinstance(article, dict) else {}
    features = article.get("features", {}) if isinstance(article, dict) else {}

    if not isinstance(raw, dict):
        raw = {}
    if not isinstance(features, dict):
        features = {}

    for flag in [
        "is_economy_section", "is_market_section", "is_national_section",
        "is_international_section", "is_country_section", "is_world_section",
        "is_opinion", "is_column", "is_editorial", "is_agency_content",
    ]:
        row[f"{flag}_count"] = 1.0 if bool(raw.get(flag, False)) else 0.0

    for numeric_key in [
        "body_length_words", "body_length_chars", "paragraph_count",
        "quote_count", "related_count", "image_count",
    ]:
        v = safe_float(raw.get(numeric_key))
        if not math.isnan(v):
            row[f"{numeric_key}_sum"] = v
            row[f"{numeric_key}_mean"] = v

    families = features.get("families", {})
    if isinstance(families, dict):
        for fam, fam_data in families.items():
            if not isinstance(fam_data, dict):
                continue
            prefix = f"news_family_{fam}"
            score = safe_float(fam_data.get("score", 0.0))
            hit_count = safe_float(fam_data.get("hit_count", 0.0))
            row[f"{prefix}_score_sum"] = 0.0 if math.isnan(score) else score
            row[f"{prefix}_score_mean"] = 0.0 if math.isnan(score) else score
            row[f"{prefix}_hit_count_sum"] = 0.0 if math.isnan(hit_count) else hit_count
            row[f"{prefix}_active_count"] = 1.0 if bool(fam_data.get("active", False)) else 0.0

    skip_feature_values = {
        ("audit", "classification_reason"),
        ("temporal", "published_date"),
        ("temporal", "published_time"),
    }

    for block_name in ["general_classification", "impact", "entities", "temporal", "audit"]:
        block = features.get(block_name, {})
        if isinstance(block, dict):
            for k, v in block.items():
                if (block_name, str(k)) in skip_feature_values:
                    continue
                add_feature_value(row, f"news_{block_name}_{feature_safe_name(k)}", v)

    return row

def aggregate_news_file(
    file_path: Path,
    source: str,
    max_publication_time: time | None = None,
) -> dict[str, float]:
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] No se pudo leer JSON de noticias {file_path}: {exc}")
        return {"news_count": 0.0}

    articles = payload.get("articles", [])

    if not isinstance(articles, list) or not articles:
        return {"news_count": 0.0, f"news_count_{source}": 0.0}

    if max_publication_time is not None:
        filtered_articles = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            published_time = parse_article_publication_time(article)
            if published_time is None:
                continue
            if published_time <= max_publication_time:
                filtered_articles.append(article)
        articles = filtered_articles

    if not articles:
        return {"news_count": 0.0, f"news_count_{source}": 0.0}

    df = pd.DataFrame([extract_article_feature_row(a, source) for a in articles]).fillna(0.0)
    agg: dict[str, float] = {}
    for col in df.columns:
        agg[col] = float(df[col].mean() if col.endswith("_mean") else df[col].sum())

    return agg

def load_news_daily_matrix(
    start: date,
    end: date,
    max_publication_time: time | None = None,
    label: str = "full",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source, source_dir in NEWS_SOURCES.items():
        files = discover_news_files(source_dir, start, end)
        print(f"  {source} ({label}): {len(files)} archivos encontrados")

        for day, path, source_name in files:
            r = aggregate_news_file(
                path,
                source_name,
                max_publication_time=max_publication_time,
            )
            r["date"] = pd.Timestamp(day)
            rows.append(r)

    index = pd.date_range(start=start, end=end, freq="D")

    if not rows:
        print(f"[WARN] No se encontraron noticias enriquecidas para matriz {label}.")
        return pd.DataFrame(index=index)

    news = pd.DataFrame(rows).groupby("date", as_index=True).sum(numeric_only=True).sort_index()
    news = news.reindex(index).fillna(0.0)
    news.index.name = "date"
    return news

def load_news_features(
    start: date,
    end: date,
    decision_mode: str = "strict_lag",
    decision_time: time | None = None,
) -> pd.DataFrame:
    print(f"Cargando noticias enriquecidas para modo {decision_mode}...")

    news_full = load_news_daily_matrix(start, end, max_publication_time=None, label="full")
    base_cols = list(news_full.select_dtypes(include=[np.number]).columns)
    features = pd.DataFrame(index=news_full.index)

    for col in base_cols:
        features[f"{col}_lag1"] = news_full[col].shift(1)
        features[f"{col}_roll3_lag1"] = news_full[col].rolling(3, min_periods=1).sum().shift(1)
        features[f"{col}_roll7_lag1"] = news_full[col].rolling(7, min_periods=1).sum().shift(1)

    if "news_count" in news_full.columns:
        weekend_news = news_full["news_count"].where(news_full.index.dayofweek >= 5, 0.0)
        features["news_weekend_pressure_roll3_lag1"] = weekend_news.rolling(3, min_periods=1).sum().shift(1)
        features["news_weekend_pressure_roll7_lag1"] = weekend_news.rolling(7, min_periods=1).sum().shift(1)

    if decision_mode == "same_day_close":
        for col in base_cols:
            features[f"{col}_same_day"] = news_full[col]

    elif decision_mode == "night_partial":
        if decision_time is None:
            raise ValueError("decision_time es obligatorio para decision_mode='night_partial'.")

        news_partial = load_news_daily_matrix(
            start,
            end,
            max_publication_time=decision_time,
            label=f"until_{decision_time.strftime('%H%M')}",
        )
        partial_cols = list(news_partial.select_dtypes(include=[np.number]).columns)

        for col in partial_cols:
            features[f"{col}_today_until_decision"] = news_partial[col]

    elif decision_mode == "strict_lag":
        pass

    else:
        raise ValueError(f"decision_mode inválido: {decision_mode}")

    features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    features.index.name = "date"
    print(f"  Features de noticias ({decision_mode}): {features.shape[1]}")
    return features
