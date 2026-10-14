from __future__ import annotations

import json
import csv
import re
from datetime import date, datetime
from pathlib import Path

import requests

from el_animal_fm.funds.application.cmf.cmf_dates import safe_date_for_filename
from el_animal_fm.funds.application.cmf.cmf_text import slugify
from el_animal_fm.funds.domain.models import FundOption


def latest_downloaded_date(download_dir: Path) -> date | None:
    """Read actual report dates, independent of filenames and modification times."""
    latest = None
    for path in download_dir.rglob("*.txt"):
        try:
            for encoding in ("utf-8-sig", "latin-1"):
                try:
                    with path.open(encoding=encoding, newline="") as stream:
                        reader = csv.DictReader(stream, delimiter=";")
                        if not reader.fieldnames or "FECHA_INF" not in reader.fieldnames:
                            break
                        for row in reader:
                            value = (row.get("FECHA_INF") or "").strip()
                            try:
                                day = datetime.strptime(value, "%Y%m%d").date()
                            except ValueError:
                                continue
                            if latest is None or day > latest:
                                latest = day
                    break
                except UnicodeDecodeError:
                    continue
        except (OSError, csv.Error):
            continue
    return latest


def fund_download_dir(download_dir: Path, fund: FundOption) -> Path:
    fund_slug = slugify(f"{fund.code}_{fund.label}")
    return download_dir / fund_slug


def expected_output_path(
    download_dir: Path,
    start_str: str,
    end_str: str,
    fund: FundOption,
) -> Path:
    fund_slug = slugify(f"{fund.code}_{fund.label}")
    return fund_download_dir(download_dir, fund) / (
        f"cmf_{fund_slug}_{safe_date_for_filename(start_str)}_{safe_date_for_filename(end_str)}.txt"
    )


def save_response_as_file(
    response: requests.Response,
    download_dir: Path,
    start_date: str,
    end_date: str,
    fund: FundOption,
) -> Path:
    content_disposition = response.headers.get("Content-Disposition", "")
    filename = None
    match = re.search(r'filename="?([^"]+)"?', content_disposition)
    if match:
        filename = match.group(1).strip()

    fund_slug = slugify(f"{fund.code}_{fund.label}")

    if not filename:
        filename = (
            f"cmf_{fund_slug}_"
            f"{safe_date_for_filename(start_date)}_{safe_date_for_filename(end_date)}.txt"
        )
    else:
        filename = f"{fund_slug}_{filename}"

    output_dir = fund_download_dir(download_dir, fund)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    if output_path.exists():
        output_path = output_dir / (
            f"cmf_{fund_slug}_"
            f"{safe_date_for_filename(start_date)}_{safe_date_for_filename(end_date)}.txt"
        )

    output_path.write_bytes(response.content)
    return output_path


def write_summary(
    download_dir: Path,
    summaries: list[dict[str, str]],
    historical_start: date,
    end_date: date,
) -> Path:
    download_dir.mkdir(exist_ok=True)
    summary_path = download_dir / (
        f"resumen_cmf_multifondos_{historical_start.isoformat()}_{end_date.isoformat()}.json"
    )
    summary_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path
