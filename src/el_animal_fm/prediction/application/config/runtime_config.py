from __future__ import annotations

import argparse
from typing import Any

from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG, FUND_MODEL_CONFIG, XGB_MODEL_CONFIG

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
