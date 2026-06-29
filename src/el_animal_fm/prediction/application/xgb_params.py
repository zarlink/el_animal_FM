from __future__ import annotations

import math
import random
from typing import Any

import numpy as np

from el_animal_fm.prediction.application.ml_dependencies import import_ml_dependencies
from el_animal_fm.prediction.application.prediction_config import RANDOM_SEED, XGB_MODEL_CONFIG, XGB_SEARCH_SPACE

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
