# patchbay_settings_dialog.py
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QFileDialog,
)

from reupdater import open_url_external
from store_config import ConfigStore, find_resink_executable_path


RESINK_REPO_URL = "https://github.com/Retzilience/reSink"


class PatchbaySettingsDialog(QDialog):
    """
    I store patchbay preferences only.
    I keep reSink separate: I show whether it is detected, and I offer a download link.
    """

    def __init__(self, store: ConfigStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Patchbay Settings")
        self.setMinimumSize(560, 260)

        self.store = store
        self.cfg = self.store.load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        outer.addLayout(form)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        self.rb_qpw = QRadioButton("qpwgraph (patchbay)")
        self.rb_helvum = QRadioButton("helvum (patchbay)")
        self.rb_custom = QRadioButton("custom")

        self.group.addButton(self.rb_qpw)
        self.group.addButton(self.rb_helvum)
        self.group.addButton(self.rb_custom)

        self.rb_qpw.setEnabled(shutil.which("qpwgraph") is not None)
        if not self.rb_qpw.isEnabled():
            self.rb_qpw.setToolTip("qpwgraph not found in PATH.")

        self.rb_helvum.setEnabled(shutil.which("helvum") is not None)
        if not self.rb_helvum.isEnabled():
            self.rb_helvum.setToolTip("helvum not found in PATH.")

        form.addRow(QLabel("Preferred patchbay:"), QLabel(""))
        form.addRow(self.rb_qpw)
        form.addRow(self.rb_helvum)
        form.addRow(self.rb_custom)

        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("/path/to/patchbay")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_custom)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        custom_row.addWidget(self.custom_edit, 1)
        custom_row.addWidget(browse_btn, 0)

        form.addRow("Custom path:", custom_row)

        form.addRow(QLabel("reSink:"), QLabel(""))
        self.resink_status = QLabel("")
        self.resink_status.setWordWrap(True)

        self.resink_btn = QPushButton("Download reSink")
        self.resink_btn.clicked.connect(lambda: open_url_external(RESINK_REPO_URL))

        resink_row = QHBoxLayout()
        resink_row.setSpacing(8)
        resink_row.addWidget(self.resink_status, 1)
        resink_row.addWidget(self.resink_btn, 0)

        form.addRow(resink_row)

        self._resink_path = find_resink_executable_path()
        if self._resink_path and Path(self._resink_path).exists():
            self.resink_status.setText(f"Detected (from reSink config): {self._resink_path}")
            self.resink_btn.setText("Open reSink repo")
        else:
            self.resink_status.setText(
                "Not detected. You either do not have it installed, or you need to run it at least once "
                "so it writes its config."
            )
            self.resink_btn.setText("Download reSink")

        selected = (self.cfg.get("Patchbay", "selected_app", fallback="") or "").strip().lower()
        custom_path = (self.cfg.get("Patchbay", "custom_path", fallback="") or "").strip()
        if custom_path:
            self.custom_edit.setText(custom_path)

        if selected == "qpwgraph" and self.rb_qpw.isEnabled():
            self.rb_qpw.setChecked(True)
        elif selected == "helvum" and self.rb_helvum.isEnabled():
            self.rb_helvum.setChecked(True)
        elif selected == "custom":
            self.rb_custom.setChecked(True)
        else:
            if self.rb_qpw.isEnabled():
                self.rb_qpw.setChecked(True)
            elif self.rb_helvum.isEnabled():
                self.rb_helvum.setChecked(True)
            else:
                self.rb_custom.setChecked(True)

        self.rb_custom.toggled.connect(self._sync_custom_enable)
        self.rb_qpw.toggled.connect(self._sync_custom_enable)
        self.rb_helvum.toggled.connect(self._sync_custom_enable)
        self._sync_custom_enable()

        btns = QHBoxLayout()
        btns.setSpacing(8)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btns.addStretch(1)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        outer.addLayout(btns)

    def _sync_custom_enable(self) -> None:
        self.custom_edit.setEnabled(self.rb_custom.isChecked())

    def _browse_custom(self) -> None:
        fp, _ = QFileDialog.getOpenFileName(self, "Select Patchbay Executable", "", "All Files (*)")
        if fp:
            self.custom_edit.setText(fp)

    def _save(self) -> None:
        if not self.cfg.has_section("Patchbay"):
            self.cfg.add_section("Patchbay")

        selected = ""
        if self.rb_qpw.isChecked():
            selected = "qpwgraph"
        elif self.rb_helvum.isChecked():
            selected = "helvum"
        elif self.rb_custom.isChecked():
            selected = "custom"

        if not selected:
            QMessageBox.warning(self, "No selection", "Select a patchbay option.")
            return

        custom_path = self.custom_edit.text().strip() if selected == "custom" else ""
        if selected == "custom":
            if not custom_path:
                QMessageBox.warning(self, "Invalid path", "Custom path cannot be empty.")
                return
            if not os.path.exists(custom_path):
                QMessageBox.warning(self, "Invalid path", "Custom path does not exist.")
                return

        self.cfg.set("Patchbay", "selected_app", selected)
        self.cfg.set("Patchbay", "custom_path", custom_path)

        self.store.save(self.cfg)
        self.accept()
