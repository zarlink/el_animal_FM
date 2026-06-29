from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

from el_animal_fm.funds.application.cmf.cmf_config import (
    DEFAULT_CAPTCHA_NAME,
    DEFAULT_DEBUG_DIR,
    DEFAULT_DOWNLOAD_DIR,
    MAX_DAYS_PER_REQUEST,
)
from el_animal_fm.funds.application.cmf.cmf_dates import (
    ask_date,
    build_ranges,
    format_cmf_date,
    parse_user_date,
)
from el_animal_fm.funds.application.download.download_fund_data import download_one_range
from el_animal_fm.funds.application.catalog.fund_selection import resolve_funds_for_run
from el_animal_fm.funds.infrastructure.cmf_storage import write_summary


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
    parser.add_argument("--base-dir", default=".", help="Directorio base para downloads, captcha y debug.")

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

    base_dir = Path(args.base_dir).resolve()
    download_dir = base_dir / DEFAULT_DOWNLOAD_DIR
    captcha_path = base_dir / DEFAULT_CAPTCHA_NAME
    debug_dir = base_dir / DEFAULT_DEBUG_DIR

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

    download_dir.mkdir(exist_ok=True)

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
                download_dir=download_dir,
                captcha_path=captcha_path,
                debug_dir=debug_dir,
            )
            summaries.append(result)

            if result.get("status") == "html_response_error":
                print()
                decision = input("Hubo error en este tramo. ¿Continuar con el siguiente? [s/N]: ").strip().lower()
                if decision not in {"s", "si", "sí", "y", "yes"}:
                    print("Proceso detenido por el usuario.")
                    summary_path = write_summary(download_dir, summaries, historical_start, end_date)
                    print(f"Resumen guardado en: {summary_path}")
                    sys.exit(0)

            if current_request < total_requests and args.sleep_between_ranges > 0:
                time.sleep(args.sleep_between_ranges)

    summary_path = write_summary(download_dir, summaries, historical_start, end_date)

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
