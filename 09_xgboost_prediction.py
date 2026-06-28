#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
09_xgboost_prediction_por_fondo.py

Versión modificada para entrenar/evaluar secuencialmente cada fondo con parámetros
propios, manteniendo los mismos parámetros principales de entrada:

- --train-start
- --train-end
- --eval-start
- --eval-end
- --fund

La diferencia central respecto del script anterior es que ahora puede trabajar de dos maneras:

1) Modo evaluación comparativa, por defecto:
   - prueba automáticamente las 3 modalidades por cada fondo:
     strict_lag, night_partial y same_day_close;
   - guarda todos los resultados en un único JSON comparativo.

2) Modo presets por fondo:
   - usa una única configuración específica por fondo desde FUND_MODEL_CONFIG.

Esto permite comparar modalidades primero y, luego, ajustar cada fondo de manera independiente.

Dependencias:
    pip install pandas numpy scikit-learn xgboost joblib

Dependencia opcional para búsqueda automática de umbrales e hiperparámetros XGBoost:
    pip install optuna

Ejemplo recomendado para evaluar las 3 modalidades:
    python 09_xgboost_prediction_por_fondo.py \
      --train-start 2025-04-04 \
      --train-end 2026-05-30 \
      --eval-start 2026-05-31 \
      --eval-end 2026-06-09 \
      --fund all

Ejecutar solo los presets por fondo:
    python 09_xgboost_prediction_por_fondo.py \
      --train-start 2025-04-04 \
      --train-end 2026-05-30 \
      --eval-start 2026-05-31 \
      --eval-end 2026-06-09 \
      --fund all \
      --single-preset-run

Buscar automáticamente umbrales con Optuna, sin afinar todavía XGBoost:
    python 09_xgboost_prediction_por_fondo.py \
      --train-start 2025-04-04 \
      --train-end 2026-05-01 \
      --eval-start 2026-05-02 \
      --eval-end 2026-06-19 \
      --fund all \
      --optuna-threshold-search \
      --optuna-trials 80


Fine tuning de hiperparámetros XGBoost con Optuna, usando los thresholds/presets por fondo:
    python 09_xgboost_prediction_por_fondo.py \
      --train-start 2025-04-04 \
      --train-end 2026-05-01 \
      --eval-start 2026-05-02 \
      --eval-end 2026-06-19 \
      --fund national_equity \
      --optuna-xgb-search \
      --optuna-xgb-trials 250 \
      --optuna-xgb-score strategy_return

Para ignorar presets por fondo y usar parámetros globales para todos:
    python 09_xgboost_prediction_por_fondo.py \
      --train-start 2025-04-04 \
      --train-end 2026-05-30 \
      --eval-start 2026-05-31 \
      --eval-end 2026-06-09 \
      --fund all \
      --single-preset-run \
      --no-fund-presets \
      --decision-mode strict_lag
