from __future__ import annotations

import argparse

from el_animal_fm.prediction.application.prediction_pipeline import main

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


if __name__ == "__main__":
    main()
