from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from el_animal_fm.news.application.download.downloader import (  # noqa: E402
    DownloadOptions,
    run_download,
)
from el_animal_fm.news.application.download.source_adapter import (  # noqa: E402
    NewsSourceAdapter,
)
from el_animal_fm.news.sources.biobio.adapter import (  # noqa: E402
    create_adapter as create_biobio_adapter,
)
from el_animal_fm.news.sources.mostrador.adapter import (  # noqa: E402
    create_adapter as create_mostrador_adapter,
)


CHILE_TZ = ZoneInfo("America/Santiago")
AUTOMATION_DIR = PROJECT_ROOT / "automation"
DEFAULT_STATE_PATH = AUTOMATION_DIR / "news_download_state.json"
DEFAULT_LOCK_PATH = AUTOMATION_DIR / "news_download.lock"

SOURCE_FACTORIES: tuple[tuple[str, Callable[[], NewsSourceAdapter]], ...] = (
    ("biobio", create_biobio_adapter),
    ("mostrador", create_mostrador_adapter),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coordina la descarga incremental de BioBio y El Mostrador.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los rangos calculados sin descargar ni modificar el estado.",
    )
    parser.add_argument(
        "--initial-days",
        type=int,
        default=3,
        help="Días a revisar cuando una fuente aún no tiene estado (predeterminado: 3).",
    )
    parser.add_argument(
        "--max-recovery-days",
        type=int,
        default=30,
        help="Máximo de días que se recuperan automáticamente (predeterminado: 30).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Ruta del archivo JSON de estado.",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=DEFAULT_LOCK_PATH,
        help="Ruta del archivo usado para impedir ejecuciones simultáneas.",
    )
    return parser


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudo leer el estado {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"El estado {path} debe contener un objeto JSON.")
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def calculate_days_count(
    source_state: Any,
    today: date,
    initial_days: int,
    max_recovery_days: int,
) -> tuple[int, date | None]:
    last_successful_date: date | None = None
    if isinstance(source_state, dict) and source_state.get("last_successful_date"):
        try:
            last_successful_date = date.fromisoformat(source_state["last_successful_date"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("last_successful_date no contiene una fecha ISO válida.") from exc

    if last_successful_date is None:
        days_count = initial_days
    else:
        elapsed_days = (today - last_successful_date).days
        if elapsed_days < 0:
            raise RuntimeError(
                f"La última fecha exitosa ({last_successful_date}) está en el futuro."
            )
        days_count = max(2, elapsed_days)

    if days_count > max_recovery_days:
        raise RuntimeError(
            f"El rango calculado ({days_count} días) supera el límite automático "
            f"de {max_recovery_days} días."
        )
    return days_count, last_successful_date


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Ya hay otra descarga automática en ejecución.") from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def source_finished_successfully(summary: list[dict[str, Any]]) -> bool:
    return bool(summary) and all(item.get("status") != "error" for item in summary)


def run_source(adapter: NewsSourceAdapter, today: date, days_count: int) -> list[dict[str, Any]]:
    options = DownloadOptions(
        end_date=today,
        days_count=days_count,
        base_dir=PROJECT_ROOT,
    )
    return run_download(adapter, options)


def coordinate(args: argparse.Namespace) -> int:
    if args.initial_days < 1:
        raise RuntimeError("--initial-days debe ser mayor o igual a 1.")
    if args.max_recovery_days < 2:
        raise RuntimeError("--max-recovery-days debe ser mayor o igual a 2.")
    if args.initial_days > args.max_recovery_days:
        raise RuntimeError("--initial-days no puede superar --max-recovery-days.")

    now = datetime.now(CHILE_TZ)
    today = now.date()
    state_path = args.state_file.expanduser().resolve()
    state = load_state(state_path)
    failures = 0

    print(f"Fecha y hora en Chile: {now.isoformat()}")
    print(f"Archivo de estado: {state_path}")

    for source_name, adapter_factory in SOURCE_FACTORIES:
        try:
            days_count, last_successful = calculate_days_count(
                state.get(source_name),
                today,
                args.initial_days,
                args.max_recovery_days,
            )
            first_date = today.fromordinal(today.toordinal() - days_count + 1)
            print(
                f"[{source_name}] última fecha exitosa: "
                f"{last_successful or 'sin estado'}; rango: {first_date} a {today} "
                f"({days_count} días)."
            )

            if args.dry_run:
                continue

            summary = run_source(adapter_factory(), today, days_count)
            if not source_finished_successfully(summary):
                raise RuntimeError("El resumen contiene uno o más días con error.")

            state[source_name] = {
                "last_successful_date": today.isoformat(),
                "last_run_at": datetime.now(CHILE_TZ).isoformat(),
            }
            save_state(state_path, state)
            print(f"[{source_name}] descarga finalizada y estado actualizado.")
        except Exception as exc:
            failures += 1
            print(f"[{source_name}] ERROR: {exc}", file=sys.stderr)

    if args.dry_run:
        print("Modo dry-run: no se realizaron descargas ni se modificó el estado.")
    return 1 if failures else 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        with exclusive_lock(args.lock_file.expanduser().resolve()):
            return coordinate(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
