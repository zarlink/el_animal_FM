from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from el_animal_fm.funds.application.cmf_config import CAPTCHA_VALIDATE_URL, CMF_URL


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


def download_captcha(session: requests.Session, captcha_url: str, captcha_path: Path) -> None:
    response = session.get(captcha_url, timeout=30)
    response.raise_for_status()
    captcha_path.write_bytes(response.content)
    print(f"CAPTCHA guardado en: {captcha_path}")


def validate_captcha(session: requests.Session, captcha: str) -> bool:
    response = session.post(
        CAPTCHA_VALIDATE_URL,
        data={"accion": "valida", "valor": captcha},
        timeout=30,
    )
    response.raise_for_status()
    return response.text.strip() == "1"


def show_captcha(captcha_path: Path) -> None:
    print("\n=== CAPTCHA ===")
    try:
        subprocess.run(["chafa", "--size=20x6", str(captcha_path)], check=True)
        return
    except FileNotFoundError:
        print("chafa no está instalado. Intentando abrir con xdg-open...")
    except subprocess.CalledProcessError:
        print("No se pudo mostrar con chafa. Intentando abrir con xdg-open...")

    try:
        subprocess.run(["xdg-open", str(captcha_path)], check=False)
    except FileNotFoundError:
        print("No se encontró xdg-open. Abre manualmente captcha.png desde el directorio del proyecto.")
