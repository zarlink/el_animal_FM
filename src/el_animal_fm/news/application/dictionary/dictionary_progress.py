from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Event, Thread
from time import perf_counter


logger = logging.getLogger("creador_diccionario")


@contextmanager
def log_stage(name: str, total: int | None = None):
    """Report stage boundaries and elapsed time during opaque library calls."""
    started = perf_counter()
    stopped = Event()
    detail = f" | textos={total}" if total is not None else ""
    logger.info("INICIO | %s%s", name, detail)

    def heartbeat():
        while not stopped.wait(30):
            logger.info(
                "EN EJECUCIÓN | %s | tiempo=%.2fs", name, perf_counter() - started
            )

    worker = Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    except BaseException:
        logger.exception("ERROR | %s | tiempo=%.2fs", name, perf_counter() - started)
        raise
    else:
        logger.info("FIN | %s | tiempo=%.2fs", name, perf_counter() - started)
    finally:
        stopped.set()
        worker.join()


def log_text_progress(name: str, completed: int, total: int, started: float):
    if completed % 500 == 0 or completed == total:
        logger.info(
            "PROGRESO | %s | %d/%d | tiempo=%.2fs",
            name, completed, total, perf_counter() - started,
        )
