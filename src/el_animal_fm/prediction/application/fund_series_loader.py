from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.prediction_utils import safe_float
from el_animal_fm.prediction.infrastructure.output_paths import DOWNLOADS_DIR

def discover_fund_files(fund_key: str) -> list[Path]:
    folder = DOWNLOADS_DIR / str(FUND_CONFIG[fund_key]["folder"])
    if not folder.exists():
        print(f"[WARN] No existe carpeta: {folder}")
        return []
    return sorted(folder.glob("*.txt"))

def read_cmf_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8", engine="python", on_bad_lines="skip")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", dtype=str, encoding="latin-1", engine="python", on_bad_lines="skip")

def choose_series(df: pd.DataFrame, fund_key: str) -> str:
    preferred = [str(x) for x in FUND_CONFIG[fund_key]["preferred_series"]]
    available = sorted(df["SERIE"].dropna().astype(str).unique().tolist())

    for serie in preferred:
        if serie in available:
            return serie

    tmp = df.copy()
    if "PATRIMONIO_NETO" in tmp.columns:
        tmp["PATRIMONIO_NETO_NUM"] = tmp["PATRIMONIO_NETO"].map(safe_float)
    else:
        tmp["PATRIMONIO_NETO_NUM"] = np.nan

    by_series = tmp.groupby("SERIE")["PATRIMONIO_NETO_NUM"].mean().sort_values(ascending=False)

    if not by_series.empty:
        selected = str(by_series.index[0])
        print(f"[WARN] Serie preferida no encontrada para {fund_key}. Uso: {selected}")
        return selected

    raise RuntimeError(f"No se pudo escoger serie para {fund_key}. Disponibles: {available}")

def load_fund_data(fund_key: str, start: date, end: date) -> tuple[pd.DataFrame, str]:
    cfg = FUND_CONFIG[fund_key]
    run_fm = str(cfg["run_fm"])
    files = discover_fund_files(fund_key)

    if not files:
        raise RuntimeError(f"No hay archivos para {fund_key}")

    frames = []
    for p in files:
        df = read_cmf_file(p)
        df.columns = [str(c).strip() for c in df.columns]

        if "RUN_FM" not in df.columns or "FECHA_INF" not in df.columns:
            print(f"[WARN] Archivo sin RUN_FM/FECHA_INF, omitido: {p}")
            continue

        df = df[df["RUN_FM"].astype(str) == run_fm]
        if not df.empty:
            frames.append(df)

    if not frames:
        raise RuntimeError(f"No se encontraron filas RUN_FM={run_fm} para {fund_key}")

    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    serie = choose_series(df, fund_key)

    df = df[df["SERIE"].astype(str) == serie].copy()
    df["date"] = pd.to_datetime(df["FECHA_INF"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))].copy()

    for col in [
        "VALOR_CUOTA", "PATRIMONIO_NETO", "ACTIVO_TOT",
        "CUOTAS_APORTADAS", "CUOTAS_RESCATADAS", "CUOTAS_EN_CIRCULACION",
        "NUM_PARTICIPES", "REM_FIJA", "REM_VARIABLE", "GASTOS_AFECTOS",
        "GASTOS_NO_AFECTOS", "COMISION_INVERSION", "COMISION_RESCATE",
    ]:
        if col in df.columns:
            df[col] = df[col].map(safe_float)

    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").set_index("date")
    df["valor_cuota"] = df["VALOR_CUOTA"].astype(float)
    df = df[df["valor_cuota"].notna() & (df["valor_cuota"] > 0)].copy()

    print(f"  {fund_key}: {len(df)} filas, serie={serie}")
    return df, serie
