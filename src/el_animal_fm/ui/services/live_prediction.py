from __future__ import annotations

import json
import re
import warnings
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.features.dataset_builder import build_dataset_for_fund
from el_animal_fm.prediction.application.features.news_feature_builder import load_news_features
from el_animal_fm.prediction.application.features.decision_scenarios import assert_model_scenario
from el_animal_fm.prediction.application.shared.prediction_utils import parse_user_time
from el_animal_fm.prediction.application.signals.prediction_output import build_prediction_output
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR
from el_animal_fm.ui.services.available_prediction_date import latest_available_prediction_date
from el_animal_fm.ui.services.live_model_config import live_configuration, news_cutoff_label


def load_live_models(day: date, *, errors: dict | None = None) -> dict:
    models = {}
    missing = {}
    for key in FUND_CONFIG:
        config, expected = live_configuration(key)
        mode = config["decision_mode"]
        cutoff = config.get("decision_time") if mode == "night_partial" else None
        prefix = mode if expected["name"] == "legacy" else expected["name"] + "_"
        paths = []
        for path in (OUTPUT_DIR / "models").glob(f"xgb_{key}_{prefix}*.joblib"):
            dates = re.search(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.joblib$", path.name)
            if dates and date.fromisoformat(dates[2]) < day:
                paths.append((date.fromisoformat(dates[2]), path.stat().st_mtime, path))
        paths.sort(reverse=True)
        for _, _, path in paths:
            try:
                payload = joblib.load(path)
            except Exception as exc:
                print(f"[WARN] No se pudo leer modelo {path.name}: {exc}", flush=True)
                continue
            actual = payload.get("prediction_scenario") or {"name": "legacy"}
            if (payload.get("fund_key") != key or payload.get("decision_mode") != mode
                    or (payload.get("decision_time") or None) != cutoff or actual != expected
                    or not payload.get("feature_cols") or "model" not in payload
                    or not payload.get("selected_series")):
                continue
            if any(not np.isclose(payload.get(field, np.nan), config[field], rtol=0, atol=1e-12)
                   for field in ("target_threshold", "probability_threshold")):
                continue
            if payload.get("use_same_day_return_features") != (not config["strict_return_lag"]):
                continue
            if any(payload.get("best_params", {}).get(name) != value for name, value in config.get("xgb_params", {}).items()):
                continue
            if (actual["name"] == "legacy" and payload.get("fund_config", {}).get("horizon_business_days")
                    != FUND_CONFIG[key]["horizon_business_days"]):
                continue
            payload = {**payload, "prediction_scenario": actual}
            models[key] = (path, payload)
            break
        if key not in models:
            missing[key] = (f"{FUND_CONFIG[key]['label']}: pendiente de entrenar un modelo compatible "
                            f"anterior al {day:%d-%m-%Y} ({expected['name']}, {news_cutoff_label(mode, cutoff)}, "
                            f"objetivo {config['target_threshold']}, probabilidad {config['probability_threshold']}).")
    if errors is None and missing:
        raise ValueError("\n".join(missing.values()))
    if errors is not None:
        errors.update(missing)
    return models


def run_live_prediction() -> dict:
    day = latest_available_prediction_date()
    errors = {}
    models = load_live_models(day, errors=errors)
    start = day - timedelta(days=120)
    news_cache = {}
    results = {}
    for key, (path, payload) in models.items():
        try:
            mode, cutoff = payload["decision_mode"], payload.get("decision_time")
            options = payload["prediction_scenario"]
            cache_key = (mode, cutoff)
            if cache_key not in news_cache:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
                    news_cache[cache_key] = load_news_features(start-timedelta(days=10), day,
                                                             decision_mode=mode,
                                                             decision_time=parse_user_time(cutoff) if cutoff else None)
            print(f"Prediciendo {FUND_CONFIG[key]['label']} al {day:%d-%m-%Y} · "
                  f"{options['name']} · {news_cutoff_label(mode, cutoff)}…", flush=True)
            dataset, series = build_dataset_for_fund(key, start, day, news_cache[cache_key],
                                                   payload["target_threshold"], scenario=options)
            assert_model_scenario(payload, dataset)
            if series != payload["selected_series"]:
                raise ValueError(f"la serie {series} difiere de la del modelo ({payload['selected_series']}).")
            rows = dataset.loc[dataset.index == pd.Timestamp(day)].copy()
            if rows.empty:
                raise ValueError("sin datos para la fecha solicitada.")
            columns = payload["feature_cols"]
            missing = set(columns) - set(rows.columns)
            if missing:
                raise ValueError(f"faltan {len(missing)} variables requeridas por el modelo; reentrena con las noticias actuales.")
            inputs = rows[columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
            probability = payload["model"].predict_proba(inputs)[:, 1]
            threshold = payload["probability_threshold"]
            horizon = int(options.get("horizon_business_days", FUND_CONFIG[key]["horizon_business_days"]))
            output = build_prediction_output(rows, probability, (probability >= threshold).astype(int),
                                             key, series, threshold, payload["target_threshold"],
                                             mode, cutoff, payload["use_same_day_return_features"], horizon, True)
            row = json.loads(output.tail(1).to_json(orient="records", date_format="iso"))[0]
            row.update(model_path=str(path), prediction_scenario=options["name"], news_cutoff=news_cutoff_label(mode, cutoff))
            results[key] = row
        except Exception as exc:
            errors[key] = f"{FUND_CONFIG[key]['label']}: {exc}"
    for error in errors.values():
        print(f"[PENDIENTE] {error}", flush=True)
    result = {"schema_version": 2, "date": day.isoformat(), "cutoff": "por_fondo", "funds": results,
              "errors": errors, "models_loaded": len(models)}
    folder = OUTPUT_DIR / "predictions"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"dashboard_live_{day}_por_fondo.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return result


if __name__ == "__main__":
    result = run_live_prediction()
    print("[LIVE_RESULT] " + json.dumps(result, ensure_ascii=False), flush=True)
