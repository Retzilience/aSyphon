# reupdater.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import re
import sys
import time
import urllib.parse
import webbrowser

from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal, QSettings
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QWidget


@dataclass(frozen=True)
class ReProject:
    owner: str
    repo: str
    version: str
    name: Optional[str] = None

    branch: str = "main"
    descriptor_path: str = "version.upd"

    settings_org: Optional[str] = None
    settings_app: Optional[str] = None

    def repo_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"

    def releases_url(self) -> str:
        return f"{self.repo_url()}/releases/latest"

    def issues_url(self) -> str:
        return f"{self.repo_url()}/issues"

    def descriptor_url(self) -> str:
        # Matches your current live convention.
        return f"{self.repo_url()}/raw/refs/heads/{self.branch}/{self.descriptor_path}"

    def settings(self) -> QSettings:
        org = (self.settings_org or self.owner or "reupdater").strip()
        app = (self.settings_app or self.repo or "app").strip()
        return QSettings(org, app)


@dataclass(frozen=True)
class UpdateEntry:
    version: str
    os_tag: str
    flags: Tuple[str, ...]
    download: str  # url (mode A) or spec (mode B)


@dataclass(frozen=True)
class UpdateResult:
    status: str  # "error" | "no_entry" | "no_update" | "update_available" | "deprecated"
    os_tag: str
    current_version: str
    latest: Optional[UpdateEntry]
    download_url: str
    message: str = ""


def detect_os_tag() -> str:
    sp = (sys.platform or "").lower()
    if sp.startswith("win"):
        return "windows"
    if sp.startswith("linux"):
        return "linux"
    if sp == "darwin":
        return "macos"
    return ""


def normalize_os_tag(tag: str) -> str:
    t = (tag or "").strip().lower()
    if t in ("darwin", "mac"):
        return "macos"
    return t


def _version_key(v: str) -> Tuple[int, ...]:
    s = (v or "").strip()
    if s.startswith(("v", "V")):
        s = s[1:]
    parts = [p for p in re.split(r"[.\-_+]", s) if p.strip() != ""]
    out = []
    for p in parts:
        m = re.match(r"^\d+$", p.strip())
        out.append(int(p) if m else 0)
    if not out:
        nums = re.findall(r"\d+", s)
        out = [int(x) for x in nums] if nums else [0]
    return tuple(out)


def compare_versions(a: str, b: str) -> int:
    ta = _version_key(a)
    tb = _version_key(b)
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    return -1 if ta < tb else (1 if ta > tb else 0)


def parse_descriptor(text: str, *, os_tag: str, current_version: str) -> Tuple[Optional[UpdateEntry], Optional[UpdateEntry]]:
    latest: Optional[UpdateEntry] = None
    current: Optional[UpdateEntry] = None

    want = normalize_os_tag(os_tag)
    cur = (current_version or "").strip()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        ver = parts[0]
        os_name = normalize_os_tag(parts[1])
        if not ver or os_name != want:
            continue

        if len(parts) == 3:
            flags: Tuple[str, ...] = ()
            dl = parts[2]
        else:
            flags = tuple(f.strip().lower() for f in re.split(r"[,\s]+", parts[2]) if f.strip())
            dl = parts[3] if len(parts) >= 4 else ""

        e = UpdateEntry(version=ver.strip(), os_tag=os_name, flags=flags, download=(dl or "").strip())

        if latest is None or compare_versions(e.version, latest.version) > 0:
            latest = e

        if compare_versions(e.version, cur) == 0:
            current = e

    return latest, current


def build_download_url(project: ReProject, entry: UpdateEntry) -> str:
    s = (entry.download or "").strip()
    if not s:
        return ""

    if re.match(r"^https?://", s, re.IGNORECASE):
        return s

    # Mode B (fallback): "tag/asset" or just "asset" (tag defaults to version).
    spec = s.lstrip("/")
    if "/" in spec:
        tag, asset = spec.split("/", 1)
        tag = tag.strip() or entry.version
        asset = asset.strip()
    else:
        tag, asset = entry.version, spec.strip()

    if not asset:
        return ""

    tag_q = urllib.parse.quote(tag, safe="")
    asset_q = urllib.parse.quote(asset, safe="")
    return f"{project.repo_url()}/releases/download/{tag_q}/{asset_q}"


def open_url_external(url: str) -> None:
    u = (url or "").strip()
    if not u:
        return
    q = QUrl(u)
    if q.isValid() and QDesktopServices.openUrl(q):
        return
    try:
        webbrowser.open(u)
    except Exception:
        pass


def get_skip_version(project: ReProject) -> str:
    try:
        s = project.settings()
        s.beginGroup("reupdater")
        v = str(s.value("skip_version", "") or "")
        s.endGroup()
        return v.strip()
    except Exception:
        return ""


