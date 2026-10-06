from __future__ import annotations

import argparse
from pathlib import Path

from el_animal_fm.news.application.download.downloader import DownloadOptions, run_download
from el_animal_fm.news.infrastructure.dates import parse_target_date
from el_animal_fm.news.sources.biobio.adapter import create_adapter as create_biobio_adapter
from el_animal_fm.news.sources.mostrador.adapter import create_adapter as create_mostrador_adapter


SOURCE_FACTORIES = {
    "biobio": create_biobio_adapter,
    "mostrador": create_mostrador_adapter,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Descarga las fuentes seleccionadas por el gestor de noticias.")
    parser.add_argument("--sources", nargs="+", choices=tuple(SOURCE_FACTORIES), required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--days-back", type=int, required=True)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--overwrite-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.days_back < 1 or args.sleep < 0:
        parser.error("Los días deben ser positivos y la pausa no puede ser negativa.")

    end_date = parse_target_date(args.date)
    sources = list(dict.fromkeys(args.sources))
    failures = False
    for index, source in enumerate(sources, start=1):
        adapter = SOURCE_FACTORIES[source]()
        print(f"\n[INFO] [{index}/{len(sources)}] Iniciando {adapter.display_name}", flush=True)
        options = DownloadOptions(
            end_date=end_date,
            days_count=args.days_back,
            base_dir=args.base_dir.resolve(),
            sleep_seconds=args.sleep,
            max_category_pages=adapter.default_max_category_pages,
            # El modo secuencial respeta la pausa entre descargas.
            article_workers=1,
            overwrite_existing=args.overwrite_existing,
        )
        try:
            summary = run_download(adapter, options)
            has_errors = not summary or any(
                item.get("status") == "error" or item.get("parse_failed_new", 0) > 0
                for item in summary
            )
            failures |= has_errors
            status = "ERROR" if has_errors else "OK"
            print(f"[{status}] {adapter.display_name}: descarga finalizada.", flush=True)
        except Exception as exc:
            failures = True
            print(f"[ERROR] {adapter.display_name}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
