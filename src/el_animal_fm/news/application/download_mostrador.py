from __future__ import annotations

from el_animal_fm.news.application.downloader import run_cli
from el_animal_fm.news.sources.mostrador.adapter import create_adapter


def run() -> None:
    run_cli(create_adapter())
