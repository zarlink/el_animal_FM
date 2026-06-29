from __future__ import annotations

from el_animal_fm.funds.application.cmf.cmf_config import FUND_CATALOG
from el_animal_fm.funds.application.cmf.cmf_text import normalize_text
from el_animal_fm.funds.domain.models import FundOption
from el_animal_fm.funds.infrastructure.cmf_form_parser import get_cmf_fund_options


def resolve_fund_from_form(
    form,
    fund_key: str,
    explicit_code: str | None = None,
) -> FundOption:
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
