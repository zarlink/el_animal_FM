from __future__ import annotations

import argparse
import json
from pathlib import Path

from el_animal_fm.news.application.normalization.normalize_news_files import (
    DEFAULT_MEDIA_DIRS,
    process_file,
)
from el_animal_fm.news.application.shared.news_file_collection import DEFAULT_NEWS_FILE_NAMES, find_news_files


def main(argv: list[str] | None = None) -> int:
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

    parser.add_argument("--input-name", default=None, help="Nombre del archivo diario de entrada.")
    parser.add_argument("--output-name", default=None, help="Nombre del archivo alternativo de salida.")
    parser.add_argument("--progress-json", action="store_true", help="Emite contadores de archivos para la interfaz.")
    args = parser.parse_args(argv)
    for name in (args.input_name, args.output_name):
        if name is not None and (not name.strip() or Path(name).name != name or name in {".", ".."}):
            parser.error("Los archivos de entrada y salida deben ser nombres sin directorios.")
    if args.no_overwrite and args.input_name and args.input_name == args.output_name:
        parser.error("El archivo alternativo de salida debe ser distinto del archivo de entrada.")

    base_dir = Path(args.base_dir).resolve()
    overwrite = not args.no_overwrite

    print("=== Normalizador de noticias ===")
    print(f"Directorio base: {base_dir}")
    print(f"Sobrescribir archivos: {overwrite}")
    print()

    file_names = (args.input_name,) if args.input_name else DEFAULT_NEWS_FILE_NAMES
    files = find_news_files(base_dir, args.media, file_names=file_names)
    global_total = len(files)
    global_ok = 0
    print(f"Archivos encontrados: {global_total}")

    def report(processed: int) -> None:
        if args.progress_json:
            counters = {"total": global_total, "processed": processed, "normalized": global_ok, "errors": processed - global_ok}
            print("[NORMALIZATION_PROGRESS] " + json.dumps(counters), flush=True)

    report(0)
    for processed, path in enumerate(files, start=1):
        global_ok += process_file(path, overwrite=overwrite, output_name=args.output_name)
        report(processed)

    print("\n=== Proceso terminado ===")
    print(f"Archivos reparados: {global_ok}/{global_total}")
    if not files:
        print("[WARN] No hay archivos para normalizar con las opciones seleccionadas.")
    return 1 if global_ok < global_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
