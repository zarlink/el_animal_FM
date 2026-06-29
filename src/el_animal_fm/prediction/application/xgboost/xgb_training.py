from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.features.dataset_builder import get_feature_columns
from el_animal_fm.prediction.application.xgboost.ml_dependencies import import_ml_dependencies
from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.signals.prediction_output import build_experiment_key, build_prediction_output, select_live_rows
from el_animal_fm.prediction.application.xgboost.xgb_evaluation import evaluate_predictions
from el_animal_fm.prediction.application.xgboost.xgb_params import base_xgb_params, merge_xgb_params, tune_params
from el_animal_fm.prediction.domain.models import TrainResult
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR

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
