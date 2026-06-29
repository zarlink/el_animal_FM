from __future__ import annotations

from el_animal_fm.funds.domain.models import FundOption


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
