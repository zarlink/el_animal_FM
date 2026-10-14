from __future__ import annotations

import json
from datetime import date

from el_animal_fm.news.infrastructure.dates import today_chile
from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
from el_animal_fm.prediction.application.features.fund_series_loader import load_fund_data
from el_animal_fm.prediction.infrastructure.output_paths import NEWS_FILE_NAME, NEWS_SOURCES


def latest_available_prediction_date() -> date:
    """Find a common day with valid fund quotes and enriched news for all sources."""
    today = today_chile()
    common = None
    if not FUND_CONFIG or not NEWS_SOURCES:
        raise ValueError("No hay fondos o fuentes de noticias configurados.")
    for key, config in FUND_CONFIG.items():
        try:
            frame, _ = load_fund_data(key, date(1900, 1, 1), today)
        except Exception as exc:
            raise ValueError(f"{config['label']}: no se pudieron leer los valores CMF ({exc}).") from exc
        days = {value.date() for value in frame.index}
        if not days:
            raise ValueError(f"{config['label']}: sin valores CMF válidos.")
        common = days if common is None else common & days
    for day in sorted(common or (), reverse=True):
        valid = True
        for folder in NEWS_SOURCES.values():
            path = folder / day.strftime("%d_%m_%Y") / NEWS_FILE_NAME
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                articles = payload.get("articles")
                if (not payload.get("metadata", {}).get("features_enriched")
                        or not isinstance(articles, list) or not articles
                        or not all(isinstance(article, dict) and isinstance(article.get("features"), dict)
                                   for article in articles)):
                    valid = False
                    break
            except (OSError, ValueError, AttributeError):
                valid = False
                break
        if valid:
            return day
    raise ValueError("Sin fecha común con valores CMF de todos los fondos y noticias enriquecidas de ambas fuentes.")
