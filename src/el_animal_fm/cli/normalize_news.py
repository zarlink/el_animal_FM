from __future__ import annotations

import argparse
from pathlib import Path

from el_animal_fm.news.application.normalize_news_files import (
    DEFAULT_MEDIA_DIRS,
    process_media_dir,
)


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
