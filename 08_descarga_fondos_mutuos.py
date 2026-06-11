#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


CMF_URL = "https://www.cmfchile.cl/institucional/estadisticas/fondos_cartola_diaria.php"
DOWNLOAD_URL = "https://www.cmfchile.cl/institucional/estadisticas/cfm_download.php"
CAPTCHA_VALIDATE_URL = "https://www.cmfchile.cl/sitio/biblioteca/captcha2/captcha.php"

MAX_DAYS_PER_REQUEST = 31

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
CAPTCHA_PATH = BASE_DIR / "captcha.png"
DEBUG_DIR = BASE_DIR / "debug_cmf"


FUND_CATALOG: dict[str, dict[str, object]] = {
    "balanceado": {
        "label": "CARTERA BALANCEADO",
        "code": "10063",
        "search_terms": ["cartera", "balanceado"],
    },
    "national_equity": {
        "label": "NATIONAL EQUITY",
        "code": "8305",
        "search_terms": ["national", "equity"],
    },
    "toesca_equity": {
        "label": "TOESCA EQUITY",
        "code": "9936",
        "search_terms": ["toesca", "equity"],
    },
    "itau_ahorro_uf": {
        "label": "AHORRO UF ITAÚ",
        "code": "10243",
        "search_terms": ["itau", "itaú", "ahorro", "uf"],
    },
}


@dataclass
class FundOption:
    key: str
    label: str
    code: str
    matched_from_cmf: str = ""


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    value = re.sub(r"\s+", " ", value)
    return value


def slugify(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "fondo"


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


def get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": CMF_URL,
        }
    )
    return session


def pick_main_form(soup: BeautifulSoup):
    forms = soup.find_all("form")
    if not forms:
        raise RuntimeError("No se encontraron formularios <form> en el HTML.")

    for form in forms:
        form_text = form.get_text(" ", strip=True).lower()
        has_captcha_word = "captcha" in str(form).lower() or "caracteres de la imagen" in form_text
        has_select = bool(form.find("select"))
        if has_captcha_word or has_select:
            return form

    return forms[0]


def find_fund_select(form):
    selects = form.find_all("select")
    if not selects:
        raise RuntimeError("No se encontró ningún <select> en el formulario.")

    return max(selects, key=lambda s: len(s.find_all("option")))


def get_cmf_fund_options(form) -> list[tuple[str, str]]:
    fund_select = find_fund_select(form)
    options: list[tuple[str, str]] = []

    for option in fund_select.find_all("option"):
        value = (option.get("value") or "").strip()
        text = option.get_text(" ", strip=True)
        if value:
            options.append((value, text))

    return options


def load_initial_form() -> tuple[requests.Session, BeautifulSoup, object]:
    session = create_session()
    print("Descargando página inicial de CMF...")
    page_response = session.get(CMF_URL, timeout=30)
    page_response.raise_for_status()
    soup = get_soup(page_response.text)
    form = pick_main_form(soup)
    return session, soup, form


def resolve_fund_from_form(form, fund_key: str, explicit_code: str | None = None) -> FundOption:
    if fund_key not in FUND_CATALOG:
        raise RuntimeError(f"Fondo no definido en catálogo: {fund_key}")

    cfg = FUND_CATALOG[fund_key]
    label = str(cfg["label"])

    if explicit_code:
        return FundOption(
            key=fund_key,
            label=label,
            code=explicit_code,
            matched_from_cmf=f"código explícito {explicit_code}",
        )

    predefined_code = cfg.get("code")
    if predefined_code:
        return FundOption(
            key=fund_key,
            label=label,
            code=str(predefined_code),
            matched_from_cmf=f"código predefinido {predefined_code}",
        )

    search_terms = [normalize_text(str(term)) for term in cfg.get("search_terms", [])]
    cmf_options = get_cmf_fund_options(form)

    matches: list[tuple[str, str]] = []

    for code, text in cmf_options:
        normalized = normalize_text(text)
        if all(term in normalized for term in search_terms):
            matches.append((code, text))

    if not matches:
        print()
        print(f"No pude resolver automáticamente el fondo: {label}")
        print(f"Términos buscados: {search_terms}")
        print("Ejecuta con --list-funds --list-filter TEXTO o usa --fund-code CODIGO.")
        raise RuntimeError(f"No se encontró opción CMF compatible para {label}.")

    if len(matches) > 1:
        print()
        print(f"Se encontraron varias opciones para {label}:")
        for idx, (code, text) in enumerate(matches, start=1):
            print(f"  {idx}. {code} | {text}")

        while True:
            raw = input("Elige el número correcto: ").strip()
            try:
                selected_index = int(raw)
                if 1 <= selected_index <= len(matches):
                    code, text = matches[selected_index - 1]
                    break
            except ValueError:
                pass
            print("Selección inválida.")
    else:
        code, text = matches[0]

    return FundOption(
        key=fund_key,
        label=label,
        code=code,
        matched_from_cmf=text,
    )


