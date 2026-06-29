from __future__ import annotations

from bs4 import BeautifulSoup


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

    return max(selects, key=lambda select: len(select.find_all("option")))


def get_cmf_fund_options(form) -> list[tuple[str, str]]:
    fund_select = find_fund_select(form)
    options: list[tuple[str, str]] = []

    for option in fund_select.find_all("option"):
        value = (option.get("value") or "").strip()
        text = option.get_text(" ", strip=True)
        if value:
            options.append((value, text))

    return options
