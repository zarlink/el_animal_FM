from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[4]
NEWS_FILE_NAME = "noticias_dia_enriquecidas.txt"
NEWS_SOURCES = {
    "biobio": BASE_DIR / "biobio",
    "mostrador": BASE_DIR / "mostrador",
}
DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "xgboost_outputs"


def ensure_output_dirs() -> None:
    for sub in ["models", "predictions", "features", "reports"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)