def print_available_catalog() -> None:
    print()
    print("Fondos configurados:")
    for key, cfg in FUND_CATALOG.items():
        code = cfg.get("code") or "se resuelve desde CMF"
        print(f"  - {key}: {cfg['label']} | código: {code}")


def print_cmf_fund_options(form, filter_text: str | None = None) -> None:
    options = get_cmf_fund_options(form)
    normalized_filter = normalize_text(filter_text or "")

    print()
    print("Opciones de fondos detectadas en CMF:")
    count = 0

    for code, text in options:
        if normalized_filter and normalized_filter not in normalize_text(text):
            continue
        count += 1
        print(f"  {code} | {text}")

    print(f"\nTotal mostradas: {count}")


def ask_fund_selection(form) -> FundOption:
    print_available_catalog()
    allowed = set(FUND_CATALOG)

    while True:
        raw = input("\nElige fondo por clave: ").strip().lower()
        if raw in allowed:
            return resolve_fund_from_form(form, raw)

        print("Clave inválida. Opciones:")
        for key in sorted(allowed):
            print(f"  - {key}")


def resolve_funds_for_run(
    requested_funds: list[str] | None,
    explicit_fund_code: str | None,
    list_funds: bool,
    list_filter: str | None,
) -> list[FundOption]:
    _, _, form = load_initial_form()

    if list_funds:
        print_cmf_fund_options(form, list_filter)
        sys.exit(0)

    if not requested_funds:
        return [ask_fund_selection(form)]

    selected: list[FundOption] = []

    for fund_key in requested_funds:
        fund_key = fund_key.strip().lower()

        if fund_key == "all":
            for key in FUND_CATALOG:
                selected.append(resolve_fund_from_form(form, key))
            continue

        selected.append(resolve_fund_from_form(form, fund_key, explicit_fund_code))

    unique_by_code: dict[str, FundOption] = {}
    for fund in selected:
        unique_by_code[fund.code] = fund

    return list(unique_by_code.values())


def find_captcha_image_url(soup: BeautifulSoup, form) -> str:
    candidates = []
    for scope in [form, soup]:
        for img in scope.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            title = img.get("title", "")
            combined = f"{src} {alt} {title}".lower()
            if "captcha" in combined or "imagen" in combined:
                candidates.append(src)

    if not candidates:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and any(token in src.lower() for token in ["captcha", "verificacion", "seguridad", "imagen"]):
                candidates.append(src)

    if not candidates:
        raise RuntimeError("No se pudo detectar automáticamente la URL del CAPTCHA.")

    return urljoin(CMF_URL, candidates[0])


def download_captcha(session: requests.Session, captcha_url: str) -> None:
    response = session.get(captcha_url, timeout=30)
    response.raise_for_status()
    CAPTCHA_PATH.write_bytes(response.content)
    print(f"CAPTCHA guardado en: {CAPTCHA_PATH}")


def validate_captcha(session: requests.Session, captcha: str) -> bool:
    response = session.post(
        CAPTCHA_VALIDATE_URL,
        data={"accion": "valida", "valor": captcha},
        timeout=30,
    )
    response.raise_for_status()
    return response.text.strip() == "1"


def show_captcha() -> None:
    print("\n=== CAPTCHA ===")
    try:
        subprocess.run(["chafa", "--size=20x6", str(CAPTCHA_PATH)], check=True)
        return
    except FileNotFoundError:
        print("chafa no está instalado. Intentando abrir con xdg-open...")
    except subprocess.CalledProcessError:
        print("No se pudo mostrar con chafa. Intentando abrir con xdg-open...")

    try:
        subprocess.run(["xdg-open", str(CAPTCHA_PATH)], check=False)
    except FileNotFoundError:
        print("No se encontró xdg-open. Abre manualmente captcha.png desde el directorio del proyecto.")


def collect_payload(form) -> dict[str, str]:
    payload: dict[str, str] = {}

    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if name:
            payload[name] = input_tag.get("value", "")

    for select in form.find_all("select"):
        name = select.get("name")
        if not name:
            continue
        selected = select.find("option", selected=True)
        if selected and selected.get("value") is not None:
            payload[name] = selected.get("value", "")
        else:
            first = select.find("option")
            payload[name] = first.get("value", "") if first else ""

    return payload


