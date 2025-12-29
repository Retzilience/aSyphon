# pw_graph.py
from __future__ import annotations

from typing import Dict, List, Tuple

from models import AudioNode
from pw_channels import canonical_channel_order
from pw_types import PwGraph, PwPort


def is_stream_node(n: AudioNode) -> bool:
    mc = n.media_class
    return mc.startswith("Stream/") and "Output" in mc and mc.endswith("/Audio")


def is_source_node(n: AudioNode) -> bool:
    return n.media_class == "Audio/Source"


def is_sink_node(n: AudioNode) -> bool:
    return n.media_class == "Audio/Sink"


def is_monitor_node(n: AudioNode) -> bool:
    return n.name.endswith(".monitor") or n.props.get("node.name", "").endswith(".monitor")


def is_internal_node(n: AudioNode) -> bool:
    app = (n.props.get("application.name") or "").strip()
    return app in ("PipeWire", "WirePlumber", "PulseAudio")


def select_ports(graph: PwGraph, node_id: int, direction: str) -> List[PwPort]:
    ps = [p for p in graph.ports.values() if p.node_id == node_id and p.direction == direction and p.full_name]
    if not ps:
        return []

    by_ch: Dict[str, PwPort] = {}
    for p in ps:
        if p.channel and p.channel not in by_ch:
            by_ch[p.channel] = p

    if by_ch:
        out: List[PwPort] = []
        used: set[int] = set()
        for ch in canonical_channel_order():
            p = by_ch.get(ch)
            if p:
                out.append(p)
                used.add(p.id)
        for p in sorted(ps, key=lambda x: x.id):
            if p.id not in used:
                out.append(p)
        return out

    return sorted(ps, key=lambda x: x.id)


def map_ports_1_to_1(src: List[PwPort], dst: List[PwPort]) -> List[Tuple[str, str]]:
    if not src or not dst:
        return []

    s_by = {p.channel: p for p in src if p.channel}
    d_by = {p.channel: p for p in dst if p.channel}

    if s_by and d_by:
        pairs: List[Tuple[str, str]] = []
        for ch in canonical_channel_order():
            if ch in s_by and ch in d_by:
                pairs.append((s_by[ch].full_name, d_by[ch].full_name))
        if pairs:
            return pairs

    n = min(len(src), len(dst))
    return [(src[i].full_name, dst[i].full_name) for i in range(n)]