def set_skip_version(project: ReProject, version: Optional[str]) -> None:
    try:
        s = project.settings()
        s.beginGroup("reupdater")
        s.setValue("skip_version", (version or "").strip())
        s.endGroup()
    except Exception:
        pass


def record_last_check(project: ReProject) -> None:
    try:
        s = project.settings()
        s.beginGroup("reupdater")
        s.setValue("last_check_unix", int(time.time()))
        s.endGroup()
    except Exception:
        pass


class UpdateClient(QObject):
    checked = Signal(object)  # UpdateResult

    def __init__(
        self,
        parent: QWidget,
        project: ReProject,
        *,
        os_tag: Optional[str] = None,
        descriptor_url: Optional[str] = None,
        get_skip: Optional[Callable[[], str]] = None,
        set_skip: Optional[Callable[[Optional[str]], None]] = None,
        record_check: Optional[Callable[[], None]] = None,
        http_timeout_ms: int = 8000,
    ) -> None:
        super().__init__(parent)

        self._parent = parent
        self._project = project
        self._os_tag = normalize_os_tag(os_tag or detect_os_tag())
        self._descriptor_url = (descriptor_url or project.descriptor_url()).strip()

        self._get_skip = get_skip or (lambda: get_skip_version(project))
        self._set_skip = set_skip or (lambda v: set_skip_version(project, v))
        self._record_check = record_check or (lambda: record_last_check(project))

        self._timeout_ms = int(max(1000, http_timeout_ms))

        self._mgr = QNetworkAccessManager(self)
        self._mgr.finished.connect(self._on_reply)

        self._in_flight = False
        self._ignore_skip = False
        self._show_dialog = False
        self._cb: Optional[Callable[[UpdateResult], None]] = None

    def check_startup(self) -> None:
        self.check_now(ignore_skip=False, show_dialog=True, callback=None)

    def check_now(
        self,
        *,
        ignore_skip: bool = False,
        show_dialog: bool = True,
        callback: Optional[Callable[[UpdateResult], None]] = None,
    ) -> None:
        if not self._os_tag or not self._descriptor_url:
            res = UpdateResult(
                status="error",
                os_tag=self._os_tag,
                current_version=str(self._project.version),
                latest=None,
                download_url="",
                message="Missing os_tag or descriptor_url.",
            )
            self._emit(res, callback)
            return

        if self._in_flight:
            res = UpdateResult(
                status="error",
                os_tag=self._os_tag,
                current_version=str(self._project.version),
                latest=None,
                download_url="",
                message="Update check already running.",
            )
            self._emit(res, callback)
            return

        self._in_flight = True
        self._ignore_skip = bool(ignore_skip)
        self._show_dialog = bool(show_dialog)
        self._cb = callback

        req = QNetworkRequest(QUrl(self._descriptor_url))
        try:
            req.setTransferTimeout(self._timeout_ms)  # Qt6
        except Exception:
            pass

        reply = self._mgr.get(req)

        timer = QTimer(self)
        timer.setSingleShot(True)

        def on_timeout() -> None:
            try:
                if reply.isRunning():
                    reply.abort()
            except Exception:
                pass

        def cleanup() -> None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass

        timer.timeout.connect(on_timeout)
        reply.finished.connect(cleanup)
        timer.start(self._timeout_ms)

    def _on_reply(self, reply: QNetworkReply) -> None:
        try:
            try:
                self._record_check()
            except Exception:
                pass

            if reply.error() != QNetworkReply.NetworkError.NoError:
                res = UpdateResult(
                    status="error",
                    os_tag=self._os_tag,
                    current_version=str(self._project.version),
                    latest=None,
                    download_url="",
                    message=reply.errorString(),
                )
                self._finish(res)
                return

            data = reply.readAll()
            try:
                text = bytes(data).decode("utf-8", errors="replace")
            except Exception:
                text = ""

            latest, current = parse_descriptor(text, os_tag=self._os_tag, current_version=str(self._project.version))
            if latest is None:
                res = UpdateResult(
                    status="no_entry",
                    os_tag=self._os_tag,
                    current_version=str(self._project.version),
                    latest=None,
                    download_url="",
                    message="No entry for this OS in descriptor.",
                )
                self._finish(res)
                return

            dl_url = build_download_url(self._project, latest)

            cur_deprecated = bool(current and any(f == "deprecated" for f in current.flags))
            if cur_deprecated:
                res = UpdateResult(
                    status="deprecated",
                    os_tag=self._os_tag,
                    current_version=str(self._project.version),
                    latest=latest,
                    download_url=dl_url,
                    message="Current version is deprecated.",
                )
                if self._show_dialog:
                    self._show_mandatory_dialog(res)
                self._finish(res)
                return

            if compare_versions(latest.version, str(self._project.version)) <= 0:
                res = UpdateResult(
                    status="no_update",
                    os_tag=self._os_tag,
                    current_version=str(self._project.version),
                    latest=latest,
                    download_url=dl_url,
                )
                self._finish(res)
                return

            if not self._ignore_skip:
                try:
                    skip = (self._get_skip() or "").strip()
                except Exception:
                    skip = ""
                if skip and skip == latest.version.strip():
                    res = UpdateResult(
                        status="no_update",
                        os_tag=self._os_tag,
                        current_version=str(self._project.version),
                        latest=latest,
                        download_url=dl_url,
                        message="Update is snoozed.",
                    )
                    self._finish(res)
                    return

            res = UpdateResult(
                status="update_available",
                os_tag=self._os_tag,
                current_version=str(self._project.version),
                latest=latest,
                download_url=dl_url,
            )
            if self._show_dialog:
                self._show_optional_dialog(res)
            self._finish(res)

        finally:
            self._in_flight = False
            try:
                reply.deleteLater()
            except Exception:
                pass

    def _emit(self, res: UpdateResult, cb: Optional[Callable[[UpdateResult], None]]) -> None:
        self.checked.emit(res)
        if cb is not None:
            try:
                cb(res)
            except Exception:
                pass

    def _finish(self, res: UpdateResult) -> None:
        cb = self._cb
        self._cb = None
        self._emit(res, cb)

    def _effective_parent(self) -> QWidget:
        w = QApplication.activeWindow()
        return w if w is not None else self._parent

    def _prepare_box(self, box: QMessageBox) -> None:
        box.setWindowModality(Qt.ApplicationModal)
        try:
            box.raise_()
            box.activateWindow()
        except Exception:
            pass

    def _show_optional_dialog(self, res: UpdateResult) -> None:
        latest = res.latest
        if latest is None:
            return

        app_name = self._project.name or self._project.repo
        box = QMessageBox(self._effective_parent())
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(f"{app_name} update available")
        box.setText(
            f"A new version is available: {latest.version}\n"
            f"Current: {self._project.version}   OS: {res.os_tag}"
        )

        snooze = QCheckBox("Do not remind me again for this version", box)
        box.setCheckBox(snooze)

        download_btn = box.addButton("Download", QMessageBox.AcceptRole)
        releases_btn = box.addButton("Releases", QMessageBox.NoRole)
        later_btn = box.addButton("Later", QMessageBox.RejectRole)
        box.setDefaultButton(download_btn)

        self._prepare_box(box)
        box.exec()

        if snooze.isChecked():
            try:
                self._set_skip(latest.version.strip())
            except Exception:
                pass

        clicked = box.clickedButton()
        if clicked is releases_btn:
            open_url_external(self._project.releases_url())
        elif clicked is download_btn:
            u = (res.download_url or "").strip() or self._project.releases_url()
            open_url_external(u)
        elif clicked is later_btn:
            return

    def _show_mandatory_dialog(self, res: UpdateResult) -> None:
        latest = res.latest
        app_name = self._project.name or self._project.repo
        latest_ver = (latest.version if latest else "").strip() or str(self._project.version)

        box = QMessageBox(self._effective_parent())
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Update required")
        box.setText(
            f"This version ({self._project.version}) has been marked as deprecated.\n"
            f"You must update to {latest_ver} to continue using {app_name}."
        )

        download_btn = box.addButton("Download", QMessageBox.AcceptRole)
        releases_btn = box.addButton("Releases", QMessageBox.NoRole)
        quit_btn = box.addButton("Quit", QMessageBox.RejectRole)
        box.setDefaultButton(download_btn)

        self._prepare_box(box)
        box.exec()

        clicked = box.clickedButton()
        if clicked is releases_btn:
            open_url_external(self._project.releases_url())
        elif clicked is download_btn:
            u = (res.download_url or "").strip() or self._project.releases_url()
            open_url_external(u)

        try:
            self._parent.close()
        except Exception:
            pass


def project_from_repo(
    repo_url: str,
    *,
    version: str,
    name: Optional[str] = None,
    branch: str = "main",
    descriptor_path: str = "version.upd",
    settings_org: Optional[str] = None,
    settings_app: Optional[str] = None,
) -> ReProject:
    u = (repo_url or "").strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+)", u, re.IGNORECASE)
    if not m:
        raise ValueError(f"Unrecognized GitHub repo URL: {repo_url!r}")
    owner, repo = m.group(1), m.group(2)
    return ReProject(
        owner=owner,
        repo=repo,
        version=str(version).strip(),
        name=name,
        branch=branch,
        descriptor_path=descriptor_path,
        settings_org=settings_org,
        settings_app=settings_app,
    )
