from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests

from el_animal_fm.news.application.download.source_adapter import NewsSourceAdapter
from el_animal_fm.news.domain.models import DiscoveredUrl
from el_animal_fm.news.infrastructure import storage as common_storage
from el_animal_fm.news.infrastructure.dates import (
    build_date_range,
    date_dir_name,
    parse_target_date,
)
from el_animal_fm.news.infrastructure.http_client import create_session


@dataclass(frozen=True)
class DownloadOptions:
    end_date: date
    days_count: int
    base_dir: Path
    max_articles: int = 0
    sleep_seconds: float = 0.5
    max_category_pages: int = 30
    article_workers: int = 8
    overwrite_existing: bool = False


def ask_days_back(adapter: NewsSourceAdapter) -> int:
    while True:
        raw = input(
            "¿Cuántos días quieres descargar hacia atrás, incluyendo la fecha final? "
            f"Ejemplo {adapter.days_back_example} = fecha final + "
            f"{adapter.days_back_example - 1} días anteriores: "
        ).strip()

        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass

        print("Ingresa un número entero mayor o igual a 1.")


def build_parser(adapter: NewsSourceAdapter) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            f"Descarga/actualiza noticias de {adapter.display_name} por rango de días, "
            "agregando solo URLs nuevas si el archivo diario ya existe."
        )
    )

    parser.add_argument(
        "--date",
        default=None,
        help=(
            "Fecha final del rango. Formatos aceptados: DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD. "
            "Si se omite, usa hoy en Chile."
        ),
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help=(
            "Cantidad de días totales a descargar hacia atrás, incluyendo la fecha final. "
            f"Ejemplo: {adapter.days_back_example} = fecha final + "
            f"{adapter.days_back_example - 1} días anteriores. Si se omite, se pregunta por consola."
        ),
    )
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directorio base del proyecto. Por defecto, carpeta actual.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=0,
        help="Límite de noticias por día para prueba. 0 = sin límite.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=adapter.default_sleep_seconds,
        help="Pausa en segundos entre descargas.",
    )
    parser.add_argument(
        "--max-category-pages",
        type=int,
        default=adapter.default_max_category_pages,
        help="Número máximo de páginas/listados a revisar durante el descubrimiento.",
    )
    parser.add_argument(
        "--article-workers",
        type=int,
        default=8,
        help="Número de noticias a descargar en paralelo por día. Usa 1 para modo secuencial.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help=(
            "Si se indica, ignora el noticias_dia.txt existente y redescarga todas las URLs detectadas. "
            "Por defecto, si el archivo existe, conserva sus noticias y agrega solo URLs nuevas."
        ),
    )

    return parser


def parse_options(adapter: NewsSourceAdapter, argv: list[str] | None = None) -> DownloadOptions:
    parser = build_parser(adapter)
    args = parser.parse_args(argv)

    end_date = parse_target_date(args.date)
    days_count = args.days_back if args.days_back is not None else ask_days_back(adapter)

    if days_count < 1:
        raise ValueError("--days-back debe ser mayor o igual a 1.")

    return DownloadOptions(
        end_date=end_date,
        days_count=days_count,
        base_dir=Path(args.base_dir).resolve(),
        max_articles=args.max_articles,
        sleep_seconds=args.sleep,
        max_category_pages=args.max_category_pages,
        article_workers=args.article_workers,
        overwrite_existing=args.overwrite_existing,
    )


def _discover_for_day(
    adapter: NewsSourceAdapter,
    session: requests.Session,
    target: date,
    options: DownloadOptions,
    preloaded: dict[str, DiscoveredUrl] | None,
) -> dict[str, DiscoveredUrl]:
    kwargs: dict[str, Any] = {
        "session": session,
        "target": target,
        "max_category_pages": options.max_category_pages,
    }

    if preloaded is not None:
        kwargs["preloaded_categoria"] = preloaded

    return adapter.discover_article_urls(**kwargs)


