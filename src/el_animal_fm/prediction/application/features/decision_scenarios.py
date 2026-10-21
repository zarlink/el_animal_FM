from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd

from el_animal_fm.prediction.application.config.prediction_config import (
    BUSINESS_HOLIDAYS, BUSINESS_WEEKMASK, FUND_CONFIG, PREDICTION_SCENARIOS,
)


def scenario_options(fund_key: str, runtime: dict) -> dict:
    name = runtime.get("scenario", "legacy")
    if name not in PREDICTION_SCENARIOS:
        raise ValueError(f"Escenario desconocido: {name}")
    if name == "legacy":
        return {"name": "legacy"}
    defaults = PREDICTION_SCENARIOS[name]
    horizon = int(runtime.get("horizon_business_days", FUND_CONFIG[fund_key]["horizon_business_days"]))
    lag = int(runtime.get("quote_lag_days", defaults["quote_lag_days"]))
    if horizon < 1 or lag < 1:
        raise ValueError("El plazo de retiro y el desfase CMF deben ser al menos 1")
    holidays = sorted({pd.Timestamp(day).date().isoformat()
                       for day in runtime.get("business_holidays", BUSINESS_HOLIDAYS)})
    return {
        "version": 1, "name": name, "news_reference": defaults["news_reference"],
        "quote_lag_days": lag, "horizon_business_days": horizon,
        "weekmask": runtime.get("business_weekmask", BUSINESS_WEEKMASK), "holidays": holidays,
        "decision_mode": runtime["decision_mode"],
        "decision_time": runtime.get("decision_time") if runtime["decision_mode"] == "night_partial" else None,
    }


def scenario_label(label: str, options: dict) -> str:
    if options.get("name", "legacy") == "legacy":
        return label
    signature = hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()[:12]
    prefix = f"{options['name']}_h{options['horizon_business_days']}_{signature}_"
    return label if label.startswith(prefix) else prefix + label


def align_decision_dataset(
    fund_features: pd.DataFrame, news: pd.DataFrame, start: date, end: date,
    threshold: float, options: dict,
) -> pd.DataFrame:
    """One row per decision day, using only quotes assumed published by that day.

    Features come from an as-of join; labels are exact future business-date quotes.
    Never forward-fill a missing target or invent a current-day fund observation.
    """
    business_day = pd.offsets.CustomBusinessDay(
        weekmask=options["weekmask"], holidays=options["holidays"],
    )
    dates = pd.date_range(start, end, freq="D", name="date")
    financial = fund_features.sort_index().copy()
    financial.index.name = "quote_date"
    financial = financial.reset_index()
    financial["quote_date"] = financial["quote_date"].astype("datetime64[ns]")
    financial["quote_available_date"] = financial["quote_date"] + pd.Timedelta(days=options["quote_lag_days"])
    decisions = pd.DataFrame({"decision_date": dates.astype("datetime64[ns]")})
    ds = pd.merge_asof(decisions, financial, left_on="decision_date", right_on="quote_available_date")
    ds = ds.dropna(subset=["quote_date"]).set_index("decision_date")
    ds.index.name = "date"
    ds["decision_date"] = ds.index
    ds["news_reference_date"] = ds["quote_date"] if options["news_reference"] == "quote_date" else ds.index
    aligned_news = news.reindex(pd.DatetimeIndex(ds["news_reference_date"])).copy()
    aligned_news.index = ds.index
    ds = ds.join(aligned_news)
    ds["quote_age_calendar_days"] = (ds["decision_date"] - ds["quote_date"]).dt.days
    ds["decision_day_of_week"] = ds.index.dayofweek
    ds["decision_is_weekend"] = (ds.index.dayofweek >= 5).astype(int)
    ds["withdrawal_start_date"] = pd.DatetimeIndex([day + business_day for day in ds.index])
    ds["future_exit_date"] = pd.DatetimeIndex([
        day + options["horizon_business_days"] * business_day for day in ds.index
    ])
    ds["target_available_date"] = ds["future_exit_date"] + pd.Timedelta(days=options["quote_lag_days"])
    ds["future_valor_cuota"] = ds["future_exit_date"].map(fund_features["valor_cuota"])
    ds["future_return_h"] = ds["future_valor_cuota"] / ds["valor_cuota"] - 1
    ds["target_up"] = (ds["future_return_h"] > threshold).astype(float).where(ds["future_return_h"].notna())
    ds["prediction_scenario"] = options["name"]
    # Only inputs are filled. Unknown targets and dates remain unknown for live use.
    target_cols = {"future_valor_cuota", "future_return_h", "target_up"}
    numeric_inputs = [col for col in ds.select_dtypes(include="number") if col not in target_cols]
    ds[numeric_inputs] = ds[numeric_inputs].replace([float("inf"), -float("inf")], float("nan")).fillna(0.0)
    ds.attrs["prediction_scenario"] = options
    return ds


def split_evaluable_dataset(dataset, train_start, train_end, eval_start, eval_end):
    if "target_available_date" in dataset and pd.Timestamp(train_end) >= pd.Timestamp(eval_start):
        raise ValueError("Los escenarios operativos requieren train_end anterior a eval_start")
    valid = dataset[dataset["future_valor_cuota"].notna() & (dataset["future_valor_cuota"] > 0)]
    train = valid.loc[(valid.index >= pd.Timestamp(train_start)) & (valid.index <= pd.Timestamp(train_end))].copy()
    evaluation = valid.loc[(valid.index >= pd.Timestamp(eval_start)) & (valid.index <= pd.Timestamp(eval_end))].copy()
    if "target_available_date" in train:
        # Fit at the end of train_end: future labels not yet published cannot train.
        train = train.loc[train["target_available_date"] <= pd.Timestamp(train_end)].copy()
    return train, evaluation


def assert_model_scenario(payload: dict, dataset: pd.DataFrame):
    expected = dataset.attrs.get("prediction_scenario", {"name": "legacy"})
    actual = payload.get("prediction_scenario", {"name": "legacy"})
    if expected != actual:
        raise ValueError("El escenario, calendario, corte o plazo del modelo no coincide con el dataset. Reentrena con la misma configuración.")


def scenario_report_tag(options: list[dict]) -> str:
    if all(option.get("name", "legacy") == "legacy" for option in options):
        return ""
    digest = hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()[:12]
    names = "_".join(sorted({option["name"] for option in options}))
    return f"_{names}_{digest}"
