# pw_channels.py
from __future__ import annotations

from typing import Dict, List


def canonical_channel_order() -> List[str]:
    return [
        "MONO",
        "FL", "FR",
        "FC", "LFE",
        "SL", "SR",
        "RL", "RR",
        "AUX0", "AUX1", "AUX2", "AUX3", "AUX4", "AUX5", "AUX6", "AUX7", "AUX8", "AUX9",
        "AUX10", "AUX11", "AUX12", "AUX13", "AUX14", "AUX15",
    ]


def normalize_channel(v: str) -> str:
    s = (v or "").strip().lower()
    if not s:
        return ""

    m = {
        "fl": "FL", "front-left": "FL",
        "fr": "FR", "front-right": "FR",
        "fc": "FC", "front-center": "FC",
        "lfe": "LFE", "low-frequency": "LFE",
        "rl": "RL", "rear-left": "RL",
        "rr": "RR", "rear-right": "RR",
        "sl": "SL", "side-left": "SL",
        "sr": "SR", "side-right": "SR",
        "mono": "MONO",
    }
    if s in m:
        return m[s]

    if s.startswith("aux"):
        tail = s[3:]
        if tail.isdigit():
            return f"AUX{int(tail)}"

    return s.upper()


def channel_from_port_props(props: Dict[str, str]) -> str:
    v = (props.get("audio.channel") or props.get("audio.position") or "").strip()
    if v:
        return normalize_channel(v)

    pn = (props.get("port.name") or "").strip()
    if not pn:
        return ""

    parts = pn.split("_")
    if len(parts) >= 2:
        ch = normalize_channel(parts[-1])
        if ch:
            return ch

    up = pn.upper()
    for tag in ("FL", "FR", "FC", "LFE", "RL", "RR", "SL", "SR", "MONO"):
        if up.endswith(tag):
            return tag

    return ""
