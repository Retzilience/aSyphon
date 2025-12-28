# theme.py
from __future__ import annotations

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(20, 20, 22))
    pal.setColor(QPalette.WindowText, QColor(230, 230, 230))
    pal.setColor(QPalette.Base, QColor(14, 14, 16))
    pal.setColor(QPalette.AlternateBase, QColor(26, 26, 28))
    pal.setColor(QPalette.Text, QColor(230, 230, 230))
    pal.setColor(QPalette.Button, QColor(34, 34, 38))
    pal.setColor(QPalette.ButtonText, QColor(230, 230, 230))
    pal.setColor(QPalette.Highlight, QColor(80, 110, 170))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(140, 140, 140))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(140, 140, 140))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(140, 140, 140))
    app.setPalette(pal)

    app.setStyleSheet(
        """
        QMainWindow { background: #141416; }

        QLabel#Title {
            font-size: 16px;
            font-weight: 650;
        }

        QFrame#Panel {
            background: #1b1b1f;
            border: 1px solid #2a2a30;
            border-radius: 10px;
        }

        QWidget#RowCard {
            background: #1f1f24;
            border: 1px solid #2a2a30;
            border-radius: 10px;
        }

        QComboBox {
            padding: 6px 10px;
            border-radius: 8px;
            border: 1px solid #2a2a30;
            background: #121216;
        }

        QComboBox QAbstractItemView {
            background: #121216;
            border: 1px solid #2a2a30;
            selection-background-color: #506eaa;
        }

        QPushButton {
            padding: 6px 10px;
            border-radius: 10px;
            border: 1px solid #2a2a30;
            background: #232329;
        }
        QPushButton:hover { background: #2a2a33; }

        QPushButton#Primary {
            background: #2c3a5a;
            border: 1px solid #3b4f7a;
        }
        QPushButton#Primary:hover { background: #34456c; }

        /* Row remove button states */
        QPushButton#Remove {
            padding: 0px;
            border-radius: 10px;
            border: 1px solid #2a2a30;
            background: #232329;
        }
        QPushButton#Remove:hover { background: #2a2a33; }

        QPushButton#RemovePending {
            padding: 0px;
            border-radius: 10px;
            border: 1px solid #7a6231;
            background: #3a3424;
            color: #f3e6c8;
        }
        QPushButton#RemovePending:hover { background: #453f2c; }

        /* Hub destroy button */
        QPushButton#Danger {
            background: #3a2424;
            border: 1px solid #7a3131;
        }
        QPushButton#Danger:hover { background: #442b2b; }

        /* Unified pending action button (hub create/destroy pending) */
        QPushButton#PendingAction {
            background: #3a3424;
            border: 1px solid #7a6231;
            color: #f3e6c8;
        }
        QPushButton#PendingAction:hover { background: #453f2c; }
        """
    )
