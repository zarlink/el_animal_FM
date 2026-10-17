from __future__ import annotations

import argparse
import os
from pathlib import Path

from el_animal_fm.news.application.dictionary.dictionary_config import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_RECORD_WORKERS,
    RECORD_CHUNKSIZE,
    RECORD_LOG_EVERY,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea candidatos de diccionario desde noticias unificadas."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_PATH,
        help="Archivo de noticias unificadas. Default: noticias_unificadas.txt.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Archivo JSON de salida. Default: candidatos_diccionario.json.",
    )
    parser.add_argument(
        "--record-workers",
        type=int,
        default=DEFAULT_RECORD_WORKERS,
        help=f"Workers para procesar registros. Default: {DEFAULT_RECORD_WORKERS}.",
    )
    parser.add_argument(
        "--record-log-every",
        type=int,
        default=RECORD_LOG_EVERY,
        help=f"Frecuencia de log de registros. Default: {RECORD_LOG_EVERY}.",
    )
    parser.add_argument(
        "--record-chunksize",
        type=int,
        default=RECORD_CHUNKSIZE,
        help=f"Chunksize para multiprocessing. Default: {RECORD_CHUNKSIZE}.",
    )
    parser.add_argument("--yake-workers", type=int, default=max(1, min(os.cpu_count() or 1, 6)),
                        help="Procesos para YAKE (default: hasta 6). Use 1 para ejecución secuencial.")
    parser.add_argument("--yake-chunksize", type=int, default=25,
                        help="Textos por bloque de trabajo YAKE (default: 25).")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="Directorio de caché (default: .dictionary_cache junto al archivo de salida).")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ejecutar sin leer ni escribir resultados intermedios.")
    args = parser.parse_args()
    if min(args.record_workers, args.record_log_every, args.record_chunksize,
           args.yake_workers, args.yake_chunksize) < 1:
        parser.error("Workers, chunksizes y frecuencia de logs deben ser positivos")

    from el_animal_fm.news.application.dictionary.create_dictionary_candidates import (
        create_dictionary_candidates,
    )

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    print("=== Creador de candidatos de diccionario ===")
    print(f"Entrada: {input_path}")
    print(f"Salida: {output_path}")
    print(f"Workers: {args.record_workers}")
    print(f"YAKE workers: {args.yake_workers}")
    print(f"Caché: {'desactivada' if args.no_cache else (args.cache_dir or output_path.parent / '.dictionary_cache')}")
    print()

    report = create_dictionary_candidates(
        input_path,
        output_path,
        record_workers=args.record_workers,
        record_log_every=args.record_log_every,
        record_chunksize=args.record_chunksize,
        yake_workers=args.yake_workers,
        yake_chunksize=args.yake_chunksize,
        cache_dir=args.cache_dir,
        use_cache=not args.no_cache,
    )

    print()
    print("=== Proceso terminado ===")
    print(f"Artículos totales: {report['metadata']['articles_total']}")
    print(f"Textos usados: {report['metadata']['texts_general_count']}")
    print(f"Archivo generado: {output_path}")


if __name__ == "__main__":
    main()
