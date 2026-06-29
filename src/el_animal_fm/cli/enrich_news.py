from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from el_animal_fm.news.application.enrich_news_files import (
    discover_news_files,
    enrich_files_parallel,
)
from el_animal_fm.news.application.enrichment_config import (
    DEFAULT_CANDIDATES_FILE,
    DEFAULT_DICTIONARY_DIR,
    DEFAULT_DICTIONARY_VERSION,
    DEFAULT_INPUT_NAME,
    DEFAULT_OUTPUT_NAME,
    DEFAULT_SOURCES,
    FAMILIES,
)
from el_animal_fm.news.application.enrichment_dictionaries import (
    compile_dictionaries,
    deduplicate_dictionaries,
    load_candidates_file,
    load_dictionary_files,
)
from el_animal_fm.news.infrastructure.dates import build_date_range, parse_target_date


def build_allowed_dates(args: argparse.Namespace) -> set | None:
    if args.date_from or args.date_to:
        if not args.date_from or not args.date_to:
            raise ValueError("Debes usar --date-from y --date-to juntos.")
        start = parse_target_date(args.date_from)
        end = parse_target_date(args.date_to)
        if start > end:
            raise ValueError("--date-from no puede ser posterior a --date-to.")
        return {start + timedelta(days=i) for i in range((end - start).days + 1)}

    if args.days_back is not None:
        end = parse_target_date(args.date)
        return set(build_date_range(end, args.days_back))

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquece noticias descargadas con features derivados de diccionarios."
    )
    parser.add_argument("--base-dir", default=".", help="Directorio base del proyecto.")
    parser.add_argument("--dictionary-dir", default=DEFAULT_DICTIONARY_DIR, help="Carpeta con diccionarios.")
    parser.add_argument("--candidates-file", default=DEFAULT_CANDIDATES_FILE, help="Archivo candidatos_diccionario.json.")
    parser.add_argument("--dictionary-version", default=DEFAULT_DICTIONARY_VERSION, help="Versión del diccionario.")
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME, help="Nombre del archivo diario de entrada.")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME, help="Nombre del archivo diario enriquecido.")
    parser.add_argument("--sources", nargs="+", default=list(DEFAULT_SOURCES), help="Fuentes a procesar: biobio mostrador.")
    parser.add_argument("--workers", type=int, default=4, help="Cantidad de archivos diarios a enriquecer en paralelo.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe archivos enriquecidos existentes.")
    parser.add_argument("--no-candidates", action="store_true", help="No usar candidatos_diccionario.json como apoyo.")
    parser.add_argument("--candidate-top-limit", type=int, default=150, help="Máximo de candidatos a importar por familia.")
    parser.add_argument("--candidate-max-df-pct", type=float, default=0.12, help="DF máximo permitido para candidatos.")
    parser.add_argument("--date", default=None, help="Fecha final. Formatos: DD_MM_YYYY, DD-MM-YYYY o YYYY-MM-DD.")
    parser.add_argument("--days-back", type=int, default=None, help="Cantidad de días hacia atrás incluyendo fecha final.")
    parser.add_argument("--date-from", default=None, help="Fecha inicial opcional.")
    parser.add_argument("--date-to", default=None, help="Fecha final opcional.")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    dictionary_dir = (base_dir / args.dictionary_dir).resolve()
    candidates_path = (base_dir / args.candidates_file).resolve()

    dictionaries = load_dictionary_files(dictionary_dir)
    if not args.no_candidates:
        load_candidates_file(
            candidates_path,
            dictionaries,
            args.candidate_top_limit,
            args.candidate_max_df_pct,
        )
    dictionaries = deduplicate_dictionaries(dictionaries)
    compiled = compile_dictionaries(dictionaries)

    print("=== Diccionarios cargados ===")
    for family in FAMILIES:
        print(f"  {family}: {len(compiled.get(family, []))} términos")

    allowed_dates = build_allowed_dates(args)
    files = discover_news_files(base_dir, args.sources, allowed_dates, args.input_name)

    print()
    print("=== Archivos encontrados ===")
    print(f"Total: {len(files)}")
    for path in files[:10]:
        print(f"  {path}")
    if len(files) > 10:
        print(f"  ... y {len(files) - 10} más")

    summaries = enrich_files_parallel(
        files,
        compiled,
        args.dictionary_version,
        args.output_name,
        args.overwrite,
        args.workers,
    )

    summary_dir = base_dir / "features_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = summary_dir / f"resumen_enriquecimiento_{timestamp}.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    enriched = sum(1 for item in summaries if item.get("status") == "enriched")
    skipped = sum(1 for item in summaries if item.get("status") == "skipped_existing_output")
    errors = sum(1 for item in summaries if item.get("status") == "error")

    print()
    print("=" * 70)
    print("PROCESO DE ENRIQUECIMIENTO TERMINADO")
    print(f"Archivos enriquecidos: {enriched}")
    print(f"Archivos omitidos: {skipped}")
    print(f"Errores: {errors}")
    print(f"Resumen guardado en: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
