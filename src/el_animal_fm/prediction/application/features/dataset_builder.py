from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from el_animal_fm.prediction.application.features.fund_feature_builder import add_fund_features, add_targets
from el_animal_fm.prediction.application.features.fund_series_loader import load_fund_data
from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG

def build_dataset_for_fund(
    fund_key: str,
    start: date,
    end: date,
    news_df: pd.DataFrame,
    target_threshold: float,
) -> tuple[pd.DataFrame, str]:
    horizon = int(FUND_CONFIG[fund_key]["horizon_business_days"])
    fund_df, serie = load_fund_data(fund_key, start, end)
    fund_features = add_fund_features(fund_df)
    fund_target = add_targets(fund_features, horizon, target_threshold)

    ds = fund_target.join(news_df, how="left")
    ds = ds.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Importante para uso real / live:
    # No eliminamos aquí las últimas filas sin future_valor_cuota.
    # Esas filas no sirven para métricas históricas, pero sí sirven para
    # generar señal live del último día disponible con valor cuota/noticias.
    return ds, serie

def get_feature_columns(df: pd.DataFrame, use_same_day_return_features: bool = True) -> list[str]:
    excluded = {
        "target_up", "future_return_h", "future_valor_cuota", "future_exit_date",
        "valor_cuota", "RUN_ADM", "NOM_ADM", "RUN_FM", "FECHA_INF", "MONEDA",
        "PARTICIPES_INST", "SERIE", "FONDO_PEN", "VALOR_CUOTA",
        "CUOTAS_APORTADAS", "CUOTAS_RESCATADAS", "CUOTAS_EN_CIRCULACION",
        "PATRIMONIO_NETO", "ACTIVO_TOT", "NUM_PARTICIPES", "REM_FIJA",
        "REM_VARIABLE", "GASTOS_AFECTOS", "GASTOS_NO_AFECTOS",
        "COMISION_INVERSION", "COMISION_RESCATE", "net_flow_cuotas_raw",
    }

    if not use_same_day_return_features:
        excluded |= {"return_1d", "log_return_1d", "patrimonio_return_1d", "participes_change_1d"}

    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]
