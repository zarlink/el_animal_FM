"""Identidad y fecha de publicación deterministas, compartidas por el pipeline."""
from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

MONTHS = {name: i for i, name in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"), 1)}
MONTHS["setiembre"] = 9
CHILE = ZoneInfo("America/Santiago")


def publication_parts(value: str) -> tuple[str, str, str]:
    """Sin fechas incompletas ni defaults dependientes del día de ejecución."""
    value = str(value or "").strip()
    spanish = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r"),?\s+(\d{4})\b", value, re.I)
    clock = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", value)
    if spanish:
        day, month, year = spanish.groups()
        day_value = date(int(year), MONTHS[month.lower()], int(day))
        clock_value = datetime.strptime(clock.group(1), "%H:%M:%S" if clock and clock.group(1).count(":") == 2 else "%H:%M").time() if clock else None
        stamp = datetime.combine(day_value, clock_value, CHILE) if clock_value else None
        return stamp.isoformat() if stamp else day_value.isoformat(), day_value.isoformat(), clock_value.isoformat() if clock_value else ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}|$)", value):
        raise ValueError(f"Fecha de publicación no reconocida: {value!r}")
    if len(value) == 10:
        day_value = date.fromisoformat(value)
        return day_value.isoformat(), day_value.isoformat(), ""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = parsed.replace(tzinfo=CHILE) if parsed.tzinfo is None else parsed.astimezone(CHILE)
    return parsed.isoformat(), parsed.date().isoformat(), parsed.time().replace(microsecond=0).isoformat()


def article_key(article: dict) -> str:
    raw = article.get("raw", article)
    value = str(raw.get("canonical_url") or raw.get("url") or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host or parsed.scheme not in {"http", "https"}:
        return ""
    query = sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"})
    return urlunsplit(("https", host, parsed.path.rstrip("/"), urlencode(query), ""))


def url_publication_date(article: dict) -> date | None:
    match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})(?:/|$)", article_key(article))
    return date(*(int(x) for x in match.groups())) if match else None


def correct_article(article: dict) -> tuple[dict, date]:
    result = copy.deepcopy(article)
    raw = result.get("raw", result)
    if not article_key(result):
        raise ValueError("Noticia sin URL válida; requiere revisión antes de guardarse")
    # La publicación original tiene prioridad sobre el día embebido en la URL:
    # algunos medios cambian la URL o republican artículos.
    parts = None
    for candidate in (raw.get("published_at_raw"), raw.get("published_at"), raw.get("published_date")):
        try:
            parts = publication_parts(candidate)
            break
        except (ValueError, TypeError):
            continue
    if parts is None:
        day = url_publication_date(result)
        if day is None:
            raise ValueError(f"Sin fecha verificable: {article_key(result)}")
        parts = (day.isoformat(), day.isoformat(), "")
        raw["publication_date_basis"] = "url_fallback"
    stamp, day_text, clock = parts
    # Una fecha original sin hora no permite conservar una medianoche inventada.
    raw.update(published_at=stamp, published_date=day_text, published_time=clock)
    if isinstance(result.get("features"), dict):
        temporal = result["features"].setdefault("temporal", {})
        day = date.fromisoformat(day_text)
        temporal.update(published_date=day_text, published_time=clock,
                        published_hour=int(clock[:2]) if clock else None,
                        published_weekday=day.weekday(), is_weekend=day.weekday() >= 5)
    return result, date.fromisoformat(day_text)


def article_quality(article: dict) -> tuple:
    raw = article.get("raw", article)
    return (bool(article.get("technical", {}).get("parse_success", True)),
            len(str(raw.get("body_text_clean") or raw.get("body_text_raw") or "")),
            str(raw.get("scraped_at") or ""))


def prepare_daily_payload(payload: dict, target: date) -> dict:
    result = copy.deepcopy(payload)
    if not isinstance(payload.get("articles"), list):
        raise ValueError("El archivo no contiene una lista de artículos")
    unique = {}
    for article in payload["articles"]:
        corrected, published = correct_article(article)
        if published != target:
            raise ValueError(f"Noticia de {published} en carpeta de {target}: {article_key(article)}. Ejecuta scripts/reconcile_news.py antes de procesar este archivo.")
        key = article_key(corrected)
        if key not in unique or article_quality(corrected) > article_quality(unique[key]):
            unique[key] = corrected
    result["articles"] = list(unique.values())
    meta = result.setdefault("metadata", {})
    meta.update(target_date=target.isoformat(), target_date_folder=target.strftime("%d_%m_%Y"),
                articles_downloaded=len(unique))
    if "features_articles_count" in meta:
        meta["features_articles_count"] = len(unique)
    return result


@lru_cache(maxsize=2048)
def _file_keys(path: str, modified_ns: int, size: int) -> tuple[str, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple({article_key(a) for a in payload.get("articles", []) if isinstance(a, dict)} - {""})


def assert_unique_daily_files(files: list[Path], proposed: tuple[Path, dict] | None = None) -> None:
    """Impide que una URL aparezca en dos días del mismo medio.

    La caché se invalida por mtime y tamaño; no se mantiene un índice persistente
    que pueda quedar desactualizado al editar archivos fuera de la aplicación.
    """
    locations = {}
    paths = set(files)
    if proposed:
        paths.add(proposed[0])
    for path in sorted(paths):
        if proposed and path == proposed[0]:
            keys = {article_key(a) for a in proposed[1]["articles"]} - {""}
        else:
            stat = path.stat()
            try:
                keys = _file_keys(str(path), stat.st_mtime_ns, stat.st_size)
            except (ValueError, TypeError, AttributeError):
                # El procesamiento individual reportará los JSON inválidos.
                continue
        for key in keys:
            identity = (str(path.parent.parent.resolve()), key)
            if identity in locations and locations[identity] != path.parent:
                raise ValueError(f"URL repetida entre {locations[identity]} y {path.parent}: {key}. Ejecuta scripts/reconcile_news.py antes de continuar.")
            locations[identity] = path.parent
