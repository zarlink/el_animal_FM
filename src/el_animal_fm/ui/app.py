from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from el_animal_fm.ui.main_window import MainWindow


def main() -> None:
    """Run the desktop dashboard application."""
    app = QApplication(sys.argv)
    app.setApplicationName("El Animal FM Dashboard")

    window = MainWindow()
    window.show()

    raise SystemExit(app.exec())
