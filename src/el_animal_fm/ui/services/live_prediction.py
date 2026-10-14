from __future__ import annotations

import json
import re
import warnings
from datetime import date, time, timedelta

import joblib
import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.features.dataset_builder import build_dataset_for_fund
from el_animal_fm.prediction.application.features.news_feature_builder import load_news_features
from el_animal_fm.prediction.application.signals.prediction_output import build_prediction_output
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR
from el_animal_fm.ui.services.available_prediction_date import latest_available_prediction_date


def load_live_models(day: date) -> dict:
    models = {}
    for key in FUND_CONFIG:
        paths = sorted((OUTPUT_DIR / "models").glob(f"xgb_{key}_night_partial*.joblib"),
                       key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            dates = re.search(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.joblib$", path.name)
            if not dates or date.fromisoformat(dates[2]) >= day:
                continue
            payload = joblib.load(path)
            if (payload.get("fund_key") == key and payload.get("decision_mode") == "night_partial"
                    and payload.get("decision_time") == "21:30" and payload.get("feature_cols")):
                models[key] = (path, payload)
                break
        if key not in models:
            raise ValueError(f"{FUND_CONFIG[key]['label']}: falta un modelo entrenado antes de {day:%d-%m-%Y} con corte 21:30.")
    return models


def run_live_prediction() -> dict:
    day = latest_available_prediction_date()
    models = load_live_models(day)
    start = day - timedelta(days=120)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
        news = load_news_features(start, day, decision_mode="night_partial", decision_time=time(21, 30))
    results = {}
    for key, (path, payload) in models.items():
        print(f"Prediciendo {FUND_CONFIG[key]['label']} al {day:%d-%m-%Y}, corte 21:30…", flush=True)
        dataset, series = build_dataset_for_fund(key, start, day, news, payload["target_threshold"])
        if series != payload["selected_series"]:
            raise ValueError(f"{key}: la serie {series} difiere de la del modelo ({payload['selected_series']}).")
        rows = dataset.loc[dataset.index == pd.Timestamp(day)].copy()
        if rows.empty:
            raise ValueError(f"{key}: sin datos para la fecha solicitada.")
        columns = payload["feature_cols"]
        missing = set(columns) - set(rows.columns)
        if missing:
            raise ValueError(f"{key}: faltan {len(missing)} variables requeridas por el modelo.")
        inputs = rows[columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        probability = payload["model"].predict_proba(inputs)[:, 1]
        threshold = payload["probability_threshold"]
        output = build_prediction_output(rows, probability, (probability >= threshold).astype(int),
                                         key, series, threshold, payload["target_threshold"],
                                         "night_partial", "21:30", payload["use_same_day_return_features"],
                                         int(FUND_CONFIG[key]["horizon_business_days"]), True)
        row = json.loads(output.tail(1).to_json(orient="records"))[0]
        row["model_path"] = str(path)
        results[key] = row
    result = {"date": day.isoformat(), "cutoff": "21:30", "funds": results}
    folder = OUTPUT_DIR / "predictions"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"dashboard_live_{day}_2130.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return result


if __name__ == "__main__":
    result = run_live_prediction()
    print("[LIVE_RESULT] " + json.dumps(result, ensure_ascii=False), flush=True)
