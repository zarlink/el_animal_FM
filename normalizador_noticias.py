from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


DEFAULT_MEDIA_DIRS = ["biobio", "mostrador"]

TEXT_FIELDS_SIMPLE = [
    "title",
    "subtitle",
    "lead",
    "ai_summary",
    "summary",
    "author_name",
    "author_role",
    "source_attribution",
    "image_caption",
    "image_credit",
    "main_image_alt",
]

BODY_FIELDS = [
    "body_text_raw",
    "body_text_clean",
]

BOILERPLATE_PATTERNS = [
    r"^lee también\.?:?$",
    r"^lee tambien\.?:?$",
    r"^ver resumen$",
    r"^suscríbete en nuestro canal",
    r"^suscribete en nuestro canal",
    r"^síguenos",
    r"^siguenos",
    r"^publicidad$",
    r"^ética y transparencia",
    r"^etica y transparencia",
    r"^visto ahora$",
    r"^noticias relacionadas$",
    r"^también te puede interesar",
    r"^tambien te puede interesar",
]


def repair_mojibake(text: str) -> str:
    """
    Corrige casos típicos de mojibake:
    'dÃ©ficit' -> 'déficit'
    'caÃ­da' -> 'caída'
    """
    if not text:
        return ""

    markers = ("Ã", "Â", "â€", "â€œ", "â€", "â€™", "ðŸ")

    if not any(marker in text for marker in markers):
        return text

    candidates = [text]

    for encoding in ("latin1", "cp1252"):
        try:
            fixed = text.encode(encoding, errors="ignore").decode("utf-8", errors="ignore")
            candidates.append(fixed)
        except Exception:
            pass

    def badness(value: str) -> int:
        return (
            value.count("Ã")
            + value.count("Â")
            + value.count("â€")
            + value.count("�") * 3
        )

    return min(candidates, key=badness)


def normalize_spaces(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_html(text: Any) -> str:
    """
    Convierte HTML o texto mixto en texto plano.
    """
    if text is None:
        return ""

    text = str(text)
    text = html.unescape(text)
    text = repair_mojibake(text)

    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "lxml")

        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)

    text = html.unescape(text)
    text = repair_mojibake(text)
    text = normalize_spaces(text)

    return text


def is_boilerplate(text: str) -> bool:
    if not text:
        return True

    clean = strip_html(text).lower().strip()

    if len(clean) <= 2:
        return True

    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, clean, flags=re.IGNORECASE):
            return True

    return False


def split_into_paragraphs(text: str) -> list[str]:
    """
    Intenta reconstruir párrafos limpios desde texto ya normalizado.
    """
    if not text:
        return []

    # Primero separamos por saltos de línea.
    chunks = re.split(r"\n+", text)

    # Si no hay saltos útiles, se deja como un solo bloque.
    if len(chunks) <= 1:
        chunks = [text]

    paragraphs: list[str] = []

    for chunk in chunks:
        chunk = strip_html(chunk)

        if not chunk:
            continue

        if is_boilerplate(chunk):
            continue

        if chunk not in paragraphs:
            paragraphs.append(chunk)

    return paragraphs


def clean_paragraphs(value: Any) -> list[str]:
    """
    Limpia una lista de párrafos o un string con HTML.
    """
    paragraphs: list[str] = []

    if isinstance(value, list):
        iterable = value
    elif isinstance(value, str):
        iterable = [value]
    else:
        iterable = []

    for item in iterable:
        cleaned = strip_html(item)

        if not cleaned:
            continue

        if is_boilerplate(cleaned):
            continue

        if cleaned not in paragraphs:
            paragraphs.append(cleaned)

    return paragraphs


def clean_body_text_from_raw(raw: dict[str, Any]) -> tuple[str, str, list[str]]:
    """
    Repara body_text_raw, body_text_clean y paragraphs.

    Prioridad:
    1. paragraphs existentes, si son útiles.
    2. body_text_raw.
    3. body_text_clean.
    4. ai_summary / subtitle como respaldo mínimo.
    """
    paragraphs = clean_paragraphs(raw.get("paragraphs", []))

    if len(paragraphs) < 2:
        candidate = (
            raw.get("body_text_raw")
            or raw.get("body_text_clean")
            or raw.get("ai_summary")
            or raw.get("subtitle")
            or ""
        )

        candidate_clean = strip_html(candidate)
        extracted = split_into_paragraphs(candidate_clean)

        if len(extracted) > len(paragraphs):
            paragraphs = extracted

    body_text_raw = "\n".join(paragraphs)
    body_text_clean = normalize_spaces(" ".join(paragraphs))

    return body_text_raw, body_text_clean, paragraphs


def clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned_items: list[str] = []

    for item in value:
        cleaned = strip_html(item)

        if not cleaned:
            continue

        if is_boilerplate(cleaned):
            continue

        if cleaned not in cleaned_items:
            cleaned_items.append(cleaned)

    return cleaned_items


def normalize_article(article: dict[str, Any]) -> dict[str, Any]:
    raw = article.get("raw", {})

    if not isinstance(raw, dict):
        return article

    # Campos simples de texto.
    for field in TEXT_FIELDS_SIMPLE:
        if field in raw:
            raw[field] = strip_html(raw.get(field, ""))

    # Listas de títulos o textos relacionados.
    for field in [
        "read_also_titles",
        "read_also_dates",
        "related_titles",
        "internal_subheadings",
        "also_interesting_titles",
        "featured_titles",
        "same_day_titles",
        "mentioned_documents_raw",
    ]:
        if field in raw:
            raw[field] = clean_string_list(raw.get(field, []))

    # Cuerpo principal.
    body_text_raw, body_text_clean, paragraphs = clean_body_text_from_raw(raw)

    raw["body_text_raw"] = body_text_raw
    raw["body_text_clean"] = body_text_clean
    raw["paragraphs"] = paragraphs
    raw["paragraph_count"] = len(paragraphs)
    raw["body_length_chars"] = len(body_text_clean)
    raw["body_length_words"] = len(body_text_clean.split())

    # Recalcular quote_count de forma simple.
    raw["quote_count"] = body_text_clean.count("“") + body_text_clean.count("”")

    article["raw"] = raw
    return article


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    articles = payload.get("articles", [])

    if not isinstance(articles, list):
        return payload

    payload["articles"] = [
        normalize_article(article)
        for article in articles
        if isinstance(article, dict)
    ]

    metadata = payload.setdefault("metadata", {})
    metadata["text_normalized"] = True
    metadata["text_normalizer_version"] = "normalize_news_texts_v1"

    return payload


def find_news_file(day_dir: Path) -> Path | None:
    candidates = [
        day_dir / "noticias_dia.txt",
        day_dir / "noticias_dia",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def process_file(path: Path, overwrite: bool = True) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] No pude leer JSON: {path} | {exc}")
        return False

    backup_path = path.with_suffix(path.suffix + ".bak")

    if not backup_path.exists():
        shutil.copy2(path, backup_path)

    normalized = normalize_payload(payload)

    if overwrite:
        output_path = path
    else:
        output_path = path.with_name(path.stem + "_normalizado" + path.suffix)

    output_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] Reparado: {output_path}")
    return True


def process_media_dir(media_dir: Path, overwrite: bool = True) -> tuple[int, int]:
    if not media_dir.exists():
        print(f"[WARN] No existe carpeta: {media_dir}")
        return 0, 0

    total = 0
    ok = 0

    for day_dir in sorted(media_dir.iterdir()):
        if not day_dir.is_dir():
            continue

        if not re.fullmatch(r"\d{2}_\d{2}_\d{4}", day_dir.name):
            continue

        news_file = find_news_file(day_dir)

        if not news_file:
            print(f"[WARN] No encontré noticias_dia en: {day_dir}")
            continue

        total += 1

        if process_file(news_file, overwrite=overwrite):
            ok += 1

    return total, ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repara y normaliza textos HTML en noticias_dia.txt de biobio y mostrador."
    )

    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directorio base del proyecto. Por defecto, carpeta actual.",
    )

    parser.add_argument(
        "--media",
        nargs="*",
        default=DEFAULT_MEDIA_DIRS,
        help="Carpetas de medios a procesar. Default: biobio mostrador.",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="No sobrescribe el archivo original. Crea noticias_dia_normalizado.txt.",
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    overwrite = not args.no_overwrite

    print("=== Normalizador de noticias ===")
    print(f"Directorio base: {base_dir}")
    print(f"Sobrescribir archivos: {overwrite}")
    print()

    global_total = 0
    global_ok = 0

    for media in args.media:
        media_dir = base_dir / media
        print(f"\nProcesando medio: {media_dir}")

        total, ok = process_media_dir(media_dir, overwrite=overwrite)

        print(f"Resumen {media}: {ok}/{total} archivos reparados")

        global_total += total
        global_ok += ok

    print("\n=== Proceso terminado ===")
    print(f"Archivos reparados: {global_ok}/{global_total}")


if __name__ == "__main__":
    main()