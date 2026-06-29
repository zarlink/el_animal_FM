from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from el_animal_fm.funds.application.cmf_config import CMF_URL


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


def load_initial_form() -> tuple[requests.Session, BeautifulSoup, object]:
    from el_animal_fm.funds.infrastructure.cmf_form_parser import pick_main_form

    session = create_session()
    print("Descargando página inicial de CMF...")
    page_response = session.get(CMF_URL, timeout=30)
    page_response.raise_for_status()
    soup = get_soup(page_response.text)
    form = pick_main_form(soup)
    return session, soup, form