"""

from __future__ import annotations

import argparse
import json
import math
import random
import warnings
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
NEWS_FILE_NAME = "noticias_dia_enriquecidas.txt"

NEWS_SOURCES = {
    "biobio": BASE_DIR / "biobio",
    "mostrador": BASE_DIR / "mostrador",
}

DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "xgboost_outputs"
RANDOM_SEED = 42


# =============================================================================
# Configuración de fondos
# =============================================================================

FUND_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "run_fm": "10063",
        "folder": "10063_crecimiento_balanceado",
        "label": "Crecimiento Balanceado",
        "horizon_business_days": 4,
        "preferred_series": ["SIMPLE", "APV", "IT"],
    },
    "ahorro_uf_itau": {
        "run_fm": "10243",
        "folder": "10243_ahorro_uf_itau",
        "label": "Ahorro UF Itaú",
        "horizon_business_days": 1,
        "preferred_series": ["SIMPLE", "APV", "F4", "F5", "IT"],
    },
    "national_equity": {
        "run_fm": "8305",
        "folder": "8305_national_equity",
        "label": "National Equity",
        "horizon_business_days": 2,
        "preferred_series": ["F1", "SIMPLE", "APV", "IT"],
    },
    "toesca_equity": {
        "run_fm": "9936",
        "folder": "9936_toesca_equity",
        "label": "Toesca Equity",
        "horizon_business_days": 2,
        "preferred_series": ["F1", "SIMPLE", "APV", "IT"],
    },
}


# Presets iniciales por fondo.
# Ajusta aquí la estrategia específica de cada fondo.
#
# Notas:
# - Ahorro UF quedó mejor con strict_lag.
# - National y Toesca quedaron mejor con night_partial.
# - Crecimiento Balanceado necesita target/probability más exigente porque tendía a mantener siempre.
#
FUND_MODEL_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.367,
    "target_threshold": 0.00053,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "ahorro_uf_itau": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.61,
    "target_threshold": 0.0000,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "national_equity": {
    "decision_mode": "same_day_close",
    "decision_time": None,
    "probability_threshold": 0.516,
    "target_threshold": 0.000766,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "toesca_equity": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.35,
    "target_threshold": 0.00030,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
}

# Parametros personalizados de XGBoost para cada fondo:
XGB_MODEL_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "n_estimators": 300,
        "learning_rate": 0.044635901521768134,
        "max_depth": 3,
        "min_child_weight": 10.986584841970366,
        "gamma": 0.31203728088487304,
        "subsample": 0.6545980821176709,
        "colsample_bytree": 0.6203292642588698,
        "reg_lambda": 23.604024417191162,
        "reg_alpha": 1.8432335340553057,
    },
    "ahorro_uf_itau": {
        "n_estimators": 350,
        "learning_rate": 0.009720352156652182,
        "max_depth": 2,
        "min_child_weight": 8.072834730440935,
        "gamma": 0.0894795501120127,
        "subsample": 0.923591189202745,
        "colsample_bytree": 0.8628372612742934,
        "reg_lambda": 19.615823733250156,
        "reg_alpha": 1.0061696391388362,
    },
    "national_equity": {
        "n_estimators": 750,
        "learning_rate": 0.03390638325130928,
        "max_depth": 5,
        "min_child_weight": 6.8517843732226265,
        "gamma": 0.6073237677504941,
        "subsample": 0.7813747356486104,
        "colsample_bytree": 0.6181567321257274,
        "reg_lambda": 1.0074031444608387,
        "reg_alpha": 0.32523623592877615,
    },
    "toesca_equity": {
        "n_estimators": 700,
        "learning_rate": 0.058234808725543166,
        "max_depth": 2,
        "min_child_weight": 9.257031448464947,
        "gamma": 0.713484004053756,
        "subsample": 0.7608626029118591,
        "colsample_bytree": 0.7612351372536184,
        "reg_lambda": 6.641498576516313,
        "reg_alpha": 0.5287333296047524,
    },
}


# Modalidades que se probarán automáticamente por defecto en modo evaluación.
# La idea es comparar estrictamente cada modalidad bajo el mismo período.
DECISION_MODE_TESTS: list[dict[str, Any]] = [
    {
        "mode_label": "strict_lag",
        "decision_mode": "strict_lag",
        "decision_time": None,
    },
    {
        "mode_label": "night_partial",
        "decision_mode": "night_partial",
        "decision_time": "21:30",
    },
    {
        "mode_label": "same_day_close",
        "decision_mode": "same_day_close",
        "decision_time": None,
    },
]


# Espacios de búsqueda iniciales para Optuna.
# Estos rangos afinan target_threshold y probability_threshold antes de pasar
# al tuning fino de XGBoost. Son deliberadamente amplios, pero acotados por tipo
# de fondo para evitar pruebas evidentemente inútiles.
THRESHOLD_SEARCH_SPACE: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "target_min": 0.0010,
        "target_max": 0.0020,
        "prob_min": 0.45,
        "prob_max": 0.55,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "ahorro_uf_itau": {
        "target_min": 0.0000,
        "target_max": 0.0025,
        "prob_min": 0.40,
        "prob_max": 0.60,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "national_equity": {
        "target_min": 0.0008,
        "target_max": 0.0015,
        "prob_min": 0.68,
        "prob_max": 0.78,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "toesca_equity": {
        "target_min": 0.0015,
        "target_max": 0.0030,
        "prob_min": 0.48,
        "prob_max": 0.62,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
}


# Espacios de búsqueda para fine tuning de hiperparámetros XGBoost.
# Se usan después de fijar decision_mode, target_threshold y probability_threshold
# en FUND_MODEL_CONFIG. La idea es afinar la forma del modelo sin volver a mover
# los thresholds iniciales ya encontrados por fondo.
XGB_SEARCH_SPACE: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "n_estimators": (150, 600),
        "learning_rate": (0.005, 0.05),
        "max_depth": (1, 3),
        "min_child_weight": (5, 15),
        "gamma": (0.0, 2.0),
        "subsample": (0.60, 0.95),
        "colsample_bytree": (0.60, 0.95),
        "reg_lambda": (5.0, 30.0),
        "reg_alpha": (0.1, 3.0),
    },
    "ahorro_uf_itau": {
        "n_estimators": (150, 600),
        "learning_rate": (0.005, 0.04),
        "max_depth": (1, 3),
        "min_child_weight": (5, 20),
        "gamma": (0.0, 2.5),
        "subsample": (0.60, 0.95),
        "colsample_bytree": (0.60, 0.95),
        "reg_lambda": (5.0, 35.0),
        "reg_alpha": (0.1, 4.0),
    },
    "national_equity": {
        "n_estimators": (250, 900),
        "learning_rate": (0.005, 0.06),
        "max_depth": (2, 5),
        "min_child_weight": (2, 12),
        "gamma": (0.0, 1.5),
        "subsample": (0.60, 1.00),
        "colsample_bytree": (0.60, 1.00),
        "reg_lambda": (1.0, 20.0),
        "reg_alpha": (0.0, 2.0),
    },
    "toesca_equity": {
        "n_estimators": (250, 900),
        "learning_rate": (0.005, 0.06),
        "max_depth": (2, 5),
        "min_child_weight": (2, 12),
        "gamma": (0.0, 1.5),
        "subsample": (0.60, 1.00),
        "colsample_bytree": (0.60, 1.00),
        "reg_lambda": (1.0, 20.0),
        "reg_alpha": (0.0, 2.0),
    },
}



def get_decision_mode_config(mode: str) -> dict[str, Any]:
    for item in DECISION_MODE_TESTS:
        if item["decision_mode"] == mode or item["mode_label"] == mode:
            return item.copy()
    raise ValueError(f"decision_mode inválido para Optuna: {mode}")


@dataclass
class TrainResult:
    experiment_key: str
    mode_label: str
    fund_key: str
    fund_label: str
    run_fm: str
    selected_series: str
    horizon_business_days: int
    decision_mode: str
    decision_time: str | None
    use_same_day_return_features: bool
    target_threshold: float
    probability_threshold: float
    train_start: str
    train_end: str
    eval_start: str
    eval_end: str
    rows_train: int
    rows_eval: int
    feature_count: int
    positive_rate_train: float
    positive_rate_eval: float
    best_params: dict[str, Any]
    metrics: dict[str, Any]
    model_path: str
    predictions_path: str
    feature_importance_path: str
    dataset_path: str
    live_predictions_path: str | None


# =============================================================================
# Utilidades
# =============================================================================

def parse_user_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d_%m_%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato no reconocido. Usa YYYY-MM-DD, DD-MM-YYYY o DD/MM/YYYY.")


def parse_user_time(value: str) -> time:
    value = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    raise ValueError("Formato de hora no reconocido. Usa HH:MM, por ejemplo 21:30.")


def ask_date(prompt: str) -> date:
    while True:
        raw = input(f"{prompt}: ").strip()
        try:
            return parse_user_date(raw)
        except ValueError as exc:
            print(exc)


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[S/n]" if default else "[s/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"s", "si", "sí", "y", "yes"}


def folder_to_date(folder_name: str) -> date | None:
    try:
        return datetime.strptime(folder_name, "%d_%m_%Y").date()
    except ValueError:
        return None


def ensure_output_dirs() -> None:
    for sub in ["models", "predictions", "features", "reports"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)


def safe_float(value: Any) -> float:
    if value is None:
        return np.nan
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return np.nan
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return np.nan


def feature_safe_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    text = text.replace("ü", "u").replace("ñ", "n")
    text = "".join(ch if ch.isalnum() else "_" for ch in text)
    text = "_".join(part for part in text.split("_") if part)
    return text[:80] or "unknown"


# =============================================================================
# Noticias
# =============================================================================

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


# =============================================================================
# Fondos CMF
# =============================================================================

def discover_fund_files(fund_key: str) -> list[Path]:
    folder = DOWNLOADS_DIR / str(FUND_CONFIG[fund_key]["folder"])
    if not folder.exists():
        print(f"[WARN] No existe carpeta: {folder}")
        return []
    return sorted(folder.glob("*.txt"))


def read_cmf_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8", engine="python", on_bad_lines="skip")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", dtype=str, encoding="latin-1", engine="python", on_bad_lines="skip")


def choose_series(df: pd.DataFrame, fund_key: str) -> str:
    preferred = [str(x) for x in FUND_CONFIG[fund_key]["preferred_series"]]
    available = sorted(df["SERIE"].dropna().astype(str).unique().tolist())

    for serie in preferred:
        if serie in available:
            return serie

    tmp = df.copy()
    if "PATRIMONIO_NETO" in tmp.columns:
        tmp["PATRIMONIO_NETO_NUM"] = tmp["PATRIMONIO_NETO"].map(safe_float)
    else:
        tmp["PATRIMONIO_NETO_NUM"] = np.nan

    by_series = tmp.groupby("SERIE")["PATRIMONIO_NETO_NUM"].mean().sort_values(ascending=False)

    if not by_series.empty:
        selected = str(by_series.index[0])
        print(f"[WARN] Serie preferida no encontrada para {fund_key}. Uso: {selected}")
        return selected

    raise RuntimeError(f"No se pudo escoger serie para {fund_key}. Disponibles: {available}")


def load_fund_data(fund_key: str, start: date, end: date) -> tuple[pd.DataFrame, str]:
    cfg = FUND_CONFIG[fund_key]
    run_fm = str(cfg["run_fm"])
    files = discover_fund_files(fund_key)

    if not files:
        raise RuntimeError(f"No hay archivos para {fund_key}")

    frames = []
    for p in files:
        df = read_cmf_file(p)
        df.columns = [str(c).strip() for c in df.columns]

        if "RUN_FM" not in df.columns or "FECHA_INF" not in df.columns:
            print(f"[WARN] Archivo sin RUN_FM/FECHA_INF, omitido: {p}")
            continue

        df = df[df["RUN_FM"].astype(str) == run_fm]
        if not df.empty:
            frames.append(df)

    if not frames:
        raise RuntimeError(f"No se encontraron filas RUN_FM={run_fm} para {fund_key}")

    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    serie = choose_series(df, fund_key)

    df = df[df["SERIE"].astype(str) == serie].copy()
    df["date"] = pd.to_datetime(df["FECHA_INF"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))].copy()

    for col in [
        "VALOR_CUOTA", "PATRIMONIO_NETO", "ACTIVO_TOT",
        "CUOTAS_APORTADAS", "CUOTAS_RESCATADAS", "CUOTAS_EN_CIRCULACION",
        "NUM_PARTICIPES", "REM_FIJA", "REM_VARIABLE", "GASTOS_AFECTOS",
        "GASTOS_NO_AFECTOS", "COMISION_INVERSION", "COMISION_RESCATE",
    ]:
        if col in df.columns:
            df[col] = df[col].map(safe_float)

    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").set_index("date")
    df["valor_cuota"] = df["VALOR_CUOTA"].astype(float)
    df = df[df["valor_cuota"].notna() & (df["valor_cuota"] > 0)].copy()

    print(f"  {fund_key}: {len(df)} filas, serie={serie}")
    return df, serie


def add_fund_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["return_1d"] = df["valor_cuota"].pct_change(1)
    df["log_return_1d"] = np.log(df["valor_cuota"]).diff(1)
    df["return_1d_lag1_safe"] = df["return_1d"].shift(1)
    df["log_return_1d_lag1_safe"] = df["log_return_1d"].shift(1)

    for lag in [1, 2, 3, 5, 10, 20]:
        df[f"return_lag_{lag}"] = df["return_1d"].shift(lag)
        df[f"log_return_lag_{lag}"] = df["log_return_1d"].shift(lag)

    for window in [3, 5, 10, 20]:
        df[f"return_roll_mean_{window}"] = df["return_1d"].rolling(window).mean().shift(1)
        df[f"return_roll_std_{window}"] = df["return_1d"].rolling(window).std().shift(1)
        df[f"momentum_{window}"] = df["valor_cuota"].pct_change(window).shift(1)

    # Medias móviles del valor cuota para semáforo técnico de entrada.
    # Se usa shift(1) para evitar que el semáforo use información futura
    # respecto de las variables técnicas disponibles al momento de decidir.
    for window in [5, 10, 20]:
        df[f"valor_cuota_ma_{window}"] = df["valor_cuota"].rolling(window).mean().shift(1)

    df["valor_cuota_vs_ma20"] = (df["valor_cuota"] / df["valor_cuota_ma_20"]) - 1
    df["ma5_vs_ma20"] = (df["valor_cuota_ma_5"] / df["valor_cuota_ma_20"]) - 1

    df["rolling_max_20"] = df["valor_cuota"].rolling(20).max().shift(1)
    df["drawdown_20"] = (df["valor_cuota"] / df["rolling_max_20"]) - 1

    if "CUOTAS_APORTADAS" in df.columns and "CUOTAS_RESCATADAS" in df.columns:
        df["net_flow_cuotas_raw"] = df["CUOTAS_APORTADAS"] - df["CUOTAS_RESCATADAS"]
        df["net_flow_cuotas_lag1"] = df["net_flow_cuotas_raw"].shift(1)
        df["net_flow_cuotas_lag2"] = df["net_flow_cuotas_raw"].shift(2)
        df["net_flow_cuotas_roll3_lag1"] = df["net_flow_cuotas_raw"].rolling(3).sum().shift(1)
        df["net_flow_cuotas_roll5_lag1"] = df["net_flow_cuotas_raw"].rolling(5).sum().shift(1)
        df["net_flow_cuotas_roll10_lag1"] = df["net_flow_cuotas_raw"].rolling(10).sum().shift(1)

    if "PATRIMONIO_NETO" in df.columns:
        df["patrimonio_return_1d"] = df["PATRIMONIO_NETO"].pct_change(1)
        df["patrimonio_return_lag1"] = df["patrimonio_return_1d"].shift(1)

    if "NUM_PARTICIPES" in df.columns:
        df["participes_change_1d"] = df["NUM_PARTICIPES"].diff(1)
        df["participes_change_lag1"] = df["participes_change_1d"].shift(1)

    df["day_of_week"] = df.index.dayofweek
    df["day_of_month"] = df.index.day
    df["month"] = df.index.month
    df["is_month_start"] = df.index.is_month_start.astype(int)
    df["is_month_end"] = df.index.is_month_end.astype(int)
    df["is_weekend_fund_date"] = (df.index.dayofweek >= 5).astype(int)

    return df


def add_targets(df: pd.DataFrame, horizon: int, threshold: float) -> pd.DataFrame:
    df = df.copy()
    df["future_exit_date"] = pd.Series(df.index, index=df.index).shift(-horizon)
    df["future_valor_cuota"] = df["valor_cuota"].shift(-horizon)
    df["future_return_h"] = (df["future_valor_cuota"] / df["valor_cuota"]) - 1
    df["target_up"] = (df["future_return_h"] > threshold).astype(int)
    return df


def build_dataset_for_fund(
    fund_key: str,
    start: date,
    end: date,
    news_df: pd.DataFrame,
    target_threshold: float,
) -> tuple[pd.DataFrame, str]:
    horizon = int(FUND_CONFIG[fund_key]["horizon_business_days"])
    fund_df, serie = load_fund_data(fund_key, start, end)
    fund_features = add_fund_features(fund_df)
    fund_target = add_targets(fund_features, horizon, target_threshold)

    ds = fund_target.join(news_df, how="left")
    ds = ds.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Importante para uso real / live:
    # No eliminamos aquí las últimas filas sin future_valor_cuota.
    # Esas filas no sirven para métricas históricas, pero sí sirven para
    # generar señal live del último día disponible con valor cuota/noticias.
    return ds, serie


def get_feature_columns(df: pd.DataFrame, use_same_day_return_features: bool = True) -> list[str]:
    excluded = {
        "target_up", "future_return_h", "future_valor_cuota", "future_exit_date",
        "valor_cuota", "RUN_ADM", "NOM_ADM", "RUN_FM", "FECHA_INF", "MONEDA",
        "PARTICIPES_INST", "SERIE", "FONDO_PEN", "VALOR_CUOTA",
        "CUOTAS_APORTADAS", "CUOTAS_RESCATADAS", "CUOTAS_EN_CIRCULACION",
        "PATRIMONIO_NETO", "ACTIVO_TOT", "NUM_PARTICIPES", "REM_FIJA",
        "REM_VARIABLE", "GASTOS_AFECTOS", "GASTOS_NO_AFECTOS",
        "COMISION_INVERSION", "COMISION_RESCATE", "net_flow_cuotas_raw",
    }

    if not use_same_day_return_features:
        excluded |= {"return_1d", "log_return_1d", "patrimonio_return_1d", "participes_change_1d"}

    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]


# =============================================================================
# ML
# =============================================================================

def import_ml_dependencies():
    try:
        from xgboost import XGBClassifier
        from sklearn.metrics import (
            accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
            precision_score, recall_score, roc_auc_score,
        )
        import joblib
    except ImportError as exc:
        print("Faltan dependencias. Ejecuta: pip install pandas numpy scikit-learn xgboost joblib")
        raise exc
    return locals()


def import_optuna_dependency():
    try:
        import optuna
    except ImportError as exc:
        print("Falta Optuna. Ejecuta: pip install optuna")
        raise exc
    return optuna


def base_xgb_params(
    scale_pos_weight: float = 1.0,
    fund_key: str | None = None,
) -> dict[str, Any]:
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "n_estimators": 500,
        "learning_rate": 0.03,
        "max_depth": 3,
        "min_child_weight": 5,
        "gamma": 0.5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 5.0,
        "reg_alpha": 0.1,
        "tree_method": "hist",
        "random_state": RANDOM_SEED,
        "scale_pos_weight": scale_pos_weight,
        "n_jobs": -1,
    }

    if fund_key is not None and fund_key in XGB_MODEL_CONFIG:
        params.update(XGB_MODEL_CONFIG[fund_key])

    return params


def merge_xgb_params(scale_pos_weight: float, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Combina parámetros base con overrides, preservando valores operativos obligatorios."""
    params = base_xgb_params(scale_pos_weight)
    if overrides:
        clean = {k: v for k, v in overrides.items() if v is not None}
        params.update(clean)

    params["objective"] = "binary:logistic"
    params["eval_metric"] = "logloss"
    params["tree_method"] = "hist"
    params["random_state"] = RANDOM_SEED
    params["scale_pos_weight"] = scale_pos_weight
    params["n_jobs"] = -1

    params["n_estimators"] = int(params["n_estimators"])
    params["max_depth"] = int(params["max_depth"])
    params["min_child_weight"] = float(params["min_child_weight"])
    return params


