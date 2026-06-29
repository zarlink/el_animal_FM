from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


TIMEZONE = "America/Santiago"


def today_chile() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def parse_target_date(value: str | None) -> date:
    """
    Acepta:
    - None: fecha actual en Chile.
    - DD_MM_YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD
    """
    if not value:
        return today_chile()

    value = value.strip()

    for fmt in ("%d_%m_%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    raise ValueError(
        "Formato de fecha no reconocido. Usa DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD."
    )


def date_dir_name(target: date) -> str:
    return target.strftime("%d_%m_%Y")


def date_from_dir_name(value: str) -> date:
    return datetime.strptime(value, "%d_%m_%Y").date()


def build_date_range(end_date: date, days_count: int) -> list[date]:
    return [end_date - timedelta(days=i) for i in range(days_count)]


def url_matches_date(url: str, target: date) -> bool:
    return target.strftime("/%Y/%m/%d/") in url
