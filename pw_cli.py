# pw_cli.py
from __future__ import annotations

import json
import subprocess
from typing import Any, List, Sequence


def _run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), capture_output=True, text=True)


def pw_dump_json() -> List[Any]:
    p = _run(["pw-dump"])
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        raise RuntimeError(f"pw-dump failed: {msg}")

    try:
        data = json.loads(p.stdout)
    except Exception as e:
        raise RuntimeError(f"pw-dump output is not valid JSON: {e}") from e

    if not isinstance(data, list):
        raise RuntimeError("pw-dump output JSON is not a list")

    return data


def pw_link_connect(out_full: str, in_full: str) -> None:
    if not out_full or not in_full:
        raise RuntimeError("Invalid port names for link creation.")
    p = _run(["pw-link", out_full, in_full])
    if p.returncode == 0:
        return

    msg = (p.stderr or p.stdout).strip()
    low = msg.lower()
    if "exist" in low or "already" in low:
        return

    raise RuntimeError(f"pw-link connect failed ({out_full} -> {in_full}): {msg}")


def pw_link_disconnect(out_full: str, in_full: str) -> None:
    if not out_full or not in_full:
        return

    p = _run(["pw-link", "-d", out_full, in_full])
    if p.returncode == 0:
        return

    msg = (p.stderr or p.stdout).strip().lower()
    if "no such" in msg or "not found" in msg or "does not exist" in msg:
        return

    return