def suggest_xgb_params_for_fund(trial: Any, fund_key: str, scale_pos_weight: float) -> dict[str, Any]:
    """Sugiere hiperparámetros XGBoost por fondo usando rangos definidos en XGB_SEARCH_SPACE."""
    space = XGB_SEARCH_SPACE[fund_key]

    params = {
        "n_estimators": trial.suggest_int("n_estimators", int(space["n_estimators"][0]), int(space["n_estimators"][1]), step=50),
        "learning_rate": trial.suggest_float("learning_rate", float(space["learning_rate"][0]), float(space["learning_rate"][1]), log=True),
        "max_depth": trial.suggest_int("max_depth", int(space["max_depth"][0]), int(space["max_depth"][1])),
        "min_child_weight": trial.suggest_float("min_child_weight", float(space["min_child_weight"][0]), float(space["min_child_weight"][1])),
        "gamma": trial.suggest_float("gamma", float(space["gamma"][0]), float(space["gamma"][1])),
        "subsample": trial.suggest_float("subsample", float(space["subsample"][0]), float(space["subsample"][1])),
        "colsample_bytree": trial.suggest_float("colsample_bytree", float(space["colsample_bytree"][0]), float(space["colsample_bytree"][1])),
        "reg_lambda": trial.suggest_float("reg_lambda", float(space["reg_lambda"][0]), float(space["reg_lambda"][1]), log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", float(space["reg_alpha"][0]), float(space["reg_alpha"][1])),
    }
    return merge_xgb_params(scale_pos_weight, params)


def generate_param_candidates(scale_pos_weight: float, n_iter: int) -> list[dict[str, Any]]:
    grid = {
        "n_estimators": [200, 400, 600, 800],
        "learning_rate": [0.01, 0.03, 0.05, 0.08],
        "max_depth": [2, 3, 4],
        "min_child_weight": [3, 5, 10, 15],
        "gamma": [0, 0.3, 0.5, 1.0, 2.0],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.7, 0.8, 0.9],
        "reg_lambda": [1.0, 5.0, 10.0, 20.0],
        "reg_alpha": [0.0, 0.1, 0.5, 1.0],
    }
    random.seed(RANDOM_SEED)
    candidates = [base_xgb_params(scale_pos_weight)]
    for _ in range(n_iter):
        params = base_xgb_params(scale_pos_weight)
        for k, values in grid.items():
            params[k] = random.choice(values)
        candidates.append(params)
    return candidates


def tune_params(X_train, y_train, scale_pos_weight, n_iter, XGBClassifier, balanced_accuracy_score) -> dict[str, Any]:
    if len(X_train) < 80 or y_train.nunique() < 2:
        print("[WARN] Pocos datos o una sola clase. Se usará configuración base.")
        return base_xgb_params(scale_pos_weight)

    split = int(len(X_train) * 0.8)
    X_sub, y_sub = X_train.iloc[:split], y_train.iloc[:split]
    X_val, y_val = X_train.iloc[split:], y_train.iloc[split:]

    best_score = -1.0
    best_params = base_xgb_params(scale_pos_weight)
    candidates = generate_param_candidates(scale_pos_weight, n_iter)

    print(f" Afinando hiperparámetros con {len(candidates)} combinaciones...")

    for i, params in enumerate(candidates, 1):
        try:
            model = XGBClassifier(**params)
            model.fit(X_sub, y_sub)
            pred = model.predict(X_val)
            score = balanced_accuracy_score(y_val, pred)
        except Exception as exc:
            print(f"  [WARN] combinación {i} falló: {exc}")
            continue

        print(f"  {i:02d}/{len(candidates)} balanced_accuracy={score:.4f}")

        if score > best_score:
            best_score, best_params = score, params

    print(f" Mejor balanced_accuracy interno: {best_score:.4f}")
    return best_params