def infer_and_fill_fields(
    form,
    payload: dict[str, str],
    start: str,
    end: str,
    captcha: str,
    fund: FundOption,
) -> dict[str, str]:
    payload["txt_inicio"] = start
    payload["txt_termino"] = end
    payload["ffmm"] = fund.code
    payload["captcha"] = captcha

    text_inputs = []
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not name:
            continue
        input_type = (input_tag.get("type") or "text").lower()
        if input_type in {"text", "date", "tel", "search"}:
            text_inputs.append(input_tag)

    if len(text_inputs) >= 1:
        payload[text_inputs[0]["name"]] = start
    if len(text_inputs) >= 2:
        payload[text_inputs[1]["name"]] = end

    for select in form.find_all("select"):
        if select.find("option", value=fund.code):
            select_name = select.get("name")
            if select_name:
                payload[select_name] = fund.code
            break

    captcha_field_name = None
    for input_tag in text_inputs:
        name = input_tag.get("name", "")
        input_id = input_tag.get("id", "")
        placeholder = input_tag.get("placeholder", "")
        combined = f"{name} {input_id} {placeholder}".lower()
        if any(token in combined for token in ["captcha", "codigo", "código", "imagen", "seguridad"]):
            captcha_field_name = name
            break

    if not captcha_field_name and len(text_inputs) >= 3:
        captcha_field_name = text_inputs[2]["name"]

    if captcha_field_name:
        payload[captcha_field_name] = captcha

    return payload


def save_response_as_file(response: requests.Response, start_date: str, end_date: str, fund: FundOption) -> Path:
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

    fund_download_dir = DOWNLOAD_DIR / fund_slug
    fund_download_dir.mkdir(parents=True, exist_ok=True)

    output_path = fund_download_dir / filename

    if output_path.exists():
        output_path = fund_download_dir / (
            f"cmf_{fund_slug}_"
            f"{safe_date_for_filename(start_date)}_{safe_date_for_filename(end_date)}.txt"
        )

    output_path.write_bytes(response.content)
    return output_path


def print_diagnostics(form, payload: dict[str, str], fund: FundOption) -> None:
    print("\n=== Diagnóstico del formulario detectado ===")
    print(f"Fondo resuelto: {fund.key} | {fund.code} | {fund.label}")
    print(f"Coincidencia CMF: {fund.matched_from_cmf}")

    print("\nInputs:")
    for input_tag in form.find_all("input"):
        print(
            f"  name={input_tag.get('name')} | "
            f"type={input_tag.get('type')} | "
            f"id={input_tag.get('id')} | "
            f"value={input_tag.get('value')}"
        )

    print("\nSelects:")
    for select in form.find_all("select"):
        options = select.find_all("option")
        print(f"  name={select.get('name')} | id={select.get('id')} | options={len(options)}")

    print("\nPayload preparado:")
    for key, value in payload.items():
        masked = "***" if "captcha" in key.lower() else value
        print(f"  {key}: {masked}")


def build_ranges(historical_start: date, end_date: date, max_days_per_request: int) -> list[tuple[date, date]]:
    if historical_start > end_date:
        raise ValueError("La fecha inicial histórica no puede ser posterior a la fecha final.")

    ranges: list[tuple[date, date]] = []
    current_start = historical_start

    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=max_days_per_request - 1), end_date)
        ranges.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)

    return ranges


def expected_output_path(start_str: str, end_str: str, fund: FundOption) -> Path:
    fund_slug = slugify(f"{fund.code}_{fund.label}")
    return DOWNLOAD_DIR / fund_slug / (
        f"cmf_{fund_slug}_{safe_date_for_filename(start_str)}_{safe_date_for_filename(end_str)}.txt"
    )


