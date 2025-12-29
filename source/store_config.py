# store_config.py
from __future__ import annotations

import configparser
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_TEXT = """\
[Patchbay]
selected_app =
custom_path =

[App]
last_exe_path =
"""


def _windows_appdata_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def _linux_xdg_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".config"


def user_config_dir(app_name: str) -> Path:
    sysname = (platform.system() or "").lower()
    if sysname.startswith("windows"):
        return _windows_appdata_dir() / app_name
    if sysname.startswith("linux"):
        return _linux_xdg_config_dir() / app_name
    return Path.home() / ".config" / app_name


def detect_executable_path() -> str:
    """
    I record the path used to launch the app.
    """
    try:
        p = Path(sys.argv[0]).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        else:
            p = p.resolve()
        return str(p)
    except Exception:
        return ""


def _read_last_exe_path_from_cfg(cfg_path: Path) -> str:
    try:
        if not cfg_path.exists():
            return ""
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path, encoding="utf-8")
        if not cfg.has_section("App"):
            return ""
        p = cfg.get("App", "last_exe_path", fallback="").strip()
        if not p:
            return ""
        pp = Path(p).expanduser()
        return str(pp) if pp.exists() else ""
    except Exception:
        return ""


def find_resink_executable_path() -> str:
    """
    I detect reSink by locating reSink's own config, then reading [App]/last_exe_path.

    I try:
      - Linux:  $XDG_CONFIG_HOME/reSink/resink.cfg  (or ~/.config/reSink/resink.cfg)
      - Windows: %APPDATA%\\reSink\\resink.cfg
    and case variants for directory/filename.
    """
    candidates: list[Path] = []
    for app_dir in ("reSink", "resink"):
        d = user_config_dir(app_dir)
        candidates.append(d / "resink.cfg")
        candidates.append(d / "reSink.cfg")

    for p in candidates:
        exe = _read_last_exe_path_from_cfg(p)
        if exe:
            return exe

    return ""


@dataclass(frozen=True)
class ConfigStore:
    app_name: str = "aSyphon"
    filename: str = "asyphon.cfg"

    @property
    def dir_path(self) -> Path:
        return user_config_dir(self.app_name)

    @property
    def file_path(self) -> Path:
        return self.dir_path / self.filename

    def ensure_exists(self) -> None:
        self.dir_path.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")

    def load(self) -> configparser.ConfigParser:
        self.ensure_exists()
        cfg = configparser.ConfigParser()
        cfg.read(self.file_path, encoding="utf-8")

        if not cfg.has_section("Patchbay"):
            cfg.add_section("Patchbay")
        cfg.set("Patchbay", "selected_app", cfg.get("Patchbay", "selected_app", fallback=""))
        cfg.set("Patchbay", "custom_path", cfg.get("Patchbay", "custom_path", fallback=""))

        if not cfg.has_section("App"):
            cfg.add_section("App")
        cfg.set("App", "last_exe_path", cfg.get("App", "last_exe_path", fallback=""))

        return cfg

    def save(self, cfg: configparser.ConfigParser) -> None:
        self.ensure_exists()
        with self.file_path.open("w", encoding="utf-8") as f:
            cfg.write(f)

    def record_last_exe_path(self) -> None:
        cfg = self.load()
        p = detect_executable_path().strip()
        if not p:
            return
        if not cfg.has_section("App"):
            cfg.add_section("App")
        if cfg.get("App", "last_exe_path", fallback="").strip() != p:
            cfg.set("App", "last_exe_path", p)
            self.save(cfg)
