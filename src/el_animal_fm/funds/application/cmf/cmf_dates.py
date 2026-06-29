from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_user_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d_%m_%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato no reconocido. Usa YYYY-MM-DD, DD-MM-YYYY o DD/MM/YYYY.")


def ask_date(prompt: str, default: date | None = None) -> date:
    while True:
        suffix = f" [{default.isoformat()}]" if default else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default:
            return default
        try:
            return parse_user_date(raw)
        except ValueError as exc:
            print(exc)


def format_cmf_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def safe_date_for_filename(value: str) -> str:
    return value.replace("/", "-")


def build_ranges(
    historical_start: date,
    end_date: date,
    max_days_per_request: int,
) -> list[tuple[date, date]]:
    if historical_start > end_date:
        raise ValueError("La fecha inicial histórica no puede ser posterior a la fecha final.")

    ranges: list[tuple[date, date]] = []
    current_start = historical_start

    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=max_days_per_request - 1), end_date)
        ranges.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)

    return ranges
