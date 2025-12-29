# rehelp.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import platform
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from reupdater import ReProject, UpdateClient, UpdateResult, open_url_external


DEFAULT_CSS = """
body { font-family: sans-serif; line-height: 1.35; margin: 0; padding: 0; background: transparent; color: #e6e6e6; }
.wrap { padding: 10px 12px; }
h1 { font-size: 16px; margin: 0 0 10px 0; }
h2 { font-size: 13px; margin: 16px 0 6px 0; color: #cfd3da; }
p { margin: 6px 0; }
ul { margin: 6px 0 6px 18px; padding: 0; }
li { margin: 4px 0; }
code { font-family: monospace; background: #202025; padding: 1px 4px; border: 1px solid #3a3a42; border-radius: 3px; }
.kv { font-family: monospace; white-space: pre-wrap; background: #202025; border: 1px solid #3a3a42; border-radius: 4px; padding: 8px; margin: 8px 0; }
.muted { color: #b0b0b0; }
a { text-decoration: none; color: #8fb3ff; }
"""


@dataclass(frozen=True)
class HelpAction:
    label: str
    kind: str  # "url" | "callback"
    url: str = ""
    callback: Optional[Callable[[], None]] = None
    tooltip: str = ""


def diagnostics_text(project: ReProject) -> str:
    qt = "Qt"
    try:
        import PySide6  # noqa: F401
        qt = "Qt/PySide6"
    except Exception:
        pass

    return (
        f"App: {project.name or project.repo}\n"
        f"Version: {project.version}\n"
        f"Repo: {project.repo_url()}\n"
        f"Descriptor: {project.descriptor_url()}\n"
        f"Platform: {platform.platform()}\n"
        f"Python: {sys.version.splitlines()[0]}\n"
        f"UI: {qt}\n"
    )


def wrap_help_html(title: str, body_html: str, *, css: str = DEFAULT_CSS) -> str:
    t = title or "Help / About"
    b = body_html or ""
    return f"""<html>
<head><style>{css}</style></head>
<body>
  <div class="wrap">
    <h1>{t}</h1>
    {b}
  </div>
</body>
</html>"""


class HelpDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        project: ReProject,
        *,
        html: str,
        updater: Optional[UpdateClient] = None,
        extra_actions: Sequence[HelpAction] = (),
        title: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or f"{project.name or project.repo} — Help / About")
        self.setMinimumSize(860, 560)
        self.resize(900, 620)

        self._project = project
        self._updater = updater or UpdateClient(self, project)
        self._updater.checked.connect(self._on_update_result)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        name_lbl = QLabel(project.name or project.repo)
        name_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        ver_lbl = QLabel(f"v{project.version}")
        ver_lbl.setStyleSheet("color: #b0b0b0;")

        header.addWidget(name_lbl)
        header.addWidget(ver_lbl)
        header.addStretch(1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #b0b0b0;")
        header.addWidget(self._status)

        outer.addLayout(header)

        self._text = QTextBrowser()
        self._text.setOpenExternalLinks(False)
        self._text.setOpenLinks(False)
        self._text.anchorClicked.connect(self._on_anchor_clicked)
        self._text.setHtml(html)
        outer.addWidget(self._text, 1)

        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(8)

        self._btn_updates = QPushButton("Check updates")
        self._btn_updates.clicked.connect(self._check_updates)

        self._btn_releases = QPushButton("Releases")
        self._btn_releases.clicked.connect(lambda: open_url_external(project.releases_url()))

        self._btn_issues = QPushButton("Report bug")
        self._btn_issues.clicked.connect(lambda: open_url_external(project.issues_url()))

        self._btn_repo = QPushButton("Repository")
        self._btn_repo.clicked.connect(lambda: open_url_external(project.repo_url()))

        self._btn_copy = QPushButton("Copy diagnostics")
        self._btn_copy.clicked.connect(self._copy_diagnostics)

        btns.addWidget(self._btn_updates)
        btns.addSpacing(6)
        btns.addWidget(self._btn_releases)
        btns.addWidget(self._btn_issues)
        btns.addWidget(self._btn_repo)
        btns.addSpacing(6)
        btns.addWidget(self._btn_copy)

        for a in extra_actions:
            b = QPushButton(a.label)
            if a.tooltip:
                b.setToolTip(a.tooltip)
            if a.kind == "url":
                u = a.url
                b.clicked.connect(lambda _=False, uu=u: open_url_external(uu))
            else:
                cb = a.callback
                b.clicked.connect(lambda _=False, c=cb: c() if c else None)
            btns.addWidget(b)

        btns.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btns.addWidget(close_btn)

        outer.addLayout(btns)

    def set_html(self, html: str) -> None:
        self._text.setHtml(html)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        try:
            open_url_external(url.toString())
        except Exception:
            pass

    def _copy_diagnostics(self) -> None:
        try:
            QGuiApplication.clipboard().setText(diagnostics_text(self._project))
            self._status.setText("Diagnostics copied.")
        except Exception:
            self._status.setText("Failed to copy diagnostics.")

    def _check_updates(self) -> None:
        self._status.setText("Checking for updates…")
        self._updater.check_now(ignore_skip=True, show_dialog=True)

    def _on_update_result(self, res: UpdateResult) -> None:
        if res.status == "no_update":
            self._status.setText("No updates available.")
        elif res.status == "update_available":
            self._status.setText(f"Update available: {res.latest.version if res.latest else ''}".strip())
        elif res.status == "deprecated":
            self._status.setText("Update required (deprecated).")
        elif res.status == "no_entry":
            self._status.setText("No update entry for this OS.")
        else:
            self._status.setText("Update check failed.")
