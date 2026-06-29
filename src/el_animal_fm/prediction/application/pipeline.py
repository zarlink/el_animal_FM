from __future__ import annotations

import json
import random
import warnings
from dataclasses import asdict
from datetime import timedelta

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.features.dataset_builder import build_dataset_for_fund
from el_animal_fm.prediction.application.features.news_feature_builder import load_news_features
from el_animal_fm.prediction.application.tuning.optuna_threshold_search import run_optuna_threshold_search
from el_animal_fm.prediction.application.tuning.optuna_xgb_search import run_optuna_xgb_search
from el_animal_fm.prediction.application.config.prediction_config import DECISION_MODE_TESTS, FUND_CONFIG, RANDOM_SEED
from el_animal_fm.prediction.application.signals.prediction_output import predict_live_from_saved_model
from el_animal_fm.prediction.application.shared.prediction_utils import ask_date, parse_user_date, parse_user_time
from el_animal_fm.prediction.application.config.runtime_config import get_runtime_config_for_fund, normalize_fund_selection, print_fund_runtime_config
from el_animal_fm.prediction.application.xgboost.xgb_evaluation import print_confusion_matrix_readable
from el_animal_fm.prediction.application.xgboost.xgb_training import train_and_evaluate_fund
from el_animal_fm.prediction.domain.models import TrainResult
from el_animal_fm.prediction.infrastructure.output_paths import OUTPUT_DIR, ensure_output_dirs

