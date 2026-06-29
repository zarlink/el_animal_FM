from __future__ import annotations

from typing import Any

RANDOM_SEED = 42

# =============================================================================
# Configuración de fondos
# =============================================================================

FUND_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "run_fm": "10063",
        "folder": "10063_crecimiento_balanceado",
        "label": "Crecimiento Balanceado",
        "horizon_business_days": 4,
        "preferred_series": ["SIMPLE", "APV", "IT"],
    },
    "ahorro_uf_itau": {
        "run_fm": "10243",
        "folder": "10243_ahorro_uf_itau",
        "label": "Ahorro UF Itaú",
        "horizon_business_days": 1,
        "preferred_series": ["SIMPLE", "APV", "F4", "F5", "IT"],
    },
    "national_equity": {
        "run_fm": "8305",
        "folder": "8305_national_equity",
        "label": "National Equity",
        "horizon_business_days": 2,
        "preferred_series": ["F1", "SIMPLE", "APV", "IT"],
    },
    "toesca_equity": {
        "run_fm": "9936",
        "folder": "9936_toesca_equity",
        "label": "Toesca Equity",
        "horizon_business_days": 2,
        "preferred_series": ["F1", "SIMPLE", "APV", "IT"],
    },
}


# Presets iniciales por fondo.
# Ajusta aquí la estrategia específica de cada fondo.
#
# Notas:
# - Ahorro UF quedó mejor con strict_lag.
# - National y Toesca quedaron mejor con night_partial.
# - Crecimiento Balanceado necesita target/probability más exigente porque tendía a mantener siempre.
#
FUND_MODEL_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.367,
    "target_threshold": 0.00053,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "ahorro_uf_itau": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.61,
    "target_threshold": 0.0000,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "national_equity": {
    "decision_mode": "same_day_close",
    "decision_time": None,
    "probability_threshold": 0.516,
    "target_threshold": 0.000766,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
    "toesca_equity": {
    "decision_mode": "night_partial",
    "decision_time": "21:30",
    "probability_threshold": 0.35,
    "target_threshold": 0.00030,
    "strict_return_lag": False,
    "tune": False,
    "tune_iter": 15,
},
}

# Parametros personalizados de XGBoost para cada fondo:
XGB_MODEL_CONFIG: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "n_estimators": 300,
        "learning_rate": 0.044635901521768134,
        "max_depth": 3,
        "min_child_weight": 10.986584841970366,
        "gamma": 0.31203728088487304,
        "subsample": 0.6545980821176709,
        "colsample_bytree": 0.6203292642588698,
        "reg_lambda": 23.604024417191162,
        "reg_alpha": 1.8432335340553057,
    },
    "ahorro_uf_itau": {
        "n_estimators": 350,
        "learning_rate": 0.009720352156652182,
        "max_depth": 2,
        "min_child_weight": 8.072834730440935,
        "gamma": 0.0894795501120127,
        "subsample": 0.923591189202745,
        "colsample_bytree": 0.8628372612742934,
        "reg_lambda": 19.615823733250156,
        "reg_alpha": 1.0061696391388362,
    },
    "national_equity": {
        "n_estimators": 750,
        "learning_rate": 0.03390638325130928,
        "max_depth": 5,
        "min_child_weight": 6.8517843732226265,
        "gamma": 0.6073237677504941,
        "subsample": 0.7813747356486104,
        "colsample_bytree": 0.6181567321257274,
        "reg_lambda": 1.0074031444608387,
        "reg_alpha": 0.32523623592877615,
    },
    "toesca_equity": {
        "n_estimators": 700,
        "learning_rate": 0.058234808725543166,
        "max_depth": 2,
        "min_child_weight": 9.257031448464947,
        "gamma": 0.713484004053756,
        "subsample": 0.7608626029118591,
        "colsample_bytree": 0.7612351372536184,
        "reg_lambda": 6.641498576516313,
        "reg_alpha": 0.5287333296047524,
    },
}