def scrape_single_day(
    adapter: NewsSourceAdapter,
    session: requests.Session,
    target: date,
    options: DownloadOptions,
    preloaded: dict[str, DiscoveredUrl] | None = None,
) -> dict[str, Any]:
    day_dir = common_storage.get_day_dir(options.base_dir, adapter.source_folder, target)
    raw_html_dir = day_dir / "html"
    output_path = common_storage.get_day_output_path(options.base_dir, adapter.source_folder, target)

    day_dir.mkdir(parents=True, exist_ok=True)
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    _, existing_articles, existing_urls = common_storage.load_existing_day_payload(
        output_path,
        normalize_url=adapter.normalize_url,
    )

    if options.overwrite_existing:
        print("[INFO] overwrite_existing=True: se ignorará el archivo previo y se redescargarán las noticias detectadas.")
        existing_articles = []
        existing_urls = set()

    print("\n" + "=" * 70)
    print(f"Scraping {adapter.display_name} para fecha: {target.isoformat()}")
    print(f"Carpeta destino: {day_dir}")
    print(f"Archivo salida: {output_path}")
    print("=" * 70)

    discoveries = _discover_for_day(adapter, session, target, options, preloaded)
    urls_detected = list(discoveries.keys())

    if options.max_articles and options.max_articles > 0:
        urls_detected = urls_detected[: options.max_articles]

    urls = [
        url for url in urls_detected
        if adapter.normalize_url(url) not in existing_urls
    ]

    print()
    print(f"Total de noticias detectadas para el día: {len(discoveries)}")
    print(f"Noticias existentes en archivo del día: {len(existing_articles)}")
    print(f"URLs existentes únicas: {len(existing_urls)}")
    print(f"Noticias nuevas por descargar: {len(urls)}")

    if options.max_articles and options.max_articles > 0:
        print(f"Modo prueba activo: universo limitado a {len(urls_detected)} URLs detectadas.")

    print()

    articles: list[dict[str, Any] | None] = [None] * len(urls)

    def worker(index: int, url: str) -> tuple[int, dict[str, Any]]:
        local_session = create_session()
        article = adapter.extract_article(local_session, discoveries[url], raw_html_dir)
        return index, article

    if options.article_workers <= 1:
        for index, url in enumerate(urls):
            print(f"[{index + 1}/{len(urls)}] Descargando: {url}")

            try:
                _, article = worker(index, url)
                articles[index] = article
            except Exception as exc:
                print(f"[{index + 1}/{len(urls)}] ERROR: {url} | {exc}")
                articles[index] = adapter.build_error_article(discoveries[url], exc)

            if options.sleep_seconds > 0:
                time.sleep(options.sleep_seconds)
    else:
        print(f"Descargando noticias en paralelo con {options.article_workers} workers...")

        with ThreadPoolExecutor(max_workers=options.article_workers) as executor:
            futures = {
                executor.submit(worker, index, url): (index, url)
                for index, url in enumerate(urls)
            }

            for completed, future in enumerate(as_completed(futures), start=1):
                index, url = futures[future]

                try:
                    result_index, article = future.result()
                    articles[result_index] = article
                    print(f"[{completed}/{len(urls)}] OK: {url}")
                except Exception as exc:
                    print(f"[{completed}/{len(urls)}] ERROR: {url} | {exc}")
                    articles[index] = adapter.build_error_article(discoveries[url], exc)

    new_articles = [article for article in articles if article is not None]
    combined_articles = common_storage.deduplicate_articles_by_url(
        existing_articles + new_articles,
        normalize_url=adapter.normalize_url,
    )

    if new_articles or options.overwrite_existing or not output_path.exists():
        common_storage.write_output(
            output_path=output_path,
            target=target,
            discovered_count=len(discoveries),
            articles=combined_articles,
            source=adapter.source_name,
            parser_version=adapter.parser_version,
            payload_normalizer=adapter.payload_normalizer,
        )
        output_written = True
    else:
        output_written = False

    successful_total = sum(
        1 for article in combined_articles
        if article.get("technical", {}).get("parse_success")
    )
    failed_total = len(combined_articles) - successful_total
    successful_new = sum(
        1 for article in new_articles
        if article.get("technical", {}).get("parse_success")
    )
    failed_new = len(new_articles) - successful_new

    print()
    print("Resumen del día:")
    print(f"  Noticias detectadas: {len(discoveries)}")
    print(f"  Noticias existentes antes de ejecutar: {len(existing_articles)}")
    print(f"  Noticias nuevas descargadas: {len(new_articles)}")
    print(f"  Noticias totales guardadas sin duplicados: {len(combined_articles)}")
    print(f"  Nuevas parseadas sin observaciones: {successful_new}")
    print(f"  Nuevas con observaciones o errores: {failed_new}")
    print(f"  Total parseadas sin observaciones: {successful_total}")
    print(f"  Total con observaciones o errores: {failed_total}")
    print(f"  Archivo guardado en: {output_path}")
    print(f"  Archivo actualizado: {output_written}")

    return {
        "target_date": target.isoformat(),
        "articles_found": len(discoveries),
        "articles_existing_before": len(existing_articles),
        "articles_new_downloaded": len(new_articles),
        "articles_total_after_merge": len(combined_articles),
        "parse_success_new": successful_new,
        "parse_failed_new": failed_new,
        "parse_success_total": successful_total,
        "parse_failed_total": failed_total,
        "output_path": str(output_path),
        "output_written": output_written,
    }


