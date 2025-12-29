# main.py
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from theme import apply_dark_theme
from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
