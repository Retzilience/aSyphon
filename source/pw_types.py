# pw_types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from models import AudioNode


@dataclass(frozen=True)
class PwPort:
    id: int
    node_id: int
    node_name: str
    port_name: str
    direction: str  # "in" | "out" | ""
    channel: str    # "FL","FR","AUX0"... or ""
    full_name: str  # "node.name:port.name" or ""


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
