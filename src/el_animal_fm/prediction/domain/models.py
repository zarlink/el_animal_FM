from __future__ import annotations

from dataclasses import dataclass
from typing import Any

class TrainResult:
    experiment_key: str
    mode_label: str
    fund_key: str
    fund_label: str
    run_fm: str
    selected_series: str
    horizon_business_days: int
    decision_mode: str
    decision_time: str | None
    use_same_day_return_features: bool
    target_threshold: float
    probability_threshold: float
    train_start: str
    train_end: str
    eval_start: str
    eval_end: str
    rows_train: int
    rows_eval: int
    feature_count: int
    positive_rate_train: float
    positive_rate_eval: float
    best_params: dict[str, Any]
    metrics: dict[str, Any]
    model_path: str
    predictions_path: str
    feature_importance_path: str
    dataset_path: str
    live_predictions_path: str | None
