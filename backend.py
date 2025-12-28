# backend.py
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pulsectl

from models import AudioNode


@dataclass(frozen=True)
class PwPort:
    id: int
    node_id: int
    node_name: str
    port_name: str
    direction: str  # "in" | "out"
    channel: str    # "FL","FR","FC","LFE","RL","RR","SL","SR","MONO","AUX0"... or ""
    full_name: str  # "node.name:port.name"


@dataclass(frozen=True)
class PwLink:
    id: int
    out_port_id: int
    in_port_id: int


@dataclass
class PwGraph:
    nodes: Dict[int, AudioNode]
    ports: Dict[int, PwPort]
    links: List[PwLink]


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _props(obj: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for src in (obj.get("props") or {}, (obj.get("info") or {}).get("props") or {}):
        if not isinstance(src, dict):
            continue
        for k, v in src.items():
            try:
                ks = str(k)
            except Exception:
                continue
            try:
                vs = "" if v is None else str(v)
            except Exception:
                vs = ""
            out[ks] = vs
    return out


def _get_media_class(props: Dict[str, str]) -> str:
    return props.get("media.class", "")


def _get_node_name(props: Dict[str, str]) -> str:
    return props.get("node.name", "")


def _get_node_desc(props: Dict[str, str]) -> str:
    return props.get("node.description") or props.get("node.nick") or props.get("node.name") or ""


def _get_port_name(props: Dict[str, str]) -> str:
    return props.get("port.name", "")


def _get_port_direction(props: Dict[str, str], info: Dict[str, Any]) -> str:
    d = (props.get("port.direction") or "").strip().lower()
    if d in ("in", "out"):
        return d
    d2 = (info.get("direction") or "").strip().lower() if isinstance(info, dict) else ""
    if d2 in ("in", "out"):
        return d2
    return ""


def _normalize_channel(v: str) -> str:
    s = (v or "").strip().lower()
    if not s:
        return ""

    mapping = {
        "fl": "FL",
        "fr": "FR",
        "fc": "FC",
        "lfe": "LFE",
        "rl": "RL",
        "rr": "RR",
        "sl": "SL",
        "sr": "SR",
        "mono": "MONO",
        "front-left": "FL",
        "front-right": "FR",
        "front-center": "FC",
        "low-frequency": "LFE",
        "rear-left": "RL",
        "rear-right": "RR",
        "side-left": "SL",
        "side-right": "SR",
    }
    if s in mapping:
        return mapping[s]

    if s.startswith("aux"):
        tail = s[3:]
        if tail.isdigit():
            return f"AUX{int(tail)}"

    return s.upper()


def _channel_from_port(props: Dict[str, str]) -> str:
    for k in ("audio.channel", "audio.position"):
        if k in props and props[k]:
            return _normalize_channel(props[k])

    pn = (props.get("port.name") or "").strip()
    if not pn:
        return ""
    parts = pn.split("_")
    if len(parts) >= 2:
        candidate = parts[-1]
        n = _normalize_channel(candidate)
        if n:
            return n
    up = pn.upper()
    for tag in ("FL", "FR", "FC", "LFE", "RL", "RR", "SL", "SR", "MONO"):
        if up.endswith(tag):
            return tag
    return ""


def _is_stream_node(node: AudioNode) -> bool:
    mc = node.media_class
    return mc.startswith("Stream/") and "Output" in mc and mc.endswith("/Audio")


def _is_source_node(node: AudioNode) -> bool:
    return node.media_class == "Audio/Source"


def _is_sink_node(node: AudioNode) -> bool:
    return node.media_class == "Audio/Sink"


def _is_monitor_node(node: AudioNode) -> bool:
    return node.name.endswith(".monitor") or node.props.get("node.name", "").endswith(".monitor")


def _is_internal_node(node: AudioNode) -> bool:
    app = (node.props.get("application.name") or "").strip()
    return app in ("PipeWire", "WirePlumber", "PulseAudio")


def _pw_dump_graph() -> PwGraph:
    p = _run(["pw-dump"])
    if p.returncode != 0:
        raise RuntimeError(f"pw-dump failed: {p.stderr.strip() or p.stdout.strip()}")

    try:
        data = json.loads(p.stdout)
    except Exception as e:
        raise RuntimeError(f"pw-dump output is not valid JSON: {e}") from e

    if not isinstance(data, list):
        raise RuntimeError("pw-dump output JSON is not a list")

    nodes: Dict[int, AudioNode] = {}
    ports: Dict[int, PwPort] = {}
    links: List[PwLink] = []

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Node"):
            continue
        oid = int(obj.get("id"))
        pr = _props(obj)
        nodes[oid] = AudioNode(
            id=oid,
            name=_get_node_name(pr),
            description=_get_node_desc(pr),
            media_class=_get_media_class(pr),
            props=pr,
        )

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Port"):
            continue
        oid = int(obj.get("id"))
        pr = _props(obj)
        info = obj.get("info") or {}

        try:
            node_id = int(pr.get("node.id", "0"))
        except Exception:
            node_id = 0

        node = nodes.get(node_id)
        node_name = node.name if node else ""

        port_name = _get_port_name(pr)
        direction = _get_port_direction(pr, info)
        channel = _channel_from_port(pr)
        full_name = f"{node_name}:{port_name}" if node_name and port_name else ""

        ports[oid] = PwPort(
            id=oid,
            node_id=node_id,
            node_name=node_name,
            port_name=port_name,
            direction=direction,
            channel=channel,
            full_name=full_name,
        )

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Link"):
            continue
        oid = int(obj.get("id"))
        pr = _props(obj)

        out_pid = pr.get("link.output.port") or pr.get("link.output.port.id")
        in_pid = pr.get("link.input.port") or pr.get("link.input.port.id")
        if not out_pid or not in_pid:
            continue
        try:
            out_i = int(out_pid)
            in_i = int(in_pid)
        except Exception:
            continue

        links.append(PwLink(id=oid, out_port_id=out_i, in_port_id=in_i))

    return PwGraph(nodes=nodes, ports=ports, links=links)


def _pw_link_connect(out_full: str, in_full: str) -> None:
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


def _pw_link_disconnect(out_full: str, in_full: str) -> None:
    if not out_full or not in_full:
        return
    p = _run(["pw-link", "-d", out_full, in_full])
    if p.returncode == 0:
        return
    msg = (p.stderr or p.stdout).strip().lower()
    if "no such" in msg or "not found" in msg or "does not exist" in msg:
        return
    return


def _canonical_channel_order() -> List[str]:
    return [
        "MONO",
        "FL", "FR",
        "FC", "LFE",
        "SL", "SR",
        "RL", "RR",
        "AUX0", "AUX1", "AUX2", "AUX3", "AUX4", "AUX5", "AUX6", "AUX7", "AUX8", "AUX9",
        "AUX10", "AUX11", "AUX12", "AUX13", "AUX14", "AUX15",
    ]


def _select_ports_by_direction(graph: PwGraph, node_id: int, direction: str) -> List[PwPort]:
    out = [p for p in graph.ports.values() if p.node_id == node_id and p.direction == direction and p.full_name]

    order = _canonical_channel_order()
    by_chan: Dict[str, PwPort] = {}
    for p in out:
        if p.channel and p.channel not in by_chan:
            by_chan[p.channel] = p

    if by_chan:
        ordered: List[PwPort] = []
        used: set[int] = set()
        for ch in order:
            if ch in by_chan:
                ordered.append(by_chan[ch])
                used.add(by_chan[ch].id)
        for p in sorted(out, key=lambda x: x.id):
            if p.id not in used:
                ordered.append(p)
        return ordered

    return sorted(out, key=lambda x: x.id)


def _map_ports_1_to_1(src_ports: List[PwPort], dst_ports: List[PwPort]) -> List[Tuple[str, str]]:
    if not src_ports or not dst_ports:
        return []

    src_by_ch: Dict[str, PwPort] = {p.channel: p for p in src_ports if p.channel}
    dst_by_ch: Dict[str, PwPort] = {p.channel: p for p in dst_ports if p.channel}

    pairs: List[Tuple[str, str]] = []

    if src_by_ch and dst_by_ch:
        for ch in _canonical_channel_order():
            if ch in src_by_ch and ch in dst_by_ch:
                pairs.append((src_by_ch[ch].full_name, dst_by_ch[ch].full_name))
        if pairs:
            return pairs

    n = min(len(src_ports), len(dst_ports))
    for i in range(n):
        pairs.append((src_ports[i].full_name, dst_ports[i].full_name))
    return pairs


class PipeWireHubBackend:
    HUB_SINK_NAME = "asiphon"
    HUB_DESC = "aSyphon"

    def __init__(self, pulse_client_name: str = "asiphon-gui") -> None:
        self._pulse_client_name = pulse_client_name
        self._pulse: Optional[pulsectl.Pulse] = None
        self._hub_pulse_module_id: Optional[int] = None
        self._graph: PwGraph = PwGraph(nodes={}, ports={}, links=[])

        self.refresh()
        self.ensure_hub_sink()

    def refresh(self) -> None:
        self._graph = _pw_dump_graph()

    def server_label(self) -> str:
        return "PipeWire (native graph)"

    def _pulse_connect(self) -> pulsectl.Pulse:
        if self._pulse is None:
            self._pulse = pulsectl.Pulse(self._pulse_client_name)
        return self._pulse

    def close(self) -> None:
        if self._pulse is not None:
            try:
                self._pulse.close()
            except Exception:
                pass
        self._pulse = None

    def _find_node_by_name(self, name: str) -> Optional[AudioNode]:
        for n in self._graph.nodes.values():
            if n.name == name:
                return n
        return None

    def _node_channel_count(self, node_id: int, direction: str) -> int:
        ports = _select_ports_by_direction(self._graph, node_id, direction)
        chans = [p.channel for p in ports if p.channel]
        return len(set(chans)) if chans else len(ports)

    def hub_exists(self) -> bool:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        return bool(hub is not None and _is_sink_node(hub))

    def hub_node_optional(self) -> Optional[AudioNode]:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is None or not _is_sink_node(hub):
            return None
        return hub

    def ensure_hub_sink(self) -> None:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is not None and _is_sink_node(hub):
            return

        try:
            pulse = self._pulse_connect()
            existing = None
            for s in pulse.sink_list():
                if s.name == self.HUB_SINK_NAME:
                    existing = s
                    break

            if existing is None:
                args = " ".join(
                    [
                        f"sink_name={self.HUB_SINK_NAME}",
                        f"sink_properties=device.description={self.HUB_DESC}",
                    ]
                )
                mid = pulse.module_load("module-null-sink", args)
                self._hub_pulse_module_id = int(mid)
            else:
                self._hub_pulse_module_id = None
        except Exception as e:
            raise RuntimeError(f"Failed to ensure hub sink via pipewire-pulse: {e}") from e

        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is None or not _is_sink_node(hub):
            raise RuntimeError("Hub sink was created via Pulse, but is not visible in PipeWire graph.")

    def destroy_hub_sink(self) -> None:
        """
        Best-effort removal of the hub sink.
        - If we created it (stored module id), unload that module.
        - Else, try unloading the sink's owner_module (if available).
        """
        try:
            pulse = self._pulse_connect()
        except Exception:
            pulse = None

        unloaded = False

        if pulse is not None and self._hub_pulse_module_id is not None:
            try:
                pulse.module_unload(self._hub_pulse_module_id)
                unloaded = True
            except Exception:
                pass
            self._hub_pulse_module_id = None

        if pulse is not None and not unloaded:
            try:
                target = None
                for s in pulse.sink_list():
                    if s.name == self.HUB_SINK_NAME:
                        target = s
                        break
                if target is not None:
                    owner = getattr(target, "owner_module", None)
                    if owner is not None:
                        pulse.module_unload(int(owner))
            except Exception:
                pass

        self.refresh()

    def destroy_hub_sink_if_owned(self) -> None:
        if self._hub_pulse_module_id is None:
            return
        try:
            pulse = self._pulse_connect()
            pulse.module_unload(self._hub_pulse_module_id)
        except Exception:
            pass
        self._hub_pulse_module_id = None
        self.refresh()

    def hub_node(self) -> AudioNode:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is None:
            raise RuntimeError("Hub sink is missing.")
        return hub

    def hub_monitor_ports(self) -> List[PwPort]:
        hub = self.hub_node()
        out_ports = _select_ports_by_direction(self._graph, hub.id, "out")
        monitors = [p for p in out_ports if p.port_name.startswith("monitor_") or p.port_name.startswith("monitor.")]
        return monitors if monitors else out_ports

    def list_stream_nodes(self) -> List[AudioNode]:
        self.refresh()
        out: List[AudioNode] = []
        for n in self._graph.nodes.values():
            if not _is_stream_node(n):
                continue
            if _is_internal_node(n):
                continue
            out.append(n)
        return out

    def list_source_nodes(self) -> List[AudioNode]:
        self.refresh()
        out: List[AudioNode] = []
        for n in self._graph.nodes.values():
            if not _is_source_node(n):
                continue
            if _is_monitor_node(n):
                continue
            if n.name == f"{self.HUB_SINK_NAME}.monitor":
                continue
            out.append(n)
        return out

    def list_sink_nodes(self) -> List[AudioNode]:
        self.refresh()
        return [n for n in self._graph.nodes.values() if _is_sink_node(n)]

    def stream_label(self, n: AudioNode) -> str:
        app = n.props.get("application.name") or n.props.get("application.process.binary") or "App"
        media = n.props.get("media.name") or n.props.get("node.nick") or n.description or n.name
        base = f"{app} — {media}" if media and media != app else f"{app}"
        return f"{base}  [id {n.id}]"

    def node_label_with_ch(self, n: AudioNode, direction: str) -> str:
        ch = self._node_channel_count(n.id, direction)
        desc = n.description or n.name
        return f"{desc}  [{n.name}]  ({ch}ch)"

    def _connect_pairs(self, pairs: List[Tuple[str, str]]) -> None:
        for out_full, in_full in pairs:
            _pw_link_connect(out_full, in_full)

    def _disconnect_pairs(self, pairs: List[Tuple[str, str]]) -> None:
        for out_full, in_full in pairs:
            _pw_link_disconnect(out_full, in_full)

    def current_link_pairs(self, refresh: bool = False) -> Set[Tuple[str, str]]:
        """
        Returns the set of all current PipeWire links as (out_full, in_full) name pairs.
        This is used by the UI to reconcile "actual" vs remembered state.
        """
        if refresh:
            self.refresh()

        out: Set[Tuple[str, str]] = set()
        for lk in self._graph.links:
            op = self._graph.ports.get(lk.out_port_id)
            ip = self._graph.ports.get(lk.in_port_id)
            if not op or not ip:
                continue
            if not op.full_name or not ip.full_name:
                continue
            out.add((op.full_name, ip.full_name))
        return out

    def pairs_exist(self, pairs: List[Tuple[str, str]], refresh: bool = False) -> bool:
        """
        True iff every pair in `pairs` currently exists in the graph.
        """
        if not pairs:
            return False
        existing = self.current_link_pairs(refresh=refresh)
        return all(p in existing for p in pairs)

    def connect_stream_to_hub(self, stream_node_id: int) -> List[Tuple[str, str]]:
        """
        Non-exclusive routing:
        - Do not drop existing connections.
        - Add links: stream outputs -> hub inputs (1:1 mapping).
        """
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        stream_out_ports = _select_ports_by_direction(self._graph, stream_node_id, "out")
        hub_in_ports = _select_ports_by_direction(self._graph, hub.id, "in")
        if not stream_out_ports or not hub_in_ports:
            raise RuntimeError("Cannot link: missing stream output ports or hub input ports.")

        created = _map_ports_1_to_1(stream_out_ports, hub_in_ports)
        if not created:
            raise RuntimeError("No compatible port pairs for stream -> hub.")
        self._connect_pairs(created)
        return created

    def connect_source_to_hub(self, source_node_id: int) -> List[Tuple[str, str]]:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        src_out_ports = _select_ports_by_direction(self._graph, source_node_id, "out")
        hub_in_ports = _select_ports_by_direction(self._graph, hub.id, "in")
        if not src_out_ports or not hub_in_ports:
            raise RuntimeError("Cannot link: missing source output ports or hub input ports.")

        created = _map_ports_1_to_1(src_out_ports, hub_in_ports)
        if not created:
            raise RuntimeError("No compatible port pairs for source -> hub.")
        self._connect_pairs(created)
        return created

    def _sink_monitor_output_ports(self, sink_node_id: int) -> List[PwPort]:
        self.refresh()
        sink = self._graph.nodes.get(sink_node_id)
        if sink is None:
            return []

        out_ports = _select_ports_by_direction(self._graph, sink.id, "out")
        monitors = [p for p in out_ports if p.port_name.startswith("monitor_") or p.port_name.startswith("monitor.")]
        if monitors:
            return monitors

        mon_node = self._find_node_by_name(f"{sink.name}.monitor")
        if mon_node is None:
            return []
        return _select_ports_by_direction(self._graph, mon_node.id, "out")

    def connect_sink_tap_to_hub(self, sink_node_id: int) -> List[Tuple[str, str]]:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        if sink_node_id == hub.id:
            raise RuntimeError("Cannot tap aSyphon into itself.")

        tap_out_ports = self._sink_monitor_output_ports(sink_node_id)
        hub_in_ports = _select_ports_by_direction(self._graph, hub.id, "in")
        if not tap_out_ports or not hub_in_ports:
            raise RuntimeError("Cannot link: missing sink monitor ports or hub input ports.")

        created = _map_ports_1_to_1(tap_out_ports, hub_in_ports)
        if not created:
            raise RuntimeError("No compatible port pairs for sink monitor -> hub.")
        self._connect_pairs(created)
        return created

    def connect_hub_to_sink(self, sink_node_id: int) -> List[Tuple[str, str]]:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        if sink_node_id == hub.id:
            raise RuntimeError("Cannot output to aSyphon itself.")

        hub_out_ports = self.hub_monitor_ports()
        sink_in_ports = _select_ports_by_direction(self._graph, sink_node_id, "in")
        if not hub_out_ports or not sink_in_ports:
            raise RuntimeError("Cannot link: missing hub monitor ports or sink input ports.")

        created = _map_ports_1_to_1(hub_out_ports, sink_in_ports)
        if not created:
            raise RuntimeError("No compatible port pairs for hub -> sink.")
        self._connect_pairs(created)
        return created

    def disconnect_pairs(self, pairs: List[Tuple[str, str]]) -> None:
        self._disconnect_pairs(pairs)
