from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.dataset_builder import build_dataset_for_fund, get_feature_columns
from el_animal_fm.prediction.application.ml_dependencies import import_ml_dependencies, import_optuna_dependency
from el_animal_fm.prediction.application.news_feature_builder import load_news_features
from el_animal_fm.prediction.application.prediction_config import FUND_CONFIG, RANDOM_SEED, THRESHOLD_SEARCH_SPACE, get_decision_mode_config
from el_animal_fm.prediction.application.prediction_utils import parse_user_time
from el_animal_fm.prediction.application.xgb_evaluation import build_threshold_score, evaluate_predictions
from el_animal_fm.prediction.application.xgb_params import base_xgb_params
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR, ensure_output_dirs

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
