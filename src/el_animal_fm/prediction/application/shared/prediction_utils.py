from __future__ import annotations

import math
from datetime import date, datetime, time

import numpy as np

def parse_user_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d_%m_%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato no reconocido. Usa YYYY-MM-DD, DD-MM-YYYY o DD/MM/YYYY.")

def parse_user_time(value: str) -> time:
    value = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    raise ValueError("Formato de hora no reconocido. Usa HH:MM, por ejemplo 21:30.")

def ask_date(prompt: str) -> date:
    while True:
        raw = input(f"{prompt}: ").strip()
        try:
            return parse_user_date(raw)
        except ValueError as exc:
            print(exc)

def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[S/n]" if default else "[s/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"s", "si", "sí", "y", "yes"}

def folder_to_date(folder_name: str) -> date | None:
    try:
        return datetime.strptime(folder_name, "%d_%m_%Y").date()
    except ValueError:
        return None

def safe_float(value: Any) -> float:
    if value is None:
        return np.nan
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return np.nan
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return np.nan

def feature_safe_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    text = text.replace("ü", "u").replace("ñ", "n")
    text = "".join(ch if ch.isalnum() else "_" for ch in text)
    text = "_".join(part for part in text.split("_") if part)
    return text[:80] or "unknown"