def evaluate_predictions(y_true, y_pred, y_prob, future_returns, deps) -> dict[str, Any]:
    out: dict[str, Any] = {}

    out["accuracy"] = float(deps["accuracy_score"](y_true, y_pred))
    out["balanced_accuracy"] = float(deps["balanced_accuracy_score"](y_true, y_pred))
    out["precision_up"] = float(deps["precision_score"](y_true, y_pred, zero_division=0))
    out["recall_up"] = float(deps["recall_score"](y_true, y_pred, zero_division=0))
    out["f1_up"] = float(deps["f1_score"](y_true, y_pred, zero_division=0))

    try:
        out["roc_auc"] = float(deps["roc_auc_score"](y_true, y_prob))
    except Exception:
        out["roc_auc"] = None

    cm = deps["confusion_matrix"](y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    out["confusion_matrix"] = cm.tolist()
    out["confusion_matrix_explained"] = {
        "rows": {"0": "real_no_sube_o_baja", "1": "real_sube"},
        "columns": {"0": "predice_mover_o_retirar", "1": "predice_mantener"},
        "table": {
            "real_no_sube_o_baja": {
                "predice_mover_o_retirar": int(tn),
                "predice_mantener": int(fp),
            },
            "real_sube": {
                "predice_mover_o_retirar": int(fn),
                "predice_mantener": int(tp),
            },
        },
        "interpretation": {
            "true_negative_salida_correcta": int(tn),
            "false_positive_mantener_incorrecto": int(fp),
            "false_negative_salida_incorrecta_oportunidad_perdida": int(fn),
            "true_positive_mantener_correcto": int(tp),
        },
    }

    future_returns = pd.Series(future_returns).astype(float)
    strategy_returns = np.where(np.array(y_pred) == 1, future_returns, 0.0)

    out["buy_hold_return_compounded"] = float(np.prod(1 + future_returns) - 1)
    out["strategy_return_compounded"] = float(np.prod(1 + strategy_returns) - 1)
    out["strategy_improvement_vs_buy_hold"] = float(out["strategy_return_compounded"] - out["buy_hold_return_compounded"])
    out["avg_future_return_when_pred_up"] = float(future_returns[np.array(y_pred) == 1].mean()) if np.any(np.array(y_pred) == 1) else 0.0
    out["avg_future_return_when_pred_down"] = float(future_returns[np.array(y_pred) == 0].mean()) if np.any(np.array(y_pred) == 0) else 0.0
    out["signals_up_mantener"] = int(np.sum(np.array(y_pred) == 1))
    out["signals_down_mover_o_retirar"] = int(np.sum(np.array(y_pred) == 0))

    return out


def build_entry_semaforo(
    predictions: pd.DataFrame,
    probability_threshold: float,
) -> pd.DataFrame:
    """Calcula semáforo técnico de entrada/permanencia.

    Semáforo estricto:
    - verde: exige condiciones mínimas obligatorias, no solo puntaje.
    - amarillo: condiciones mixtas; no entrada nueva ideal, pero posible mantener si ya estás dentro.
    - rojo: esperar fuera o evaluar salida/mover a defensivo.

    Esta capa no reentrena XGBoost ni modifica pred_up. Solo agrega columnas
    operativas al CSV de predicciones para monitoreo y decisión manual.
    """
    out = predictions.copy()

    required_cols = [
        "pred_up",
        "pred_prob_up",
        "momentum_10",
        "valor_cuota_vs_ma20",
        "drawdown_20",
    ]
    for col in required_cols:
        if col not in out.columns:
            out[col] = 0.0

    out["semaforo_cond_pred_up"] = (out["pred_up"] == 1).astype(int)
    out["semaforo_cond_prob"] = (out["pred_prob_up"] >= probability_threshold).astype(int)
    out["semaforo_cond_momentum_10"] = (out["momentum_10"] > 0).astype(int)
    out["semaforo_cond_valor_vs_ma20"] = (out["valor_cuota_vs_ma20"] > 0).astype(int)
    out["semaforo_cond_drawdown_20"] = (out["drawdown_20"] > -0.04).astype(int)

    out["entry_score"] = (
        out["semaforo_cond_pred_up"]
        + out["semaforo_cond_prob"]
        + out["semaforo_cond_momentum_10"]
        + out["semaforo_cond_valor_vs_ma20"]
        + out["semaforo_cond_drawdown_20"]
    )

    # Regla estricta: el verde no se activa solo por puntaje.
    # Debe cumplir condiciones mínimas de entrada técnica.
    # Esto evita que un fondo marque "verde" con momentum_10 negativo,
    # aunque reúna 4 puntos por las demás condiciones.
    green_required = (
        (out["pred_up"] == 1)
        & (out["pred_prob_up"] >= probability_threshold)
        & (out["momentum_10"] > 0)
        & (out["valor_cuota_vs_ma20"] > 0)
        & (out["drawdown_20"] > -0.04)
    )

    out["semaforo_green_required"] = green_required.astype(int)

    out["semaforo"] = np.select(
        [
            green_required & (out["entry_score"] >= 4),
            out["entry_score"] >= 2,
        ],
        [
            "verde",
            "amarillo",
        ],
        default="rojo",
    )

    out["decision_if_out"] = np.where(
        out["semaforo"] == "verde",
        "entrar",
        "esperar",
    )

    out["decision_if_in"] = np.select(
        [
            out["semaforo"] == "verde",
            out["semaforo"] == "amarillo",
        ],
        [
            "mantener",
            "mantener_con_alerta",
        ],
        default="salir_o_mover_defensivo",
    )

    return out


def build_experiment_key(
    fund_key: str,
    mode_label: str,
    probability_threshold: float,
    target_threshold: float,
) -> str:
    return (
        f"{fund_key}_{mode_label}"
        f"_prob{probability_threshold:.3f}".replace(".", "p")
        + f"_target{target_threshold:.4f}".replace(".", "p")
    )


def build_prediction_output(
    source_df: pd.DataFrame,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
    fund_key: str,
    selected_series: str,
    probability_threshold: float,
    target_threshold: float,
    decision_mode: str,
    decision_time_text: str | None,
    use_same_day_return_features: bool,
    horizon: int,
    is_live_signal: bool,
) -> pd.DataFrame:
    """Construye salida de predicción histórica o live con semáforo operativo."""
    cfg = FUND_CONFIG[fund_key]

    prediction_base_cols = [
        "valor_cuota",
        "future_exit_date",
        "future_valor_cuota",
        "future_return_h",
        "target_up",
    ]

    semaforo_feature_cols = [
        "momentum_10",
        "valor_cuota_vs_ma20",
        "drawdown_20",
        "return_roll_mean_5",
        "return_roll_mean_10",
        "return_roll_std_10",
        "ma5_vs_ma20",
    ]

    cols = [c for c in prediction_base_cols + semaforo_feature_cols if c in source_df.columns]
    predictions = source_df[cols].copy()

    # Asegura columnas base aunque sea señal live sin futuro conocido.
    for col in prediction_base_cols:
        if col not in predictions.columns:
            predictions[col] = np.nan

    predictions["pred_prob_up"] = y_prob
    predictions["pred_up"] = y_pred
    predictions["decision"] = np.where(predictions["pred_up"] == 1, "mantener", "mover_o_retirar")
    predictions["horizon_business_days"] = horizon
    predictions["fund_key"] = fund_key
    predictions["fund_label"] = str(cfg["label"])
    predictions["selected_series"] = selected_series
    predictions["decision_mode"] = decision_mode
    predictions["decision_time"] = decision_time_text or ""
    predictions["target_threshold"] = target_threshold
    predictions["probability_threshold"] = probability_threshold
    predictions["use_same_day_return_features"] = use_same_day_return_features
    predictions["is_live_signal"] = bool(is_live_signal)
    predictions["is_evaluable"] = ~((predictions["future_valor_cuota"] <= 0) | predictions["future_valor_cuota"].isna())

    if is_live_signal:
        predictions["captured_return_if_follow_signal"] = np.nan
    else:
        predictions["captured_return_if_follow_signal"] = np.where(
            predictions["pred_up"] == 1,
            predictions["future_return_h"],
            0.0,
        )

    predictions = build_entry_semaforo(
        predictions=predictions,
        probability_threshold=probability_threshold,
    )

    return predictions


def select_live_rows(dataset: pd.DataFrame, eval_start: date, eval_end: date) -> pd.DataFrame:
    """Filas dentro del rango que tienen valor cuota/noticias, pero no futuro evaluable."""
    live_df = dataset[
        (dataset.index >= pd.Timestamp(eval_start))
        & (dataset.index <= pd.Timestamp(eval_end))
        & (
            (dataset["future_valor_cuota"] <= 0)
            | (dataset["future_valor_cuota"].isna())
        )
    ].copy()
    return live_df


def print_confusion_matrix_readable(metrics: dict[str, Any]) -> None:
    explained = metrics.get("confusion_matrix_explained", {})
    table = explained.get("table", {})

    if not table:
        return

    real_down = table.get("real_no_sube_o_baja", {})
    real_up = table.get("real_sube", {})

    tn = int(real_down.get("predice_mover_o_retirar", 0))
    fp = int(real_down.get("predice_mantener", 0))
    fn = int(real_up.get("predice_mover_o_retirar", 0))
    tp = int(real_up.get("predice_mantener", 0))

    print("\nMatriz de confusión interpretada:")
    print("Filas = resultado real | Columnas = decisión del modelo\n")
    print("+----------------------+------------------------+-------------------+")
    print("| Resultado real       | Pred. mover/retiro     | Pred. mantener    |")
    print("+----------------------+------------------------+-------------------+")
    print(f"| No sube / baja       | {tn:^22} | {fp:^17} |")
    print(f"| Sube                 | {fn:^22} | {tp:^17} |")
    print("+----------------------+------------------------+-------------------+")
    print("Lectura:")
    print(f"  Salidas correctas:              {tn}")
    print(f"  Mantener incorrecto:            {fp}  <-- error riesgoso")
    print(f"  Salida incorrecta:              {fn}  <-- oportunidad perdida")
    print(f"  Mantener correcto:              {tp}")


def train_and_evaluate_fund(
    fund_key: str,
    dataset: pd.DataFrame,
    selected_series: str,
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    tune: bool,
    tune_iter: int,
    probability_threshold: float,
    decision_mode: str,
    decision_time_text: str | None,
    use_same_day_return_features: bool,
    target_threshold: float,
    dataset_path: Path,
    mode_label: str | None = None,
    xgb_params_override: dict[str, Any] | None = None,
) -> TrainResult:
    deps = import_ml_dependencies()
    XGBClassifier = deps["XGBClassifier"]
    joblib = deps["joblib"]

    cfg = FUND_CONFIG[fund_key]
    horizon = int(cfg["horizon_business_days"])
    dataset = dataset.sort_index()

    # Dataset completo conserva filas live sin futuro conocido.
    # Dataset evaluable se usa solamente para entrenamiento y métricas históricas.
    evaluated_dataset = dataset[dataset["future_valor_cuota"] > 0].copy()

    train_df = evaluated_dataset[(evaluated_dataset.index >= pd.Timestamp(train_start)) & (evaluated_dataset.index <= pd.Timestamp(train_end))].copy()
    eval_df = evaluated_dataset[(evaluated_dataset.index >= pd.Timestamp(eval_start)) & (evaluated_dataset.index <= pd.Timestamp(eval_end))].copy()

    print(f"  Dataset total: {len(dataset)} filas | evaluables: {len(evaluated_dataset)} | live/no evaluables: {len(dataset) - len(evaluated_dataset)}")
    if len(dataset):
        print(f"  Última fecha dataset: {dataset.index.max().date()}")
    if len(evaluated_dataset):
        print(f"  Última fecha evaluable: {evaluated_dataset.index.max().date()}")

    if len(train_df) < 30:
        raise RuntimeError(f"Entrenamiento insuficiente: {len(train_df)} filas")

    if len(eval_df) < 1:
        raise RuntimeError(
            "Evaluación sin filas evaluables. "
            "Para predecir solo el último día sin futuro conocido, usa --predict-live-only."
        )

    feature_cols = get_feature_columns(dataset, use_same_day_return_features=use_same_day_return_features)

    X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train = train_df["target_up"].astype(int)
    X_eval = eval_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_eval = eval_df["target_up"].astype(int)

    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    scale_pos_weight = (negatives / positives) if positives > 0 else 1.0

    if positives == 0 or negatives == 0:
        print(f"[WARN] {fund_key}: una sola clase en entrenamiento.")

    # Prioridad de selección de hiperparámetros:
    # 1) Si tune=True, se ejecuta el tuning interno clásico.
    # 2) Si se entrega xgb_params_override, se usan esos parámetros, combinados
    #    con los parámetros operativos obligatorios de XGBoost.
    # 3) Si no hay override, se usa la configuración base.
    if tune:
        best_params = tune_params(
            X_train,
            y_train,
            scale_pos_weight,
            tune_iter,
            XGBClassifier,
            deps["balanced_accuracy_score"],
        )
    elif xgb_params_override:
        best_params = merge_xgb_params(scale_pos_weight, xgb_params_override)
    else:
        best_params = base_xgb_params(scale_pos_weight)

    model = XGBClassifier(**best_params)
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_eval)[:, 1]
    y_pred = (y_prob >= probability_threshold).astype(int)

    metrics = evaluate_predictions(y_eval, y_pred, y_prob, eval_df["future_return_h"].values, deps)

    effective_mode_label = mode_label or decision_mode
    experiment_key = build_experiment_key(
        fund_key=fund_key,
        mode_label=effective_mode_label,
        probability_threshold=probability_threshold,
        target_threshold=target_threshold,
    )

    suffix = (
        f"{experiment_key}"
        + f"_{train_start}_{train_end}"
    )
    model_path = OUTPUT_DIR / "models" / f"xgb_{suffix}.joblib"

    joblib.dump(
        {
            "model": model,
            "feature_cols": feature_cols,
            "fund_key": fund_key,
            "fund_config": cfg,
            "selected_series": selected_series,
            "best_params": best_params,
            "probability_threshold": probability_threshold,
            "target_threshold": target_threshold,
            "decision_mode": decision_mode,
            "decision_time": decision_time_text,
            "use_same_day_return_features": use_same_day_return_features,
        },
        model_path,
    )

    predictions = build_prediction_output(
        source_df=eval_df,
        y_prob=y_prob,
        y_pred=y_pred,
        fund_key=fund_key,
        selected_series=selected_series,
        probability_threshold=probability_threshold,
        target_threshold=target_threshold,
        decision_mode=decision_mode,
        decision_time_text=decision_time_text,
        use_same_day_return_features=use_same_day_return_features,
        horizon=horizon,
        is_live_signal=False,
    )

    predictions_path = OUTPUT_DIR / "predictions" / f"predicciones_{suffix}_eval_{eval_start}_{eval_end}.csv"
    predictions.to_csv(predictions_path, index_label="date", encoding="utf-8")

    # Señales live: filas del rango que todavía no tienen futuro conocido.
    # Se predicen con el mismo modelo entrenado y se guardan en CSV separado.
    live_predictions_path: Path | None = None
    live_df = select_live_rows(dataset, eval_start, eval_end)
    if not live_df.empty:
        X_live = live_df.copy()
        for col in feature_cols:
            if col not in X_live.columns:
                X_live[col] = 0.0
        X_live = X_live[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

        live_prob = model.predict_proba(X_live)[:, 1]
        live_pred = (live_prob >= probability_threshold).astype(int)
        live_predictions = build_prediction_output(
            source_df=live_df,
            y_prob=live_prob,
            y_pred=live_pred,
            fund_key=fund_key,
            selected_series=selected_series,
            probability_threshold=probability_threshold,
            target_threshold=target_threshold,
            decision_mode=decision_mode,
            decision_time_text=decision_time_text,
            use_same_day_return_features=use_same_day_return_features,
            horizon=horizon,
            is_live_signal=True,
        )

        live_predictions_path = OUTPUT_DIR / "predictions" / f"live_predicciones_{suffix}_eval_{eval_start}_{eval_end}.csv"
        live_predictions.to_csv(live_predictions_path, index_label="date", encoding="utf-8")
        print(f"Señales live guardadas en: {live_predictions_path}")

    importance = pd.DataFrame({"feature": feature_cols, "importance": model.feature_importances_}).sort_values("importance", ascending=False)
    importance_path = OUTPUT_DIR / "features" / f"importancia_{suffix}_eval_{eval_start}_{eval_end}.csv"
    importance.to_csv(importance_path, index=False, encoding="utf-8")

    return TrainResult(
        experiment_key=experiment_key,
        mode_label=effective_mode_label,
        fund_key=fund_key,
        fund_label=str(cfg["label"]),
        run_fm=str(cfg["run_fm"]),
        selected_series=selected_series,
        horizon_business_days=horizon,
        decision_mode=decision_mode,
        decision_time=decision_time_text,
        use_same_day_return_features=use_same_day_return_features,
        target_threshold=target_threshold,
        probability_threshold=probability_threshold,
        train_start=train_start.isoformat(),
        train_end=train_end.isoformat(),
        eval_start=eval_start.isoformat(),
        eval_end=eval_end.isoformat(),
        rows_train=len(train_df),
        rows_eval=len(eval_df),
        feature_count=len(feature_cols),
        positive_rate_train=float(y_train.mean()),
        positive_rate_eval=float(y_eval.mean()),
        best_params=best_params,
        metrics=metrics,
        model_path=str(model_path),
        predictions_path=str(predictions_path),
        feature_importance_path=str(importance_path),
        dataset_path=str(dataset_path),
        live_predictions_path=str(live_predictions_path) if live_predictions_path else None,
    )



def predict_live_from_saved_model(
    fund_key: str,
    dataset: pd.DataFrame,
    selected_series: str,
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    probability_threshold: float,
    decision_mode: str,
    decision_time_text: str | None,
    use_same_day_return_features: bool,
    target_threshold: float,
    mode_label: str | None = None,
) -> str | None:
    """Carga el modelo esperado por fondo/configuración y genera solo señales live.

    Útil para el uso diario: tengo noticias y valor cuota hasta hoy, pero no
    future_valor_cuota. No calcula métricas ni reentrena.
    """
    deps = import_ml_dependencies()
    joblib = deps["joblib"]

    cfg = FUND_CONFIG[fund_key]
    horizon = int(cfg["horizon_business_days"])
    dataset = dataset.sort_index()

    effective_mode_label = mode_label or decision_mode
    experiment_key = build_experiment_key(
        fund_key=fund_key,
        mode_label=effective_mode_label,
        probability_threshold=probability_threshold,
        target_threshold=target_threshold,
    )
    suffix = f"{experiment_key}_{train_start}_{train_end}"
    model_path = OUTPUT_DIR / "models" / f"xgb_{suffix}.joblib"

    if not model_path.exists():
        raise RuntimeError(
            f"No existe modelo guardado para {fund_key}: {model_path}. "
            "Primero ejecuta una corrida normal de entrenamiento/evaluación con los mismos parámetros."
        )

    payload = joblib.load(model_path)
    model = payload["model"]
    feature_cols = list(payload.get("feature_cols", []))
    if not feature_cols:
        raise RuntimeError(f"Modelo sin feature_cols en payload: {model_path}")

    # En live-only usamos las filas no evaluables. Si no hay, tomamos la última
    # fila disponible del rango como señal práctica del día solicitado.
    live_df = select_live_rows(dataset, eval_start, eval_end)
    if live_df.empty:
        live_df = dataset[
            (dataset.index >= pd.Timestamp(eval_start))
            & (dataset.index <= pd.Timestamp(eval_end))
        ].tail(1).copy()

    if live_df.empty:
        print(f"[WARN] Sin filas para señal live de {fund_key} entre {eval_start} y {eval_end}.")
        return None

    X_live = live_df.copy()
    for col in feature_cols:
        if col not in X_live.columns:
            X_live[col] = 0.0
    X_live = X_live[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    live_prob = model.predict_proba(X_live)[:, 1]
    live_pred = (live_prob >= probability_threshold).astype(int)

    live_predictions = build_prediction_output(
        source_df=live_df,
        y_prob=live_prob,
        y_pred=live_pred,
        fund_key=fund_key,
        selected_series=selected_series,
        probability_threshold=probability_threshold,
        target_threshold=target_threshold,
        decision_mode=decision_mode,
        decision_time_text=decision_time_text,
        use_same_day_return_features=use_same_day_return_features,
        horizon=horizon,
        is_live_signal=True,
    )

    live_predictions_path = OUTPUT_DIR / "predictions" / f"live_predicciones_{suffix}_eval_{eval_start}_{eval_end}.csv"
    live_predictions.to_csv(live_predictions_path, index_label="date", encoding="utf-8")

    print(f"Modelo cargado: {model_path}")
    print(f"Señales live guardadas en: {live_predictions_path}")
    print(live_predictions.tail(5)[[
        "valor_cuota",
        "pred_prob_up",
        "pred_up",
        "momentum_10",
        "valor_cuota_vs_ma20",
        "drawdown_20",
        "entry_score",
        "semaforo_green_required",
        "semaforo",
        "decision_if_out",
        "decision_if_in",
    ]].to_string())

    return str(live_predictions_path)


# =============================================================================
# Búsqueda Optuna de hiperparámetros XGBoost
# =============================================================================

def build_xgb_score(metrics: dict[str, Any], score_mode: str) -> float:
    """Score para fine tuning de XGBoost con thresholds ya fijados por fondo."""
    strategy_return = float(metrics.get("strategy_return_compounded", 0.0) or 0.0)
    improvement = float(metrics.get("strategy_improvement_vs_buy_hold", 0.0) or 0.0)
    avg_up = float(metrics.get("avg_future_return_when_pred_up", 0.0) or 0.0)
    avg_down = float(metrics.get("avg_future_return_when_pred_down", 0.0) or 0.0)
    balanced_accuracy = float(metrics.get("balanced_accuracy", 0.0) or 0.0)

    if score_mode == "strategy_return":
        score = strategy_return
    elif score_mode == "improvement":
        score = improvement
    elif score_mode == "balanced_accuracy":
        score = balanced_accuracy
    elif score_mode == "risk_adjusted":
        score = improvement + 0.50 * strategy_return + 0.50 * (avg_up - avg_down)
    else:
        raise ValueError(f"score_mode inválido: {score_mode}")

    # Penalización suave si la señal no separa retornos esperados.
    if avg_up <= avg_down:
        score -= 0.02 + abs(avg_down - avg_up)

    return float(score)


def train_eval_for_xgb_trial(
    fund_key: str,
    dataset: pd.DataFrame,
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    probability_threshold: float,
    use_same_day_return_features: bool,
    xgb_params: dict[str, Any],
) -> dict[str, Any]:
    """Entrena/evalúa una prueba de hiperparámetros XGBoost sin escribir modelo."""
    deps = import_ml_dependencies()
    XGBClassifier = deps["XGBClassifier"]

    dataset = dataset.sort_index()
    train_df = dataset[(dataset.index >= pd.Timestamp(train_start)) & (dataset.index <= pd.Timestamp(train_end))].copy()
    eval_df = dataset[(dataset.index >= pd.Timestamp(eval_start)) & (dataset.index <= pd.Timestamp(eval_end))].copy()

    if len(train_df) < 30 or len(eval_df) < 1:
        raise RuntimeError(f"Filas insuficientes: train={len(train_df)}, eval={len(eval_df)}")

    feature_cols = get_feature_columns(dataset, use_same_day_return_features=use_same_day_return_features)
    X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train = train_df["target_up"].astype(int)
    X_eval = eval_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_eval = eval_df["target_up"].astype(int)

    if y_train.nunique() < 2:
        raise RuntimeError(f"{fund_key}: una sola clase en entrenamiento")

    model = XGBClassifier(**xgb_params)
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_eval)[:, 1]
    y_pred = (y_prob >= probability_threshold).astype(int)
    metrics = evaluate_predictions(y_eval, y_pred, y_prob, eval_df["future_return_h"].values, deps)

    return {
        "rows_train": int(len(train_df)),
        "rows_eval": int(len(eval_df)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_eval": float(y_eval.mean()),
        "feature_count": int(len(feature_cols)),
        "metrics": metrics,
    }


def run_optuna_xgb_search(
    funds: list[str],
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    args: argparse.Namespace,
) -> None:
    """Fine tuning de XGBoost por fondo usando FUND_MODEL_CONFIG como preset operativo."""
    optuna = import_optuna_dependency()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    ensure_output_dirs()

    print("\n" + "=" * 80)
    print("BÚSQUEDA OPTUNA DE HIPERPARÁMETROS XGBOOST")
    print("=" * 80)
    print(f"Trials por fondo: {args.optuna_xgb_trials}")
    print(f"Score: {args.optuna_xgb_score}")
    print("Los thresholds y decision_mode se toman desde FUND_MODEL_CONFIG salvo overrides CLI.")

    fund_runtime_configs = {fund_key: get_runtime_config_for_fund(fund_key, args) for fund_key in funds}

    news_start = train_start - timedelta(days=10)
    unique_news_configs = sorted({
        (
            str(cfg["decision_mode"]),
            str(cfg.get("decision_time")) if cfg.get("decision_mode") == "night_partial" else None,
        )
        for cfg in fund_runtime_configs.values()
    })

    news_cache: dict[tuple[str, str | None], pd.DataFrame] = {}
    print("\nConfiguraciones noticiosas necesarias para XGB Optuna:")
    for mode, dtime_text in unique_news_configs:
        print(f"  - {mode} | {dtime_text or 'N/A'}")
        dtime_obj = parse_user_time(dtime_text) if mode == "night_partial" and dtime_text else None
        news_cache[(mode, dtime_text)] = load_news_features(
            news_start,
            eval_end,
            decision_mode=mode,
            decision_time=dtime_obj,
        )

    all_trials_flat: list[dict[str, Any]] = []
    best_results: list[dict[str, Any]] = []

    for fund_key in funds:
        runtime_cfg = fund_runtime_configs[fund_key]
        print("\n" + "#" * 80)
        print(f"OPTUNA XGB | FONDO: {fund_key} | {FUND_CONFIG[fund_key]['label']}")
        print("#" * 80)
        print_fund_runtime_config(fund_key, runtime_cfg)

        decision_mode = str(runtime_cfg["decision_mode"])
        decision_time_text = str(runtime_cfg.get("decision_time")) if decision_mode == "night_partial" else None
        target_threshold = float(runtime_cfg["target_threshold"])
        probability_threshold = float(runtime_cfg["probability_threshold"])
        use_same_day_return_features = not bool(runtime_cfg["strict_return_lag"])

        news_df = news_cache[(decision_mode, decision_time_text)]
        dataset, serie = build_dataset_for_fund(
            fund_key=fund_key,
            start=train_start,
            end=eval_end,
            news_df=news_df,
            target_threshold=target_threshold,
        )
        dataset_suffix = (
            f"optuna_xgb_dataset_{fund_key}_{decision_mode}"
            f"_prob{probability_threshold:.3f}".replace(".", "p")
            + f"_target{target_threshold:.6f}".replace(".", "p")
            + f"_{train_start}_{eval_end}"
        )
        ds_path = OUTPUT_DIR / "features" / f"{dataset_suffix}.csv"
        dataset.to_csv(ds_path, index_label="date", encoding="utf-8")

        train_df = dataset[(dataset.index >= pd.Timestamp(train_start)) & (dataset.index <= pd.Timestamp(train_end))].copy()
        positives = int(train_df["target_up"].astype(int).sum())
        negatives = int(len(train_df) - positives)
        if positives == 0 or negatives == 0:
            print(f"[WARN] {fund_key}: una sola clase en entrenamiento. Se omite XGB Optuna.")
            continue
        scale_pos_weight = negatives / positives

        def objective(trial):
            params = suggest_xgb_params_for_fund(trial, fund_key, scale_pos_weight)
            try:
                trial_result = train_eval_for_xgb_trial(
                    fund_key=fund_key,
                    dataset=dataset,
                    train_start=train_start,
                    train_end=train_end,
                    eval_start=eval_start,
                    eval_end=eval_end,
                    probability_threshold=probability_threshold,
                    use_same_day_return_features=use_same_day_return_features,
                    xgb_params=params,
                )
            except Exception as exc:
                trial.set_user_attr("failed_reason", str(exc))
                return -999.0

            metrics = trial_result["metrics"]
            score = build_xgb_score(metrics, args.optuna_xgb_score)

            trial.set_user_attr("fund_key", fund_key)
            trial.set_user_attr("fund_label", str(FUND_CONFIG[fund_key]["label"]))
            trial.set_user_attr("selected_series", serie)
            trial.set_user_attr("decision_mode", decision_mode)
            trial.set_user_attr("decision_time", decision_time_text)
            trial.set_user_attr("target_threshold", target_threshold)
            trial.set_user_attr("probability_threshold", probability_threshold)
            trial.set_user_attr("rows_train", trial_result["rows_train"])
            trial.set_user_attr("rows_eval", trial_result["rows_eval"])
            trial.set_user_attr("positive_rate_train", trial_result["positive_rate_train"])
            trial.set_user_attr("positive_rate_eval", trial_result["positive_rate_eval"])
            trial.set_user_attr("feature_count", trial_result["feature_count"])
            trial.set_user_attr("metrics", metrics)
            trial.set_user_attr("score", score)
            trial.set_user_attr("dataset_path", str(ds_path))
            trial.set_user_attr("xgb_params", params)
            return score

        sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(
            objective,
            n_trials=int(args.optuna_xgb_trials),
            timeout=args.optuna_xgb_timeout,
            show_progress_bar=bool(args.optuna_progress_bar),
        )

        fund_rows: list[dict[str, Any]] = []
        for t in study.trials:
            attrs = dict(t.user_attrs)
            metrics = attrs.get("metrics", {}) if isinstance(attrs.get("metrics", {}), dict) else {}
            xgb_params = attrs.get("xgb_params", {}) if isinstance(attrs.get("xgb_params", {}), dict) else {}
            row = {
                "fund_key": fund_key,
                "fund_label": str(FUND_CONFIG[fund_key]["label"]),
                "trial_number": t.number,
                "state": str(t.state),
                "score": attrs.get("score", t.value),
                "decision_mode": attrs.get("decision_mode"),
                "decision_time": attrs.get("decision_time"),
                "target_threshold": attrs.get("target_threshold"),
                "probability_threshold": attrs.get("probability_threshold"),
                "rows_train": attrs.get("rows_train"),
                "rows_eval": attrs.get("rows_eval"),
                "positive_rate_train": attrs.get("positive_rate_train"),
                "positive_rate_eval": attrs.get("positive_rate_eval"),
                "feature_count": attrs.get("feature_count"),
                "failed_reason": attrs.get("failed_reason", ""),
                "dataset_path": attrs.get("dataset_path", ""),
            }
            for k, v in xgb_params.items():
                if k in {"objective", "eval_metric", "tree_method", "random_state", "n_jobs"}:
                    continue
                row[f"xgb_{k}"] = v
            for k, v in metrics.items():
                if isinstance(v, (dict, list)):
                    continue
                row[f"metric_{k}"] = v
            fund_rows.append(row)
            all_trials_flat.append(row)

        fund_rows_sorted = sorted(
            fund_rows,
            key=lambda r: float(r["score"]) if r.get("score") is not None else -999.0,
            reverse=True,
        )
        best_row = fund_rows_sorted[0] if fund_rows_sorted else {}
        best_results.append(best_row)

        print("\nMejor configuración XGBoost encontrada:")
        print(json.dumps(best_row, ensure_ascii=False, indent=2))

        preview_cols = [
            "trial_number", "score", "xgb_n_estimators", "xgb_learning_rate", "xgb_max_depth",
            "xgb_min_child_weight", "xgb_gamma", "xgb_subsample", "xgb_colsample_bytree",
            "xgb_reg_lambda", "xgb_reg_alpha",
            "metric_strategy_return_compounded", "metric_strategy_improvement_vs_buy_hold",
            "metric_avg_future_return_when_pred_up", "metric_avg_future_return_when_pred_down",
            "metric_signals_up_mantener", "metric_signals_down_mover_o_retirar",
        ]
        preview = pd.DataFrame(fund_rows_sorted[: min(10, len(fund_rows_sorted))])
        if not preview.empty:
            print("\nTop configuraciones XGBoost:")
            print(preview[[c for c in preview_cols if c in preview.columns]].to_string(index=False))

        fund_csv = OUTPUT_DIR / "reports" / (
            f"optuna_xgb_trials_{fund_key}_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
        )
        pd.DataFrame(fund_rows_sorted).to_csv(fund_csv, index=False, encoding="utf-8")
        print(f"\nTrials XGB del fondo guardados en: {fund_csv}")

        # Entrena y guarda el modelo final del mejor trial para dejarlo listo para validación externa.
        best_params = {k.replace("xgb_", ""): v for k, v in best_row.items() if str(k).startswith("xgb_")}
        if best_params:
            final_result = train_and_evaluate_fund(
                fund_key=fund_key,
                dataset=dataset,
                selected_series=serie,
                train_start=train_start,
                train_end=train_end,
                eval_start=eval_start,
                eval_end=eval_end,
                tune=False,
                tune_iter=0,
                probability_threshold=probability_threshold,
                decision_mode=decision_mode,
                decision_time_text=decision_time_text,
                use_same_day_return_features=use_same_day_return_features,
                target_threshold=target_threshold,
                dataset_path=ds_path,
                mode_label=f"{decision_mode}_xgb_optuna",
                xgb_params_override=best_params,
            )
            print(f"Modelo final del mejor trial guardado en: {final_result.model_path}")

    all_csv = OUTPUT_DIR / "reports" / (
        f"optuna_xgb_trials_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )
    best_csv = OUTPUT_DIR / "reports" / (
        f"optuna_xgb_best_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )
    best_json = OUTPUT_DIR / "reports" / (
        f"optuna_xgb_best_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
    )

    pd.DataFrame(all_trials_flat).to_csv(all_csv, index=False, encoding="utf-8")
    pd.DataFrame(best_results).to_csv(best_csv, index=False, encoding="utf-8")
    best_json.write_text(json.dumps(best_results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print("OPTUNA XGBOOST TERMINADO")
    print(f"Todos los trials XGB: {all_csv}")
    print(f"Mejores XGB por fondo CSV: {best_csv}")
    print(f"Mejores XGB por fondo JSON: {best_json}")
    print("=" * 80)


# =============================================================================
# Búsqueda Optuna de target_threshold y probability_threshold
# =============================================================================

def build_threshold_score(metrics: dict[str, Any], score_mode: str, min_signals_up: int, min_signals_down: int) -> float:
    """Score para Optuna.

    Se optimiza antes del tuning fino de XGBoost. Por eso el score castiga
    configuraciones degeneradas como "mantener siempre" o "salir siempre".
    """
    strategy_return = float(metrics.get("strategy_return_compounded", 0.0) or 0.0)
    improvement = float(metrics.get("strategy_improvement_vs_buy_hold", 0.0) or 0.0)
    avg_up = float(metrics.get("avg_future_return_when_pred_up", 0.0) or 0.0)
    avg_down = float(metrics.get("avg_future_return_when_pred_down", 0.0) or 0.0)
    signals_up = int(metrics.get("signals_up_mantener", 0) or 0)
    signals_down = int(metrics.get("signals_down_mover_o_retirar", 0) or 0)

    if score_mode == "strategy_return":
        score = strategy_return
    elif score_mode == "improvement":
        score = improvement
    elif score_mode == "risk_adjusted":
        score = improvement + 0.50 * strategy_return + 0.50 * (avg_up - avg_down)
    else:
        raise ValueError(f"score_mode inválido: {score_mode}")

    if signals_up < min_signals_up:
        score -= 0.02 * (min_signals_up - signals_up)
    if signals_down < min_signals_down:
        score -= 0.02 * (min_signals_down - signals_down)

    if signals_up > 0 and signals_down > 0 and avg_up <= avg_down:
        score -= 0.02 + abs(avg_down - avg_up)

    return float(score)


def train_eval_for_threshold_trial(
    fund_key: str,
    dataset: pd.DataFrame,
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    probability_threshold: float,
    decision_mode: str,
    decision_time_text: str | None,
    use_same_day_return_features: bool,
    target_threshold: float,
) -> dict[str, Any]:
    """Entrena/evalúa una prueba de umbrales sin escribir modelo ni predicciones."""
    deps = import_ml_dependencies()
    XGBClassifier = deps["XGBClassifier"]

    dataset = dataset.sort_index()
    train_df = dataset[(dataset.index >= pd.Timestamp(train_start)) & (dataset.index <= pd.Timestamp(train_end))].copy()
    eval_df = dataset[(dataset.index >= pd.Timestamp(eval_start)) & (dataset.index <= pd.Timestamp(eval_end))].copy()

    if len(train_df) < 30 or len(eval_df) < 1:
        raise RuntimeError(f"Filas insuficientes: train={len(train_df)}, eval={len(eval_df)}")

    feature_cols = get_feature_columns(dataset, use_same_day_return_features=use_same_day_return_features)

    X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train = train_df["target_up"].astype(int)
    X_eval = eval_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_eval = eval_df["target_up"].astype(int)

    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)

    if positives == 0 or negatives == 0:
        raise RuntimeError(
            f"{fund_key}: una sola clase en entrenamiento para target={target_threshold:.6f}. "
            f"positives={positives}, negatives={negatives}"
        )

    scale_pos_weight = negatives / positives
    params = base_xgb_params(scale_pos_weight)

    model = XGBClassifier(**params)
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_eval)[:, 1]
    y_pred = (y_prob >= probability_threshold).astype(int)

    metrics = evaluate_predictions(y_eval, y_pred, y_prob, eval_df["future_return_h"].values, deps)

    return {
        "fund_key": fund_key,
        "decision_mode": decision_mode,
        "decision_time": decision_time_text,
        "target_threshold": float(target_threshold),
        "probability_threshold": float(probability_threshold),
        "use_same_day_return_features": bool(use_same_day_return_features),
        "rows_train": int(len(train_df)),
        "rows_eval": int(len(eval_df)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_eval": float(y_eval.mean()),
        "feature_count": int(len(feature_cols)),
        "metrics": metrics,
    }


def run_optuna_threshold_search(
    funds: list[str],
    train_start: date,
    train_end: date,
    eval_start: date,
    eval_end: date,
    args: argparse.Namespace,
) -> None:
    optuna = import_optuna_dependency()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    ensure_output_dirs()

    news_start = train_start - timedelta(days=10)
    requested_modes = args.optuna_modes
    if not requested_modes or "all" in requested_modes:
        requested_modes = ["strict_lag", "night_partial", "same_day_close"]
    requested_modes = [str(x) for x in requested_modes]

    unique_news_configs: list[tuple[str, str | None]] = []
    for mode in requested_modes:
        mode_cfg = get_decision_mode_config(mode)
        decision_mode = str(mode_cfg["decision_mode"])
        decision_time_text = str(mode_cfg.get("decision_time")) if decision_mode == "night_partial" else None
        key = (decision_mode, decision_time_text)
        if key not in unique_news_configs:
            unique_news_configs.append(key)

    news_cache: dict[tuple[str, str | None], pd.DataFrame] = {}
    print("\nCargando matrices de noticias para Optuna:")
    for decision_mode, decision_time_text in unique_news_configs:
        dtime_obj = parse_user_time(decision_time_text) if decision_mode == "night_partial" and decision_time_text else None
        print(f"  - {decision_mode} | {decision_time_text or 'N/A'}")
        news_cache[(decision_mode, decision_time_text)] = load_news_features(
            news_start,
            eval_end,
            decision_mode=decision_mode,
            decision_time=dtime_obj,
        )

    all_trials_flat: list[dict[str, Any]] = []
    best_results: list[dict[str, Any]] = []

    print("\n" + "=" * 80)
    print("BÚSQUEDA OPTUNA DE UMBRALES")
    print("=" * 80)
    print(f"Trials por fondo: {args.optuna_trials}")
    print(f"Score: {args.optuna_score}")
    print(f"Modos: {requested_modes}")

    for fund_key in funds:
        print("\n" + "#" * 80)
        print(f"OPTUNA | FONDO: {fund_key} | {FUND_CONFIG[fund_key]['label']}")
        print("#" * 80)

        space = THRESHOLD_SEARCH_SPACE[fund_key].copy()
        target_min = args.optuna_target_min if args.optuna_target_min is not None else float(space["target_min"])
        target_max = args.optuna_target_max if args.optuna_target_max is not None else float(space["target_max"])
        prob_min = args.optuna_prob_min if args.optuna_prob_min is not None else float(space["prob_min"])
        prob_max = args.optuna_prob_max if args.optuna_prob_max is not None else float(space["prob_max"])

        available_modes = [m for m in requested_modes if m in set(space["modes"])]
        if not available_modes:
            available_modes = list(space["modes"])

        dataset_cache: dict[tuple[str, str, str | None, float], tuple[pd.DataFrame, str, Path]] = {}

        def get_dataset_for_trial(decision_mode: str, decision_time_text: str | None, target_threshold: float):
            target_key = round(float(target_threshold), 8)
            cache_key = (fund_key, decision_mode, decision_time_text, target_key)
            if cache_key in dataset_cache:
                return dataset_cache[cache_key]

            news_df = news_cache[(decision_mode, decision_time_text)]
            dataset, serie = build_dataset_for_fund(
                fund_key=fund_key,
                start=train_start,
                end=eval_end,
                news_df=news_df,
                target_threshold=target_threshold,
            )

            dataset_suffix = (
                f"optuna_dataset_{fund_key}_{decision_mode}"
                f"_target{target_threshold:.6f}".replace(".", "p")
                + f"_{train_start}_{eval_end}"
            )
            ds_path = OUTPUT_DIR / "features" / f"{dataset_suffix}.csv"
            dataset.to_csv(ds_path, index_label="date", encoding="utf-8")
            dataset_cache[cache_key] = (dataset, serie, ds_path)
            return dataset_cache[cache_key]

        def objective(trial):
            decision_mode = trial.suggest_categorical("decision_mode", available_modes)
            mode_cfg = get_decision_mode_config(str(decision_mode))
            effective_mode = str(mode_cfg["decision_mode"])
            decision_time_text = str(mode_cfg.get("decision_time")) if effective_mode == "night_partial" else None

            target_threshold = round(float(trial.suggest_float("target_threshold", target_min, target_max)), 6)
            probability_threshold = round(float(trial.suggest_float("probability_threshold", prob_min, prob_max)), 4)

            dataset, serie, ds_path = get_dataset_for_trial(effective_mode, decision_time_text, target_threshold)

            try:
                trial_result = train_eval_for_threshold_trial(
                    fund_key=fund_key,
                    dataset=dataset,
                    train_start=train_start,
                    train_end=train_end,
                    eval_start=eval_start,
                    eval_end=eval_end,
                    probability_threshold=probability_threshold,
                    decision_mode=effective_mode,
                    decision_time_text=decision_time_text,
                    use_same_day_return_features=not bool(args.strict_return_lag),
                    target_threshold=target_threshold,
                )
            except Exception as exc:
                trial.set_user_attr("failed_reason", str(exc))
                return -999.0

            metrics = trial_result["metrics"]
            score = build_threshold_score(
                metrics=metrics,
                score_mode=args.optuna_score,
                min_signals_up=args.optuna_min_signals_up,
                min_signals_down=args.optuna_min_signals_down,
            )

            trial.set_user_attr("fund_key", fund_key)
            trial.set_user_attr("fund_label", str(FUND_CONFIG[fund_key]["label"]))
            trial.set_user_attr("selected_series", serie)
            trial.set_user_attr("decision_time", decision_time_text)
            trial.set_user_attr("target_threshold", target_threshold)
            trial.set_user_attr("probability_threshold", probability_threshold)
            trial.set_user_attr("rows_train", trial_result["rows_train"])
            trial.set_user_attr("rows_eval", trial_result["rows_eval"])
            trial.set_user_attr("positive_rate_train", trial_result["positive_rate_train"])
            trial.set_user_attr("positive_rate_eval", trial_result["positive_rate_eval"])
            trial.set_user_attr("feature_count", trial_result["feature_count"])
            trial.set_user_attr("metrics", metrics)
            trial.set_user_attr("score", score)
            trial.set_user_attr("dataset_path", str(ds_path))
            return score

        sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(
            objective,
            n_trials=int(args.optuna_trials),
            timeout=args.optuna_timeout,
            show_progress_bar=bool(args.optuna_progress_bar),
        )

        fund_rows: list[dict[str, Any]] = []
        for t in study.trials:
            attrs = dict(t.user_attrs)
            metrics = attrs.get("metrics", {}) if isinstance(attrs.get("metrics", {}), dict) else {}
            row = {
                "fund_key": fund_key,
                "fund_label": str(FUND_CONFIG[fund_key]["label"]),
                "trial_number": t.number,
                "state": str(t.state),
                "score": attrs.get("score", t.value),
                "decision_mode": t.params.get("decision_mode"),
                "decision_time": attrs.get("decision_time"),
                "target_threshold": attrs.get("target_threshold", t.params.get("target_threshold")),
                "probability_threshold": attrs.get("probability_threshold", t.params.get("probability_threshold")),
                "rows_train": attrs.get("rows_train"),
                "rows_eval": attrs.get("rows_eval"),
                "positive_rate_train": attrs.get("positive_rate_train"),
                "positive_rate_eval": attrs.get("positive_rate_eval"),
                "feature_count": attrs.get("feature_count"),
                "failed_reason": attrs.get("failed_reason", ""),
                "dataset_path": attrs.get("dataset_path", ""),
            }
            for k, v in metrics.items():
                if isinstance(v, (dict, list)):
                    continue
                row[f"metric_{k}"] = v
            fund_rows.append(row)
            all_trials_flat.append(row)

        fund_rows_sorted = sorted(
            fund_rows,
            key=lambda r: float(r["score"]) if r.get("score") is not None else -999.0,
            reverse=True,
        )
        best_row = fund_rows_sorted[0] if fund_rows_sorted else {}
        best_results.append(best_row)

        print("\nMejor configuración encontrada:")
        print(json.dumps(best_row, ensure_ascii=False, indent=2))

        print("\nTop configuraciones:")
        preview_cols = [
            "trial_number", "score", "decision_mode", "target_threshold", "probability_threshold",
            "metric_strategy_return_compounded", "metric_strategy_improvement_vs_buy_hold",
            "metric_avg_future_return_when_pred_up", "metric_avg_future_return_when_pred_down",
            "metric_signals_up_mantener", "metric_signals_down_mover_o_retirar",
        ]
        preview = pd.DataFrame(fund_rows_sorted[: min(10, len(fund_rows_sorted))])
        if not preview.empty:
            print(preview[[c for c in preview_cols if c in preview.columns]].to_string(index=False))

        fund_csv = OUTPUT_DIR / "reports" / (
            f"optuna_threshold_trials_{fund_key}_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
        )
        pd.DataFrame(fund_rows_sorted).to_csv(fund_csv, index=False, encoding="utf-8")
        print(f"\nTrials del fondo guardados en: {fund_csv}")

    all_csv = OUTPUT_DIR / "reports" / (
        f"optuna_threshold_trials_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )
    best_csv = OUTPUT_DIR / "reports" / (
        f"optuna_threshold_best_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )
    best_json = OUTPUT_DIR / "reports" / (
        f"optuna_threshold_best_ALL_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
    )

    pd.DataFrame(all_trials_flat).to_csv(all_csv, index=False, encoding="utf-8")
    pd.DataFrame(best_results).to_csv(best_csv, index=False, encoding="utf-8")
    best_json.write_text(json.dumps(best_results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print("OPTUNA TERMINADO")
    print(f"Todos los trials: {all_csv}")
    print(f"Mejores por fondo CSV: {best_csv}")
    print(f"Mejores por fondo JSON: {best_json}")
    print("=" * 80)


# =============================================================================
# Configuración por fondo y CLI
# =============================================================================

def get_runtime_config_for_fund(fund_key: str, args: argparse.Namespace) -> dict[str, Any]:
    if args.no_fund_presets:
        cfg = {
            "decision_mode": args.decision_mode,
            "decision_time": args.decision_time if args.decision_mode == "night_partial" else None,
            "probability_threshold": args.probability_threshold,
            "target_threshold": args.target_threshold,
            "strict_return_lag": args.strict_return_lag,
            "tune": args.tune,
            "tune_iter": args.tune_iter,
        }
        if not args.no_fund_xgb_config and fund_key in XGB_MODEL_CONFIG:
            cfg["xgb_params"] = XGB_MODEL_CONFIG[fund_key].copy()
        return cfg

    cfg = FUND_MODEL_CONFIG.get(fund_key, {}).copy()

    if not args.no_fund_xgb_config and fund_key in XGB_MODEL_CONFIG:
        # Se guarda dentro de la configuración runtime para que cada experimento
        # pueda usar hiperparámetros XGBoost específicos del fondo sin duplicar código.
        cfg["xgb_params"] = XGB_MODEL_CONFIG[fund_key].copy()

    # Overrides opcionales desde CLI. Si se dejan en None, se usa preset por fondo.
    if args.override_decision_mode is not None:
        cfg["decision_mode"] = args.override_decision_mode
        cfg["decision_time"] = args.decision_time if args.override_decision_mode == "night_partial" else None

    if args.override_probability_threshold is not None:
        cfg["probability_threshold"] = args.override_probability_threshold

    if args.override_target_threshold is not None:
        cfg["target_threshold"] = args.override_target_threshold

    if args.override_strict_return_lag is not None:
        cfg["strict_return_lag"] = args.override_strict_return_lag

    if args.tune:
        cfg["tune"] = True
        cfg["tune_iter"] = args.tune_iter

    return cfg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Entrena y evalúa XGBoost por fondo usando parámetros específicos por fondo."
    )

    parser.add_argument("--train-start", default=None)
    parser.add_argument("--train-end", default=None)
    parser.add_argument("--eval-start", default=None)
    parser.add_argument("--eval-end", default=None)
    parser.add_argument("--fund", nargs="+", default=None, help="Fondos: crecimiento_balanceado ahorro_uf_itau national_equity toesca_equity all")

    # Parámetros globales de compatibilidad con el script anterior.
    parser.add_argument("--tune", action="store_true")
    parser.add_argument("--tune-iter", type=int, default=15)
    parser.add_argument("--target-threshold", type=float, default=0.0)
    parser.add_argument("--probability-threshold", type=float, default=0.5)
    parser.add_argument("--decision-mode", choices=["strict_lag", "night_partial", "same_day_close"], default="strict_lag")
    parser.add_argument("--decision-time", default="21:30")
    parser.add_argument("--strict-return-lag", action="store_true")

    # Nuevo comportamiento.
    parser.add_argument(
        "--single-preset-run",
        action="store_true",
        help=(
            "Ejecuta una sola configuración por fondo. Si no se activa, el script prueba por defecto "
            "las 3 modalidades: strict_lag, night_partial y same_day_close."
        ),
    )

    parser.add_argument(
        "--no-fund-presets",
        action="store_true",
        help="Desactiva presets por fondo y usa los parámetros globales anteriores para todos los fondos.",
    )
    parser.add_argument(
        "--no-fund-xgb-config",
        action="store_true",
        help=(
            "Desactiva XGB_MODEL_CONFIG en ejecuciones normales. "
            "Útil si quieres volver temporalmente a base_xgb_params."
        ),
    )
    parser.add_argument(
        "--predict-live-only",
        action="store_true",
        help=(
            "No reentrena ni calcula métricas. Carga el modelo .joblib esperado para cada fondo "
            "y genera solo live_predicciones para el último día/rango solicitado."
        ),
    )

    # Overrides selectivos para aplicar una prueba global sin editar FUND_MODEL_CONFIG.
    parser.add_argument("--override-decision-mode", choices=["strict_lag", "night_partial", "same_day_close"], default=None)
    parser.add_argument("--override-probability-threshold", type=float, default=None)
    parser.add_argument("--override-target-threshold", type=float, default=None)

    parser.add_argument(
        "--override-strict-return-lag",
        choices=["true", "false"],
        default=None,
        help="Override opcional: true/false.",
    )

    # Fine tuning de hiperparámetros XGBoost con Optuna.
    parser.add_argument(
        "--optuna-xgb-search",
        action="store_true",
        help=(
            "Activa fine tuning de hiperparámetros XGBoost con Optuna. "
            "Usa decision_mode, target_threshold y probability_threshold desde FUND_MODEL_CONFIG."
        ),
    )
    parser.add_argument("--optuna-xgb-trials", type=int, default=200, help="Número de trials XGBoost por fondo.")
    parser.add_argument("--optuna-xgb-timeout", type=int, default=None, help="Timeout en segundos por fondo para XGB Optuna.")
    parser.add_argument(
        "--optuna-xgb-score",
        choices=["risk_adjusted", "strategy_return", "improvement", "balanced_accuracy"],
        default="risk_adjusted",
        help="Métrica objetivo para el fine tuning de XGBoost.",
    )

    # Búsqueda automática de target_threshold y probability_threshold con Optuna.
    parser.add_argument(
        "--optuna-threshold-search",
        action="store_true",
        help=(
            "Activa búsqueda automática con Optuna para target_threshold, "
            "probability_threshold y decision_mode. No afina hiperparámetros de XGBoost."
        ),
    )
    parser.add_argument("--optuna-trials", type=int, default=80, help="Número de trials por fondo.")
    parser.add_argument("--optuna-timeout", type=int, default=None, help="Timeout en segundos por fondo.")
    parser.add_argument(
        "--optuna-modes",
        nargs="+",
        choices=["all", "strict_lag", "night_partial", "same_day_close"],
        default=["all"],
        help="Modos de decisión a incluir en la búsqueda Optuna.",
    )
    parser.add_argument(
        "--optuna-score",
        choices=["risk_adjusted", "strategy_return", "improvement"],
        default="risk_adjusted",
        help="Métrica objetivo para Optuna.",
    )
    parser.add_argument(
        "--optuna-min-signals-up",
        type=int,
        default=2,
        help="Mínimo deseado de señales mantener; se penaliza si hay menos.",
    )
    parser.add_argument(
        "--optuna-min-signals-down",
        type=int,
        default=2,
        help="Mínimo deseado de señales mover/retiro; se penaliza si hay menos.",
    )
    parser.add_argument("--optuna-target-min", type=float, default=None)
    parser.add_argument("--optuna-target-max", type=float, default=None)
    parser.add_argument("--optuna-prob-min", type=float, default=None)
    parser.add_argument("--optuna-prob-max", type=float, default=None)
    parser.add_argument(
        "--optuna-progress-bar",
        action="store_true",
        help="Muestra barra de progreso de Optuna.",
    )

    args = parser.parse_args()

    if args.override_strict_return_lag is not None:
        args.override_strict_return_lag = args.override_strict_return_lag.lower() == "true"

    return args


def choose_funds_interactively() -> list[str]:
    print("\nFondos disponibles:")
    for key, cfg in FUND_CONFIG.items():
        print(f"  - {key}: {cfg['label']} | retiro: {cfg['horizon_business_days']} días hábiles")
    print("  - all: todos")
    raw = input("\nEscribe fondo(s) separados por espacio, o all: ").strip().lower()
    return raw.split() if raw else ["all"]


def normalize_fund_selection(selection: list[str] | None) -> list[str]:
    if not selection:
        selection = choose_funds_interactively()

    cleaned = [x.strip().lower() for x in selection]

    if "all" in cleaned:
        return list(FUND_CONFIG.keys())

    invalid = [x for x in cleaned if x not in FUND_CONFIG]
    if invalid:
        raise ValueError(f"Fondos inválidos: {invalid}. Opciones: {list(FUND_CONFIG)} o all.")

    return cleaned


def print_fund_runtime_config(fund_key: str, cfg: dict[str, Any]) -> None:
    print("Parámetros del fondo:")
    print(f"  decision_mode:           {cfg['decision_mode']}")
    print(f"  decision_time:           {cfg.get('decision_time') or 'N/A'}")
    print(f"  target_threshold:        {cfg['target_threshold']}")
    print(f"  probability_threshold:   {cfg['probability_threshold']}")
    print(f"  strict_return_lag:       {cfg['strict_return_lag']}")
    print(f"  tune:                    {cfg['tune']}")
    print(f"  tune_iter:               {cfg['tune_iter']}")
    if cfg.get("xgb_params"):
        print("  xgb_params:              configurados por fondo")


def main() -> None:
    warnings.filterwarnings("ignore")
    np.random.seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    args = parse_args()
    ensure_output_dirs()

    print("=" * 80)
    print("APP XGBOOST FONDOS MUTUOS + NOTICIAS | EVALUACIÓN MULTIMODAL")
    print("=" * 80)

    train_start = parse_user_date(args.train_start) if args.train_start else ask_date("Fecha inicio entrenamiento")
    train_end = parse_user_date(args.train_end) if args.train_end else ask_date("Fecha término entrenamiento")
    eval_start = parse_user_date(args.eval_start) if args.eval_start else ask_date("Fecha inicio evaluación/práctica")
    eval_end = parse_user_date(args.eval_end) if args.eval_end else ask_date("Fecha término evaluación/práctica")

    if train_start > train_end or eval_start > eval_end:
        raise ValueError("Rangos de fechas inválidos.")

    if train_end >= eval_start:
        print("[WARN] Entrenamiento se cruza o toca evaluación. Idealmente train_end < eval_start.")

    funds = normalize_fund_selection(args.fund)

    run_all_modes = not bool(args.single_preset_run)

    print("\nConfiguración general:")
    print(f"  Train: {train_start} a {train_end}")
    print(f"  Eval:  {eval_start} a {eval_end}")
    print(f"  Fondos: {funds}")
    print(f"  Modo evaluación 3 modalidades: {run_all_modes}")
    print(f"  Usa presets por fondo: {not args.no_fund_presets}")
    print(f"  Usa XGB_MODEL_CONFIG: {not args.no_fund_xgb_config}")
    print(f"  Predict live only: {bool(args.predict_live_only)}")
    print(f"  Optuna threshold search: {bool(args.optuna_threshold_search)}")
    print(f"  Optuna XGB search: {bool(args.optuna_xgb_search)}")

    if args.optuna_xgb_search:
        run_optuna_xgb_search(
            funds=funds,
            train_start=train_start,
            train_end=train_end,
            eval_start=eval_start,
            eval_end=eval_end,
            args=args,
        )
        return

    if args.optuna_threshold_search:
        run_optuna_threshold_search(
            funds=funds,
            train_start=train_start,
            train_end=train_end,
            eval_start=eval_start,
            eval_end=eval_end,
            args=args,
        )
        return

    # Configuración base por fondo: thresholds, target y retorno del mismo día.
    # En modo multimodal se mantiene eso por fondo, pero se reemplaza decision_mode.
    fund_runtime_configs: dict[str, dict[str, Any]] = {
        fund_key: get_runtime_config_for_fund(fund_key, args)
        for fund_key in funds
    }

    # Construye la grilla de experimentos.
    experiments: list[dict[str, Any]] = []

    if run_all_modes:
        for fund_key in funds:
            base_cfg = fund_runtime_configs[fund_key].copy()

            for mode_cfg in DECISION_MODE_TESTS:
                exp_cfg = base_cfg.copy()
                exp_cfg["mode_label"] = str(mode_cfg["mode_label"])
                exp_cfg["decision_mode"] = str(mode_cfg["decision_mode"])
                exp_cfg["decision_time"] = mode_cfg.get("decision_time")

                # Overrides globales opcionales siguen respetándose.
                if args.override_probability_threshold is not None:
                    exp_cfg["probability_threshold"] = args.override_probability_threshold
                if args.override_target_threshold is not None:
                    exp_cfg["target_threshold"] = args.override_target_threshold
                if args.override_strict_return_lag is not None:
                    exp_cfg["strict_return_lag"] = args.override_strict_return_lag
                if args.tune:
                    exp_cfg["tune"] = True
                    exp_cfg["tune_iter"] = args.tune_iter

                experiments.append(
                    {
                        "fund_key": fund_key,
                        "config": exp_cfg,
                    }
                )
    else:
        for fund_key in funds:
            exp_cfg = fund_runtime_configs[fund_key].copy()
            exp_cfg["mode_label"] = str(exp_cfg["decision_mode"])
            experiments.append(
                {
                    "fund_key": fund_key,
                    "config": exp_cfg,
                }
            )

    print("\nExperimentos a ejecutar:")
    for exp in experiments:
        fk = exp["fund_key"]
        cfg = exp["config"]
        print(
            f"  - {fk} | {cfg['mode_label']} | "
            f"mode={cfg['decision_mode']} | "
            f"time={cfg.get('decision_time') or 'N/A'} | "
            f"prob={cfg['probability_threshold']} | "
            f"target={cfg['target_threshold']}"
        )

    # Carga noticias una sola vez por combinación única de decision_mode/decision_time.
    news_start = train_start - timedelta(days=10)
    news_cache: dict[tuple[str, str | None], pd.DataFrame] = {}

    unique_news_configs = sorted({
        (
            str(exp["config"]["decision_mode"]),
            str(exp["config"].get("decision_time")) if exp["config"].get("decision_mode") == "night_partial" else None,
        )
        for exp in experiments
    })

    print("\nConfiguraciones noticiosas necesarias:")
    for mode, dtime in unique_news_configs:
        print(f"  - {mode} | {dtime or 'N/A'}")

    for mode, dtime_text in unique_news_configs:
        dtime_obj = parse_user_time(dtime_text) if mode == "night_partial" and dtime_text else None
        news_cache[(mode, dtime_text)] = load_news_features(
            news_start,
            eval_end,
            decision_mode=mode,
            decision_time=dtime_obj,
        )

    results: list[TrainResult] = []

    # Ejecución secuencial: fondo por fondo, modalidad por modalidad.
    for exp in experiments:
        fund_key = str(exp["fund_key"])
        runtime_cfg = exp["config"]

        print("\n" + "#" * 80)
        print(f"FONDO: {fund_key} | {FUND_CONFIG[fund_key]['label']} | MODALIDAD: {runtime_cfg['mode_label']}")
        print("#" * 80)

        try:
            print_fund_runtime_config(fund_key, runtime_cfg)

            decision_mode = str(runtime_cfg["decision_mode"])
            decision_time_text = str(runtime_cfg.get("decision_time")) if decision_mode == "night_partial" else None
            mode_label = str(runtime_cfg.get("mode_label") or decision_mode)

            news_df = news_cache[(decision_mode, decision_time_text)]

            target_threshold = float(runtime_cfg["target_threshold"])
            probability_threshold = float(runtime_cfg["probability_threshold"])
            tune = bool(runtime_cfg["tune"])
            tune_iter = int(runtime_cfg["tune_iter"])
            use_same_day_return_features = not bool(runtime_cfg["strict_return_lag"])

            dataset, serie = build_dataset_for_fund(
                fund_key=fund_key,
                start=train_start,
                end=eval_end,
                news_df=news_df,
                target_threshold=target_threshold,
            )

            dataset_suffix = (
                f"{fund_key}_{mode_label}"
                f"_prob{probability_threshold:.3f}".replace(".", "p")
                + f"_target{target_threshold:.4f}".replace(".", "p")
                + f"_{train_start}_{eval_end}"
            )
            ds_path = OUTPUT_DIR / "features" / f"dataset_{dataset_suffix}.csv"
            dataset.to_csv(ds_path, index_label="date", encoding="utf-8")
            print(f" Dataset guardado en: {ds_path}")

            if args.predict_live_only:
                predict_live_from_saved_model(
                    fund_key=fund_key,
                    dataset=dataset,
                    selected_series=serie,
                    train_start=train_start,
                    train_end=train_end,
                    eval_start=eval_start,
                    eval_end=eval_end,
                    probability_threshold=probability_threshold,
                    decision_mode=decision_mode,
                    decision_time_text=decision_time_text,
                    use_same_day_return_features=use_same_day_return_features,
                    target_threshold=target_threshold,
                    mode_label=mode_label,
                )
                continue

            result = train_and_evaluate_fund(
                fund_key=fund_key,
                dataset=dataset,
                selected_series=serie,
                train_start=train_start,
                train_end=train_end,
                eval_start=eval_start,
                eval_end=eval_end,
                tune=tune,
                tune_iter=tune_iter,
                probability_threshold=probability_threshold,
                decision_mode=decision_mode,
                decision_time_text=decision_time_text,
                use_same_day_return_features=use_same_day_return_features,
                target_threshold=target_threshold,
                dataset_path=ds_path,
                mode_label=mode_label,
                xgb_params_override=runtime_cfg.get("xgb_params"),
            )
            results.append(result)

            print("\nResultados evaluación:")
            print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
            print_confusion_matrix_readable(result.metrics)
            print(f"Modelo: {result.model_path}")
            print(f"Predicciones: {result.predictions_path}")
            if result.live_predictions_path:
                print(f"Predicciones live: {result.live_predictions_path}")
            print(f"Importancia variables: {result.feature_importance_path}")

        except Exception as exc:
            print(f"[ERROR] Falló experimento {fund_key} | {runtime_cfg.get('mode_label')}: {exc}")

    summary = [asdict(r) for r in results]

    # Archivo único consolidado para analizar las tres modalidades.
    summary_path = OUTPUT_DIR / "reports" / (
        f"resumen_xgboost_3_modalidades_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
        if run_all_modes
        else f"resumen_xgboost_por_fondo_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # También guardamos una tabla plana CSV para análisis rápido en pandas/excel.
    flat_rows: list[dict[str, Any]] = []
    for r in results:
        item = asdict(r)
        metrics = item.pop("metrics", {})
        flat = {**item}
        for k, v in metrics.items():
            if isinstance(v, (dict, list)):
                continue
            flat[f"metric_{k}"] = v
        flat_rows.append(flat)

    flat_path = OUTPUT_DIR / "reports" / (
        f"resumen_xgboost_3_modalidades_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
        if run_all_modes
        else f"resumen_xgboost_por_fondo_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )

    if flat_rows:
        pd.DataFrame(flat_rows).to_csv(flat_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame().to_csv(flat_path, index=False, encoding="utf-8")

    print("\n" + "=" * 80)
    print("PROCESO TERMINADO")
    print(f"Experimentos ejecutados correctamente: {len(results)}")
    print(f"Resumen JSON único: {summary_path}")
    print(f"Resumen CSV plano:  {flat_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
