#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
graficar_reportes_xgboost.py

Lee archivos JSON de resumen generados por 09_xgboost_prediction.py desde:
    xgboost_outputs/reports/

y genera una pantalla/gráfico resumen por cada reporte.

Cada pantalla incluye:
1. Retorno acumulado Buy & Hold vs Estrategia.
2. Mejora de la estrategia frente a Buy & Hold.
3. Métricas de clasificación principales.
4. Retorno futuro promedio según señal.
5. Matriz de confusión interpretada por fondo.

Dependencias:
    pip install matplotlib pandas numpy

Uso básico:
    python graficar_reportes_xgboost.py

Mostrar ventanas en pantalla:
    python graficar_reportes_xgboost.py --show

Solo guardar imágenes:
    python graficar_reportes_xgboost.py --save-only

Indicar carpeta específica:
    python graficar_reportes_xgboost.py --report-dir xgboost_outputs/reports

Filtrar reportes:
    python graficar_reportes_xgboost.py --pattern "resumen_xgboost_night_partial*.json"
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = BASE_DIR / "xgboost_outputs" / "reports"
DEFAULT_OUTPUT_DIR = BASE_DIR / "xgboost_outputs" / "report_charts"


def safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: float) -> float:
    """Convierte fraccion decimal a porcentaje."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan
    return float(value) * 100.0


def pp(value: float) -> float:
    """Convierte fraccion decimal a puntos porcentuales."""
    return pct(value)


def read_report(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"No se pudo leer {path}: {exc}") from exc

    if not isinstance(payload, list):
        raise RuntimeError(f"El archivo {path} no contiene una lista JSON.")

    return [x for x in payload if isinstance(x, dict)]


def normalize_report(report: list[dict[str, Any]], report_path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in report:
        metrics = item.get("metrics", {}) or {}
        cm = metrics.get("confusion_matrix", [[0, 0], [0, 0]])

        try:
            tn = int(cm[0][0])
            fp = int(cm[0][1])
            fn = int(cm[1][0])
            tp = int(cm[1][1])
        except Exception:
            tn = fp = fn = tp = 0

        buy_hold = safe_float(metrics.get("buy_hold_return_compounded"), 0.0)
        strategy = safe_float(metrics.get("strategy_return_compounded"), 0.0)

        rows.append(
            {
                "report_file": report_path.name,
                "fund_key": item.get("fund_key", ""),
                "fund_label": item.get("fund_label", item.get("fund_key", "")),
                "decision_mode": item.get("decision_mode", ""),
                "decision_time": item.get("decision_time", None),
                "train_start": item.get("train_start", ""),
                "train_end": item.get("train_end", ""),
                "eval_start": item.get("eval_start", ""),
                "eval_end": item.get("eval_end", ""),
                "rows_train": safe_float(item.get("rows_train"), 0),
                "rows_eval": safe_float(item.get("rows_eval"), 0),
                "feature_count": safe_float(item.get("feature_count"), 0),
                "accuracy": safe_float(metrics.get("accuracy")),
                "balanced_accuracy": safe_float(metrics.get("balanced_accuracy")),
                "precision_up": safe_float(metrics.get("precision_up")),
                "recall_up": safe_float(metrics.get("recall_up")),
                "f1_up": safe_float(metrics.get("f1_up")),
                "roc_auc": safe_float(metrics.get("roc_auc")),
                "buy_hold_return_pct": pct(buy_hold),
                "strategy_return_pct": pct(strategy),
                "strategy_improvement_pp": pp(strategy - buy_hold),
                "avg_future_return_when_pred_up_pct": pct(
                    safe_float(metrics.get("avg_future_return_when_pred_up"), 0.0)
                ),
                "avg_future_return_when_pred_down_pct": pct(
                    safe_float(metrics.get("avg_future_return_when_pred_down"), 0.0)
                ),
                "signals_up_mantener": safe_float(metrics.get("signals_up_mantener"), 0),
                "signals_down_mover_o_retirar": safe_float(metrics.get("signals_down_mover_o_retirar"), 0),
                "tn_salida_correcta": tn,
                "fp_mantener_incorrecto": fp,
                "fn_salida_incorrecta": fn,
                "tp_mantener_correcto": tp,
            }
        )

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(["fund_label"]).reset_index(drop=True)

    return df


def short_label(label: str, max_len: int = 18) -> str:
    text = str(label)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def make_report_title(df: pd.DataFrame, report_path: Path) -> str:
    if df.empty:
        return report_path.name

    mode = str(df["decision_mode"].iloc[0] or "sin_modo")
    decision_time = df["decision_time"].iloc[0]
    train_start = df["train_start"].iloc[0]
    train_end = df["train_end"].iloc[0]
    eval_start = df["eval_start"].iloc[0]
    eval_end = df["eval_end"].iloc[0]

    time_part = f" | hora {decision_time}" if decision_time not in [None, "", "None", np.nan] else ""

    return (
        f"{report_path.name}\n"
        f"Modo: {mode}{time_part} | Train: {train_start} a {train_end} | Eval: {eval_start} a {eval_end}"
    )


def annotate_bars(ax, bars, suffix: str = "", decimals: int = 2) -> None:
    for bar in bars:
        height = bar.get_height()
        if np.isnan(height):
            continue

        va = "bottom" if height >= 0 else "top"
        offset = 3 if height >= 0 else -3

        ax.annotate(
            f"{height:.{decimals}f}{suffix}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=va,
            fontsize=8,
        )


def plot_returns(ax, df: pd.DataFrame) -> None:
    labels = [short_label(x) for x in df["fund_label"]]
    x = np.arange(len(labels))
    width = 0.38

    bars1 = ax.bar(x - width / 2, df["buy_hold_return_pct"], width, label="Buy & Hold")
    bars2 = ax.bar(x + width / 2, df["strategy_return_pct"], width, label="Estrategia")

    ax.axhline(0, linewidth=0.8)
    ax.set_title("Retorno acumulado")
    ax.set_ylabel("Retorno (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    annotate_bars(ax, bars1, suffix="%")
    annotate_bars(ax, bars2, suffix="%")


def plot_improvement(ax, df: pd.DataFrame) -> None:
    labels = [short_label(x) for x in df["fund_label"]]
    x = np.arange(len(labels))

    bars = ax.bar(x, df["strategy_improvement_pp"])

    ax.axhline(0, linewidth=0.8)
    ax.set_title("Mejora estrategia vs Buy & Hold")
    ax.set_ylabel("Puntos porcentuales")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)

    annotate_bars(ax, bars, suffix=" pp")


def plot_classification_metrics(ax, df: pd.DataFrame) -> None:
    labels = [short_label(x) for x in df["fund_label"]]
    x = np.arange(len(labels))
    metrics = [
        ("balanced_accuracy", "Balanced acc."),
        ("precision_up", "Precision up"),
        ("recall_up", "Recall up"),
        ("roc_auc", "ROC AUC"),
    ]

    width = 0.18

    for i, (col, label) in enumerate(metrics):
        offset = (i - 1.5) * width
        values = df[col].astype(float) * 100.0
        ax.bar(x + offset, values, width, label=label)

    ax.set_title("Metricas de clasificacion")
    ax.set_ylabel("Porcentaje / score (%)")
    ax.set_ylim(0, 110)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)


def plot_confusion_table(ax, df: pd.DataFrame) -> None:
    ax.axis("off")
    ax.set_title("Matriz de confusion interpretada")

    columns = [
        "Fondo",
        "Salida correcta\nTN",
        "Mantener incorrecto\nFP",
        "Salida incorrecta\nFN",
        "Mantener correcto\nTP",
        "Senales\nmantener",
        "Senales\nmover",
    ]

    table_data = []

    for _, row in df.iterrows():
        table_data.append(
            [
                short_label(row["fund_label"], 16),
                int(row["tn_salida_correcta"]),
                int(row["fp_mantener_incorrecto"]),
                int(row["fn_salida_incorrecta"]),
                int(row["tp_mantener_correcto"]),
                int(row["signals_up_mantener"]),
                int(row["signals_down_mover_o_retirar"]),
            ]
        )

    table = ax.table(
        cellText=table_data,
        colLabels=columns,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.55)

    ax.text(
        0.5,
        -0.08,
        "FP = mantener incorrecto: error mas riesgoso. FN = salida incorrecta: oportunidad perdida.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
    )


def plot_signal_returns(ax, df: pd.DataFrame) -> None:
    labels = [short_label(x) for x in df["fund_label"]]
    x = np.arange(len(labels))
    width = 0.38

    bars1 = ax.bar(
        x - width / 2,
        df["avg_future_return_when_pred_up_pct"],
        width,
        label="Prom. cuando predice mantener",
    )
    bars2 = ax.bar(
        x + width / 2,
        df["avg_future_return_when_pred_down_pct"],
        width,
        label="Prom. cuando predice mover/retiro",
    )

    ax.axhline(0, linewidth=0.8)
    ax.set_title("Retorno futuro promedio segun senal")
    ax.set_ylabel("Retorno promedio (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    annotate_bars(ax, bars1, suffix="%")
    annotate_bars(ax, bars2, suffix="%")


def create_dashboard(df: pd.DataFrame, report_path: Path, output_path: Path, show: bool) -> None:
    if df.empty:
        print(f"[WARN] Reporte vacio: {report_path}")
        return

    fig = plt.figure(figsize=(18, 11))
    fig.suptitle(make_report_title(df, report_path), fontsize=13, y=0.98)

    ax1 = fig.add_subplot(2, 3, 1)
    ax2 = fig.add_subplot(2, 3, 2)
    ax3 = fig.add_subplot(2, 3, 3)
    ax4 = fig.add_subplot(2, 3, 4)
    ax5 = fig.add_subplot(2, 3, (5, 6))

    plot_returns(ax1, df)
    plot_improvement(ax2, df)
    plot_classification_metrics(ax3, df)
    plot_signal_returns(ax4, df)
    plot_confusion_table(ax5, df)

    fig.tight_layout(rect=[0, 0.02, 1, 0.94])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    print(f"[OK] Grafico guardado: {output_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def find_reports(report_dir: Path, pattern: str) -> list[Path]:
    if not report_dir.exists():
        raise RuntimeError(f"No existe carpeta de reportes: {report_dir}")

    reports = sorted(report_dir.glob(pattern))

    if not reports:
        raise RuntimeError(f"No se encontraron reportes con patron {pattern} en {report_dir}")

    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera graficos matplotlib desde reportes JSON de XGBoost."
    )

    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Carpeta donde estan los JSON de resumen.",
    )

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Carpeta donde guardar los graficos PNG.",
    )

    parser.add_argument(
        "--pattern",
        default="resumen_xgboost*.json",
        help='Patron de archivos JSON. Ejemplo: "resumen_xgboost_night_partial*.json"',
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Muestra una ventana matplotlib por cada reporte.",
    )

    parser.add_argument(
        "--save-only",
        action="store_true",
        help="Solo guarda PNG; no muestra ventanas.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    report_dir = Path(args.report_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    show = bool(args.show and not args.save_only)

    reports = find_reports(report_dir, args.pattern)

    print("=" * 80)
    print("GRAFICADOR REPORTES XGBOOST")
    print("=" * 80)
    print(f"Reportes encontrados: {len(reports)}")
    print(f"Carpeta reportes: {report_dir}")
    print(f"Carpeta salida:   {output_dir}")
    print(f"Mostrar ventanas: {show}")
    print("=" * 80)

    for report_path in reports:
        try:
            report = read_report(report_path)
            df = normalize_report(report, report_path)

            output_name = report_path.stem + ".png"
            output_path = output_dir / output_name

            create_dashboard(df, report_path, output_path, show=show)

        except Exception as exc:
            print(f"[ERROR] Fallo reporte {report_path}: {exc}")

    print("=" * 80)
    print("PROCESO TERMINADO")
    print("=" * 80)


if __name__ == "__main__":
    main()
