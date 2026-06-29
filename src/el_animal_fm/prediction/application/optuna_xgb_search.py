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
from el_animal_fm.prediction.application.prediction_config import FUND_CONFIG, RANDOM_SEED
from el_animal_fm.prediction.application.prediction_utils import parse_user_time
from el_animal_fm.prediction.application.runtime_config import get_runtime_config_for_fund, print_fund_runtime_config
from el_animal_fm.prediction.application.xgb_evaluation import build_xgb_score, evaluate_predictions
from el_animal_fm.prediction.application.xgb_params import base_xgb_params, suggest_xgb_params_for_fund
from el_animal_fm.prediction.application.xgb_training import train_and_evaluate_fund
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR, ensure_output_dirs

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
