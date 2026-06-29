from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

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