# Modalidades que se probarán automáticamente por defecto en modo evaluación.
# La idea es comparar estrictamente cada modalidad bajo el mismo período.
DECISION_MODE_TESTS: list[dict[str, Any]] = [
    {
        "mode_label": "strict_lag",
        "decision_mode": "strict_lag",
        "decision_time": None,
    },
    {
        "mode_label": "night_partial",
        "decision_mode": "night_partial",
        "decision_time": "21:30",
    },
    {
        "mode_label": "same_day_close",
        "decision_mode": "same_day_close",
        "decision_time": None,
    },
]


# Espacios de búsqueda iniciales para Optuna.
# Estos rangos afinan target_threshold y probability_threshold antes de pasar
# al tuning fino de XGBoost. Son deliberadamente amplios, pero acotados por tipo
# de fondo para evitar pruebas evidentemente inútiles.
THRESHOLD_SEARCH_SPACE: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "target_min": 0.0010,
        "target_max": 0.0020,
        "prob_min": 0.45,
        "prob_max": 0.55,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "ahorro_uf_itau": {
        "target_min": 0.0000,
        "target_max": 0.0025,
        "prob_min": 0.40,
        "prob_max": 0.60,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "national_equity": {
        "target_min": 0.0008,
        "target_max": 0.0015,
        "prob_min": 0.68,
        "prob_max": 0.78,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
    "toesca_equity": {
        "target_min": 0.0015,
        "target_max": 0.0030,
        "prob_min": 0.48,
        "prob_max": 0.62,
        "modes": ["strict_lag", "night_partial", "same_day_close"],
    },
}


# Espacios de búsqueda para fine tuning de hiperparámetros XGBoost.
# Se usan después de fijar decision_mode, target_threshold y probability_threshold
# en FUND_MODEL_CONFIG. La idea es afinar la forma del modelo sin volver a mover
# los thresholds iniciales ya encontrados por fondo.
XGB_SEARCH_SPACE: dict[str, dict[str, Any]] = {
    "crecimiento_balanceado": {
        "n_estimators": (150, 600),
        "learning_rate": (0.005, 0.05),
        "max_depth": (1, 3),
        "min_child_weight": (5, 15),
        "gamma": (0.0, 2.0),
        "subsample": (0.60, 0.95),
        "colsample_bytree": (0.60, 0.95),
        "reg_lambda": (5.0, 30.0),
        "reg_alpha": (0.1, 3.0),
    },
    "ahorro_uf_itau": {
        "n_estimators": (150, 600),
        "learning_rate": (0.005, 0.04),
        "max_depth": (1, 3),
        "min_child_weight": (5, 20),
        "gamma": (0.0, 2.5),
        "subsample": (0.60, 0.95),
        "colsample_bytree": (0.60, 0.95),
        "reg_lambda": (5.0, 35.0),
        "reg_alpha": (0.1, 4.0),
    },
    "national_equity": {
        "n_estimators": (250, 900),
        "learning_rate": (0.005, 0.06),
        "max_depth": (2, 5),
        "min_child_weight": (2, 12),
        "gamma": (0.0, 1.5),
        "subsample": (0.60, 1.00),
        "colsample_bytree": (0.60, 1.00),
        "reg_lambda": (1.0, 20.0),
        "reg_alpha": (0.0, 2.0),
    },
    "toesca_equity": {
        "n_estimators": (250, 900),
        "learning_rate": (0.005, 0.06),
        "max_depth": (2, 5),
        "min_child_weight": (2, 12),
        "gamma": (0.0, 1.5),
        "subsample": (0.60, 1.00),
        "colsample_bytree": (0.60, 1.00),
        "reg_lambda": (1.0, 20.0),
        "reg_alpha": (0.0, 2.0),
    },
}



def get_decision_mode_config(mode: str) -> dict[str, Any]:
    for item in DECISION_MODE_TESTS:
        if item["decision_mode"] == mode or item["mode_label"] == mode:
            return item.copy()
    raise ValueError(f"decision_mode inválido para Optuna: {mode}")
