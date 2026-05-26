from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin
import re
import subprocess
import sys

import requests
from bs4 import BeautifulSoup


CMF_URL = "https://www.cmfchile.cl/institucional/estadisticas/fondos_cartola_diaria.php"

# Fondo indicado:
# 10063 - CARTERA BALANCEADO
FUND_CODE = "10063"

DAYS_BACK = 31

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
CAPTCHA_PATH = BASE_DIR / "captcha.png"
DEBUG_HTML_PATH = BASE_DIR / "debug_response.html"


def format_cmf_date(value: date) -> str:
    """Formato que usa el formulario CMF: dd/mm/aaaa."""
    return value.strftime("%d/%m/%Y")


def get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def pick_main_form(soup: BeautifulSoup):
    """
    Intenta ubicar el formulario correcto.
    Priorizamos el form que contenga el fondo 10063 o una imagen CAPTCHA.
    """
    forms = soup.find_all("form")

    if not forms:
        raise RuntimeError("No se encontraron formularios <form> en el HTML.")

    for form in forms:
        form_text = form.get_text(" ", strip=True).lower()
        has_fund = bool(form.find("option", value=FUND_CODE))
        has_captcha_word = "captcha" in str(form).lower() or "caracteres de la imagen" in form_text

        if has_fund or has_captcha_word:
            return form

    # Si no encontramos uno evidente, usamos el primer formulario.
    return forms[0]


def find_captcha_image_url(soup: BeautifulSoup, form) -> str:
    """
    Busca la imagen CAPTCHA dentro del formulario y, si no aparece,
    busca globalmente en la página.
    """
    candidates = []

    for scope in [form, soup]:
        for img in scope.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            title = img.get("title", "")
            combined = f"{src} {alt} {title}".lower()

            if "captcha" in combined or "imagen" in combined:
                candidates.append(src)

    # Si no aparece la palabra captcha, intentamos detectar una imagen cercana
    # al texto "Ingrese los caracteres de la imagen".
    if not candidates:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and any(token in src.lower() for token in ["captcha", "verificacion", "seguridad", "imagen"]):
                candidates.append(src)

    if not candidates:
        raise RuntimeError(
            "No se pudo detectar automáticamente la URL del CAPTCHA. "
            "Ejecuta el script y revisa el archivo debug_response.html si se genera."
        )

    return urljoin(CMF_URL, candidates[0])


def download_captcha(session: requests.Session, captcha_url: str) -> None:
    response = session.get(captcha_url, timeout=30)
    response.raise_for_status()

    CAPTCHA_PATH.write_bytes(response.content)
    print(f"CAPTCHA guardado en: {CAPTCHA_PATH}")


def show_captcha() -> None:
    """
    Intenta mostrar el CAPTCHA en la terminal con chafa.
    Si no está disponible, abre la imagen con xdg-open.
    """
    print("\n=== CAPTCHA ===")

    try:
        subprocess.run(["chafa", str(CAPTCHA_PATH)], check=True)
        return
    except FileNotFoundError:
        print("chafa no está instalado. Intentando abrir con xdg-open...")
    except subprocess.CalledProcessError:
        print("No se pudo mostrar con chafa. Intentando abrir con xdg-open...")

    try:
        subprocess.run(["xdg-open", str(CAPTCHA_PATH)], check=False)
    except FileNotFoundError:
        print(
            "No se encontró xdg-open. Abre manualmente el archivo captcha.png "
            "desde el directorio del proyecto."
        )


def collect_payload(form) -> dict[str, str]:
    """
    Captura todos los inputs/selects existentes para preservar campos ocultos.
    Luego modificamos fechas, fondo y captcha.
    """
    payload: dict[str, str] = {}

    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not name:
            continue

        input_type = (input_tag.get("type") or "text").lower()
        value = input_tag.get("value", "")

        # Incluimos hidden, text, submit y otros, porque algunos sitios antiguos
        # esperan valores específicos.
        payload[name] = value

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


def infer_and_fill_fields(form, payload: dict[str, str], start: str, end: str, captcha: str) -> dict[str, str]:
    """
    Intenta inferir los nombres reales de los campos.

    Estrategia:
    - Primeros dos inputs de texto/date: fecha inicio y fecha término.
    - Select que contiene opción 10063: fondo.
    - Input de texto restante más probable: captcha.
    """

    text_inputs = []
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        if not name:
            continue

        input_type = (input_tag.get("type") or "text").lower()

        if input_type in {"text", "date", "tel", "search"}:
            text_inputs.append(input_tag)

    if len(text_inputs) < 3:
        print("\nAdvertencia: se esperaban al menos 3 campos de texto: inicio, término y CAPTCHA.")
        print("Campos encontrados:")
        for tag in text_inputs:
            print(f"  name={tag.get('name')} type={tag.get('type')} value={tag.get('value')}")

    # Fechas: usamos los dos primeros campos de texto.
    if len(text_inputs) >= 1:
        payload[text_inputs[0]["name"]] = start

    if len(text_inputs) >= 2:
        payload[text_inputs[1]["name"]] = end

    # Fondo: buscamos el select que contenga la opción FUND_CODE.
    fund_select_name = None

    for select in form.find_all("select"):
        if select.find("option", value=FUND_CODE):
            fund_select_name = select.get("name")
            break

    if not fund_select_name:
        selects = form.find_all("select")
        if selects:
            fund_select_name = selects[0].get("name")

    if fund_select_name:
        payload[fund_select_name] = FUND_CODE
    else:
        raise RuntimeError("No se pudo detectar el selector del fondo mutuo.")

    # CAPTCHA: intentamos detectar por nombre; si no, usamos el tercer campo de texto.
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
    else:
        raise RuntimeError("No se pudo detectar el campo donde se ingresa el CAPTCHA.")

    return payload


