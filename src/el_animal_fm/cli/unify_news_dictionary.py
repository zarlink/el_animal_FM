from __future__ import annotations

import argparse
import json
from pathlib import Path

from el_animal_fm.news.application.shared.news_file_collection import DEFAULT_MEDIA_DIRS
from el_animal_fm.news.application.unification.news_unifier import unify_news


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unifica todos los archivos noticias_dia.txt de biobio y mostrador."
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
        "--output",
        default="noticias_unificadas.txt",
        help="Nombre del archivo de salida. Default: noticias_unificadas.txt.",
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_path = base_dir / args.output

    print("=== Unificador de noticias ===")
    print(f"Directorio base: {base_dir}")
    print(f"Medios: {', '.join(args.media)}")
    print(f"Salida: {output_path}")
    print()

    unified = unify_news(base_dir, args.media)

    output_path.write_text(
        json.dumps(unified, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== Proceso terminado ===")
    print(f"Archivos procesados: {unified['metadata']['files_processed']}")
    print(f"Noticias unificadas: {unified['metadata']['articles_unified']}")
    print(f"Archivo generado: {output_path}")


if __name__ == "__main__":
    main()
