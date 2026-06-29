from __future__ import annotations

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.prediction_config import FUND_CONFIG

def add_fund_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["return_1d"] = df["valor_cuota"].pct_change(1)
    df["log_return_1d"] = np.log(df["valor_cuota"]).diff(1)
    df["return_1d_lag1_safe"] = df["return_1d"].shift(1)
    df["log_return_1d_lag1_safe"] = df["log_return_1d"].shift(1)

    for lag in [1, 2, 3, 5, 10, 20]:
        df[f"return_lag_{lag}"] = df["return_1d"].shift(lag)
        df[f"log_return_lag_{lag}"] = df["log_return_1d"].shift(lag)

    for window in [3, 5, 10, 20]:
        df[f"return_roll_mean_{window}"] = df["return_1d"].rolling(window).mean().shift(1)
        df[f"return_roll_std_{window}"] = df["return_1d"].rolling(window).std().shift(1)
        df[f"momentum_{window}"] = df["valor_cuota"].pct_change(window).shift(1)

    # Medias móviles del valor cuota para semáforo técnico de entrada.
    # Se usa shift(1) para evitar que el semáforo use información futura
    # respecto de las variables técnicas disponibles al momento de decidir.
    for window in [5, 10, 20]:
        df[f"valor_cuota_ma_{window}"] = df["valor_cuota"].rolling(window).mean().shift(1)

    df["valor_cuota_vs_ma20"] = (df["valor_cuota"] / df["valor_cuota_ma_20"]) - 1
    df["ma5_vs_ma20"] = (df["valor_cuota_ma_5"] / df["valor_cuota_ma_20"]) - 1

    df["rolling_max_20"] = df["valor_cuota"].rolling(20).max().shift(1)
    df["drawdown_20"] = (df["valor_cuota"] / df["rolling_max_20"]) - 1

    if "CUOTAS_APORTADAS" in df.columns and "CUOTAS_RESCATADAS" in df.columns:
        df["net_flow_cuotas_raw"] = df["CUOTAS_APORTADAS"] - df["CUOTAS_RESCATADAS"]
        df["net_flow_cuotas_lag1"] = df["net_flow_cuotas_raw"].shift(1)
        df["net_flow_cuotas_lag2"] = df["net_flow_cuotas_raw"].shift(2)
        df["net_flow_cuotas_roll3_lag1"] = df["net_flow_cuotas_raw"].rolling(3).sum().shift(1)
        df["net_flow_cuotas_roll5_lag1"] = df["net_flow_cuotas_raw"].rolling(5).sum().shift(1)
        df["net_flow_cuotas_roll10_lag1"] = df["net_flow_cuotas_raw"].rolling(10).sum().shift(1)

    if "PATRIMONIO_NETO" in df.columns:
        df["patrimonio_return_1d"] = df["PATRIMONIO_NETO"].pct_change(1)
        df["patrimonio_return_lag1"] = df["patrimonio_return_1d"].shift(1)

    if "NUM_PARTICIPES" in df.columns:
        df["participes_change_1d"] = df["NUM_PARTICIPES"].diff(1)
        df["participes_change_lag1"] = df["participes_change_1d"].shift(1)

    df["day_of_week"] = df.index.dayofweek
    df["day_of_month"] = df.index.day
    df["month"] = df.index.month
    df["is_month_start"] = df.index.is_month_start.astype(int)
    df["is_month_end"] = df.index.is_month_end.astype(int)
    df["is_weekend_fund_date"] = (df.index.dayofweek >= 5).astype(int)

    return df

def add_targets(df: pd.DataFrame, horizon: int, threshold: float) -> pd.DataFrame:
    df = df.copy()
    df["future_exit_date"] = pd.Series(df.index, index=df.index).shift(-horizon)
    df["future_valor_cuota"] = df["valor_cuota"].shift(-horizon)
    df["future_return_h"] = (df["future_valor_cuota"] / df["valor_cuota"]) - 1
    df["target_up"] = (df["future_return_h"] > threshold).astype(int)
    return df