def get_form_action_and_method(form) -> tuple[str, str]:
    action = form.get("action") or CMF_URL
    method = (form.get("method") or "get").lower()

    action_url = urljoin(CMF_URL, action)

    if method not in {"get", "post"}:
        method = "get"

    return action_url, method


def save_response_as_file(response: requests.Response, start_date: str, end_date: str) -> Path:
    """
    Guarda la respuesta como archivo.
    Si el servidor envía Content-Disposition, intenta rescatar el nombre.
    Si no, usa un nombre estable.
    """

    content_disposition = response.headers.get("Content-Disposition", "")

    filename = None

    match = re.search(r'filename="?([^"]+)"?', content_disposition)
    if match:
        filename = match.group(1).strip()

    if not filename:
        safe_start = start_date.replace("/", "-")
        safe_end = end_date.replace("/", "-")
        filename = f"cmf_{FUND_CODE}_cartera_balanceado_{safe_start}_{safe_end}.txt"

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    output_path = DOWNLOAD_DIR / filename

    output_path.write_bytes(response.content)

    return output_path


def print_diagnostics(form, payload: dict[str, str]) -> None:
    print("\n=== Diagnóstico del formulario detectado ===")
    print("Inputs:")
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
        print(
            f"  name={select.get('name')} | "
            f"id={select.get('id')} | "
            f"options={len(options)}"
        )

    print("\nPayload preparado:")
    for key, value in payload.items():
        masked = "***" if "captcha" in key.lower() else value
        print(f"  {key}: {masked}")


def main() -> None:
    today = date.today()
    start = today - timedelta(days=DAYS_BACK)

    start_str = format_cmf_date(start)
    end_str = format_cmf_date(today)

    print("=== Descarga Cartola Diaria CMF por consola ===")
    print(f"Fondo: {FUND_CODE} - CARTERA BALANCEADO")
    print(f"Fecha inicio: {start_str}")
    print(f"Fecha término: {end_str}")
    print()

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

    print("Descargando página inicial de CMF...")
    page_response = session.get(CMF_URL, timeout=30)
    page_response.raise_for_status()

    soup = get_soup(page_response.text)
    form = pick_main_form(soup)

    captcha_url = find_captcha_image_url(soup, form)

    print(f"URL CAPTCHA detectada: {captcha_url}")
    download_captcha(session, captcha_url)
    show_captcha()

    captcha_value = input("\nIngrese el CAPTCHA visto en la imagen: ").strip()

    if not captcha_value:
        print("No ingresaste CAPTCHA. Proceso cancelado.")
        sys.exit(1)

    payload = collect_payload(form)
    payload = infer_and_fill_fields(
        form=form,
        payload=payload,
        start=start_str,
        end=end_str,
        captcha=captcha_value,
    )

    action_url, method = get_form_action_and_method(form)

    print()
    print(f"Enviando formulario por método {method.upper()} a:")
    print(action_url)

    # Útil durante el primer ajuste. Puedes dejarlo comentado después.
    print_diagnostics(form, payload)

    if method == "post":
        response = session.post(action_url, data=payload, timeout=60)
    else:
        response = session.get(action_url, params=payload, timeout=60)

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    # Si vuelve HTML, probablemente hubo error de CAPTCHA o el formulario no fue enviado bien.
    if "text/html" in content_type and len(response.content) > 0:
        DEBUG_HTML_PATH.write_bytes(response.content)

        print()
        print("La respuesta recibida parece HTML, no archivo de datos.")
        print("Esto puede ocurrir si el CAPTCHA fue incorrecto o si algún campo no fue inferido bien.")
        print(f"Guardé la respuesta en: {DEBUG_HTML_PATH}")
        print("Revisa ese archivo para ver el mensaje exacto de la CMF.")
        sys.exit(1)

    output_path = save_response_as_file(response, start_str, end_str)

    print()
    print("Descarga completada correctamente.")
    print(f"Archivo guardado en: {output_path}")


if __name__ == "__main__":
    main()