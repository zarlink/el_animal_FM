from __future__ import annotations

import logging
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from el_animal_fm.news.application.dictionary.dictionary_classifier import (
    classify_text_families,
    should_use_for_financial_dictionary,
)
from el_animal_fm.news.application.dictionary.dictionary_config import (
    DEFAULT_RECORD_WORKERS,
    RECORD_CHUNKSIZE,
    RECORD_LOG_EVERY,
)
from el_animal_fm.news.application.dictionary.dictionary_text import build_dictionary_text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("creador_diccionario")


def process_article_for_record(a: dict) -> dict:
    """
    Worker independiente para procesar una noticia.

    Retorna un dict con status:
    - ok: artículo convertido en record válido.
    - excluded: descartado por sección/tipo.
    - empty: sin texto útil.
    - error: error controlado.
    """
    try:
        if not should_use_for_financial_dictionary(a):
            return {
                "status": "excluded",
                "reason": "section_or_type_excluded",
            }

        txt = build_dictionary_text(a)

        if not txt:
            return {
                "status": "empty",
                "reason": "empty_dictionary_text",
            }

        family_info = classify_text_families(txt)

        return {
            "status": "ok",
            "record": {
                "article": a,
                "text": txt,
                "family_info": family_info,
            },
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": repr(exc),
            "url": a.get("url", ""),
            "title": a.get("title", ""),
        }

def build_records_parallel(
    articles: list[dict],
    max_workers: int = DEFAULT_RECORD_WORKERS,
    log_every: int = RECORD_LOG_EVERY,
    chunksize: int = RECORD_CHUNKSIZE,
) -> tuple[list[dict], Counter]:
    """
    Construye records en paralelo.

    Cada artículo se procesa de forma independiente:
    - filtro por sección/tipo
    - construcción de texto
    - limpieza
    - clasificación por familias
    """
    total = len(articles)
    records = []
    stats = Counter()

    logger.info(
        f"INICIO | Construcción paralela de records | "
        f"artículos={total} | workers={max_workers} | chunksize={chunksize}"
    )

    start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results_iter = executor.map(
            process_article_for_record,
            articles,
            chunksize=chunksize,
        )

        for index, result in enumerate(results_iter, start=1):
            status = result.get("status", "unknown")
            stats[status] += 1

            if status == "ok":
                records.append(result["record"])

            elif status == "error":
                logger.warning(
                    "Error procesando artículo | "
                    f"url={result.get('url', '')} | "
                    f"title={result.get('title', '')} | "
                    f"error={result.get('error', '')}"
                )

            if index % log_every == 0 or index == total:
                elapsed = time.perf_counter() - start
                logger.info(
                    f"PROGRESO | records | {index}/{total} | "
                    f"ok={stats['ok']} | "
                    f"excluidos={stats['excluded']} | "
                    f"vacíos={stats['empty']} | "
                    f"errores={stats['error']} | "
                    f"tiempo={elapsed:.2f}s"
                )

    elapsed = time.perf_counter() - start

    logger.info(
        f"FIN | Construcción paralela de records | "
        f"records={len(records)} | "
        f"excluidos={stats['excluded']} | "
        f"vacíos={stats['empty']} | "
        f"errores={stats['error']} | "
        f"tiempo_total={elapsed:.2f}s"
    )

    return records, stats
