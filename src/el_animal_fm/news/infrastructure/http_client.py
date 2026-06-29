from __future__ import annotations

import requests


REQUEST_TIMEOUT = 30


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
        }
    )
    return session


def decode_response_text(response: requests.Response) -> str:
    """
    Decodifica HTML/XML de forma estable.
    Evita problemas de caracteres cuando response.text no detecta bien encoding.
    """
    try:
        return response.content.decode("utf-8", errors="replace")
    except Exception:
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        return response.text


def fetch_text(session: requests.Session, url: str) -> tuple[str, int, str]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    content_type = response.headers.get("Content-Type", "")
    response.raise_for_status()
    return decode_response_text(response), response.status_code, content_type
