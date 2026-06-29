from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from el_animal_fm.funds.application.cmf.cmf_config import DOWNLOAD_URL
from el_animal_fm.funds.application.cmf.cmf_dates import format_cmf_date, safe_date_for_filename
from el_animal_fm.funds.application.cmf.cmf_payload import (
    collect_payload,
    infer_and_fill_fields,
    print_diagnostics,
)
from el_animal_fm.funds.application.cmf.cmf_text import slugify
from el_animal_fm.funds.domain.models import FundOption
from el_animal_fm.funds.infrastructure.cmf_captcha import (
    download_captcha,
    find_captcha_image_url,
    show_captcha,
    validate_captcha,
)
from el_animal_fm.funds.infrastructure.cmf_client import load_initial_form
from el_animal_fm.funds.infrastructure.cmf_storage import (
    expected_output_path,
    save_response_as_file,
)


def download_one_range(
    range_index: int,
    total_ranges: int,
    start_date: date,
    end_date: date,
    fund: FundOption,
    show_diagnostics: bool,
    skip_existing: bool,
    *,
    download_dir: Path,
    captcha_path: Path,
    debug_dir: Path,
) -> dict[str, str]:
    start_str = format_cmf_date(start_date)
    end_str = format_cmf_date(end_date)
    expected_path = expected_output_path(download_dir, start_str, end_str, fund)

    print()
    print("=" * 72)
    print(f"[{range_index}/{total_ranges}] Tramo CMF")
    print(f"Fondo: {fund.code} - {fund.label}")
    if fund.matched_from_cmf:
        print(f"CMF: {fund.matched_from_cmf}")
    print(f"Fecha inicio: {start_str}")
    print(f"Fecha término: {end_str}")
    print("=" * 72)

    if skip_existing and expected_path.exists() and expected_path.stat().st_size > 0:
        print(f"Archivo ya existe. Se omite: {expected_path}")
        return {
            "fund_key": fund.key,
            "fund_code": fund.code,
            "fund_label": fund.label,
            "range": f"{start_str} - {end_str}",
            "status": "skipped_existing",
            "output_path": str(expected_path),
        }

    session, soup, form = load_initial_form()
    captcha_url = find_captcha_image_url(soup, form)

    print(f"URL CAPTCHA detectada: {captcha_url}")
    download_captcha(session, captcha_url, captcha_path)
    show_captcha(captcha_path)

    captcha_value = input("\nIngrese el CAPTCHA visto en la imagen para este tramo: ").strip()

    if not captcha_value:
        print("No ingresaste CAPTCHA. Proceso cancelado.")
        sys.exit(1)

    if not validate_captcha(session, captcha_value):
        print("El CAPTCHA fue rechazado por la CMF. Proceso cancelado.")
        sys.exit(1)

    payload = collect_payload(form)
    payload = infer_and_fill_fields(form, payload, start_str, end_str, captcha_value, fund)

    print()
    print("Enviando formulario por método POST a:")
    print(DOWNLOAD_URL)

    if show_diagnostics:
        print_diagnostics(form, payload, fund)

    response = session.post(DOWNLOAD_URL, data=payload, timeout=60)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if "text/html" in content_type and len(response.content) > 0:
        debug_dir.mkdir(exist_ok=True)
        fund_slug = slugify(f"{fund.code}_{fund.label}")
        debug_path = debug_dir / (
            f"debug_cmf_{fund_slug}_{safe_date_for_filename(start_str)}_{safe_date_for_filename(end_str)}.html"
        )
        debug_path.write_bytes(response.content)

        print()
        print("La respuesta recibida parece HTML, no archivo de datos.")
        print("Puede ser CAPTCHA incorrecto, rango no permitido o campo de formulario mal enviado.")
        print(f"Guardé la respuesta en: {debug_path}")

        return {
            "fund_key": fund.key,
            "fund_code": fund.code,
            "fund_label": fund.label,
            "range": f"{start_str} - {end_str}",
            "status": "html_response_error",
            "debug_path": str(debug_path),
        }

    output_path = save_response_as_file(response, download_dir, start_str, end_str, fund)

    print()
    print("Descarga completada correctamente.")
    print(f"Archivo guardado en: {output_path}")

    return {
        "fund_key": fund.key,
        "fund_code": fund.code,
        "fund_label": fund.label,
        "range": f"{start_str} - {end_str}",
        "status": "downloaded",
        "output_path": str(output_path),
    }
