from __future__ import annotations

import logging
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

from el_animal_fm.news.application.dictionary import dictionary_config as config
from el_animal_fm.news.application.dictionary.dictionary_cache import DictionaryCache, dependencies, fingerprint

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
    return _process_record_task((a, None))


def _process_record_task(task: tuple[dict, str | None]) -> dict:
    """
    Worker independiente para procesar una noticia.

    Retorna un dict con status:
    - ok: artículo convertido en record válido.
    - excluded: descartado por sección/tipo.
    - empty: sin texto útil.
    - error: error controlado.
    """
    a, cached_text = task
    try:
        if not should_use_for_financial_dictionary(a):
            return {
                "status": "excluded",
                "reason": "section_or_type_excluded",
            }

        txt = cached_text if cached_text is not None else build_dictionary_text(a)

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
    cache: DictionaryCache | None = None,
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

    if max_workers < 1 or chunksize < 1 or log_every < 1:
        raise ValueError("Workers, chunksize y frecuencia de logs deben ser positivos")
    text_signature = dependencies("dictionary_text", values=list(config.PHRASE_NORMALIZATIONS.items()))
    family_signature = dependencies(
        "dictionary_classifier", "dictionary_text",
        values={name: value for name, value in vars(config).items()
                if name.endswith("_SEEDS")} | {"PHRASE_NORMALIZATIONS": list(config.PHRASE_NORMALIZATIONS.items())},
    )
    prepared = []
    reused = 0
    for article in articles:
        if not should_use_for_financial_dictionary(article):
            prepared.append(({"status": "excluded", "reason": "section_or_type_excluded"}, None, None))
            continue
        text_key = fingerprint([text_signature, article])
        cached_text = cache.get("record_text", text_key) if cache is not None else None
        family_key = fingerprint([family_signature, cached_text]) if cached_text is not None else None
        family = cache.get("record_family", family_key) if cache is not None and family_key is not None else None
        if cached_text == "":
            result = {"status": "empty", "reason": "empty_dictionary_text"}
        elif family is not None:
            result = {"status": "ok", "record": {"article": article, "text": cached_text, "family_info": family}}
            reused += 1
        else:
            result = None
        prepared.append((result, text_key, (article, cached_text)))

    logger.info("CACHÉ | records | reutilizados=%d | por_calcular=%d",
                reused, sum(result is None for result, _, _ in prepared))
    tasks = [task for result, _, task in prepared if result is None]

    def collect(results_iter):
        results_iter = iter(results_iter)
        for index, (result, text_key, _) in enumerate(prepared, start=1):
            calculated = result is None
            if calculated:
                result = next(results_iter)
            status = result.get("status", "unknown")
            stats[status] += 1
            if status == "ok":
                record = result["record"]
                records.append(record)
                if calculated and cache is not None:
                    cache.put("record_text", text_key, record["text"])
                    cache.put("record_family", fingerprint([family_signature, record["text"]]), record["family_info"])
            elif status == "empty" and calculated and cache is not None:
                cache.put("record_text", text_key, "")
            elif status == "error":
                logger.warning("Error procesando artículo | url=%s | title=%s | error=%s",
                               result.get("url", ""), result.get("title", ""), result.get("error", ""))
            if index % log_every == 0 or index == total:
                logger.info(
                    "PROGRESO | records | %d/%d | ok=%d | excluidos=%d | vacíos=%d | errores=%d | tiempo=%.2fs",
                    index, total, stats['ok'], stats['excluded'], stats['empty'], stats['error'],
                    time.perf_counter() - start,
                )

    if tasks and max_workers > 1:
        with ProcessPoolExecutor(max_workers=min(max_workers, len(tasks)),
                                 mp_context=get_context("spawn")) as executor:
            collect(executor.map(_process_record_task, tasks, chunksize=chunksize))
    else:
        collect(map(_process_record_task, tasks))

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
