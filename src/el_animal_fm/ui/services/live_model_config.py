from __future__ import annotations

from types import SimpleNamespace

from el_animal_fm.prediction.application.config.runtime_config import get_runtime_config_for_fund
from el_animal_fm.prediction.application.features.decision_scenarios import scenario_options


def live_configuration(fund_key: str) -> tuple[dict, dict]:
    """Mismos presets y escenario predeterminado que la CLI, sin overrides."""
    args = SimpleNamespace(
        no_fund_presets=False, no_fund_xgb_config=False, scenario=None,
        quote_lag_days=None, withdrawal_days=None, business_holidays=None,
        override_decision_mode=None, override_probability_threshold=None,
        override_target_threshold=None, override_strict_return_lag=None,
        tune=False,
    )
    config = get_runtime_config_for_fund(fund_key, args)
    return config, scenario_options(fund_key, config)


def news_cutoff_label(mode: str, decision_time: str | None) -> str:
    if mode == "night_partial":
        return f"Hasta las {decision_time}"
    if mode == "same_day_close":
        return "Día completo"
    return "Días anteriores a la referencia"
