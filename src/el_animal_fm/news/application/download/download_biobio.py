from __future__ import annotations

from el_animal_fm.news.application.download.downloader import run_cli
from el_animal_fm.news.sources.biobio.adapter import create_adapter


def run() -> None:
    run_cli(create_adapter())
