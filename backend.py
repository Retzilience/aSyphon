# backend.py
from __future__ import annotations

from typing import List, Optional, Set, Tuple

import pulsectl

from models import AudioNode
from pw_cli import pw_link_connect, pw_link_disconnect
from pw_dump import dump_graph
from pw_graph import (
    is_internal_node,
    is_monitor_node,
    is_sink_node,
    is_source_node,
    is_stream_node,
    map_ports_1_to_1,
    select_ports,
)
from pw_types import PwGraph, PwPort


LinkPairs = List[Tuple[str, str]]


class PipeWireHubBackend:
    HUB_SINK_NAME = "asyphon"
    HUB_DESC = "aSyphon"

    def __init__(self, pulse_client_name: str = "asyphon-gui") -> None:
        self._pulse_client_name = pulse_client_name
        self._pulse: Optional[pulsectl.Pulse] = None
        self._hub_pulse_module_id: Optional[int] = None
        self._graph: PwGraph = PwGraph(nodes={}, ports={}, links=[])

        self.refresh()
        self.ensure_hub_sink()

    def refresh(self) -> None:
        self._graph = dump_graph()

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
        ps = select_ports(self._graph, node_id, direction)
        chans = [p.channel for p in ps if p.channel]
        return len(set(chans)) if chans else len(ps)

    def hub_exists(self) -> bool:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        return bool(hub is not None and is_sink_node(hub))

    def hub_node_optional(self) -> Optional[AudioNode]:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is None or not is_sink_node(hub):
            return None
        return hub

    def ensure_hub_sink(self) -> None:
        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is not None and is_sink_node(hub):
            return

        try:
            pulse = self._pulse_connect()
            existing = next((s for s in pulse.sink_list() if s.name == self.HUB_SINK_NAME), None)
            if existing is None:
                args = " ".join(
                    [
                        f"sink_name={self.HUB_SINK_NAME}",
                        f"sink_properties=device.description={self.HUB_DESC}",
                    ]
                )
                self._hub_pulse_module_id = int(pulse.module_load("module-null-sink", args))
            else:
                self._hub_pulse_module_id = None
        except Exception as e:
            raise RuntimeError(f"Failed to ensure hub sink via pipewire-pulse: {e}") from e

        self.refresh()
        hub = self._find_node_by_name(self.HUB_SINK_NAME)
        if hub is None or not is_sink_node(hub):
            raise RuntimeError("Hub sink was created via Pulse, but is not visible in PipeWire graph.")

    def destroy_hub_sink(self) -> None:
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
                target = next((s for s in pulse.sink_list() if s.name == self.HUB_SINK_NAME), None)
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
            self._pulse_connect().module_unload(self._hub_pulse_module_id)
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
        outs = select_ports(self._graph, hub.id, "out")
        mons = [p for p in outs if p.port_name.startswith("monitor_") or p.port_name.startswith("monitor.")]
        return mons if mons else outs

    def list_stream_nodes(self) -> List[AudioNode]:
        self.refresh()
        out: List[AudioNode] = []
        for n in self._graph.nodes.values():
            if is_stream_node(n) and not is_internal_node(n):
                out.append(n)
        return out

    def list_source_nodes(self) -> List[AudioNode]:
        self.refresh()
        out: List[AudioNode] = []
        for n in self._graph.nodes.values():
            if not is_source_node(n):
                continue
            if is_monitor_node(n):
                continue
            if n.name == f"{self.HUB_SINK_NAME}.monitor":
                continue
            out.append(n)
        return out

    def list_sink_nodes(self) -> List[AudioNode]:
        self.refresh()
        return [n for n in self._graph.nodes.values() if is_sink_node(n)]

    def stream_label(self, n: AudioNode) -> str:
        app = n.props.get("application.name") or n.props.get("application.process.binary") or "App"
        media = n.props.get("media.name") or n.props.get("node.nick") or n.description or n.name
        base = f"{app} — {media}" if media and media != app else f"{app}"
        return f"{base}  [id {n.id}]"

    def node_label_with_ch(self, n: AudioNode, direction: str) -> str:
        ch = self._node_channel_count(n.id, direction)
        desc = n.description or n.name
        return f"{desc}  [{n.name}]  ({ch}ch)"

    def _connect_pairs(self, pairs: LinkPairs) -> None:
        for o, i in pairs:
            pw_link_connect(o, i)

    def _disconnect_pairs(self, pairs: LinkPairs) -> None:
        for o, i in pairs:
            pw_link_disconnect(o, i)

    def current_link_pairs(self, refresh: bool = False) -> Set[Tuple[str, str]]:
        if refresh:
            self.refresh()
        out: Set[Tuple[str, str]] = set()
        for lk in self._graph.links:
            op = self._graph.ports.get(lk.out_port_id)
            ip = self._graph.ports.get(lk.in_port_id)
            if not op or not ip or not op.full_name or not ip.full_name:
                continue
            out.add((op.full_name, ip.full_name))
        return out

    def pairs_exist(self, pairs: LinkPairs, refresh: bool = False) -> bool:
        if not pairs:
            return False
        existing = self.current_link_pairs(refresh=refresh)
        return all(p in existing for p in pairs)

    def connect_stream_to_hub(self, stream_node_id: int) -> LinkPairs:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        src_out = select_ports(self._graph, stream_node_id, "out")
        hub_in = select_ports(self._graph, hub.id, "in")
        if not src_out or not hub_in:
            raise RuntimeError("Cannot link: missing stream output ports or hub input ports.")

        pairs = map_ports_1_to_1(src_out, hub_in)
        if not pairs:
            raise RuntimeError("No compatible port pairs for stream -> hub.")
        self._connect_pairs(pairs)
        return pairs

    def connect_source_to_hub(self, source_node_id: int) -> LinkPairs:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        src_out = select_ports(self._graph, source_node_id, "out")
        hub_in = select_ports(self._graph, hub.id, "in")
        if not src_out or not hub_in:
            raise RuntimeError("Cannot link: missing source output ports or hub input ports.")

        pairs = map_ports_1_to_1(src_out, hub_in)
        if not pairs:
            raise RuntimeError("No compatible port pairs for source -> hub.")
        self._connect_pairs(pairs)
        return pairs

    def _sink_monitor_output_ports(self, sink_node_id: int) -> List[PwPort]:
        self.refresh()
        sink = self._graph.nodes.get(sink_node_id)
        if sink is None:
            return []

        outs = select_ports(self._graph, sink.id, "out")
        mons = [p for p in outs if p.port_name.startswith("monitor_") or p.port_name.startswith("monitor.")]
        if mons:
            return mons

        mon_node = self._find_node_by_name(f"{sink.name}.monitor")
        if mon_node is None:
            return []
        return select_ports(self._graph, mon_node.id, "out")

    def connect_sink_tap_to_hub(self, sink_node_id: int) -> LinkPairs:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        if sink_node_id == hub.id:
            raise RuntimeError("Cannot tap aSyphon into itself.")

        tap_out = self._sink_monitor_output_ports(sink_node_id)
        hub_in = select_ports(self._graph, hub.id, "in")
        if not tap_out or not hub_in:
            raise RuntimeError("Cannot link: missing sink monitor ports or hub input ports.")

        pairs = map_ports_1_to_1(tap_out, hub_in)
        if not pairs:
            raise RuntimeError("No compatible port pairs for sink monitor -> hub.")
        self._connect_pairs(pairs)
        return pairs

    def connect_hub_to_sink(self, sink_node_id: int) -> LinkPairs:
        self.ensure_hub_sink()
        self.refresh()
        hub = self.hub_node()

        if sink_node_id == hub.id:
            raise RuntimeError("Cannot output to aSyphon itself.")

        hub_out = self.hub_monitor_ports()
        sink_in = select_ports(self._graph, sink_node_id, "in")
        if not hub_out or not sink_in:
            raise RuntimeError("Cannot link: missing hub monitor ports or sink input ports.")

        pairs = map_ports_1_to_1(hub_out, sink_in)
        if not pairs:
            raise RuntimeError("No compatible port pairs for hub -> sink.")
        self._connect_pairs(pairs)
        return pairs

    def disconnect_pairs(self, pairs: LinkPairs) -> None:
        self._disconnect_pairs(pairs)