def run_download(adapter: NewsSourceAdapter, options: DownloadOptions) -> list[dict[str, Any]]:
    targets = build_date_range(options.end_date, options.days_count)
    session = create_session()

    print(f"=== Scraper {adapter.display_name} por rango de días ===")
    print(f"Fecha final: {options.end_date.isoformat()}")
    print(f"Días totales a descargar: {options.days_count}")
    print(f"Primera fecha a procesar: {targets[0].isoformat()}")
    print(f"Última fecha a procesar: {targets[-1].isoformat()}")
    print(f"Directorio base: {options.base_dir}")
    print(f"Sobrescribir archivo diario existente: {options.overwrite_existing}")

    existing_file_targets = [
        target for target in targets
        if common_storage.get_day_output_path(options.base_dir, adapter.source_folder, target).exists()
    ]

    print(f"Días con noticias_dia.txt existente: {len(existing_file_targets)}")
    print("Modo incremental por URL: no se omiten carpetas existentes; se agregan solo noticias nuevas.")

    if adapter.preload_range and targets:
        print()
        print(f"Precargando listados compartidos para el rango completo ({len(targets)} días a revisar)...")
        preloaded_by_date = adapter.preload_range(session, targets, options.max_category_pages)
    else:
        preloaded_by_date = {}

    global_summary: list[dict[str, Any]] = []

    for target in targets:
        try:
            summary = scrape_single_day(
                adapter=adapter,
                session=session,
                target=target,
                options=options,
                preloaded=preloaded_by_date.get(target),
            )

            if summary.get("articles_new_downloaded", 0) > 0:
                summary["status"] = "updated_with_new_articles"
            elif summary.get("output_written"):
                summary["status"] = "written_without_new_articles"
            else:
                summary["status"] = "no_new_articles"

            global_summary.append(summary)
        except Exception as exc:
            print(f"[ERROR] Falló la descarga del día {target.isoformat()}: {exc}")
            global_summary.append(
                {
                    "target_date": target.isoformat(),
                    "status": "error",
                    "error": str(exc),
                }
            )

    summary_dir = options.base_dir / adapter.source_folder
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"resumen_descarga_{date_dir_name(options.end_date)}_{options.days_count}_dias.txt"
    summary_path.write_text(
        json.dumps(adapter.payload_normalizer(global_summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    updated_days = sum(1 for item in global_summary if item.get("status") == "updated_with_new_articles")
    no_new_days = sum(1 for item in global_summary if item.get("status") == "no_new_articles")
    written_days = sum(1 for item in global_summary if item.get("status") == "written_without_new_articles")
    error_days = sum(1 for item in global_summary if item.get("status") == "error")
    total_new_articles = sum(int(item.get("articles_new_downloaded", 0)) for item in global_summary)
    total_after_merge = sum(int(item.get("articles_total_after_merge", 0)) for item in global_summary)

    print("\n" + "=" * 70)
    print("PROCESO GENERAL TERMINADO")
    print(f"Días en rango: {len(global_summary)}")
    print(f"Días actualizados con noticias nuevas: {updated_days}")
    print(f"Días sin noticias nuevas: {no_new_days}")
    print(f"Días escritos sin noticias nuevas: {written_days}")
    print(f"Días con error: {error_days}")
    print(f"Noticias nuevas descargadas en total: {total_new_articles}")
    print(f"Noticias totales acumuladas en archivos procesados: {total_after_merge}")
    print(f"Resumen general guardado en: {summary_path}")
    print("=" * 70)

    return global_summary


def run_cli(adapter: NewsSourceAdapter, argv: list[str] | None = None) -> list[dict[str, Any]]:
    options = parse_options(adapter, argv)
    return run_download(adapter, options)

