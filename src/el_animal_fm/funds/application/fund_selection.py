from __future__ import annotations

import sys

from el_animal_fm.funds.application.cmf_config import FUND_CATALOG
from el_animal_fm.funds.application.cmf_text import normalize_text
from el_animal_fm.funds.application.fund_catalog import (
    print_available_catalog,
    resolve_fund_from_form,
)
from el_animal_fm.funds.domain.models import FundOption
from el_animal_fm.funds.infrastructure.cmf_client import load_initial_form
from el_animal_fm.funds.infrastructure.cmf_form_parser import get_cmf_fund_options


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
