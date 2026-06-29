from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.features.dataset_builder import get_feature_columns
from el_animal_fm.prediction.application.xgboost.ml_dependencies import import_ml_dependencies
from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.shared.prediction_utils import parse_user_time
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR

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