def main() -> None:
    from el_animal_fm.cli.xgboost_prediction import parse_args

    warnings.filterwarnings("ignore")
    np.random.seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    args = parse_args()
    ensure_output_dirs()

    print("=" * 80)
    print("APP XGBOOST FONDOS MUTUOS + NOTICIAS | EVALUACIÓN MULTIMODAL")
    print("=" * 80)

    train_start = parse_user_date(args.train_start) if args.train_start else ask_date("Fecha inicio entrenamiento")
    train_end = parse_user_date(args.train_end) if args.train_end else ask_date("Fecha término entrenamiento")
    eval_start = parse_user_date(args.eval_start) if args.eval_start else ask_date("Fecha inicio evaluación/práctica")
    eval_end = parse_user_date(args.eval_end) if args.eval_end else ask_date("Fecha término evaluación/práctica")

    if train_start > train_end or eval_start > eval_end:
        raise ValueError("Rangos de fechas inválidos.")

    if train_end >= eval_start:
        print("[WARN] Entrenamiento se cruza o toca evaluación. Idealmente train_end < eval_start.")

    funds = normalize_fund_selection(args.fund)

    run_all_modes = not bool(args.single_preset_run)

    print("\nConfiguración general:")
    print(f"  Train: {train_start} a {train_end}")
    print(f"  Eval:  {eval_start} a {eval_end}")
    print(f"  Fondos: {funds}")
    print(f"  Modo evaluación 3 modalidades: {run_all_modes}")
    print(f"  Usa presets por fondo: {not args.no_fund_presets}")
    print(f"  Usa XGB_MODEL_CONFIG: {not args.no_fund_xgb_config}")
    print(f"  Predict live only: {bool(args.predict_live_only)}")
    print(f"  Optuna threshold search: {bool(args.optuna_threshold_search)}")
    print(f"  Optuna XGB search: {bool(args.optuna_xgb_search)}")

    if args.optuna_xgb_search:
        run_optuna_xgb_search(
            funds=funds,
            train_start=train_start,
            train_end=train_end,
            eval_start=eval_start,
            eval_end=eval_end,
            args=args,
        )
        return

    if args.optuna_threshold_search:
        run_optuna_threshold_search(
            funds=funds,
            train_start=train_start,
            train_end=train_end,
            eval_start=eval_start,
            eval_end=eval_end,
            args=args,
        )
        return

    # Configuración base por fondo: thresholds, target y retorno del mismo día.
    # En modo multimodal se mantiene eso por fondo, pero se reemplaza decision_mode.
    fund_runtime_configs: dict[str, dict[str, Any]] = {
        fund_key: get_runtime_config_for_fund(fund_key, args)
        for fund_key in funds
    }

    # Construye la grilla de experimentos.
    experiments: list[dict[str, Any]] = []

    if run_all_modes:
        for fund_key in funds:
            base_cfg = fund_runtime_configs[fund_key].copy()

            for mode_cfg in DECISION_MODE_TESTS:
                exp_cfg = base_cfg.copy()
                exp_cfg["mode_label"] = str(mode_cfg["mode_label"])
                exp_cfg["decision_mode"] = str(mode_cfg["decision_mode"])
                exp_cfg["decision_time"] = mode_cfg.get("decision_time")

                # Overrides globales opcionales siguen respetándose.
                if args.override_probability_threshold is not None:
                    exp_cfg["probability_threshold"] = args.override_probability_threshold
                if args.override_target_threshold is not None:
                    exp_cfg["target_threshold"] = args.override_target_threshold
                if args.override_strict_return_lag is not None:
                    exp_cfg["strict_return_lag"] = args.override_strict_return_lag
                if args.tune:
                    exp_cfg["tune"] = True
                    exp_cfg["tune_iter"] = args.tune_iter

                experiments.append(
                    {
                        "fund_key": fund_key,
                        "config": exp_cfg,
                    }
                )
    else:
        for fund_key in funds:
            exp_cfg = fund_runtime_configs[fund_key].copy()
            exp_cfg["mode_label"] = str(exp_cfg["decision_mode"])
            experiments.append(
                {
                    "fund_key": fund_key,
                    "config": exp_cfg,
                }
            )

    print("\nExperimentos a ejecutar:")
    for exp in experiments:
        fk = exp["fund_key"]
        cfg = exp["config"]
        print(
            f"  - {fk} | {cfg['mode_label']} | "
            f"mode={cfg['decision_mode']} | "
            f"time={cfg.get('decision_time') or 'N/A'} | "
            f"prob={cfg['probability_threshold']} | "
            f"target={cfg['target_threshold']}"
        )

    # Carga noticias una sola vez por combinación única de decision_mode/decision_time.
    news_start = train_start - timedelta(days=10)
    news_cache: dict[tuple[str, str | None], pd.DataFrame] = {}

    unique_news_configs = sorted({
        (
            str(exp["config"]["decision_mode"]),
            str(exp["config"].get("decision_time")) if exp["config"].get("decision_mode") == "night_partial" else None,
        )
        for exp in experiments
    })

    print("\nConfiguraciones noticiosas necesarias:")
    for mode, dtime in unique_news_configs:
        print(f"  - {mode} | {dtime or 'N/A'}")

    for mode, dtime_text in unique_news_configs:
        dtime_obj = parse_user_time(dtime_text) if mode == "night_partial" and dtime_text else None
        news_cache[(mode, dtime_text)] = load_news_features(
            news_start,
            eval_end,
            decision_mode=mode,
            decision_time=dtime_obj,
        )

    results: list[TrainResult] = []

    # Ejecución secuencial: fondo por fondo, modalidad por modalidad.
    for exp in experiments:
        fund_key = str(exp["fund_key"])
        runtime_cfg = exp["config"]

        print("\n" + "#" * 80)
        print(f"FONDO: {fund_key} | {FUND_CONFIG[fund_key]['label']} | MODALIDAD: {runtime_cfg['mode_label']}")
        print("#" * 80)

        try:
            print_fund_runtime_config(fund_key, runtime_cfg)

            decision_mode = str(runtime_cfg["decision_mode"])
            decision_time_text = str(runtime_cfg.get("decision_time")) if decision_mode == "night_partial" else None
            mode_label = str(runtime_cfg.get("mode_label") or decision_mode)

            news_df = news_cache[(decision_mode, decision_time_text)]

            target_threshold = float(runtime_cfg["target_threshold"])
            probability_threshold = float(runtime_cfg["probability_threshold"])
            tune = bool(runtime_cfg["tune"])
            tune_iter = int(runtime_cfg["tune_iter"])
            use_same_day_return_features = not bool(runtime_cfg["strict_return_lag"])

            dataset, serie = build_dataset_for_fund(
                fund_key=fund_key,
                start=train_start,
                end=eval_end,
                news_df=news_df,
                target_threshold=target_threshold,
            )

            dataset_suffix = (
                f"{fund_key}_{mode_label}"
                f"_prob{probability_threshold:.3f}".replace(".", "p")
                + f"_target{target_threshold:.4f}".replace(".", "p")
                + f"_{train_start}_{eval_end}"
            )
            ds_path = OUTPUT_DIR / "features" / f"dataset_{dataset_suffix}.csv"
            dataset.to_csv(ds_path, index_label="date", encoding="utf-8")
            print(f" Dataset guardado en: {ds_path}")

            if args.predict_live_only:
                predict_live_from_saved_model(
                    fund_key=fund_key,
                    dataset=dataset,
                    selected_series=serie,
                    train_start=train_start,
                    train_end=train_end,
                    eval_start=eval_start,
                    eval_end=eval_end,
                    probability_threshold=probability_threshold,
                    decision_mode=decision_mode,
                    decision_time_text=decision_time_text,
                    use_same_day_return_features=use_same_day_return_features,
                    target_threshold=target_threshold,
                    mode_label=mode_label,
                )
                continue

            result = train_and_evaluate_fund(
                fund_key=fund_key,
                dataset=dataset,
                selected_series=serie,
                train_start=train_start,
                train_end=train_end,
                eval_start=eval_start,
                eval_end=eval_end,
                tune=tune,
                tune_iter=tune_iter,
                probability_threshold=probability_threshold,
                decision_mode=decision_mode,
                decision_time_text=decision_time_text,
                use_same_day_return_features=use_same_day_return_features,
                target_threshold=target_threshold,
                dataset_path=ds_path,
                mode_label=mode_label,
                xgb_params_override=runtime_cfg.get("xgb_params"),
            )
            results.append(result)

            print("\nResultados evaluación:")
            print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
            print_confusion_matrix_readable(result.metrics)
            print(f"Modelo: {result.model_path}")
            print(f"Predicciones: {result.predictions_path}")
            if result.live_predictions_path:
                print(f"Predicciones live: {result.live_predictions_path}")
            print(f"Importancia variables: {result.feature_importance_path}")

        except Exception as exc:
            print(f"[ERROR] Falló experimento {fund_key} | {runtime_cfg.get('mode_label')}: {exc}")

    summary = [asdict(r) for r in results]

    # Archivo único consolidado para analizar las tres modalidades.
    summary_path = OUTPUT_DIR / "reports" / (
        f"resumen_xgboost_3_modalidades_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
        if run_all_modes
        else f"resumen_xgboost_por_fondo_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.json"
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # También guardamos una tabla plana CSV para análisis rápido en pandas/excel.
    flat_rows: list[dict[str, Any]] = []
    for r in results:
        item = asdict(r)
        metrics = item.pop("metrics", {})
        flat = {**item}
        for k, v in metrics.items():
            if isinstance(v, (dict, list)):
                continue
            flat[f"metric_{k}"] = v
        flat_rows.append(flat)

    flat_path = OUTPUT_DIR / "reports" / (
        f"resumen_xgboost_3_modalidades_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
        if run_all_modes
        else f"resumen_xgboost_por_fondo_{train_start}_{train_end}_eval_{eval_start}_{eval_end}.csv"
    )

    if flat_rows:
        pd.DataFrame(flat_rows).to_csv(flat_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame().to_csv(flat_path, index=False, encoding="utf-8")

    print("\n" + "=" * 80)
    print("PROCESO TERMINADO")
    print(f"Experimentos ejecutados correctamente: {len(results)}")
    print(f"Resumen JSON único: {summary_path}")
    print(f"Resumen CSV plano:  {flat_path}")
    print("=" * 80)