def download_one_range(
    range_index: int,
    total_ranges: int,
    start_date: date,
    end_date: date,
    fund: FundOption,
    show_diagnostics: bool,
    skip_existing: bool,
) -> dict[str, str]:
    start_str = format_cmf_date(start_date)
    end_str = format_cmf_date(end_date)
    expected_path = expected_output_path(start_str, end_str, fund)

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
    download_captcha(session, captcha_url)
    show_captcha()

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
        DEBUG_DIR.mkdir(exist_ok=True)
        fund_slug = slugify(f"{fund.code}_{fund.label}")
        debug_path = DEBUG_DIR / (
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

    output_path = save_response_as_file(response, start_str, end_str, fund)

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


def write_summary(summaries: list[dict[str, str]], historical_start: date, end_date: date) -> Path:
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    summary_path = DOWNLOAD_DIR / (
        f"resumen_cmf_multifondos_{historical_start.isoformat()}_{end_date.isoformat()}.json"
    )
    summary_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga cartola diaria CMF para varios fondos en tramos secuenciales de máximo 31 días."
    )

    parser.add_argument("--start-date", default=None, help="Fecha histórica inicial, más antigua. Ejemplo: 2025-04-04.")
    parser.add_argument("--end-date", default=None, help="Fecha final, más reciente. Si se omite, usa hoy.")
    parser.add_argument("--max-days-per-request", type=int, default=MAX_DAYS_PER_REQUEST)
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--sleep-between-ranges", type=float, default=1.0)

    parser.add_argument(
        "--fund",
        nargs="+",
        default=None,
        help=(
            "Fondo a descargar. Opciones: balanceado, national_equity, toesca_equity, "
            "itau_ahorro_uf, all. Si se omite, se pregunta por consola."
        ),
    )

    parser.add_argument("--fund-code", default=None, help="Código CMF explícito para el fondo indicado.")
    parser.add_argument("--list-funds", action="store_true", help="Lista fondos detectados en CMF y termina.")
    parser.add_argument("--list-filter", default=None, help="Filtro para --list-funds. Ejemplo: itau, toesca, national.")

    args = parser.parse_args()

    today = date.today()

    historical_start = parse_user_date(args.start_date) if args.start_date else ask_date(
        "Ingrese la fecha histórica inicial, más antigua"
    )
    end_date = parse_user_date(args.end_date) if args.end_date else ask_date(
        "Ingrese la fecha final, más reciente",
        default=today,
    )

    if historical_start > end_date:
        print("Error: la fecha histórica inicial no puede ser posterior a la fecha final.")
        sys.exit(1)

    if args.max_days_per_request < 1:
        print("Error: --max-days-per-request debe ser mayor o igual a 1.")
        sys.exit(1)

    funds = resolve_funds_for_run(
        requested_funds=args.fund,
        explicit_fund_code=args.fund_code,
        list_funds=args.list_funds,
        list_filter=args.list_filter,
    )

    ranges = build_ranges(historical_start, end_date, args.max_days_per_request)

    print("=== Descarga Cartola Diaria CMF por consola ===")
    print(f"Fecha histórica inicial: {format_cmf_date(historical_start)}")
    print(f"Fecha final: {format_cmf_date(end_date)}")
    print(f"Máximo días por solicitud: {args.max_days_per_request}")
    print(f"Cantidad de tramos por fondo: {len(ranges)}")
    print()
    print("Fondos seleccionados:")
    for fund in funds:
        print(f"  - {fund.key}: {fund.code} | {fund.label} | CMF: {fund.matched_from_cmf}")

    print()
    print("Tramos:")
    for idx, (range_start, range_end) in enumerate(ranges, start=1):
        print(f"  {idx:03d}. {format_cmf_date(range_start)} a {format_cmf_date(range_end)}")

    total_requests = len(funds) * len(ranges)
    print()
    print(f"Total solicitudes con CAPTCHA: {total_requests}")

    confirm = input("\n¿Continuar con la descarga secuencial? [s/N]: ").strip().lower()
    if confirm not in {"s", "si", "sí", "y", "yes"}:
        print("Proceso cancelado por el usuario.")
        sys.exit(0)

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    summaries: list[dict[str, str]] = []
    current_request = 0

    for fund in funds:
        print()
        print("#" * 72)
        print(f"INICIANDO FONDO: {fund.code} - {fund.label}")
        print("#" * 72)

        for idx, (range_start, range_end) in enumerate(ranges, start=1):
            current_request += 1
            print()
            print(f"Solicitud global {current_request}/{total_requests}")

            result = download_one_range(
                range_index=idx,
                total_ranges=len(ranges),
                start_date=range_start,
                end_date=range_end,
                fund=fund,
                show_diagnostics=args.diagnostics,
                skip_existing=args.skip_existing,
            )
            summaries.append(result)

            if result.get("status") == "html_response_error":
                print()
                decision = input("Hubo error en este tramo. ¿Continuar con el siguiente? [s/N]: ").strip().lower()
                if decision not in {"s", "si", "sí", "y", "yes"}:
                    print("Proceso detenido por el usuario.")
                    summary_path = write_summary(summaries, historical_start, end_date)
                    print(f"Resumen guardado en: {summary_path}")
                    sys.exit(0)

            if current_request < total_requests and args.sleep_between_ranges > 0:
                time.sleep(args.sleep_between_ranges)

    summary_path = write_summary(summaries, historical_start, end_date)

    downloaded = sum(1 for item in summaries if item.get("status") == "downloaded")
    skipped = sum(1 for item in summaries if item.get("status") == "skipped_existing")
    errors = sum(1 for item in summaries if "error" in item.get("status", ""))

    print()
    print("=" * 72)
    print("PROCESO TERMINADO")
    print(f"Solicitudes procesadas: {len(summaries)} / {total_requests}")
    print(f"Tramos descargados: {downloaded}")
    print(f"Tramos omitidos por existentes: {skipped}")
    print(f"Tramos con error: {errors}")
    print(f"Resumen guardado en: {summary_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
