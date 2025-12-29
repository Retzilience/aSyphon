# app_meta.py
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

APP_NAME = "aSyphon"
REPO_URL = "https://github.com/Retzilience/aSyphon"

# Keep this updated (or override via env/build tooling).
VERSION = "0.3"

_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
_TAG_LONG_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:-(\d+)-g([0-9a-f]{7,40}))?$", re.IGNORECASE)


def _with_dirty(ver: str, dirty: bool) -> str:
    if not dirty:
        return ver
    return f"{ver}.dirty" if "+" in ver else f"{ver}+dirty"


def _normalize_git_describe(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return str(VERSION).strip() or "0"

    dirty = False
    if s.endswith("-dirty"):
        dirty = True
        s = s[:-6]

    s = s.lstrip("vV")

    # Tag forms:
    #   v0.1            -> 0.1
    #   v0.1-3-g482024d -> 0.1+r3.g482024d
    m = _TAG_LONG_RE.match(s)
    if m:
        base, ahead, ghash = m.group(1), m.group(2), m.group(3)
        if ahead and ghash and int(ahead) > 0:
            v = f"{base}+r{ahead}.g{ghash}"
        else:
            v = base
        return _with_dirty(v, dirty)

    # No tag case:
    #   482024d -> 0.1+g482024d
    if _HASH_RE.match(s):
        v = f"{str(VERSION).strip() or '0'}+g{s}"
        return _with_dirty(v, dirty)

    # Unknown output: fall back to base VERSION only.
    v = str(VERSION).strip() or "0"
    return _with_dirty(v, dirty)


def detect_version() -> str:
    v = (os.environ.get("ASYPHON_VERSION") or "").strip()
    if v:
        return v

    try:
        import importlib.metadata

        for name in ("aSyphon", "asyphon", "asyphon-gui"):
            try:
                vv = importlib.metadata.version(name)
                if vv:
                    return str(vv)
            except Exception:
                pass
    except Exception:
        pass

    try:
        root = Path(__file__).resolve().parent
        if (root / ".git").exists() or (root.parent / ".git").exists():
            p = subprocess.run(
                ["git", "describe", "--tags", "--dirty", "--always"],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
            if p.returncode == 0:
                gd = (p.stdout or "").strip()
                if gd:
                    return _normalize_git_describe(gd)
    except Exception:
        pass

    return str(VERSION).strip() or "0"
